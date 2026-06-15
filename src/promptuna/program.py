"""Defines the unit that we want to evaluate and optimize.

An :class:`Experiment` wires a :class:`Program` (prompt template + LM config)
that the harness runs over a dataset of :class:`Example` rows.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass
class Example:
    """A single dataset row.

    ``inputs`` keys must match the :class:`Program` parameter names (unpacked
    as keyword arguments). ``reference`` is optional — not all metrics need
    ground truth.
    """

    inputs: dict[str, Any]
    reference: Any | None = None


def _parse_jsonl_line(path: Path, line_no: int, line: str) -> dict[str, Any]:
    try:
        row = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}:{line_no}: invalid JSON") from exc

    if not isinstance(row, dict):
        raise ValueError(f"{path}:{line_no}: row must be a JSON object")
    return row


def _expect_key_set(
    keys: frozenset[str],
    expected: frozenset[str] | None,
    *,
    path: Path,
    line_no: int,
    label: str,
) -> frozenset[str]:
    if expected is None:
        return keys
    if keys != expected:
        raise ValueError(
            f"{path}:{line_no}: {label} keys {sorted(keys)} do not match "
            f"expected keys {sorted(expected)}"
        )
    return expected


def _parse_jsonl_inputs(row_dict: dict[str, Any], path: Path, line_no: int) -> dict[str, Any]:
    extra = frozenset(row_dict) - {"inputs", "reference"}
    if extra:
        raise ValueError(f"{path}:{line_no}: unexpected keys: {sorted(extra)}")

    if "inputs" not in row_dict:
        raise ValueError(f"{path}:{line_no}: row must have an `inputs` key")

    inputs = row_dict["inputs"]
    if not isinstance(inputs, dict):
        raise ValueError(f"{path}:{line_no}: `inputs` must be a JSON object")
    return inputs


def load_jsonl(path: str | Path) -> list[Example]:
    """Load dataset rows from a JSONL file.

    Each non-empty line must be a JSON object with an ``inputs`` dict and an
    optional ``reference``. Every row must share the same top-level keys and
    the same ``inputs`` keys.
    """
    path = Path(path)
    examples: list[Example] = []
    expected_keys: frozenset[str] | None = None
    expected_input_keys: frozenset[str] | None = None

    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            row_dict = _parse_jsonl_line(path, line_no, stripped)
            keys = frozenset(row_dict)
            expected_keys = _expect_key_set(
                keys, expected_keys, path=path, line_no=line_no, label="row"
            )

            inputs_dict = _parse_jsonl_inputs(row_dict, path, line_no)
            input_keys = frozenset(inputs_dict)
            expected_input_keys = _expect_key_set(
                input_keys,
                expected_input_keys,
                path=path,
                line_no=line_no,
                label="`inputs`",
            )

            examples.append(Example(inputs=inputs_dict, reference=row_dict.get("reference")))

    return examples


@dataclass
class LMConfig:
    """How to invoke a language model.

    Shared across program, judge, and optimizer call sites.

    Note:
        Structured-output schemas are intentionally *not* part of this
        config. Callers define the response shape they need.
    """

    model: str
    generation_kwargs: dict[str, Any] | None = None


class Program(Protocol):
    """The shape every function under evaluation must follow.

    A program is a function that achieves a goal using **exactly one** LM
    completion. It may run arbitrary deterministic code before the call to
    prepare the prompt (e.g. format inputs, render the template) and after
    the call to refine the model's response (e.g. parse, validate, repair).
    Chains of multiple LM calls are out of scope.

    The program may return whatever Python value is most natural for the
    downstream scorers — a bool, a string, a pydantic model, a tuple. The
    harness captures the underlying ``CompletionRequest`` /
    ``CompletionResponse`` automatically via ``lmdk.observe``, so the program
    does not need to surface them explicitly.
    """

    def __call__(  # noqa: D102
        self,
        prompt_template: str,
        config: LMConfig,
        **inputs: Any,
    ) -> Any: ...


@dataclass
class Experiment:
    """A named program plus the prompt and LM config under test.

    Each ``repeats`` run becomes its own :class:`~promptuna.run.Trial` tagged
    with ``replicate``.
    """

    program: Program
    prompt_template: str
    config: LMConfig
    repeats: int = 1
