"""Tests for promptuna.run."""

from helpers import minimal_program

from promptuna.program import Example
from promptuna.run import FailedTrial, SuccessfulTrial, run_trial


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
