"""Prompt-template optimization.

Closes the loop around :func:`promptuna.evaluate.run_experiment`: given a fixed
model and a set of metrics, search for a prompt template that scores better
on a flat ``list[Example]``.

The search is OPRO-style and free-form. Each step the proposer rewrites the
template from scratch given the full chronological trajectory, with the best
checkpoint clearly marked. The objective is fixed to ``RunResults.overall.mean``
and the budget is a fixed number of steps; the archive keeps the best
checkpoint, so the search may regress without losing the winner. Proposing
stops early once a checkpoint scores perfectly (``overall.mean >= 1.0``).
"""

import inspect
import json
import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from lmdk import complete, render_template
from pydantic import BaseModel, Field

from promptuna.evaluate import Metric, RunResults, run_experiment
from promptuna.program import Example, Experiment, LMConfig
from promptuna.report import render_run

logger = logging.getLogger(__name__)

default_proposer_template = (
    Path(__file__).parent / "prompt_templates" / "optimizer.jinja"
).read_text()


@dataclass(frozen=True)
class Step:
    """One search checkpoint: a candidate template and how it scored."""

    prompt_template: str
    result: RunResults

    @property
    def score(self) -> float:
        """The headline objective for this step (``RunResults.overall.mean``)."""
        return self.result.overall.mean


@dataclass
class OptimizationResult:
    """Archive from :func:`optimize`; ``steps[0]`` is the baseline."""

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
            "Cluster failure modes using the metric descriptions and judge reasons; "
            "spot ambiguity and infer missing rubric — not generic advice."
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
    advice: str | None = Field(
        default=None,
        description=(
            "Recommendations outside the editable template (schema, pre/post-processing), if any. "
            "Use only when the trajectory is not improving by just touching the template."
        ),
    )


_PROGRAM_SOURCE_ERROR = (
    "Cannot introspect program source. Define the program in a .py module and import it — "
    "functions defined in notebook cells (or wrapped with functools.partial) cannot be "
    "introspected."
)


def extract_output_schema(steps: list[Step]) -> str | None:
    """JSON Schema of the program's structured-output Pydantic model, from telemetry."""
    for step in steps:
        for trial in step.result.successful_trials:
            request = trial.request
            if request is not None and request.output_schema is not None:
                return json.dumps(request.output_schema.model_json_schema(), indent=2)
    return None


def extract_program_source(steps: list[Step]) -> str:
    """Python source of the program under optimization."""
    program = steps[0].result.experiment.program if steps else None
    assert program is not None
    try:
        return inspect.getsource(program)
    except (OSError, TypeError) as exc:
        raise type(exc)(_PROGRAM_SOURCE_ERROR) from exc


def render_metrics(steps: list[Step]) -> str:
    """Markdown listing each metric's name and description (the scoring rubric)."""
    by_name: dict[str, Metric] = {}
    for step in steps:
        for scoring in step.result.successful_scorings:
            by_name.setdefault(scoring.metric.name, scoring.metric)

    blocks: list[str] = []
    for name in sorted(by_name):
        metric = by_name[name]
        blocks.append(f"## `{metric.name}`\n\n{metric.description}")
    return "\n\n".join(blocks)


def default_proposer(
    steps: list[Step], config: LMConfig, template: str = default_proposer_template
) -> str:
    """Propose a new template from the trajectory via structured output.

    Args:
        steps: Chronological archive from :func:`optimize`.
        config: Proposer model and generation kwargs.
        template: Jinja template; expects ``HISTORY``, ``METRICS``, ``OUTPUT_SCHEMA``,
            and ``PROGRAM_SOURCE`` variables.

    Returns:
        Proposed prompt template.
    """
    prompt = render_template(
        template=template,
        HISTORY=render_history(steps),
        METRICS=render_metrics(steps),
        OUTPUT_SCHEMA=extract_output_schema(steps),
        PROGRAM_SOURCE=extract_program_source(steps),
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
    """Search for a higher-scoring prompt template on ``examples``.

    Same contract as :func:`promptuna.evaluate.run_experiment` (no train/test
    split — holdout evaluation is the caller's responsibility). See the module
    docstring for loop details.

    Args:
        experiment: Baseline program and template; not mutated per candidate.
        examples: Dataset to optimize against.
        metrics: Scoring metrics for each candidate run.
        proposer_config: Model for the proposer.
        steps: Candidates to propose beyond the baseline (``>= 0``).
        proposer: Candidate generator; defaults to :func:`default_proposer`.
        workers: Thread-pool size per ``run_experiment`` call.

    Returns:
        Chronological archive; see :attr:`OptimizationResult.best`.
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
    """Render the trajectory for the proposer's ``HISTORY`` context.

    Returns:
        Human-readable string; empty input yields ``""``.
    """
    if not steps:
        return ""

    baseline_score = steps[0].score
    best_index = max(range(len(steps)), key=lambda i: steps[i].score)
    # Error analysis only earns its keep on the checkpoints the proposer is asked
    # to act on: the best one it may refine and the latest one it just tried, both
    # with rendered prompts. Superseded candidates omit it entirely — their score
    # delta and template already carry the signal, and stale per-example detail
    # just bloats the trajectory. ``best`` and ``last`` collapse when they coincide.
    detailed = {best_index, len(steps) - 1}

    step_blocks: list[str] = []
    for i, step in enumerate(steps):
        error_format = "rendered" if i in detailed else None
        sections = [
            _render_step_heading(step, i, baseline_score, is_best=i == best_index),
            "### Template",
            "",
            f"<template>\n{step.prompt_template}\n</template>",
            render_run(step.result, telemetry=False, error_format=error_format),
        ]
        step_blocks.append("\n\n".join(sections))

    return "\n\n---\n\n".join(step_blocks)
