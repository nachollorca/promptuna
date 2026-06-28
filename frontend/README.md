# promptuna frontend

**SvelteKit** web UI for launching jobs and exploring run / evaluate / optimize results from [`promptuna-server`](../server/README.md).

## Dev

First-time setup from the repository root:

```bash
just frontend-install
```

Run API and UI in separate terminals:

```bash
just server          # API → http://127.0.0.1:6969
just frontend-dev    # UI → http://localhost:5173
```

Set `PUBLIC_API_URL` in `.env` (see `.env.example`) to the **API origin without a path suffix** — e.g. `http://127.0.0.1:6969`. The client appends `/api` to each request (`/api/catalog`, `/api/jobs`, …).

Other recipes: `just frontend-check`, `just frontend-build`.

## Features

- Launch **run**, **evaluate**, or **optimize** jobs with catalog-driven selectors
- Stream results over SSE with live partial aggregates
- Expand trial rows for inputs, outputs, telemetry, and scores
- Optimize view with per-step proposals, trials, and checkpoint scores
- Browse and replay persisted jobs from `GET /api/jobs` and `GET /api/jobs/{id}`

## Deploy

For a single container serving both UI and API, see [Docker in `server/README.md`](../server/README.md#docker-ui--api-in-one-container). The built frontend is served from the same origin; leave `PUBLIC_API_URL` empty at build time.
