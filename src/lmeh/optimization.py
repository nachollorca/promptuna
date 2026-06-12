"""Prompt-template optimization.

Closes the loop around :func:`lmeh.execution.run_experiment`: given a fixed
model and a set of metrics, search for a prompt template that scores better
on a flat ``list[Example]``.

The search is OPRO-style and free-form. Each step the proposer rewrites the
template from scratch given the full chronological trajectory, with the best
checkpoint clearly marked. The objective is fixed to ``RunResults.overall.mean``
and the budget is a fixed number of steps; the archive keeps the best
checkpoint, so the search may regress without losing the winner.
"""

from dataclasses import replace
from typing import Protocol

from lmdk import complete, render_template
from pydantic import BaseModel, Field

from lmeh.datatypes import Example, Experiment, LMConfig, Metric, OptimizationResult, Step
from lmeh.execution import run_experiment
from lmeh.rendering import render_history


class Proposer(Protocol):
    """Generates the next candidate template from the trajectory so far."""

    def __call__(  # noqa: D102
        self,
        steps: list[Step],
        config: LMConfig,
    ) -> str: ...


default_proposer_template = """
We have a function that calls a language model to accomplish a task.
Its output quality is measured by one or more metrics over a fixed dataset.
Each metric is normalized to [0, 1] and combined into a single headline score (higher is better).

We are searching for a prompt template that maximizes that headline score.

Below is the full optimization trajectory in chronological order. A legend at the top
explains how to read the scores and sections.

{{ HISTORY }}

Study the trajectory: infer what changes helped, what hurt, and where the
current best prompt still fails. Then write an improved prompt template. You may
refine the best checkpoint or explore a different approach.

Keep every Jinja placeholder (enclosed in double curly braces) from the templates
above exactly as-is (same names and syntax). Removing or renaming them breaks
rendering and makes the template unusable.

Return the complete prompt template, ready to use as-is.
""".strip()


class _ProposedTemplate(BaseModel):
    """Structured-output schema for :func:`default_proposer`."""

    thinking: str = Field(
        description="What seems to work? What is the error analysis? What could be improved?"
    )
    prompt_template: str


def default_proposer(
    steps: list[Step], config: LMConfig, template: str = default_proposer_template
) -> str:
    """Render the trajectory and ask the model for a better template.

    Renders ``template`` with the ``HISTORY`` produced by
    :func:`render_history` and calls the model with structured output, so the
    returned value is a clean template string rather than free-form prose.

    Args:
        steps: Chronological archive built by :func:`optimize`.
        config: Model id and generation kwargs for the proposer call.
        template: Proposer prompt template; expects a ``HISTORY`` variable.

    Returns:
        The proposed prompt template.
    """
    prompt = render_template(
        template=template,
        HISTORY=render_history(steps),
        strip_curly_brackets=False,
    )
    response = complete(
        model=config.model,
        prompt=prompt,
        output_schema=_ProposedTemplate,
        generation_kwargs=config.generation_kwargs,
    )
    parsed = response.parsed
    assert parsed is not None, "proposer model returned no structured output"
    return parsed.prompt_template


def optimize(
    experiment: Experiment,
    examples: list[Example],
    metrics: list[Metric],
    proposer_config: LMConfig,
    steps: int,
    proposer: Proposer = default_proposer,
    workers: int = 1,
) -> OptimizationResult:
    """Search for a prompt template that scores better on ``examples``.

    Mirrors :func:`lmeh.execution.run_experiment`: same positional contract
    (``experiment``, ``examples``, ``metrics``), operating on a flat
    ``list[Example]`` with no train/test split — holdout evaluation is the
    caller's responsibility.

    The loop is: evaluate the experiment's current template as the baseline
    (step 0), then for each of ``steps`` iterations render the trajectory, ask
    ``proposer`` for a new template, evaluate it, and append it to the archive.
    The objective is fixed to ``RunResults.overall.mean`` and there is no early
    stopping; :attr:`OptimizationResult.best` selects the winner, which need not
    be the last step.

    Args:
        experiment: Carries the target, the baseline ``prompt_template``, and
            the (fixed) target model config. Not mutated — each candidate is
            evaluated on a copy.
        examples: Dataset to optimize against.
        metrics: Metrics to score each run; combined via.
        proposer: Candidate generator. Defaults to :func:`default_proposer`.
        proposer_config: Model id and generation kwargs for the proposer.
        steps: Number of candidates to propose beyond the baseline (``>= 0``).
        workers: Thread-pool size forwarded to each ``run_experiment`` call.

    Returns:
        The chronological archive and its best step.
    """
    if steps < 0:
        raise ValueError(f"steps must be >= 0, got {steps}")

    baseline = run_experiment(
        experiment=experiment, examples=examples, metrics=metrics, workers=workers
    )
    archive = [Step(prompt_template=experiment.prompt_template, result=baseline)]

    for _ in range(steps):
        candidate = proposer(steps=archive, config=proposer_config)
        candidate_experiment = replace(experiment, prompt_template=candidate)
        result = run_experiment(
            experiment=candidate_experiment, examples=examples, metrics=metrics, workers=workers
        )
        archive.append(Step(prompt_template=candidate, result=result))

    return OptimizationResult(steps=archive)
