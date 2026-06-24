"""Tests for promptuna.projects."""

from __future__ import annotations

from pathlib import Path

import pytest

from promptuna.projects import (
    ProjectValidationError,
    build_experiment,
    default_projects_root,
    get_projects_root,
    resolve_examples,
    resolve_metrics,
    resolve_program,
    resolve_project_dir,
    resolve_prompt_template,
    set_projects_root,
)

FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "fixtures"
TEST_PROJECT = FIXTURES_ROOT / "test_project"


@pytest.fixture(autouse=True)
def reset_projects_root():
    yield
    set_projects_root(None)


@pytest.fixture
def fixtures_projects_root():
    set_projects_root(FIXTURES_ROOT)
    return FIXTURES_ROOT


def test_build_experiment_resolves_fixture_project(fixtures_projects_root):
    experiment, examples, metrics = build_experiment(
        project="test_project",
        program="echo",
        prompt="baseline",
        model="test:model",
        examples="dev",
        metrics=["exact_match"],
    )

    assert experiment.model == "test:model"
    assert experiment.prompt_template.strip() == "Answer: {{ question }}"
    assert len(examples) == 2
    assert metrics is not None
    assert [metric.name for metric in metrics] == ["exact_match"]


@pytest.mark.parametrize(
    ("project", "match"),
    [
        ("../escape", "invalid project name"),
        ("missing", "not found"),
    ],
)
def test_resolve_project_dir_rejects_invalid_names(
    fixtures_projects_root, project: str, match: str
):
    with pytest.raises(ProjectValidationError, match=match):
        resolve_project_dir(project)


def test_resolve_program_rejects_private_names(fixtures_projects_root):
    project_dir = resolve_project_dir("test_project")

    with pytest.raises(ProjectValidationError, match="invalid program name"):
        resolve_program(project_dir, "_hidden")


def test_resolve_metrics_rejects_private_names(fixtures_projects_root):
    project_dir = resolve_project_dir("test_project")

    with pytest.raises(ProjectValidationError, match="invalid metric name"):
        resolve_metrics(project_dir, ["_secret"])


def test_resolve_program_rejects_invalid_signature(tmp_path):
    project_dir = tmp_path / "bad_program"
    project_dir.mkdir()
    (project_dir / "programs.py").write_text(
        "def bad(**inputs):\n    return inputs\n",
        encoding="utf-8",
    )
    set_projects_root(tmp_path)

    with pytest.raises(ProjectValidationError, match="prompt_template"):
        resolve_program(project_dir, "bad")


def test_resolve_metrics_rejects_non_metric_instance(tmp_path):
    project_dir = tmp_path / "bad_metric"
    project_dir.mkdir()
    (project_dir / "metrics.py").write_text(
        "def not_a_metric():\n    pass\n",
        encoding="utf-8",
    )
    set_projects_root(tmp_path)

    with pytest.raises(ProjectValidationError, match="not a Metric instance"):
        resolve_metrics(project_dir, ["not_a_metric"])


def test_resolve_prompt_rejects_invalid_name(fixtures_projects_root):
    project_dir = resolve_project_dir("test_project")

    with pytest.raises(ProjectValidationError, match="invalid prompt name"):
        resolve_prompt_template(project_dir, "../outside")


def test_resolve_examples_rejects_missing_dataset(fixtures_projects_root):
    project_dir = resolve_project_dir("test_project")

    with pytest.raises(ProjectValidationError, match="not found"):
        resolve_examples(project_dir, "missing")


def test_resolve_examples_rejects_empty_dataset(tmp_path):
    project_dir = tmp_path / "empty_data"
    project_dir.mkdir()
    (project_dir / "data").mkdir()
    (project_dir / "data" / "dev.jsonl").write_text("", encoding="utf-8")
    set_projects_root(tmp_path)

    with pytest.raises(ProjectValidationError, match="is empty"):
        resolve_examples(project_dir, "dev")


def test_get_projects_root_uses_env_var(monkeypatch, fixtures_projects_root):
    monkeypatch.setenv("PROMPTUNA_PROJECTS_ROOT", str(FIXTURES_ROOT))

    assert get_projects_root() == FIXTURES_ROOT.resolve()


def test_set_projects_root_overrides_env_var(monkeypatch, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setenv("PROMPTUNA_PROJECTS_ROOT", str(FIXTURES_ROOT))
    set_projects_root(other)

    assert get_projects_root() == other.resolve()


def test_default_projects_root_points_at_samples():
    assert default_projects_root().name == "samples"


def test_build_experiment_without_metrics_returns_none(fixtures_projects_root):
    experiment, examples, metrics = build_experiment(
        project="test_project",
        program="echo",
        prompt="baseline",
        model="test:model",
        examples="dev",
    )

    project_dir = resolve_project_dir("test_project")
    assert experiment.program is resolve_program(project_dir, "echo")
    assert len(examples) == 2
    assert metrics is None
