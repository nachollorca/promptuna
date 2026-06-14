"""Tests for promptuna.program."""

from promptuna.program import Example, Experiment, LMConfig


def test_example_stores_inputs_and_optional_reference():
    example = Example(inputs={"x": 1}, reference="yes")
    assert example.inputs == {"x": 1}
    assert example.reference == "yes"


def test_example_reference_defaults_to_none():
    example = Example(inputs={"x": 1})
    assert example.reference is None


def test_lm_config_stores_model_and_generation_kwargs():
    config = LMConfig(model="test:model", generation_kwargs={"temperature": 0})
    assert config.model == "test:model"
    assert config.generation_kwargs == {"temperature": 0}


def test_experiment_defaults_to_one_repeat(experiment):
    assert experiment.repeats == 1
