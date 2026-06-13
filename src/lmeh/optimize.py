"""Prompt-template optimization.

Closes the loop around :func:`lmeh.evaluate.run_experiment`: given a fixed
model and a set of metrics, search for a prompt template that scores better
on a flat ``list[Example]``.

The search is OPRO-style and free-form. Each step the proposer rewrites the
template from scratch given the full chronological trajectory, with the best
checkpoint clearly marked. The objective is fixed to ``RunResults.overall.mean``
and the budget is a fixed number of steps; the archive keeps the best
checkpoint, so the search may regress without losing the winner. Proposing
stops early once a checkpoint scores perfectly (``overall.mean >= 1.0``).
"""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from lmdk import complete, render_template
from pydantic import BaseModel, Field

from lmeh.evaluate import Metric, RunResults, run_experiment
from lmeh.program import Example, Experiment, LMConfig
from lmeh.report import _render_legend, render_run

default_proposer_template = (
    Path(__file__).parent / "prompt_templates" / "optimizer.jinja"
).read_text()


@dataclass(frozen=True)
class Step:
    """One checkpoint in the search: a candidate template and how it scored.

    Args:
        prompt_template: The candidate template that was evaluated.
        result: The full run produced by evaluating it on the examples.
    """

    prompt_template: str
    result: RunResults

    @property
    def score(self) -> float:
        """The headline objective for this step (``RunResults.overall.mean``)."""
        return self.result.overall.mean


@dataclass
class OptimizationResult:
    """The full archive produced by :func:`optimize`.

    Args:
        steps: Every checkpoint in chronological order. ``steps[0]`` is the
            baseline (the experiment's original template); each later entry is
            a proposed candidate.
    """

    steps: list[Step]

    @property
    def best(self) -> Step:
        """The highest-scoring step (ties resolve to the earliest)."""
        return max(self.steps, key=lambda step: step.score)


class Proposer(Protocol):
    """Generates the next candidate template from the trajectory so far."""

    def __call__(  # noqa: D102
        self, steps: list[Step], config: LMConfig
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
    :func:`~lmeh.report.render_history` and calls the model with structured output, so the
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

    Mirrors :func:`lmeh.evaluate.run_experiment`: same positional contract
    (``experiment``, ``examples``, ``metrics``), operating on a flat
    ``list[Example]`` with no train/test split — holdout evaluation is the
    caller's responsibility.

    The loop is: evaluate the experiment's current template as the baseline
    (step 0), then for each of ``steps`` iterations render the trajectory, ask
    ``proposer`` for a new template, evaluate it, and append it to the archive.
    The objective is fixed to ``RunResults.overall.mean``. Proposing stops once
    a checkpoint reaches a perfect overall score (``>= 1.0``), or the budgeted
    ``steps`` are exhausted. :attr:`OptimizationResult.best` selects the winner,
    which does not need to be the last step.

    Args:
        experiment: Carries the program, the baseline ``prompt_template``, and
            the (fixed) program model config. Not mutated — each candidate is
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


def _signed(delta: float) -> str:
    """Format a score delta with an explicit sign, e.g. ``+0.09`` / ``-0.01``."""
    return f"{delta:+.2f}"


def _render_step_heading(step: Step, index: int, baseline_score: float, is_best: bool) -> str:
    """Build the per-step ``##`` heading for :func:`render_history`."""
    role = "baseline" if index == 0 else "candidate"
    parts = [f"## Step {index} — {role} · score {step.score:.2f}"]
    if index > 0:
        parts.append(f"Δ {_signed(step.score - baseline_score)} vs baseline")
    if is_best:
        parts.append("⭐ best")
    return " · ".join(parts)


def render_history(steps: list[Step]) -> str:
    """Render the chronological trajectory into the proposer's context string.

    Pure function over the archive. Opens with a one-time legend, then each
    checkpoint is a ``## Step N`` heading with role/score/delta metadata, a
    ``<template>`` block with the exact template, and the shared
    :func:`~lmeh.report.render_run` body (without telemetry or per-step legends).

    Args:
        steps: Chronological archive; ``steps[0]`` is the baseline.

    Returns:
        A human-readable, model-facing string. Empty input yields ``""``.
    """
    if not steps:
        return ""

    baseline_score = steps[0].score
    best_index = max(range(len(steps)), key=lambda i: steps[i].score)

    preamble = "\n\n".join(
        [
            "## How to read these results",
            "",
            _render_legend(trajectory=True),
        ]
    )

    step_blocks: list[str] = []
    for i, step in enumerate(steps):
        sections = [
            _render_step_heading(step, i, baseline_score, is_best=i == best_index),
            f"<template>\n{step.prompt_template}\n</template>",
            render_run(step.result, telemetry=False, legend=False),
        ]
        step_blocks.append("\n\n".join(sections))

    return preamble + "\n\n" + "\n\n---\n\n".join(step_blocks)
