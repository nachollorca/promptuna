"""Render :class:`~lmeh.datatypes.RunResults` and optimization trajectories as markdown."""

from lmeh.datatypes import Aggregate, Example, RunResults, Step

_MAX_WEAK_EXAMPLES = 3

MetricBreakdown = tuple[str, float, str]
WeakExampleEntry = tuple[Example, float, list[MetricBreakdown]]


def _fmt(agg: Aggregate) -> str:
    """Render an ``Aggregate`` as ``mean ± sd (n=...)``."""
    return f"{agg.mean:.2f} ± {agg.sd:.2f} (n={agg.n})"


def _weakest_examples(result: RunResults, limit: int) -> list[WeakExampleEntry]:
    """Return up to ``limit`` lowest-scoring imperfect examples with per-metric detail.

    Each entry is ``(example, mean_normalized, [(metric, normalized, reason)])``,
    sorted worst-first. Examples are pooled across metrics and replicates by
    ``id(example)``, mirroring ``RunResults.per_example``. Examples with a
    perfect mean (``>= 1.0``) are excluded — they have no room to improve, so
    surfacing them as "weak" would be misleading. ``limit`` is therefore a cap,
    not a target: fewer (or zero) entries come back when fewer examples are
    imperfect.
    """
    grouped: dict[int, tuple[Example, list[MetricBreakdown]]] = {}
    for scoring in result.successful_scorings:
        example = scoring.trial.example
        _, breakdown = grouped.setdefault(id(example), (example, []))
        breakdown.append((scoring.metric.name, scoring.score.normalized, scoring.score.reason))

    ranked: list[WeakExampleEntry] = []
    for example, breakdown in grouped.values():
        mean_score = sum(n for _, n, _ in breakdown) / len(breakdown)
        if mean_score >= 1.0:
            continue  # perfect score — no room to improve, not a "weak" example
        ranked.append((example, mean_score, breakdown))

    ranked.sort(key=lambda entry: entry[1])
    return ranked[:limit]


def _render_quality(results: RunResults) -> str:
    """Render the quality section for a single run."""
    overall = results.overall
    metric_label = "metric" if overall.n == 1 else "metrics"
    lines = [
        "### Quality",
        "",
        "Headline score is the mean across per-metric means (each metric weighted equally).",
        "",
        f"- **Overall**: {overall.mean:.2f} ({overall.n} {metric_label})",
    ]

    per_metric = results.per_metric()
    if per_metric:
        noise = results.replicate_noise()
        lines.extend(
            [
                "",
                "Each cell is `mean ± sd (n)`. `Score` aggregates per-example "
                "means (dispersion = dataset heterogeneity); `Replicate noise` "
                "is the average within-cell SD across replicates (dispersion = "
                "measurement instability).",
                "",
                "| Metric | Score | Replicate noise |",
                "| --- | --- | --- |",
            ]
        )
        for name in sorted(per_metric):
            lines.append(f"| `{name}` | {_fmt(per_metric[name])} | {_fmt(noise[name])} |")

    return "\n".join(lines)


def _render_reliability(results: RunResults) -> str:
    """Render the reliability section for a single run."""
    return "\n".join(
        [
            "### Reliability",
            "",
            "Trial failures count against the run (the target is under "
            "evaluation); scorer failures are excluded from quality aggregates.",
            "",
            f"- **Trials**: {len(results.successful_trials)} successful / "
            f"{len(results.trials)} total",
            f"- **Trial failure rate**: {results.failure_rate:.2%}",
            f"- **Scorings**: {len(results.successful_scorings)} successful / "
            f"{len(results.scorings)} total",
            f"- **Scoring failure rate**: {results.scoring_failure_rate:.2%}",
        ]
    )


def _render_weak_examples(results: RunResults) -> str:
    """Render weakest-example detail for a single run."""
    weak = _weakest_examples(results, _MAX_WEAK_EXAMPLES)
    lines = ["### Weak examples", ""]
    if weak:
        for i, (example, mean_score, breakdown) in enumerate(weak, start=1):
            lines.append(f"{i}. **mean {mean_score:.2f}** — `{example.inputs!r}`")
            for metric_name, normalized, reason in breakdown:
                detail = f"   - `{metric_name}`: {normalized:.2f}"
                if reason:
                    detail += f" — {reason}"
                lines.append(detail)
    elif results.successful_scorings:
        lines.append("All examples scored perfectly.")
    else:
        lines.append("(no scores)")
    return "\n".join(lines)


def _render_telemetry(results: RunResults) -> str:
    """Render the telemetry section for a single run."""
    return "\n".join(
        [
            "### Telemetry",
            "",
            "Totals across successful trials only.",
            "",
            f"- **Total latency**: {results.latency:.3f} s",
            f"- **Total output tokens**: {results.output_tokens}",
            f"- **Throughput**: {results.speed:.1f} tok/s",
        ]
    )


def render_run(results: RunResults, *, telemetry: bool = True) -> str:
    """Render a single run as markdown sections.

    Args:
        results: The run to render.
        telemetry: When ``False``, omit the telemetry section (optimizer context).

    Returns:
        Markdown with quality, reliability, and weak examples; telemetry is
        included when ``telemetry=True``.
    """
    sections = [
        _render_quality(results),
        _render_reliability(results),
        _render_weak_examples(results),
    ]
    if telemetry:
        sections.append(_render_telemetry(results))
    return "\n\n".join(sections)


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

    Pure function over the archive. Each checkpoint is a ``## Step N`` heading
    with role/score/delta metadata, the shared :func:`render_run` body
    (without telemetry), and a ``<template>`` block with the exact template.

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
        sections = [
            _render_step_heading(step, i, baseline_score, is_best=i == best_index),
            render_run(step.result, telemetry=False),
            f"<template>\n{step.prompt_template}\n</template>",
        ]
        blocks.append("\n\n".join(sections))
    return "\n\n".join(blocks)
