# promptuna frontend

**SvelteKit** web UI for launching jobs and exploring run / evaluate / optimize results from `promptuna-server`.

Design reference: [HANDOFF.md](./HANDOFF.md)

## Dev

```bash
just server          # API → http://127.0.0.1:6969
just frontend-dev    # UI → http://localhost:5173
```

Set `PUBLIC_API_URL` in `.env` (see `.env.example`) to point at the API base URL.

## Features

- Launch **run**, **evaluate**, or **optimize** jobs with catalog-driven selectors
- Stream results over SSE with live partial aggregates
- Expand trial rows for inputs, outputs, telemetry, and scores
- Optimize view with per-step proposals, trials, and checkpoint scores
- Browse and replay persisted jobs from `GET /jobs` and `GET /jobs/{id}`
