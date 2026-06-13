"""Execute a :class:`~lmeh.program.Program` against dataset rows.

:func:`run_trial` is a total function: it never raises, wrapping failures into
:class:`FailedTrial` so callers can treat crashed programs as data.
"""

from dataclasses import dataclass
from typing import Any

from lmdk import CompletionRequest, CompletionResponse, observe

from lmeh.program import Example, LMConfig, Program


@dataclass(frozen=True)
class SuccessfulTrial:
    """A trial whose program executed without raising.

    ``output`` is whatever the program returned (free-form). ``request`` and
    ``response`` are captured automatically by the harness via
    ``lmdk.observe`` around the program call: they hold the final rendered
    prompt + kwargs and the raw LM response (latency, tokens, finish reason,
    etc.). They are ``None`` only if the program performed no completion.

    ``replicate`` is the 0-indexed repeat number; with
    ``Experiment.repeats=1`` (default) it is always ``0``.
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
"""One execution of an Experiment against one Example.

A tagged union: pattern-match on ``SuccessfulTrial`` / ``FailedTrial`` (or
use ``isinstance``) to consume. The program is what's under evaluation, so
failed trials remain in ``RunResults.trials`` and count against the run.
"""


def run_trial(
    program: Program,
    prompt_template: str,
    config: LMConfig,
    example: Example,
    replicate: int = 0,
) -> Trial:
    """Execute ``program`` against one ``example``.

    ``example.inputs`` is unpacked as keyword arguments, so the program's
    parameter names must match the dict keys.

    Total function: any exception raised by the program is captured into a
    :class:`FailedTrial`. The program is what is under evaluation, so its
    failures are data, not bugs in the harness.
    """
    try:
        with observe() as obs:
            output = program(prompt_template=prompt_template, config=config, **example.inputs)

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
