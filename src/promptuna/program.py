"""Defines the unit that we want to evaluate and optimize.

An :class:`Experiment` wires a :class:`Program` (prompt template + LM config)
that the harness runs over a dataset of :class:`Example` rows.
"""

from dataclasses import dataclass
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
