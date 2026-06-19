"""Tests for promptuna.report."""

from helpers import make_run_results, make_trial

from promptuna.evaluate import FailedScoring, Score, SuccessfulScoring
from promptuna.report import render_run
from promptuna.run import FailedTrial


def test_render_run_includes_quality_reliability_and_error_analysis(
    experiment, examples, exact_match_metric
):
    results = make_run_results(experiment, examples, exact_match_metric, scores=[1.0, 0.25])
    markdown = render_run(results, telemetry=False)

    assert "### Quality" in markdown
    assert "### Reliability" in markdown
    assert "### Error Analysis" in markdown
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


def test_render_run_error_format_inputs_shows_dataset_inputs(experiment, examples, exact_match_metric):
    results = make_run_results(experiment, examples, exact_match_metric, scores=[1.0, 0.25])
    markdown = render_run(results, telemetry=False, error_format="inputs")

    assert repr(examples[1].inputs) in markdown
    assert "Rendered Prompt:" not in markdown
    assert "**Output**" not in markdown


def test_render_run_error_format_rendered_shows_rendered_prompt_and_output(
    experiment, examples, exact_match_metric
):
    weak_example = examples[1]
    trial = make_trial(
        weak_example,
        output=[0, 2],
        rendered_prompt="[0] first sentence\n[1] second sentence",
    )
    results = make_run_results(experiment, examples, exact_match_metric, scores=[1.0, 0.25])
    results.trials[1] = trial
    results.scorings[1] = SuccessfulScoring(
        trial=trial,
        metric=exact_match_metric,
        score=results.scorings[1].score,
    )

    markdown = render_run(results, telemetry=False, error_format="rendered")

    assert "[0] first sentence" in markdown
    assert "Rendered Prompt:" in markdown
    assert "<rendered_prompt>" in markdown
    assert repr(trial.output) in markdown
    assert "<output>" not in markdown
    assert repr(weak_example.inputs) not in markdown


def test_render_run_rendered_prompt_with_fenced_markup_does_not_bleed(experiment, examples, exact_match_metric):
    # A rendered prompt that carries its own fenced markup must not bleed into
    # the report — the tag delimiters isolate it.
    weak_example = examples[1]
    trial = make_trial(weak_example, output=[0, 2], rendered_prompt="```\nfenced body\n```")
    results = make_run_results(experiment, examples, exact_match_metric, scores=[1.0, 0.25])
    results.trials[1] = trial
    results.scorings[1] = SuccessfulScoring(
        trial=trial,
        metric=exact_match_metric,
        score=results.scorings[1].score,
    )

    markdown = render_run(results, telemetry=False, error_format="rendered")

    assert "<rendered_prompt>" in markdown
    assert "</rendered_prompt>" in markdown
    assert "#### Example" in markdown
    assert "**Quality:**" in markdown


def test_render_run_error_format_none_omits_error_analysis(experiment, examples, exact_match_metric):
    results = make_run_results(experiment, examples, exact_match_metric, scores=[1.0, 0.25])
    markdown = render_run(results, telemetry=False, error_format=None)

    assert "### Quality" in markdown
    assert "### Reliability" in markdown
    assert "### Error Analysis" not in markdown


def test_render_run_error_format_rendered_falls_back_to_inputs_without_successful_trial(
    experiment, example, exact_match_metric
):
    failed_trial = FailedTrial(example=example, error=RuntimeError("boom"))
    results = make_run_results(experiment, [example], exact_match_metric, scores=[0.25])
    results.trials = [failed_trial]
    results.scorings = [
        SuccessfulScoring(
            trial=failed_trial,
            metric=exact_match_metric,
            score=Score(raw=0.25, normalized=0.25, reason="trial failed"),
        )
    ]

    markdown = render_run(results, telemetry=False, error_format="rendered")

    assert repr(example.inputs) in markdown
    assert "Rendered Prompt:" not in markdown


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
