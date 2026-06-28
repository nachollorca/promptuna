# promptuna-server

> Server surface for the [`promptuna`](https://pypi.org/project/promptuna/) evaluation harness. See the [main project README](https://github.com/nachollorca/promptuna#readme) for the full overview, library API, and usage surfaces.

HTTP + SSE transport for `promptuna` jobs (`run`, `evaluate`, `optimize`).

This package is **transport only**. It does not define evaluation logic — that lives in the core `promptuna` library. On-disk projects are resolved via [`promptuna.projects`](../src/promptuna/projects.py); user projects do not belong in this directory.

## Development

From the repository root:

```bash
just server
```

Uses bundled `samples/` by default. Override the projects root:

```bash
PROMPTUNA_PROJECTS_ROOT=/path/to/projects just server
```

API listens on port **6969** under the `/api` prefix (e.g. `GET /api/health`). Job progress streams at `GET /api/jobs/{job_id}/events` (SSE).

## Docker (UI + API in one container)

From the repository root:

```bash
just docker-build
just docker-run
```

Open **http://localhost:8080**. The image bundles `samples/`; mount your own projects and pass API keys:

```bash
just docker-run -v /path/to/projects:/projects -e PROMPTUNA_PROJECTS_ROOT=/projects
```

Uses **podman** when available, otherwise **docker**. Rebuild after code changes — the image is a snapshot at build time. Day-to-day development still uses `just server` and `just frontend-dev` (see [`frontend/README.md`](../frontend/README.md)).

Released images are published to GitHub Container Registry on each version tag:

```bash
podman pull ghcr.io/nachollorca/promptuna:latest
podman run --rm -p 8080:8080 --env-file .env ghcr.io/nachollorca/promptuna:latest
```

Set the package visibility to public in GitHub (Packages → promptuna → Package settings) so users can pull without logging in.

Completed jobs are persisted under ``<projects_root>/jobs/<job_id>/`` as ``manifest.json``, append-only ``events.jsonl``, and a terminal ``summary.json``.

`GET /api/catalog` lists project and artifact names under the active projects root so clients can build job selectors.

A future `promptuna serve` command will wrap uvicorn and accept `--projects-root` explicitly.
