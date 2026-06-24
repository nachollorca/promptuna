"""FastAPI application: routes, CORS, and job orchestration."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from promptuna.projects import ProjectValidationError, build_experiment
from promptuna_server import jobs
from promptuna_server.schemas import EvaluateRequest, JobStartResponse, OptimizeRequest, RunRequest

app = FastAPI(title="promptuna-server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validation_error(exc: ProjectValidationError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}


@app.post("/run", response_model=JobStartResponse)
def start_run(request: RunRequest) -> JobStartResponse:
    """Start a run job; stream trials via ``GET /jobs/{job_id}/events``."""
    try:
        experiment, examples, _ = build_experiment(
            project=request.project,
            program=request.program,
            prompt=request.prompt,
            model=request.model,
            examples=request.examples,
        )
    except ProjectValidationError as exc:
        raise _validation_error(exc) from exc

    try:
        job_id = jobs.start_run_job(
            experiment=experiment,
            examples=examples,
            workers=request.workers,
        )
    except jobs.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return JobStartResponse(job_id=job_id)


@app.post("/evaluate", response_model=JobStartResponse)
def start_evaluate(request: EvaluateRequest) -> JobStartResponse:
    """Start an evaluate job; stream trials and scorings via SSE."""
    try:
        experiment, examples, metrics = build_experiment(
            project=request.project,
            program=request.program,
            prompt=request.prompt,
            model=request.model,
            examples=request.examples,
            metrics=request.metrics,
        )
    except ProjectValidationError as exc:
        raise _validation_error(exc) from exc

    assert metrics is not None
    try:
        job_id = jobs.start_evaluate_job(
            experiment=experiment,
            examples=examples,
            metrics=metrics,
            workers=request.workers,
        )
    except jobs.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return JobStartResponse(job_id=job_id)


@app.post("/optimize", response_model=JobStartResponse)
def start_optimize(request: OptimizeRequest) -> JobStartResponse:
    """Start an optimize job; stream trials, scorings, and steps via SSE."""
    try:
        experiment, examples, metrics = build_experiment(
            project=request.project,
            program=request.program,
            prompt=request.prompt,
            model=request.model,
            examples=request.examples,
            metrics=request.metrics,
        )
    except ProjectValidationError as exc:
        raise _validation_error(exc) from exc

    assert metrics is not None
    try:
        job_id = jobs.start_optimize_job(
            experiment=experiment,
            examples=examples,
            metrics=metrics,
            workers=request.workers,
            steps=request.steps,
            proposer_model=request.proposer_model,
        )
    except jobs.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return JobStartResponse(job_id=job_id)


@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    """Server-sent events for one job until it completes or errors."""
    try:
        jobs.get_job(job_id)
    except jobs.JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found") from exc

    return StreamingResponse(
        jobs.stream_job_events(job_id),
        media_type="text/event-stream",
    )
