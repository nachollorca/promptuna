# promptuna-server

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

API listens on port **6969**. Job progress streams at `GET /jobs/{job_id}/events` (SSE).

`GET /catalog` lists project and artifact names under the active projects root so clients can build job selectors. The response includes `projects_root` plus, for each project, name lists for `programs`, `metrics`, `prompts`, and `datasets`.

A future `promptuna serve` command will wrap uvicorn and accept `--projects-root` explicitly.
