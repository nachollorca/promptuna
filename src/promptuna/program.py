"""Configuration for what is under test.

An :class:`Experiment` wires a :class:`Program` (prompt template + LM config)
that the harness runs over a dataset of :class:`Example` rows.
"""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class Example:
    """A single dataset row.

    ``reference`` is optional because some metrics do not require ground truth.
    For example: "is length less than X?" is measured on the output w/o reference.

    Args:
        inputs: Arbitrary inputs the program needs — domain objects, raw text,
            whatever the production caller would pass. Unpacked as keyword
            arguments into the :class:`Program`; the keys must match the
            program's parameter names.
        reference: Expected output, if available.
    """

    inputs: dict[str, Any]
    reference: Any | None = None


@dataclass
class LMConfig:  # I am not sure if this is the best name. Maybe we can run with LM alone or Model
    """How to invoke a language model.

    Uniform across program, judge, and optimizer call sites — none
    of them need anything more than this to dispatch a completion.

    Args:
        model: Identifier of the model to call.
        generation_kwargs: Extra arguments forwarded to the model call.

    Note:
        Structured-output schemas are intentionally *not* part of this
        config. The expected response shape is the caller's responsibility:
        a program defines the schema it needs internally, and LLM
        judges build their own schema from the metric's scale. ``LMConfig``
        only carries what is genuinely shared across call sites.
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

    Args:
        program: The function under evaluation.
        prompt_template: Jinja-style template the program renders before
            calling the model.
        config: How to invoke the program model.
        repeats: How many times to run the program per example. LLMs are
            stochastic, so >1 yields a distribution of outputs per example
            instead of a point estimate. Each repeat becomes its own
            :class:`~promptuna.run.Trial` tagged with ``replicate``.
    """

    program: Program
    prompt_template: str
    config: LMConfig
    repeats: int = 1
