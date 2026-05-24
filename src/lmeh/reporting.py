"""Utilities to report experiment results."""

from lmeh.datatypes import Aggregate, RunResults


def markdown_report(results: RunResults) -> str:
    """Synthethises the results of an experiment to a Markdown string."""
    lines: list[str] = []
    lines.append(f"# Run report: `{results.experiment.name}`")
    lines.append("")
    lines.append("Summary of one experiment run across the dataset.")
    lines.append("")

    # Metadata
    lines.append("## Experiment")
    lines.append("")
    lines.append(f"- **Model**: `{results.experiment.config.model}`")
    lines.append(f"- **Target repeats**: {results.experiment.repeats}")
    lines.append(f"- **Run timestamp**: {results.run.timestamp.isoformat()}")
    if results.run.version is not None:
        lines.append(f"- **Version**: `{results.run.version}`")
    lines.append("")

    # Quality
    lines.append("## Quality")
    lines.append("")
    lines.append(
        "Headline score is the mean across per-metric means (each metric "
        "weighted equally). Dispersion is reported as `mean ± sd (n)`."
    )
    lines.append("")
    lines.append(f"- **Overall**: {_fmt(results.overall)}")
    lines.append("")

    per_metric = results.per_metric()
    if per_metric:
        noise = results.replicate_noise()
        lines.append("### Per-metric")
        lines.append("")
        lines.append(
            "`Score` aggregates per-example means (dispersion = dataset "
            "heterogeneity). `Replicate noise` is the average within-cell "
            "SD across replicates (dispersion = measurement instability)."
        )
        lines.append("")
        lines.append("| Metric | Score | Replicate noise |")
        lines.append("| --- | --- | --- |")
        for name in sorted(per_metric):
            lines.append(f"| `{name}` | {_fmt(per_metric[name])} | {_fmt(noise[name])} |")
        lines.append("")

    # Reliability
    lines.append("## Reliability")
    lines.append("")
    lines.append(
        "Trial failures count against the run (the target is under "
        "evaluation); scorer failures are excluded from quality aggregates."
    )
    lines.append("")
    lines.append(
        f"- **Trials**: {len(results.successful_trials)} successful / {len(results.trials)} total"
    )
    lines.append(f"- **Trial failure rate**: {results.failure_rate:.2%}")
    lines.append(
        f"- **Scorings**: {len(results.successful_scorings)} successful / "
        f"{len(results.scorings)} total"
    )
    lines.append(f"- **Scoring failure rate**: {results.scoring_failure_rate:.2%}")
    lines.append("")

    # Telemetry
    lines.append("## Telemetry")
    lines.append("")
    lines.append("Totals across successful trials only.")
    lines.append("")
    lines.append(f"- **Total latency**: {results.latency:.3f} s")
    lines.append(f"- **Total output tokens**: {results.output_tokens}")
    lines.append(f"- **Throughput**: {results.speed:.1f} tok/s")

    return "\n".join(lines)


def _fmt(agg: Aggregate) -> str:
    """Render an ``Aggregate`` as ``mean ± sd (n=...)``."""
    return f"{agg.mean:.4f} ± {agg.sd:.4f} (n={agg.n})"
