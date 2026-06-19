"""Defines the unit that we want to evaluate and optimize.

An :class:`Experiment` wires a :class:`Program` (prompt template + model)
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


class Program(Protocol):
    """The shape every function under evaluation must follow.

    A **program** is an ordinary Python function that solves a task with
    **exactly one** LM completion. Around that call sits a deterministic
    **scaffold**: code that prepares inputs and renders the template before
    the call, and code that parses, validates, or repairs the model output
    after. Chains of multiple LM calls are out of scope.

    The harness evaluates the whole function — scaffold, completion, and
    return value — not the raw model response. During optimization, only the
    prompt template is editable; the scaffold, output schema, and model stay
    fixed.

    The harness passes ``prompt_template`` and ``model`` on every call.
    Programs may optionally accept ``generation_kwargs`` to forward sampling
    parameters to ``lmdk.complete``; when omitted, the harness does not inject
    it.

    The program may return whatever Python value is most natural for the
    downstream scorers — a bool, a string, a pydantic model, a tuple. The
    harness captures the underlying ``CompletionRequest`` /
    ``CompletionResponse`` automatically via ``lmdk.observe``, so the program
    does not need to surface them explicitly.
    """

    def __call__(  # noqa: D102
        self,
        prompt_template: str,
        model: str,
        **inputs: Any,
    ) -> Any: ...


@dataclass
class Experiment:
    """A named program plus the prompt and model under test.

    Each ``repeats`` run becomes its own :class:`~promptuna.run.Trial` tagged
    with ``replicate``.
    """

    program: Program
    prompt_template: str
    model: str
    repeats: int = 1
