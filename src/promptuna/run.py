"""Execute a :class:`~promptuna.program.Program` against dataset rows.

:func:`run_trial` is a total function: it never raises, wrapping failures into
:class:`FailedTrial` so callers can treat crashed programs as data.

:func:`stream_run` runs trials over a dataset with a thread pool, yielding each
:class:`Trial` as it completes. For scoring use
:func:`promptuna.evaluate.stream_evaluate`.
"""

import inspect
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from lmdk import CompletionRequest, CompletionResponse, observe

from promptuna.program import Example, Experiment, Program


@dataclass(frozen=True)
class SuccessfulTrial:
    """A trial whose program executed without raising.

    ``request`` and ``response`` are captured via ``lmdk.observe`` around the
    program call.
    """

    example: Example
    output: Any
    request: CompletionRequest | None = None
    response: CompletionResponse | None = None
    replicate: int = 0

    @property
    def rendered_prompt(self) -> str:
        """The exact user prompt sent by the program.

        The harness assumes programs send exactly one user message.
        """
        assert self.request is not None, "Successful trial must carry a request"
        return self.request.prompt[0].content


@dataclass(frozen=True)
class FailedTrial:
    """A trial whose program raised. ``error`` is surfaced in aggregates."""

    example: Example
    error: Exception
    replicate: int = 0


Trial = SuccessfulTrial | FailedTrial
"""One program run against one example (tagged union)."""


def _invoke_program(
    program: Program,
    *,
    prompt_template: str,
    model: str,
    generation_kwargs: dict[str, Any] | None,
    inputs: dict[str, Any],
) -> Any:
    """Call ``program``, injecting only harness params it accepts."""
    kwargs: dict[str, Any] = {"prompt_template": prompt_template, "model": model, **inputs}
    sig = inspect.signature(program)
    accepts_var_kw = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    if "generation_kwargs" in sig.parameters or accepts_var_kw:
        kwargs["generation_kwargs"] = generation_kwargs
    return program(**kwargs)


def run_trial(
    program: Program,
    prompt_template: str,
    model: str,
    example: Example,
    replicate: int = 0,
    generation_kwargs: dict[str, Any] | None = None,
) -> Trial:
    """Execute ``program`` against one ``example``.

    ``example.inputs`` is unpacked as keyword arguments.
    """
    try:
        with observe() as obs:
            output = _invoke_program(
                program,
                prompt_template=prompt_template,
                model=model,
                generation_kwargs=generation_kwargs,
                inputs=example.inputs,
            )

        assert len(obs.records) == 1, "The program must call `complete` exactly one time"
        last = obs.records[-1] if obs.records else None
        return SuccessfulTrial(
            example=example,
            output=output,
            request=last.request if last else None,
            response=last.response if last else None,
            replicate=replicate,
        )
    except Exception as err:
        return FailedTrial(example=example, error=err, replicate=replicate)


def stream_run(
    experiment: Experiment,
    examples: list[Example],
    workers: int = 1,
) -> Iterator[Trial]:
    """Run ``experiment`` over ``examples``, yielding trials as they land.

    Order is not deterministic: trials arrive in completion order. Each
    ``(example, replicate)`` pair becomes one trial when ``experiment.repeats``
    is greater than one.
    """
    _validate_experiment(experiment)
    _validate_examples(examples)

    with ThreadPoolExecutor(max_workers=max(workers, 1)) as pool:
        yield from _stream_trials(pool, experiment, examples)


def _stream_trials(
    pool: ThreadPoolExecutor,
    experiment: Experiment,
    examples: list[Example],
) -> Iterator[Trial]:
    for fut in as_completed(_submit_trials(pool, experiment, examples)):
        yield fut.result()  # run_trial never raises


def _submit_trials(
    pool: ThreadPoolExecutor,
    experiment: Experiment,
    examples: list[Example],
) -> dict[Future[Trial], Example]:
    """Submit one trial future per ``(example, replicate)`` pair."""
    return {
        pool.submit(
            run_trial,
            experiment.program,
            experiment.prompt_template,
            experiment.model,
            ex,
            replicate=r,
        ): ex
        for ex in examples
        for r in range(experiment.repeats)
    }


def _validate_examples(examples: list[Example]) -> None:
    if not examples:
        raise ValueError("examples is empty")

    has_ref = [ex.reference is not None for ex in examples]
    if any(has_ref) and not all(has_ref):
        raise ValueError(
            "examples mix rows with and without `reference`; "
            "make this all-or-nothing so reference-dependent metrics are unambiguous"
        )


def _validate_experiment(experiment: Experiment) -> None:
    if not experiment.prompt_template:
        raise ValueError("experiment.prompt_template is empty")
    if not experiment.model:
        raise ValueError("experiment.model is empty")
    if experiment.repeats < 1:
        raise ValueError(f"experiment.repeats must be >= 1, got {experiment.repeats}")
