"""Tests for the promptuna-server HTTP API."""

from __future__ import annotations

import json
import threading
from functools import partial
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from helpers import fake_complete
from promptuna_server import jobs
from promptuna_server.main import app
from promptuna_server.projects import set_projects_root

from promptuna.optimize import Proposal, stream_optimize
from promptuna.run import stream_run as library_stream_run

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "test_project"


@pytest.fixture(autouse=True)
def isolated_jobs():
    jobs.reset_jobs()
    yield
    jobs.reset_jobs()


@pytest.fixture(autouse=True)
def projects_root():
    set_projects_root(FIXTURES.parent)
    yield
    set_projects_root(None)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_complete_patch():
    with patch("lmdk.complete", side_effect=fake_complete):
        yield


def _read_sse_events(response) -> list[dict]:
    events: list[dict] = []
    for line in response.iter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line.removeprefix("data: ")))
    return events


def _wait_for_events(client: TestClient, job_id: str) -> list[dict]:
    with client.stream("GET", f"/jobs/{job_id}/events") as response:
        assert response.status_code == 200
        return _read_sse_events(response)


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        (
            {
                "project": "../escape",
                "program": "echo",
                "prompt": "baseline",
                "model": "test:model",
                "examples": "dev",
            },
            "invalid project name",
        ),
        (
            {
                "project": "missing",
                "program": "echo",
                "prompt": "baseline",
                "model": "test:model",
                "examples": "dev",
            },
            "not found",
        ),
        (
            {
                "project": "test_project",
                "program": "_hidden",
                "prompt": "baseline",
                "model": "test:model",
                "examples": "dev",
            },
            "invalid program name",
        ),
    ],
)
def test_run_validation_errors(client: TestClient, payload: dict, detail: str):
    response = client.post("/run", json=payload)
    assert response.status_code == 400
    assert detail in response.json()["detail"]


def test_concurrent_job_returns_409(client: TestClient, fake_complete_patch):
    started = threading.Event()
    release = threading.Event()

    def blocking_stream_run(*args, **kwargs):
        started.set()
        assert release.wait(timeout=2)
        yield from library_stream_run(*args, **kwargs)

    with patch("promptuna_server.jobs.stream_run", side_effect=blocking_stream_run):
        first = client.post(
            "/run",
            json={
                "project": "test_project",
                "program": "echo",
                "prompt": "baseline",
                "model": "test:model",
                "examples": "dev",
                "workers": 1,
            },
        )
        assert first.status_code == 200
        job_id = first.json()["job_id"]
        assert started.wait(timeout=2)

        second = client.post(
            "/run",
            json={
                "project": "test_project",
                "program": "echo",
                "prompt": "baseline",
                "model": "test:model",
                "examples": "dev",
                "workers": 1,
            },
        )
        assert second.status_code == 409
        release.set()

    events = _wait_for_events(client, job_id)
    assert events
    assert all(event["job_id"] == job_id for event in events)
    assert all(event["type"] == "trial" for event in events)


def test_run_streams_trial_events(client: TestClient, fake_complete_patch):
    start = client.post(
        "/run",
        json={
            "project": "test_project",
            "program": "echo",
            "prompt": "baseline",
            "model": "test:model",
            "examples": "dev",
            "workers": 2,
        },
    )
    job_id = start.json()["job_id"]
    events = _wait_for_events(client, job_id)

    assert [event["type"] for event in events] == ["trial", "trial"]
    assert all(event["step_index"] == 0 for event in events)
    assert events[0]["seq"] == 0
    assert events[1]["seq"] == 1


def test_evaluate_streams_trial_and_scoring_events(client: TestClient, fake_complete_patch):
    start = client.post(
        "/evaluate",
        json={
            "project": "test_project",
            "program": "echo",
            "prompt": "baseline",
            "model": "test:model",
            "examples": "dev",
            "metrics": ["exact_match"],
            "workers": 1,
        },
    )
    job_id = start.json()["job_id"]
    events = _wait_for_events(client, job_id)

    types = [event["type"] for event in events]
    assert types.count("trial") == 2
    assert types.count("scoring") == 2
    assert "step" not in types
    assert all(event["step_index"] == 0 for event in events)


def test_optimize_streams_checkpoint_events(client: TestClient, fake_complete_factory):
    def proposer(steps, model):
        return Proposal(thinking=None, prompt_template="Improved: {{ question }}")

    with (
        fake_complete_factory("wrong"),
        patch(
            "promptuna_server.jobs.stream_optimize",
            partial(stream_optimize, proposer=proposer),
        ),
    ):
        start = client.post(
            "/optimize",
            json={
                "project": "test_project",
                "program": "echo",
                "prompt": "baseline",
                "model": "test:model",
                "examples": "dev",
                "metrics": ["exact_match"],
                "workers": 1,
                "steps": 1,
                "proposer_model": "test:model",
            },
        )
        job_id = start.json()["job_id"]
        events = _wait_for_events(client, job_id)

    types = [event["type"] for event in events]
    assert "trial" in types
    assert "scoring" in types
    assert "step" in types
    assert types.index("step") > types.index("trial")

    step_indices = [event["step_index"] for event in events if event["type"] == "step"]
    assert step_indices == [0, 1]


def test_unknown_job_events_returns_404(client: TestClient):
    response = client.get("/jobs/does-not-exist/events")
    assert response.status_code == 404
