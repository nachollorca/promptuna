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

from dataclasses import dataclass, replace
from typing import Protocol

from lmdk import complete, render_template
from pydantic import BaseModel

from lmeh.datatypes import Example, Experiment, LMConfig, Metric, RunResults
from lmeh.execution import run_experiment

# How many of the weakest examples to surface per checkpoint in the history.
_MAX_WEAK_EXAMPLES = 3


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
        self,
        steps: list[Step],
        config: LMConfig,
    ) -> str: ...


def render_history(steps: list[Step]) -> str:
    """Render the chronological trajectory into the proposer's context string.

    Pure function over the archive. For each checkpoint it emits the headline
    score, its delta versus the baseline, an explicit ``★`` marker on the
    best-so-far step, the per-metric breakdown, the full prompt template, and a
    sample of the weakest examples with the judge's reasoning — everything the
    proposer needs to reason about what helped, what hurt, and where the
    current best still fails.

    Args:
        steps: Chronological archive; ``steps[0]`` is the baseline.

    Returns:
        A human-readable, model-facing string. Empty input yields ``""``.
    """
    if not steps:
        return ""

    baseline_score = steps[0].score
    best_index = max(range(len(steps)), key=lambda i: steps[i].score)

    blocks: list[str] = []
    for i, step in enumerate(steps):
        blocks.append(_render_step(step, i, baseline_score, is_best=i == best_index))
    return "\n\n".join(blocks)


# I think we should actually also show the results per-metric
# Even though the best checkpoint is clearly defined by the overall mean
# It could help the model correct the prompt (just like the worst examples)
# Or are we doing this already?
def _render_step(step: Step, index: int, baseline_score: float, *, is_best: bool) -> str:
    """Render a single checkpoint block for :func:`render_history`."""
    label = "baseline" if index == 0 else f"candidate {index}"
    marker = " ★ best so far" if is_best else ""
    header = f"=== Step {index} ({label}){marker} | score {step.score:.4f}"
    if index > 0:
        header += f" ({_signed(step.score - baseline_score)} vs baseline)"
    header += " ==="

    lines = [header, "", "Per-metric:"]
    per_metric = step.result.per_metric()
    if per_metric:
        for name in sorted(per_metric):
            lines.append(f"  - {name}: {per_metric[name].mean:.4f}")
    else:
        lines.append("  (no scores)")

    lines += ["", "Prompt:", step.prompt_template]

    weak = _weakest_examples(step.result, _MAX_WEAK_EXAMPLES)
    if weak:
        lines += ["", "Weakest examples:"]
        for example, mean_score, breakdown in weak:
            lines.append(f"  - inputs={example.inputs!r} | mean {mean_score:.4f}")
            for metric_name, normalized, reason in breakdown:
                detail = f"      {metric_name}: {normalized:.4f}"
                if reason:
                    detail += f" — {reason}"
                lines.append(detail)

    return "\n".join(lines)


# The output hint of this function seems convoluted
# wouldn't it make sense to make a little dataclass for it?
def _weakest_examples(
    result: RunResults, limit: int
) -> list[tuple[Example, float, list[tuple[str, float, str]]]]:
    """Return the ``limit`` lowest-scoring examples with their per-metric detail.

    Each entry is ``(example, mean_normalized, [(metric, normalized, reason)])``,
    sorted worst-first. Examples are pooled across metrics and replicates by
    ``id(example)``, mirroring ``RunResults.per_example``.
    """
    grouped: dict[int, tuple[Example, list[tuple[str, float, str]]]] = {}
    for scoring in result.successful_scorings:
        example = scoring.trial.example
        _, breakdown = grouped.setdefault(id(example), (example, []))
        breakdown.append((scoring.metric.name, scoring.score.normalized, scoring.score.reason))

    ranked: list[tuple[Example, float, list[tuple[str, float, str]]]] = []
    for example, breakdown in grouped.values():
        mean_score = sum(n for _, n, _ in breakdown) / len(breakdown)
        ranked.append((example, mean_score, breakdown))

    ranked.sort(key=lambda entry: entry[1])
    return ranked[:limit]


def _signed(delta: float) -> str:
    """Format a score delta with an explicit sign, e.g. ``+0.0900`` / ``-0.0100``."""
    return f"{delta:+.4f}"


# ---------------------------------------------------------------------------
# Default proposer
# ---------------------------------------------------------------------------


default_proposer_template = """
We have a function that calls a language model to accomplish a task.
Its output quality is measured by one or more metrics over a fixed dataset.
Each metric is normalized to [0, 1] and combined into a single headline score (higher is better).

We are searching for a prompt template that maximizes that headline score.

Below is the full optimization trajectory in chronological order. Step 0 is the
original prompt and its baseline results; every later step is a candidate that
was proposed and evaluated. The best step so far is marked with ★. For each step
you can see its headline score, the per-metric breakdown, the exact prompt that
produced it, and a sample of its weakest examples with the judge's reasoning.

<history>
{{ HISTORY }}
</history>

Study the trajectory: infer what changes helped, what hurt, and where the
current best prompt still fails. Then write an improved prompt template. You may
refine the best checkpoint or explore a different approach.

Return the complete prompt template, ready to use as-is.
""".strip()


# I am not sure this is a good idea vs. simply have the model output the new template
# in a string
class _ProposedTemplate(BaseModel):
    """Structured-output schema for :func:`default_proposer`."""

    prompt_template: str


def default_proposer(
    steps: list[Step],
    config: LMConfig,
    *,  # Why this?
    template: str = default_proposer_template,
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
    prompt = render_template(template=template, HISTORY=render_history(steps))
    response = complete(
        model=config.model,
        prompt=prompt,
        output_schema=_ProposedTemplate,
        generation_kwargs=config.generation_kwargs,
    )
    parsed = response.parsed
    assert parsed is not None, "proposer model returned no structured output"
    return parsed.prompt_template


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def optimize(
    experiment: Experiment,
    examples: list[Example],
    metrics: list[Metric],
    *,  # Why this?
    proposer: Proposer = default_proposer,
    proposer_config: LMConfig,
    steps: int,
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
        candidate = proposer(archive, proposer_config)
        candidate_experiment = replace(experiment, prompt_template=candidate)
        result = run_experiment(
            experiment=candidate_experiment, examples=examples, metrics=metrics, workers=workers
        )
        archive.append(Step(prompt_template=candidate, result=result))

    return OptimizationResult(steps=archive)
