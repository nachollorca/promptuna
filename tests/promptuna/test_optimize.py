"""Tests for promptuna.optimize."""

import logging
from typing import Literal
from unittest.mock import patch

import pytest
from helpers import make_run_results, make_trial
from lmdk import CompletionResponse
from pydantic import BaseModel

from promptuna.evaluate import RunInfo, RunResults, SuccessfulScoring
from promptuna.optimize import (
    OptimizationResult,
    Output,
    Step,
    Thinking,
    default_proposer,
    extract_output_schema,
    extract_program_source,
    optimize,
    render_history,
    render_metrics,
)


class _BlockSchema(BaseModel):
    confidence: Literal["weak", "decent", "strong"]


def test_step_score_reads_run_results_overall(experiment, examples, exact_match_metric):
    result = make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.8])
    step = Step(prompt_template="baseline", result=result)

    assert step.score == 0.8


def test_optimization_result_best_prefers_earliest_tie(experiment, examples, exact_match_metric):
    first = Step(
        prompt_template="a",
        result=make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.9]),
    )
    second = Step(
        prompt_template="b",
        result=make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.9]),
    )

    archive = OptimizationResult(steps=[first, second])

    assert archive.best is first


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
    assert "<template>" in history
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
        score=result.scorings[0].score,
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
            trial=trial, metric=exact_match_metric, score=result.scorings[0].score
        )
        return Step(prompt_template=template, result=result)

    baseline = step_with_rendered("baseline", 0.4, "BASELINE_RENDERED")
    best = step_with_rendered("best", 0.9, "BEST_RENDERED")
    last = step_with_rendered("last", 0.5, "LAST_RENDERED")

    history = render_history([baseline, best, last])

    # best (step 1) and last (step 2) show the rendered prompt; the superseded
    # baseline omits error analysis entirely (no rendered prompt, no raw inputs).
    assert "BEST_RENDERED" in history
    assert "LAST_RENDERED" in history
    assert "BASELINE_RENDERED" not in history
    assert repr(examples[0].inputs) not in history
    # exactly two error-analysis sections (best + last), none for the baseline.
    assert history.count("### Error Analysis") == 2


def test_render_metrics_is_empty_without_steps():
    assert render_metrics([]) == ""


def test_render_metrics_lists_name_and_description(experiment, examples, exact_match_metric):
    results = make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.5])
    step = Step(prompt_template="t", result=results)

    markdown = render_metrics([step])

    assert "## `exact_match`" in markdown
    assert "Output must match the reference answer." in markdown


def test_extract_output_schema_is_none_without_schema(experiment, examples, exact_match_metric):
    results = make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.5])
    step = Step(prompt_template="t", result=results)

    assert extract_output_schema([step]) is None


def test_extract_output_schema_surfaces_model_source(experiment, example):
    trial = make_trial(example, output_schema=_BlockSchema)
    results = RunResults(experiment=experiment, run=RunInfo(), trials=[trial], scorings=[])
    step = Step(prompt_template="t", result=results)

    schema_source = extract_output_schema([step])

    assert schema_source is not None
    assert "class _BlockSchema" in schema_source
    assert "confidence" in schema_source
    assert "weak" in schema_source


def test_extract_program_source_includes_program_body(experiment, examples, exact_match_metric):
    results = make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.5])
    step = Step(prompt_template="t", result=results)

    source = extract_program_source([step])

    assert "def echo_program" in source


def test_extract_program_source_raises_for_unintrospectable_program(experiment):
    from functools import partial

    from helpers import echo_program

    experiment_no_source = type(experiment)(
        program=partial(echo_program),
        prompt_template=experiment.prompt_template,
        config=experiment.config,
    )
    results = RunResults(experiment=experiment_no_source, run=RunInfo(), trials=[], scorings=[])
    step = Step(prompt_template="t", result=results)

    with pytest.raises(TypeError):
        extract_program_source([step])


def test_optimize_rejects_negative_steps(experiment, examples, exact_match_metric):
    with pytest.raises(ValueError, match="steps must be >= 0"):
        optimize(
            experiment=experiment,
            examples=examples,
            metrics=[exact_match_metric],
            proposer_config=experiment.config,
            steps=-1,
        )


def test_optimize_runs_baseline_and_one_proposed_step(
    experiment, examples, exact_match_metric, fake_complete_factory
):
    def proposer(steps, config):
        return "Improved: {{ question }}"

    with fake_complete_factory("wrong"):
        result = optimize(
            experiment=experiment,
            examples=examples[:1],
            metrics=[exact_match_metric],
            proposer_config=experiment.config,
            steps=1,
            proposer=proposer,
            workers=1,
        )

    assert len(result.steps) == 2
    assert result.steps[0].prompt_template == experiment.prompt_template
    assert result.steps[1].prompt_template == "Improved: {{ question }}"


def test_optimize_stops_early_when_score_is_perfect(
    experiment, examples, exact_match_metric, fake_complete
):
    calls = {"n": 0}

    def proposer(steps, config):
        calls["n"] += 1
        return "should not be evaluated"

    perfect = make_run_results(experiment, examples[:1], exact_match_metric, scores=[1.0])

    with patch("promptuna.optimize.run_experiment", return_value=perfect):
        result = optimize(
            experiment=experiment,
            examples=examples[:1],
            metrics=[exact_match_metric],
            proposer_config=experiment.config,
            steps=3,
            proposer=proposer,
        )

    assert len(result.steps) == 1
    assert calls["n"] == 0
