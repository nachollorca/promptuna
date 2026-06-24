"""Job lifecycle: background threads, queues, SSE event bridging, and on-disk jobs."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from promptuna.evaluate import Metric, stream_experiment
from promptuna.jobs import JobArchive, JobConfig, JobKind, JobStatus, get_jobs_root
from promptuna.optimize import Step, stream_optimize
from promptuna.program import Example, Experiment
from promptuna.run import stream_run
from promptuna.serialize import serialize_error, serialize_event

_WAIT_TIMEOUT_SECONDS = 1.0


@dataclass
class JobState:
    """In-memory job record for one streaming job."""

    job_id: str
    kind: JobKind
    archive: JobArchive
    status: JobStatus = "running"
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    _cond: threading.Condition = field(default_factory=threading.Condition)


_jobs: dict[str, JobState] = {}
_jobs_lock = threading.Lock()


def _has_running_job() -> bool:
    return any(job.status == "running" for job in _jobs.values())


def _append_event(job: JobState, envelope: dict[str, Any]) -> None:
    with job._cond:
        job.events.append(envelope)
        job.archive.append_event(envelope)
        job._cond.notify_all()


def _finish_job(job: JobState) -> None:
    with job._cond:
        job._cond.notify_all()


def start_run_job(
    *,
    config: JobConfig,
    experiment: Experiment,
    examples: list[Example],
    workers: int,
) -> str:
    """Start a run job and return its ``job_id``."""
    return _start_job(
        "run",
        _run_worker,
        config=config,
        experiment=experiment,
        examples=examples,
        workers=workers,
    )


def start_evaluate_job(
    *,
    config: JobConfig,
    experiment: Experiment,
    examples: list[Example],
    metrics: list[Metric],
    workers: int,
) -> str:
    """Start an evaluate job and return its ``job_id``."""
    return _start_job(
        "evaluate",
        _evaluate_worker,
        config=config,
        experiment=experiment,
        examples=examples,
        metrics=metrics,
        workers=workers,
    )


def start_optimize_job(
    *,
    config: JobConfig,
    experiment: Experiment,
    examples: list[Example],
    metrics: list[Metric],
    workers: int,
    steps: int,
    proposer_model: str,
) -> str:
    """Start an optimize job and return its ``job_id``."""
    return _start_job(
        "optimize",
        _optimize_worker,
        config=config,
        experiment=experiment,
        examples=examples,
        metrics=metrics,
        workers=workers,
        steps=steps,
        proposer_model=proposer_model,
    )


def _start_job(kind: JobKind, worker, *, config: JobConfig, **kwargs: Any) -> str:
    with _jobs_lock:
        if _has_running_job():
            raise ConflictError("another job is already running")
        job_id = str(uuid.uuid4())
        archive = JobArchive.open(get_jobs_root(), job_id, config)
        job = JobState(job_id=job_id, kind=kind, archive=archive)
        _jobs[job_id] = job

    thread = threading.Thread(
        target=_job_thread,
        args=(job, worker),
        kwargs=kwargs,
        daemon=True,
        name=f"promptuna-{kind}-{job_id[:8]}",
    )
    thread.start()
    return job_id


class ConflictError(Exception):
    """Raised when a second job is started while one is running."""


class JobNotFoundError(Exception):
    """Raised when ``job_id`` is unknown."""


def get_job(job_id: str) -> JobState:
    """Return job state or raise :class:`JobNotFoundError`."""
    try:
        return _jobs[job_id]
    except KeyError as exc:
        raise JobNotFoundError(job_id) from exc


def _job_thread(job: JobState, worker, **kwargs: Any) -> None:
    seq = 0
    step_index = 0
    try:
        for envelope in worker(job_id=job.job_id, step_index=step_index, seq=seq, **kwargs):
            _append_event(job, envelope)
            seq = envelope["seq"] + 1
            if envelope["type"] == "step":
                step_index += 1
        job.status = "done"
        job.archive.finalize("done")
    except Exception as exc:
        job.status = "error"
        job.error = str(exc)
        _append_event(
            job,
            serialize_error(job_id=job.job_id, seq=seq, message=str(exc), step_index=step_index),
        )
        job.archive.finalize("error", error=str(exc))
    finally:
        _finish_job(job)


def _run_worker(
    *,
    job_id: str,
    experiment: Experiment,
    examples: list[Example],
    workers: int,
    seq: int,
    step_index: int,
) -> Iterator[dict[str, Any]]:
    for item in stream_run(experiment, examples, workers=workers):
        yield serialize_event(item, job_id=job_id, seq=seq, step_index=0)
        seq += 1


def _evaluate_worker(
    *,
    job_id: str,
    experiment: Experiment,
    examples: list[Example],
    metrics: list[Metric],
    workers: int,
    seq: int,
    step_index: int,
) -> Iterator[dict[str, Any]]:
    for item in stream_experiment(experiment, examples, metrics, workers=workers):
        yield serialize_event(item, job_id=job_id, seq=seq, step_index=0)
        seq += 1


def _optimize_worker(
    *,
    job_id: str,
    experiment: Experiment,
    examples: list[Example],
    metrics: list[Metric],
    workers: int,
    steps: int,
    proposer_model: str,
    seq: int,
    step_index: int,
) -> Iterator[dict[str, Any]]:
    for item in stream_optimize(
        experiment,
        examples,
        metrics,
        proposer_model=proposer_model,
        steps=steps,
        workers=workers,
    ):
        if isinstance(item, Step):
            yield serialize_event(item, job_id=job_id, seq=seq, step_index=step_index)
            step_index += 1
        else:
            yield serialize_event(item, job_id=job_id, seq=seq, step_index=step_index)
        seq += 1


async def stream_job_events(job_id: str):
    """Async generator yielding SSE ``data:`` lines for ``job_id``."""
    job = get_job(job_id)
    offset = 0
    while True:
        batch, done = await asyncio.to_thread(_wait_for_events, job, offset)
        for envelope in batch:
            yield f"data: {json.dumps(envelope)}\n\n"
            offset += 1
        if done and offset >= len(job.events):
            break


def _wait_for_events(job: JobState, offset: int) -> tuple[list[dict[str, Any]], bool]:
    with job._cond:
        while offset >= len(job.events) and job.status == "running":
            job._cond.wait(timeout=_WAIT_TIMEOUT_SECONDS)
        return job.events[offset:], job.status != "running"


def reset_jobs() -> None:
    """Clear all jobs (tests only)."""
    with _jobs_lock:
        _jobs.clear()
