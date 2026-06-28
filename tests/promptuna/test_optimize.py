"""Tests for promptuna.optimize."""

import json
from typing import Literal
from unittest.mock import patch

import pytest
from helpers import make_run_results, make_trial
from pydantic import BaseModel

from promptuna.evaluate import RunInfo, RunResults, SuccessfulScoring
from promptuna.optimize import (
    OptimizationResult,
    Proposal,
    Step,
    Thinking,
    extract_output_schema,
    extract_program_source,
    optimize,
    render_metrics,
    render_prior_rationale,
    stream_optimize,
)
from promptuna.run import SuccessfulTrial


class _BlockSchema(BaseModel):
    confidence: Literal["weak", "decent", "strong"]


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


def test_render_prior_rationale_is_empty_for_baseline_only(
    experiment, examples, exact_match_metric
):
    baseline = Step(
        prompt_template="baseline template",
        result=make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.4]),
    )

    rationale = render_prior_rationale([baseline])

    assert rationale == ""


def test_render_prior_rationale_surfaces_last_proposal_thinking(
    experiment, examples, exact_match_metric
):
    baseline = Step(
        prompt_template="baseline template",
        result=make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.4]),
    )
    candidate = Step(
        prompt_template="better template",
        result=make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.9]),
        thinking=_sample_thinking(failure_analysis="Judges penalize formatting."),
    )

    rationale = render_prior_rationale([baseline, candidate])

    assert "**Failure analysis:**" in rationale
    assert "Judges penalize formatting." in rationale
    assert "**Improvement hypothesis:**" in rationale


def test_optimize_stores_thinking_from_proposer(
    experiment, examples, exact_match_metric, fake_complete_factory
):
    thinking = _sample_thinking()

    def proposer(steps, model):
        return Proposal(thinking=thinking, prompt_template="Improved: {{ question }}")

    with fake_complete_factory("wrong"):
        result = optimize(
            experiment=experiment,
            examples=examples[:1],
            metrics=[exact_match_metric],
            proposer_model=experiment.model,
            steps=1,
            proposer=proposer,
        )

    assert result.steps[0].thinking is None
    assert result.steps[1].thinking == thinking


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


def test_extract_output_schema_surfaces_json_schema(experiment, example):
    trial = make_trial(example, output_schema=_BlockSchema)
    results = RunResults(experiment=experiment, run=RunInfo(), trials=[trial], scorings=[])
    step = Step(prompt_template="t", result=results)

    schema_json = extract_output_schema([step])

    assert schema_json is not None
    schema = json.loads(schema_json)
    assert schema["properties"]["confidence"]["enum"] == ["weak", "decent", "strong"]


def test_extract_program_source_includes_program_body(experiment, examples, exact_match_metric):
    results = make_run_results(experiment, examples[:1], exact_match_metric, scores=[0.5])
    step = Step(prompt_template="t", result=results)

    source = extract_program_source([step])

    assert "def echo_program" in source


def test_extract_program_source_raises_when_unintrospectable(experiment):
    from functools import partial

    from helpers import echo_program

    experiment_no_source = type(experiment)(
        program=partial(echo_program),
        prompt_template=experiment.prompt_template,
        model=experiment.model,
    )
    results = RunResults(experiment=experiment_no_source, run=RunInfo(), trials=[], scorings=[])
    step = Step(prompt_template="t", result=results)

    with pytest.raises(TypeError, match="Cannot introspect program source"):
        extract_program_source([step])


def test_optimize_rejects_negative_steps(experiment, examples, exact_match_metric):
    with pytest.raises(ValueError, match="steps must be >= 0"):
        optimize(
            experiment=experiment,
            examples=examples,
            metrics=[exact_match_metric],
            proposer_model=experiment.model,
            steps=-1,
        )


def test_optimize_runs_baseline_and_one_proposed_step(
    experiment, examples, exact_match_metric, fake_complete_factory
):
    def proposer(steps, model):
        return Proposal(thinking=None, prompt_template="Improved: {{ question }}")

    with fake_complete_factory("wrong"):
        result = optimize(
            experiment=experiment,
            examples=examples[:1],
            metrics=[exact_match_metric],
            proposer_model=experiment.model,
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

    def proposer(steps, model):
        calls["n"] += 1
        return Proposal(thinking=None, prompt_template="should not be evaluated")

    perfect = make_run_results(experiment, examples[:1], exact_match_metric, scores=[1.0])
    perfect_step = Step(prompt_template=experiment.prompt_template, result=perfect)

    with patch("promptuna.optimize._stream_step") as stream_step:
        stream_step.return_value = iter([perfect_step])
        result = optimize(
            experiment=experiment,
            examples=examples[:1],
            metrics=[exact_match_metric],
            proposer_model=experiment.model,
            steps=3,
            proposer=proposer,
        )

    assert len(result.steps) == 1
    assert calls["n"] == 0


def test_stream_optimize_yields_proposal_trials_scorings_then_step(
    experiment, examples, exact_match_metric, fake_complete_factory
):
    with fake_complete_factory("wrong"):
        items = list(
            stream_optimize(
                experiment=experiment,
                examples=examples[:1],
                metrics=[exact_match_metric],
                proposer_model=experiment.model,
                steps=0,
            )
        )

    assert len(items) == 4
    assert isinstance(items[0], Proposal)
    assert isinstance(items[1], SuccessfulTrial)
    assert isinstance(items[2], SuccessfulScoring)
    assert isinstance(items[3], Step)


def test_stream_optimize_rejects_negative_steps(experiment, examples, exact_match_metric):
    with pytest.raises(ValueError, match="steps must be >= 0"):
        list(
            stream_optimize(
                experiment=experiment,
                examples=examples,
                metrics=[exact_match_metric],
                proposer_model=experiment.model,
                steps=-1,
            )
        )


def test_stream_optimize_matches_optimize(
    experiment, examples, exact_match_metric, fake_complete_factory
):
    def proposer(steps, model):
        return Proposal(thinking=None, prompt_template="Improved: {{ question }}")

    with fake_complete_factory("wrong"):
        streamed_steps = [
            e
            for e in stream_optimize(
                experiment=experiment,
                examples=examples[:1],
                metrics=[exact_match_metric],
                proposer_model=experiment.model,
                steps=1,
                proposer=proposer,
                workers=1,
            )
            if isinstance(e, Step)
        ]
        blocked = optimize(
            experiment=experiment,
            examples=examples[:1],
            metrics=[exact_match_metric],
            proposer_model=experiment.model,
            steps=1,
            proposer=proposer,
            workers=1,
        )

    assert len(streamed_steps) == len(blocked.steps)
    for streamed, blocked_step in zip(streamed_steps, blocked.steps, strict=True):
        assert streamed.prompt_template == blocked_step.prompt_template
        assert streamed.score == blocked_step.score
        assert len(streamed.result.trials) == len(blocked_step.result.trials)
        assert len(streamed.result.scorings) == len(blocked_step.result.scorings)


def test_stream_optimize_step_index_from_step_count(
    experiment, examples, exact_match_metric, fake_complete_factory
):
    def proposer(steps, model):
        return Proposal(thinking=None, prompt_template="Improved: {{ question }}")

    with fake_complete_factory("wrong"):
        completed_steps = 0
        for event in stream_optimize(
            experiment=experiment,
            examples=examples[:1],
            metrics=[exact_match_metric],
            proposer_model=experiment.model,
            steps=1,
            proposer=proposer,
        ):
            if isinstance(event, Step):
                assert completed_steps in {0, 1}
                completed_steps += 1
            elif isinstance(event, Proposal):
                assert completed_steps in {0, 1}
            else:
                assert completed_steps in {0, 1}

        assert completed_steps == 2


def test_stream_optimize_emits_proposal_before_each_step_trials(
    experiment, examples, exact_match_metric, fake_complete_factory
):
    def proposer(steps, model):
        return Proposal(thinking=None, prompt_template="Improved: {{ question }}")

    with fake_complete_factory("wrong"):
        items = list(
            stream_optimize(
                experiment=experiment,
                examples=examples[:1],
                metrics=[exact_match_metric],
                proposer_model=experiment.model,
                steps=1,
                proposer=proposer,
            )
        )

    proposal_indexes = [index for index, item in enumerate(items) if isinstance(item, Proposal)]
    trial_indexes = [index for index, item in enumerate(items) if isinstance(item, SuccessfulTrial)]

    assert proposal_indexes == [0, 4]
    assert all(
        proposal_index < trial_index
        for proposal_index, trial_index in zip(proposal_indexes, trial_indexes[:2], strict=True)
    )
