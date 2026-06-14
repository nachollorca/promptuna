"""Tests for promptuna.optimize."""

from unittest.mock import patch

import pytest

from promptuna.optimize import OptimizationResult, Step, optimize, render_history
from helpers import make_run_results


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
    assert "better template" in history
    assert "Δ +0.50 vs baseline" in history


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
