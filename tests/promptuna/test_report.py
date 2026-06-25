"""Tests for promptuna.report."""

from helpers import make_run_results, make_trial, score_of

from promptuna.evaluate import FailedScoring, Score, SuccessfulScoring
from promptuna.optimize import Step, Thinking
from promptuna.report import render_history, render_run
from promptuna.run import FailedTrial


def _sample_thinking(**overrides: str) -> Thinking:
    defaults = {
        "reinstate_goal": "Maximize headline score.",
        "trajectory_summary": "Baseline weak; step 1 improved.",
        "failure_analysis": "Model skips reasoning.",
        "what_works": "Explicit step-by-step instructions.",
        "what_hurts": "Overlong prompts add noise.",
        "improvement_hypothesis": "Shorter rubric should reduce confusion.",
        "edit_plan": "Refine best checkpoint; tighten scoring criteria.",
    }
    defaults.update(overrides)
    return Thinking(**defaults)


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


def test_render_run_reports_all_perfect_when_no_weak_examples(
    experiment, example, exact_match_metric
):
    results = make_run_results(experiment, [example], exact_match_metric, scores=[1.0])
    markdown = render_run(results, telemetry=False)

    assert "All examples scored perfectly." in markdown


def test_render_run_error_format_inputs_shows_dataset_inputs(
    experiment, examples, exact_match_metric
):
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
        score=score_of(results.scorings[1]),
    )

    markdown = render_run(results, telemetry=False, error_format="rendered")

    assert "[0] first sentence" in markdown
    assert "Rendered Prompt:" in markdown
    assert "````rendered_prompt" in markdown
    assert repr(trial.output) in markdown
    assert "<output>" not in markdown
    assert repr(weak_example.inputs) not in markdown


def test_render_run_rendered_prompt_with_fenced_markup_does_not_bleed(
    experiment, examples, exact_match_metric
):
    # A rendered prompt that carries its own fenced markup must not bleed into
    # the report — the four-backtick fence isolates it from the outer markdown.
    weak_example = examples[1]
    trial = make_trial(weak_example, output=[0, 2], rendered_prompt="```\nfenced body\n```")
    results = make_run_results(experiment, examples, exact_match_metric, scores=[1.0, 0.25])
    results.trials[1] = trial
    results.scorings[1] = SuccessfulScoring(
        trial=trial,
        metric=exact_match_metric,
        score=score_of(results.scorings[1]),
    )

    markdown = render_run(results, telemetry=False, error_format="rendered")

    assert "````rendered_prompt" in markdown
    assert markdown.count("````") >= 2
    assert "#### Example" in markdown
    assert "**Quality:**" in markdown


def test_render_run_error_format_none_omits_error_analysis(
    experiment, examples, exact_match_metric
):
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


def test_render_history_is_empty_without_steps():
    assert render_history([]) == ""


def test_render_history_marks_best_step_and_includes_templates(
    experiment, examples, exact_match_metric
):
    baseline = Step(
        prompt_template="baseline template",
        result=make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.4]),
    )
    candidate = Step(
        prompt_template="better template",
        result=make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.9]),
    )

    history = render_history([baseline, candidate])

    assert "⭐ best" in history
    assert "````template" in history
    assert "### Template" in history
    assert "better template" in history
    assert "Δ +0.50 vs baseline" in history


def test_render_history_uses_rendered_error_format(experiment, examples, exact_match_metric):
    weak_example = examples[0]
    trial = make_trial(
        weak_example,
        output="wrong",
        rendered_prompt="Classify: indexed prompt text",
    )
    result = make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.4])
    result.trials[0] = trial
    result.scorings[0] = SuccessfulScoring(
        trial=trial,
        metric=exact_match_metric,
        score=score_of(result.scorings[0]),
    )
    step = Step(prompt_template="baseline template", result=result)

    history = render_history([step])

    assert "Classify: indexed prompt text" in history
    assert "<output>\n'wrong'\n</output>" not in history
    assert "'wrong'" in history
    assert "Rendered Prompt:" in history


def test_render_history_renders_rendered_prompt_only_for_best_and_last(
    experiment, examples, exact_match_metric
):
    def step_with_rendered(template, score, rendered_prompt):
        trial = make_trial(examples[0], output="wrong", rendered_prompt=rendered_prompt)
        result = make_run_results(experiment, examples[:1], exact_match_metric, scores=[score])
        result.trials[0] = trial
        result.scorings[0] = SuccessfulScoring(
            trial=trial, metric=exact_match_metric, score=score_of(result.scorings[0])
        )
        return Step(prompt_template=template, result=result)

    baseline = step_with_rendered("baseline", 0.4, "BASELINE_RENDERED")
    best = step_with_rendered("best", 0.9, "BEST_RENDERED")
    last = step_with_rendered("last", 0.5, "LAST_RENDERED")

    history = render_history([baseline, best, last])

    assert "BEST_RENDERED" in history
    assert "LAST_RENDERED" in history
    assert "BASELINE_RENDERED" not in history
    assert repr(examples[0].inputs) not in history
    assert history.count("### Error Analysis") == 2


def test_render_history_shows_intent_for_proposed_steps(experiment, examples, exact_match_metric):
    baseline = Step(
        prompt_template="baseline template",
        result=make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.4]),
    )
    candidate = Step(
        prompt_template="better template",
        result=make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.9]),
        thinking=_sample_thinking(),
    )

    history = render_history([baseline, candidate])

    assert history.count("### Intent") == 1
    assert "**Hypothesis:** Shorter rubric should reduce confusion." in history
    assert "**Edit plan:** Refine best checkpoint; tighten scoring criteria." in history
    assert "Reinstate goal" not in history
