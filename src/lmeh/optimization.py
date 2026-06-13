"""Prompt-template optimization.

Closes the loop around :func:`lmeh.execution.run_experiment`: given a fixed
model and a set of metrics, search for a prompt template that scores better
on a flat ``list[Example]``.

The search is OPRO-style and free-form. Each step the proposer rewrites the
template from scratch given the full chronological trajectory, with the best
checkpoint clearly marked. The objective is fixed to ``RunResults.overall.mean``
and the budget is a fixed number of steps; the archive keeps the best
checkpoint, so the search may regress without losing the winner. Proposing
stops early once a checkpoint scores perfectly (``overall.mean >= 1.0``).
"""

from dataclasses import replace
from pathlib import Path
from typing import Protocol

from lmdk import complete, render_template
from pydantic import BaseModel, Field

from lmeh.datatypes import Example, Experiment, LMConfig, Metric, OptimizationResult, Step
from lmeh.execution import run_experiment
from lmeh.rendering import render_history

default_proposer_template = (
    Path(__file__).parent / "prompt_templates" / "optimizer.jinja"
).read_text()


class Proposer(Protocol):
    """Generates the next candidate template from the trajectory so far."""

    def __call__(  # noqa: D102
        self,
        steps: list[Step],
        config: LMConfig,
    ) -> str: ...


class Thinking(BaseModel):
    """Structured reasoning forced upon the optimizer before proposing a new template.

    Follows the approach explained in Attentive Reasoning Query paper: https://arxiv.org/pdf/2503.03669
    """

    reinstate_goal: str = Field(
        description="Repeat the goal at hand and the given constraints in a clear and concise way."
    )
    trajectory_summary: str = Field(
        description=(
            "Brief hronological analysis of the archive: baseline score, best checkpoint (⭐), "
            "which candidates helped or hurt, and the remaining gap to a perfect score."
        )
    )
    failure_analysis: str = Field(
        description=(
            "Analyze the weakest examples from the best (or latest) checkpoint. "
            "Cluster failure modes using judge reasons; infer missing rubric, "
            "ambiguity, or formatting issues — not generic advice."
        )
    )
    what_works: str = Field(
        description=(
            "Concrete patterns in higher-scoring templates or positive deltas "
            "(instructions, examples, output format, tone). Cite step numbers."
        )
    )
    what_hurts: str = Field(
        description=(
            "Patterns correlated with regressions, noise, or scorer confusion. "
            "Distinguish real harm from replicate noise when possible."
        )
    )
    improvement_hypothesis: str = Field(
        description=(
            "One falsifiable theory: 'If we change X, score should improve because Y' "
            "grounded in failure_analysis and trajectory evidence."
        )
    )
    edit_plan: str = Field(
        description=(
            "Specific edits to apply (add/remove/rephrase sections). "
            "Exploit or explore? Say whether you refine the best step or explore a new approach."
        )
    )


class Output(BaseModel):
    """Structured-output schema for :func:`default_proposer`."""

    thinking: Thinking = Field(
        description="Comprehensive analysis of the trajectory to propose a new template candidate."
    )
    prompt_template: str = Field(
        description="The new prompt template candidate grounded on the analysis of the trajectory."
    )


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
        output_schema=Output,
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
    The objective is fixed to ``RunResults.overall.mean``. Proposing stops once
    a checkpoint reaches a perfect overall score (``>= 1.0``), even if
    ``steps`` has not been exhausted; :attr:`OptimizationResult.best` selects
    the winner, which need not be the last step.

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
        if archive[-1].score >= 1.0:
            break
        candidate = proposer(steps=archive, config=proposer_config)
        candidate_experiment = replace(experiment, prompt_template=candidate)
        result = run_experiment(
            experiment=candidate_experiment, examples=examples, metrics=metrics, workers=workers
        )
        archive.append(Step(prompt_template=candidate, result=result))

    return OptimizationResult(steps=archive)
