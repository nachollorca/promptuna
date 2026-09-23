"""Tests for the promptuna CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from promptuna_cli.main import app
from typer.testing import CliRunner

from promptuna.jobs import get_jobs_root, load_job
from promptuna.projects import set_projects_root

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "test_project"
RUNNER = CliRunner()


@pytest.fixture(autouse=True)
def projects_root():
    set_projects_root(FIXTURES.parent)
    yield
    set_projects_root(None)


def test_run_writes_job_and_renders_human_output(fake_complete):
    result = RUNNER.invoke(
        app,
        [
            "run",
            "--project",
            "test_project",
            "--program",
            "echo",
            "--prompt",
            "baseline",
            "--examples",
            "dev",
            "--model",
            "test:model",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "job_id:" in result.stderr
    assert "### Reliability" in result.stdout

    job_id = result.stderr.strip().split()[-1]
    record = load_job(get_jobs_root(), job_id)
    assert record.manifest["kind"] == "run"
    assert record.summary is not None
    assert record.summary["trial_count"] == 2


def test_run_repeats_multiplies_trials(fake_complete):
    result = RUNNER.invoke(
        app,
        [
            "run",
            "--project",
            "test_project",
            "--program",
            "echo",
            "--prompt",
            "baseline",
            "--examples",
            "dev",
            "--model",
            "test:model",
            "--repeats",
            "3",
        ],
    )

    assert result.exit_code == 0, result.stdout
    job_id = result.stderr.strip().split()[-1]
    record = load_job(get_jobs_root(), job_id)
    assert record.manifest["repeats"] == 3
    assert record.summary is not None
    assert record.summary["trial_count"] == 6


def test_evaluate_accepts_comma_separated_metrics(fake_complete):
    result = RUNNER.invoke(
        app,
        [
            "evaluate",
            "--project",
            "test_project",
            "--program",
            "echo",
            "--prompt",
            "baseline",
            "--examples",
            "dev",
            "--model",
            "test:model",
            "--metric",
            "exact_match",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "### Quality" in result.stdout


def test_evaluate_json_output(fake_complete):
    result = RUNNER.invoke(
        app,
        [
            "evaluate",
            "--project",
            "test_project",
            "--program",
            "echo",
            "--prompt",
            "baseline",
            "--examples",
            "dev",
            "--model",
            "test:model",
            "--metric",
            "exact_match",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["kind"] == "evaluate"
    assert "exact_match" in summary["per_metric"]


def test_optimize_renders_history(fake_complete_factory):
    with fake_complete_factory("wrong"):
        result = RUNNER.invoke(
            app,
            [
                "optimize",
                "--project",
                "test_project",
                "--program",
                "echo",
                "--prompt",
                "baseline",
                "--examples",
                "dev",
                "--model",
                "test:model",
                "--metric",
                "exact_match",
                "--steps",
                "0",
                "--proposer-model",
                "test:model",
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert "## Step 0" in result.stdout


def test_report_reads_finished_job(fake_complete):
    run_result = RUNNER.invoke(
        app,
        [
            "run",
            "--project",
            "test_project",
            "--program",
            "echo",
            "--prompt",
            "baseline",
            "--examples",
            "dev",
            "--model",
            "test:model",
            "--format",
            "json",
        ],
    )
    assert run_result.exit_code == 0
    job_id = run_result.stderr.strip().split()[-1]

    report_result = RUNNER.invoke(app, ["report", job_id])
    assert report_result.exit_code == 0
    assert json.loads(report_result.stdout)["job_id"] == job_id


def test_export_writes_every_eval_pair(fake_complete, tmp_path: Path):
    run_result = RUNNER.invoke(
        app,
        [
            "evaluate",
            "--project",
            "test_project",
            "--program",
            "echo",
            "--prompt",
            "baseline",
            "--examples",
            "dev",
            "--model",
            "test:model",
            "--metric",
            "exact_match",
        ],
    )
    assert run_result.exit_code == 0, run_result.stdout
    job_id = run_result.stderr.strip().split()[-1]

    export_result = RUNNER.invoke(
        app,
        [
            "export",
            job_id,
            "--out",
            str(tmp_path),
            "--uuid",
            "123e4567-e89b-42d3-a456-426614174000",
        ],
    )

    assert export_result.exit_code == 0, export_result.output
    aggregate = json.loads(Path(export_result.stdout.strip()).read_text())
    assert aggregate["evaluation_id"].startswith("test_project_echo/")
    assert aggregate["evaluation_results"][0]["metric_config"]["metric_name"] == "exact_match"
    assert aggregate["detailed_evaluation_results"]["total_rows"] == 2


def test_export_missing_job_exits_with_code_2(tmp_path: Path):
    result = RUNNER.invoke(app, ["export", "nope", "--out", str(tmp_path)])

    assert result.exit_code == 2


def test_invalid_project_exits_with_code_2():
    result = RUNNER.invoke(
        app,
        [
            "run",
            "--project",
            "missing_project",
            "--program",
            "echo",
            "--prompt",
            "baseline",
            "--examples",
            "dev",
            "--model",
            "test:model",
        ],
    )

    assert result.exit_code == 2
    assert "not found" in result.stderr
