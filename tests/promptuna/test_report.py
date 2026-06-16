"""Tests for promptuna.report."""

from promptuna.evaluate import FailedScoring, Score, SuccessfulScoring
from promptuna.program import Example
from promptuna.report import render_run
from promptuna.run import FailedTrial
from helpers import make_run_results, make_trial


def test_render_run_includes_quality_reliability_and_weak_examples(
    experiment, examples, exact_match_metric
):
    results = make_run_results(experiment, examples, exact_match_metric, scores=[1.0, 0.25])
    markdown = render_run(results, telemetry=False)

    assert "### Quality" in markdown
    assert "### Reliability" in markdown
    assert "### Weak examples" in markdown
    assert "exact_match" in markdown
    assert "0.25" in markdown


def test_render_run_can_hide_telemetry(experiment, example, exact_match_metric):
    results = make_run_results(experiment, [example], exact_match_metric, scores=[1.0])
    markdown = render_run(results, telemetry=False)

    assert "### Telemetry" not in markdown


def test_render_run_reports_all_perfect_when_no_weak_examples(experiment, example, exact_match_metric):
    results = make_run_results(experiment, [example], exact_match_metric, scores=[1.0])
    markdown = render_run(results, telemetry=False)

    assert "All examples scored perfectly." in markdown


def test_render_run_reports_trial_and_scoring_failures(experiment, example, exact_match_metric):
    failed_trial = FailedTrial(example=example, error=RuntimeError("boom"))
    failed_scoring = FailedScoring(
        trial=make_trial(example),
        metric=exact_match_metric,
        error=RuntimeError("judge failed"),
    )
    results = make_run_results(experiment, [example], exact_match_metric, scores=[0.5])
    results.trials = [failed_trial]
    results.scorings = [
        SuccessfulScoring(
            trial=make_trial(example),
            metric=exact_match_metric,
            score=Score(raw=0.5, normalized=0.5),
        ),
        failed_scoring,
    ]

    markdown = render_run(results, telemetry=True)

    assert "Trial failure rate" in markdown
    assert "Scoring failure rate" in markdown
    assert "### Telemetry" in markdown
