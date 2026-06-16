"""Tests for promptuna.optimize."""

import logging
from typing import Literal
from unittest.mock import patch

import pytest
from helpers import make_run_results, make_trial
from lmdk import CompletionResponse
from pydantic import BaseModel

from promptuna.evaluate import RunInfo, RunResults
from promptuna.optimize import (
    Advice,
    OptimizationResult,
    Output,
    Step,
    Thinking,
    default_proposer,
    extract_output_schema,
    extract_program_source,
    optimize,
    render_history,
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
    assert "better template" in history
    assert "Δ +0.50 vs baseline" in history


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


def test_default_proposer_returns_template_and_logs_advisories(
    experiment, examples, exact_match_metric, caplog
):
    step = Step(
        prompt_template="baseline",
        result=make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.5]),
    )
    output = Output(
        thinking=Thinking(
            reinstate_goal="",
            trajectory_summary="",
            failure_analysis="",
            what_works="",
            what_hurts="",
            improvement_hypothesis="",
            edit_plan="",
        ),
        prompt_template="Improved: {{ question }}",
        advices=[Advice(target="output_schema", suggestion="add a confidence field")],
    )
    response = CompletionResponse(
        content="", input_tokens=1, output_tokens=1, latency=0.1, parsed=output
    )

    with patch("promptuna.optimize.complete", return_value=response):
        with caplog.at_level(logging.INFO, logger="promptuna.optimize"):
            template = default_proposer([step], experiment.config)

    assert template == "Improved: {{ question }}"
    assert "add a confidence field" in caplog.text
    assert "output_schema" in caplog.text


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
