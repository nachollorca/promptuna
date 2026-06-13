"""Render :class:`~lmeh.evaluate.RunResults` and optimization trajectories as markdown."""

from lmeh.evaluate import Aggregate, Example, RunResults

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


def _render_legend(*, trajectory: bool = False) -> str:
    """Render score semantics and section conventions once per report or trajectory."""
    lines = [
        "Headline score is the mean across per-metric means (each metric weighted equally).",
        "",
        "Each quality table cell is `mean ± sd (n)`. `Score` aggregates per-example "
        "means (dispersion = dataset heterogeneity); `Replicate noise` is the average "
        "within-cell SD across replicates (dispersion = measurement instability).",
        "",
        "Trial failures count against the run (the program is under evaluation); "
        "scorer failures are excluded from quality aggregates.",
    ]
    if trajectory:
        lines.extend(
            [
                "",
                "Each `## Step N` heading shows role (baseline or candidate), headline score, "
                "delta vs baseline (candidates only), and `⭐ best` on the winning step so far.",
                "",
                "Each step opens with the verbatim template in a `template` block, then the "
                "quality, reliability, and weak-example results it produced.",
            ]
        )
    return "\n".join(lines)


def _render_quality(results: RunResults) -> str:
    """Render the quality section for a single run."""
    overall = results.overall
    metric_label = "metric" if overall.n == 1 else "metrics"
    lines = [
        "### Quality",
        "",
        f"- **Overall**: {overall.mean:.2f} ({overall.n} {metric_label})",
    ]

    per_metric = results.per_metric()
    if per_metric:
        noise = results.replicate_noise()
        lines.extend(
            [
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


def render_run(results: RunResults, *, telemetry: bool = True, legend: bool = True) -> str:
    """Render a single run as markdown sections.

    Args:
        results: The run to render.
        telemetry: When ``False``, omit the telemetry section (optimizer context).
        legend: When ``True``, prepend score semantics before the sections.

    Returns:
        Markdown with quality, reliability, and weak examples; telemetry is
        included when ``telemetry=True``.
    """
    sections: list[str] = []
    if legend:
        sections.append(_render_legend())
    sections.extend(
        [
            _render_quality(results),
            _render_reliability(results),
            _render_weak_examples(results),
        ]
    )
    if telemetry:
        sections.append(_render_telemetry(results))
    return "\n\n".join(sections)
