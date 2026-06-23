"""Tests for promptuna.run."""

import pytest
from helpers import minimal_program

from promptuna.run import FailedTrial, SuccessfulTrial, run_trial, stream_run


def test_run_trial_returns_successful_trial_with_observed_completion(
    experiment, example, fake_complete_factory
):
    with fake_complete_factory("4"):
        trial = run_trial(
            experiment.program,
            experiment.prompt_template,
            experiment.model,
            example,
        )

    assert isinstance(trial, SuccessfulTrial)
    assert trial.output == "4"
    assert trial.rendered_prompt == "Answer: 2+2?"


def test_run_trial_wraps_program_errors_in_failed_trial(experiment, example):
    def broken_program(prompt_template, model, **inputs):
        raise ValueError("boom")

    trial = run_trial(
        broken_program,
        experiment.prompt_template,
        experiment.model,
        example,
    )

    assert isinstance(trial, FailedTrial)
    assert str(trial.error) == "boom"


def test_run_trial_fails_when_program_skips_complete(experiment, example):
    def no_lm_call(prompt_template, model, **inputs):
        return "done without calling the model"

    trial = run_trial(
        no_lm_call,
        experiment.prompt_template,
        experiment.model,
        example,
    )

    assert isinstance(trial, FailedTrial)
    assert "exactly one time" in str(trial.error)


def test_run_trial_works_when_program_omits_generation_kwargs(
    experiment, example, fake_complete_factory
):
    with fake_complete_factory("4"):
        trial = run_trial(
            minimal_program,
            experiment.prompt_template,
            experiment.model,
            example,
        )

    assert isinstance(trial, SuccessfulTrial)
    assert trial.output == "4"


def test_run_trial_preserves_replicate_index(experiment, example, fake_complete):
    trial = run_trial(
        experiment.program,
        experiment.prompt_template,
        experiment.model,
        example,
        replicate=2,
    )

    assert trial.replicate == 2


def test_stream_run_yields_one_trial_per_example(experiment, examples, fake_complete_factory):
    with fake_complete_factory("4"):
        trials = list(stream_run(experiment, examples[:1]))

    assert len(trials) == 1
    assert isinstance(trials[0], SuccessfulTrial)
    assert trials[0].output == "4"


def test_stream_run_with_empty_examples_raises(experiment):
    with pytest.raises(ValueError, match="examples is empty"):
        list(stream_run(experiment, []))


def test_stream_run_respects_repeats(experiment, example, fake_complete):
    experiment.repeats = 3
    trials = list(stream_run(experiment, [example]))

    assert len(trials) == 3
    assert {t.replicate for t in trials} == {0, 1, 2}


def test_stream_run_uses_thread_pool(experiment, examples, fake_complete_factory):
    with fake_complete_factory("4"):
        trials = list(stream_run(experiment, examples, workers=2))

    assert len(trials) == len(examples)
    assert all(isinstance(t, SuccessfulTrial) for t in trials)
