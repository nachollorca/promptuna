"""Tests for the Every Eval Ever exporter."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from helpers import make_trial

from promptuna.evaluate import Ordinal, ProgrammaticMetric, Score, SuccessfulScoring
from promptuna.every_eval import export_every_eval
from promptuna.serialize import serialize_event

LOG_UUID = "123e4567-e89b-42d3-a456-426614174000"

# The `required` lists of eval.schema.json / instance_level_eval.schema.json.
AGGREGATE_REQUIRED = {
    "schema_version",
    "evaluation_id",
    "retrieved_timestamp",
    "source_metadata",
    "model_info",
    "eval_library",
    "evaluation_results",
}
AGGREGATE_ALLOWED = AGGREGATE_REQUIRED | {"evaluation_timestamp", "detailed_evaluation_results"}
INSTANCE_REQUIRED = {
    "schema_version",
    "evaluation_id",
    "model_id",
    "evaluation_name",
    "sample_id",
    "interaction_type",
    "input",
    "answer_attribution",
    "evaluation",
}


def _manifest(**overrides) -> dict:
    manifest = {
        "job_id": "job-1",
        "schema_version": 1,
        "promptuna_version": "1.37.2",
        "kind": "evaluate",
        "status": "done",
        "started_at": "2026-01-01T00:00:00+00:00",
        "finished_at": "2026-01-01T00:01:00+00:00",
        "project": "demo",
        "program": "echo",
        "prompt": "baseline",
        "examples": "dev",
        "dataset_path": "/tmp/dev.jsonl",
        "dataset_sha256": "a" * 64,
        "model": "openai:gpt-4o-mini",
        "workers": 1,
        "repeats": 1,
        "error": None,
    }
    manifest.update(overrides)
    return manifest


def _write_job(tmp_path: Path, manifest: dict, events: list[dict]) -> Path:
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    (job_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (job_dir / "events.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )
    return job_dir


@pytest.fixture
def job_dir(tmp_path: Path, example, exact_match_metric):
    trial = make_trial(example)
    request = trial.request
    assert request is not None
    trial = replace(trial, request=replace(request, model_id="openai/gpt-4o-mini"))
    second = make_trial(example, output="5", replicate=1)
    scorings = [
        SuccessfulScoring(
            trial=trial,
            metric=exact_match_metric,
            score=Score(raw=1.0, normalized=1.0, reason="exact"),
        ),
        SuccessfulScoring(
            trial=second,
            metric=exact_match_metric,
            score=Score(raw=0.0, normalized=0.0, reason="mismatch"),
        ),
    ]
    events = [serialize_event(trial, job_id="job-1", seq=0, step_index=0)]
    events.append(serialize_event(second, job_id="job-1", seq=1, step_index=0))
    events += [
        serialize_event(scoring, job_id="job-1", seq=seq, step_index=0)
        for seq, scoring in enumerate(scorings, start=2)
    ]
    return _write_job(tmp_path, _manifest(), events)


def _load_pair(aggregate_path: Path) -> tuple[dict, list[dict], Path]:
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    samples_path = aggregate_path.parent / f"{aggregate_path.stem}_samples.jsonl"
    rows = [json.loads(line) for line in samples_path.read_text(encoding="utf-8").splitlines()]
    return aggregate, rows, samples_path


def test_export_writes_datastore_pair(job_dir: Path, tmp_path: Path):
    aggregate_path = export_every_eval(job_dir, tmp_path / "out", log_uuid=LOG_UUID)
    aggregate, rows, samples_path = _load_pair(aggregate_path)

    assert aggregate_path == (
        tmp_path / "out" / "data" / "demo" / "openai" / "gpt-4o-mini" / f"{LOG_UUID}.json"
    )
    assert AGGREGATE_REQUIRED <= set(aggregate) <= AGGREGATE_ALLOWED
    assert aggregate["schema_version"] == "0.3.0"
    assert aggregate["evaluation_id"].startswith("demo_echo/openai/gpt-4o-mini/")
    assert aggregate["model_info"]["id"] == "openai/gpt-4o-mini"
    assert aggregate["source_metadata"]["source_type"] == "evaluation_run"
    assert aggregate["eval_library"]["name"] == "promptuna"

    detail = aggregate["detailed_evaluation_results"]
    assert detail["format"] == "jsonl"
    assert detail["total_rows"] == len(rows) == 2
    assert detail["file_path"] == f"data/demo/openai/gpt-4o-mini/{LOG_UUID}_samples.jsonl"
    assert detail["checksum"] == hashlib.sha256(samples_path.read_bytes()).hexdigest()


def test_export_result_pools_replicates_on_the_metric_scale(job_dir: Path, tmp_path: Path):
    aggregate, _, _ = _load_pair(export_every_eval(job_dir, tmp_path / "out", log_uuid=LOG_UUID))

    (result,) = aggregate["evaluation_results"]
    metric = result["metric_config"]
    assert metric["score_type"] == "continuous"
    assert (metric["min_score"], metric["max_score"]) == (0.0, 1.0)
    assert metric["lower_is_better"] is False
    # Two replicates, one exact match: mean 0.5, and the score sits inside its own bounds.
    score = result["score_details"]["score"]
    assert metric["min_score"] <= score <= metric["max_score"]
    assert score == pytest.approx(0.5)
    assert result["score_details"]["uncertainty"]["num_samples"] == 2
    assert result["evaluation_result_id"] == "demo_echo:exact_match"


def test_export_instance_rows_pair_with_the_aggregate(job_dir: Path, tmp_path: Path):
    aggregate_path = export_every_eval(job_dir, tmp_path / "out", log_uuid=LOG_UUID)
    aggregate, rows, _ = _load_pair(aggregate_path)

    for row in rows:
        assert set(row) >= INSTANCE_REQUIRED
        assert row["evaluation_id"] == aggregate["evaluation_id"]
        assert row["model_id"] == aggregate["model_info"]["id"]
        assert row["evaluation_name"] == aggregate["evaluation_results"][0]["evaluation_name"]
        assert row["interaction_type"] == "single_turn"
        assert row["input"]["raw"] == "2+2?"
        assert row["input"]["reference"] == ["4"]
        assert len(row["sample_hash"]) == 64
        assert row["answer_attribution"][0]["is_terminal"] is True

    assert [row["output"]["raw"] for row in rows] == [["4"], ["5"]]
    assert [row["evaluation"]["is_correct"] for row in rows] == [True, False]
    assert rows[0]["token_usage"] == {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7}
    assert rows[0]["performance"]["latency_ms"] == pytest.approx(200.0)


def test_export_ordinal_metric_reports_levels(tmp_path: Path, example, exact_match_metric):
    metric = ProgrammaticMetric(
        name="quality",
        description="How good is it?",
        scale=Ordinal(["bad", "ok", "great"]),
        scorer=exact_match_metric.scorer,
    )
    trial = make_trial(example)
    scoring = SuccessfulScoring(
        trial=trial, metric=metric, score=Score(raw="great", normalized=1.0, reason="")
    )
    job_dir = _write_job(
        tmp_path,
        _manifest(),
        [
            serialize_event(trial, job_id="job-1", seq=0, step_index=0),
            serialize_event(scoring, job_id="job-1", seq=1, step_index=0),
        ],
    )

    aggregate_path = export_every_eval(job_dir, tmp_path / "out", log_uuid=LOG_UUID)
    aggregate, rows, _ = _load_pair(aggregate_path)

    metric_config = aggregate["evaluation_results"][0]["metric_config"]
    assert metric_config["score_type"] == "levels"
    assert metric_config["level_names"] == ["bad", "ok", "great"]
    assert metric_config["has_unknown_level"] is False
    # Native scale: the top level is index 2, not the normalized 1.0.
    assert aggregate["evaluation_results"][0]["score_details"]["score"] == pytest.approx(2.0)
    assert rows[0]["evaluation"]["score"] == pytest.approx(2.0)


def test_export_omits_samples_when_no_metric_scored(tmp_path: Path, example):
    trial = make_trial(example)
    job_dir = _write_job(
        tmp_path, _manifest(), [serialize_event(trial, job_id="job-1", seq=0, step_index=0)]
    )

    output = tmp_path / "out"
    aggregate_path = export_every_eval(job_dir, output, log_uuid=LOG_UUID)

    assert "detailed_evaluation_results" not in json.loads(aggregate_path.read_text())
    assert not list(output.rglob("*_samples.jsonl"))


def test_export_is_reproducible_with_a_fixed_uuid(job_dir: Path, tmp_path: Path):
    first = export_every_eval(job_dir, tmp_path / "a", log_uuid=LOG_UUID)
    second = export_every_eval(job_dir, tmp_path / "b", log_uuid=LOG_UUID)
    first_aggregate, first_rows, _ = _load_pair(first)
    second_aggregate, second_rows, _ = _load_pair(second)
    # Only the retrieval timestamp moves between runs; that is what it is for.
    drop_id = [{k: v for k, v in row.items() if k != "evaluation_id"} for row in first_rows]

    assert uuid.UUID(LOG_UUID).version == 4
    assert first_aggregate["evaluation_results"] == second_aggregate["evaluation_results"]
    assert drop_id == [
        {k: v for k, v in row.items() if k != "evaluation_id"} for row in second_rows
    ]
