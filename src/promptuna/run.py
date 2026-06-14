"""Execute a :class:`~promptuna.program.Program` against dataset rows.

:func:`run_trial` is a total function: it never raises, wrapping failures into
:class:`FailedTrial` so callers can treat crashed programs as data.
"""

from dataclasses import dataclass
from typing import Any

from lmdk import CompletionRequest, CompletionResponse, observe

from promptuna.program import Example, LMConfig, Program


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


def run_trial(
    program: Program,
    prompt_template: str,
    config: LMConfig,
    example: Example,
    replicate: int = 0,
) -> Trial:
    """Execute ``program`` against one ``example``.

    ``example.inputs`` is unpacked as keyword arguments.
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
