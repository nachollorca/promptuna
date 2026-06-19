"""Pytest fixtures for promptuna tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
from helpers import (
    echo_program,
    exact_match_scorer,
)
from helpers import (
    fake_complete as fake_complete_fn,
)
from helpers import (
    fake_complete_factory as build_fake_complete_factory,
)

from promptuna.evaluate import Metric, ProgrammaticMetric, Range
from promptuna.program import Example, Experiment


@pytest.fixture
def example() -> Example:
    return Example(inputs={"question": "2+2?"}, reference="4")


@pytest.fixture
def examples(example: Example) -> list[Example]:
    return [
        example,
        Example(inputs={"question": "3+3?"}, reference="6"),
    ]


@pytest.fixture
def model() -> str:
    return "test:model"


@pytest.fixture
def experiment(model: str) -> Experiment:
    return Experiment(
        program=echo_program,
        prompt_template="Answer: {{ question }}",
        model=model,
    )


@pytest.fixture
def exact_match_metric() -> ProgrammaticMetric:
    return ProgrammaticMetric(
        name="exact_match",
        description="Output must match the reference answer.",
        scale=Range(0.0, 1.0),
        scorer=exact_match_scorer,
    )


@pytest.fixture
def metrics(exact_match_metric: ProgrammaticMetric) -> list[Metric]:
    return [exact_match_metric]


@pytest.fixture
def fake_complete():
    """Patch lmdk.complete with a local fake for the duration of a test."""
    with patch("lmdk.complete", side_effect=fake_complete_fn):
        yield


@pytest.fixture
def fake_complete_factory() -> Callable[[str], Any]:
    return build_fake_complete_factory
