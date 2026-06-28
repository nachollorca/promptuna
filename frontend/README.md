# promptuna frontend

Planned **SvelteKit** app for launching jobs and exploring run / evaluate / optimize results from `promptuna-server`.

**Start here:** [HANDOFF.md](./HANDOFF.md) — full design brief, API reference, event model, component breakdown, and implementation order. Written to be understandable without chat context.

## Status

Not implemented yet. The server already exposes:

- `GET /catalog`, `GET /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/events`
- `POST /run`, `POST /evaluate`, `POST /optimize`

## Dev (once scaffolded)

```bash
just server          # API → http://127.0.0.1:6969
cd frontend && npm run dev   # UI → http://localhost:5173
```

Set `PUBLIC_API_URL` (or equivalent) to the API base URL.
