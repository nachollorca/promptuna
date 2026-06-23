"""Job lifecycle: background threads, queues, and SSE event bridging."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from queue import Queue
from typing import Any, Literal

from promptuna.evaluate import Metric, stream_experiment
from promptuna.optimize import Step, stream_optimize
from promptuna.program import Example, Experiment
from promptuna.run import stream_run
from promptuna.serialize import serialize_error, serialize_event

_STREAM_SENTINEL = object()
JobStatus = Literal["running", "done", "error"]


class JobKind(StrEnum):
    """Discriminator for which library stream drives a job."""

    RUN = "run"
    EVALUATE = "evaluate"
    OPTIMIZE = "optimize"


@dataclass
class JobState:
    """In-memory job record for one streaming job."""

    job_id: str
    kind: JobKind
    status: JobStatus = "running"
    queue: Queue[Any] = field(default_factory=Queue)
    error: str | None = None


_jobs: dict[str, JobState] = {}
_jobs_lock = threading.Lock()


def _has_running_job() -> bool:
    return any(job.status == "running" for job in _jobs.values())


def start_run_job(
    *,
    experiment: Experiment,
    examples: list[Example],
    workers: int,
) -> str:
    """Start a run job and return its ``job_id``."""
    return _start_job(
        JobKind.RUN,
        _run_worker,
        experiment=experiment,
        examples=examples,
        workers=workers,
    )


def start_evaluate_job(
    *,
    experiment: Experiment,
    examples: list[Example],
    metrics: list[Metric],
    workers: int,
) -> str:
    """Start an evaluate job and return its ``job_id``."""
    return _start_job(
        JobKind.EVALUATE,
        _evaluate_worker,
        experiment=experiment,
        examples=examples,
        metrics=metrics,
        workers=workers,
    )


def start_optimize_job(
    *,
    experiment: Experiment,
    examples: list[Example],
    metrics: list[Metric],
    workers: int,
    steps: int,
    proposer_model: str,
) -> str:
    """Start an optimize job and return its ``job_id``."""
    return _start_job(
        JobKind.OPTIMIZE,
        _optimize_worker,
        experiment=experiment,
        examples=examples,
        metrics=metrics,
        workers=workers,
        steps=steps,
        proposer_model=proposer_model,
    )


def _start_job(kind: JobKind, worker, **kwargs: Any) -> str:
    with _jobs_lock:
        if _has_running_job():
            raise ConflictError("another job is already running")
        job_id = str(uuid.uuid4())
        job = JobState(job_id=job_id, kind=kind)
        _jobs[job_id] = job

    thread = threading.Thread(
        target=_job_thread,
        args=(job, worker),
        kwargs=kwargs,
        daemon=True,
        name=f"promptuna-{kind.value}-{job_id[:8]}",
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
            job.queue.put(envelope)
            seq = envelope["seq"] + 1
            if envelope["type"] == "step":
                step_index += 1
        job.status = "done"
    except Exception as exc:
        job.status = "error"
        job.error = str(exc)
        job.queue.put(
            serialize_error(job_id=job.job_id, seq=seq, message=str(exc), step_index=step_index)
        )
    finally:
        job.queue.put(_STREAM_SENTINEL)


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
    while True:
        item = await asyncio.to_thread(job.queue.get)
        if item is _STREAM_SENTINEL:
            break
        yield f"data: {json.dumps(item)}\n\n"


def reset_jobs() -> None:
    """Clear all jobs (tests only)."""
    with _jobs_lock:
        _jobs.clear()
