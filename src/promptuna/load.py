"""Load :class:`~promptuna.program.Example` rows from on-disk datasets."""

import json
from pathlib import Path
from typing import Any

from promptuna.program import Example


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
