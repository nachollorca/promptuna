# Frontend handoff

Design brief for the Promptuna web GUI. This document is self-contained: everything below can be verified against the repository and a running `promptuna-server` instance.

## Goal

Build a **reactive**, **interactive**, **simple** web UI that lets users:

1. Pick an operation (`run`, `evaluate`, or `optimize`) and its parameters.
2. Launch a job and watch results arrive incrementally (SSE).
3. Expand rows to inspect per-example detail without breaking live updates.
4. Replay completed jobs from disk (`GET /jobs/{job_id}`).

The server is transport-only; all domain logic lives in the `promptuna` library. The frontend consumes HTTP + SSE and mirrors the on-disk job format under `<projects_root>/jobs/<job_id>/`.

## Recommended stack

**SvelteKit** (Vite dev server on port **5173**) was the agreed choice:

- Built-in reactivity suits streaming UIs.
- Less boilerplate than React for someone not steeped in JS frameworks.
- CORS is already configured for `http://localhost:5173` and `http://127.0.0.1:5173` in `server/src/promptuna_server/main.py`.

Point the app at the API base URL (default `http://127.0.0.1:6969`; start with `just server`).

No frontend code exists yet — only this directory.

---

## Server API

Authoritative route definitions: `server/src/promptuna_server/main.py`
Request/response models: `server/src/promptuna_server/schemas.py`

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness (`{"status":"ok"}`) |
| `GET` | `/catalog` | Projects and artifact names for selectors |
| `POST` | `/run` | Start a run job → `{ "job_id": "…" }` |
| `POST` | `/evaluate` | Start evaluate job |
| `POST` | `/optimize` | Start optimize job |
| `GET` | `/jobs` | List persisted jobs (manifest summaries, newest first) |
| `GET` | `/jobs/{job_id}` | Replay: `{ manifest, events, summary }` |
| `GET` | `/jobs/{job_id}/events` | SSE stream until job completes |

### Constraints

- **One job at a time** in memory. A second `POST` while one is running returns **409** with `{"detail":"another job is already running"}`.
- **`model`** and **`proposer_model`** are free-text strings (`provider:model-id`); they are **not** in `/catalog`.
- **`summary`** in `GET /jobs/{id}` is `null` while `manifest.status === "running"`. Prefer in-memory events for active jobs (the endpoint already does this server-side).

### Catalog (`GET /catalog`)

```json
{
  "projects_root": "/abs/path/to/samples",
  "projects": [
    {
      "name": "classify_sentiment",
      "programs": ["echo"],
      "metrics": ["exact_match"],
      "prompts": ["baseline"],
      "datasets": ["dev"]
    }
  ]
}
```

Use cascading selects: operation → project → program, prompt, dataset; for evaluate/optimize add metrics (multi-select); for optimize add `steps` and `proposer_model`; all operations expose `workers`.

### Job start bodies

**Run** — `RunRequest`:

```json
{
  "project": "test_project",
  "program": "echo",
  "prompt": "baseline",
  "model": "test:model",
  "examples": "dev",
  "workers": 1
}
```

**Evaluate** — adds `"metrics": ["exact_match"]` (min length 1).

**Optimize** — adds `"steps": 5` and `"proposer_model": "test:model"`.

---

## Event model

Serialization: `src/promptuna/serialize.py`
Persistence: `src/promptuna/jobs.py` (`events.jsonl`, one envelope per line)

Every streamed/stored event shares this **envelope**:

```json
{
  "seq": 0,
  "job_id": "uuid",
  "step_index": 0,
  "type": "trial | scoring | step | proposal | error",
  "payload": { }
}
```

`step_index` semantics:

- Always **0** for `run` and `evaluate` jobs.
- For `optimize`: `proposal`, trials, and scorings for a step share the same `step_index`. **`step_index` increments only after a `step` event** (see `stream_job` in `src/promptuna/jobs.py`).

### Event types and payloads

#### `trial`

```json
{
  "status": "success | failed",
  "trial_id": "16-char-hex",
  "example": { "inputs": { }, "reference": "…" },
  "replicate": 0,
  "output": "…",
  "telemetry": {
    "rendered_prompt": "…",
    "request": { "model_id", "prompt", … },
    "response": { "content", "input_tokens", "output_tokens", "latency", … }
  }
}
```

Failed trials have `"error": { "type", "message" }` and no `telemetry`.
`trial_id` is stable per `(inputs, reference, replicate)` within a job.

#### `scoring` (evaluate / optimize only)

```json
{
  "trial_id": "…",
  "metric": { "name", "description", "kind": "programmatic | llm_judge" },
  "replicate": 0,
  "status": "success | failed",
  "score": { "raw", "normalized", "reason" }
}
```

Attach scorings to trials by `trial_id`. Trials and scorings arrive **interleaved** in completion order (not “all trials then all scorings”).

#### `proposal` (optimize only)

Emitted **before** that step’s trials so the UI can show template + reasoning first:

```json
{
  "prompt_template": "Answer: {{ question }}",
  "thinking": null
}
```

`thinking` is a structured object (seven string fields) or `null` for the baseline step. Field names match `Thinking` in `src/promptuna/optimize.py`: `reinstate_goal`, `trajectory_summary`, `failure_analysis`, `what_works`, `what_hurts`, `improvement_hypothesis`, `edit_plan`.

#### `step` (optimize only)

Emitted **after** all trials and scorings for that step:

```json
{
  "score": 0.8,
  "prompt_template": "…",
  "thinking": { … } | null,
  "summary": {
    "overall": { "mean", "sd", "n" },
    "per_metric": { "exact_match": { "mean", "sd", "n" } },
    "failure_rate": 0.0,
    "scoring_failure_rate": 0.0
  }
}
```

`score` is `RunResults.overall.mean` — the checkpoint objective.
`step` duplicates template/thinking from `proposal` for that step (backward compatibility and static replay). Prefer **`proposal` for “about to run”** UI and **`step` for finalized score + aggregates**.

#### `error`

Fatal job failure: `{ "message": "…" }`. Job `manifest.status` becomes `"error"`.

### Ordering by job kind

| Kind | Stream order |
|------|----------------|
| `run` | `trial`, `trial`, … |
| `evaluate` | `trial` / `scoring` interleaved |
| `optimize` | Per step: `proposal` → trials/scorings → `step`; then silence while proposer runs; repeat |

Optimize contract (docstring in `stream_optimize`, `src/promptuna/optimize.py`):

```
proposal₀ → trials/scorings → step₀
[proposer runs — no events]
proposal₁ → trials/scorings → step₁
…
```

Early stop when a checkpoint scores perfectly (`overall.mean >= 1.0`) means fewer steps appear; no error.

### SSE wire format

`GET /jobs/{job_id}/events` returns `text/event-stream`. Each message is a single line:

```
data: {"seq":0,"job_id":"…","type":"trial",…}

```

No `event:` or `id:` fields. Late subscribers receive the full buffered history (including completed jobs).

---

## Data flow architecture

Use one code path for **live** and **replay** data:

```
┌─────────────────┐     ┌─────────────────┐
│ SSE /events     │     │ GET /jobs/{id}  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
              ┌─────────────┐
              │  EventStore │  ← plain TS module, not a Svelte store initially
              │  (reducer)  │
              └──────┬──────┘
                     │
     ┌───────────────┼───────────────┐
     ▼               ▼               ▼
 JobManifest    StepSection[]    JobSummary
                     │
                 TrialRow[]
```

### `EventStore` responsibilities

Ingest envelopes sequentially (`seq` is monotonic). Maintain:

- **`trialsById`**: map `trial_id` → trial payload + attached scorings (append as scorings arrive).
- **`steps`**: for optimize, group by `step_index`; each step holds optional `proposal`, trial ids, optional `step` summary.
- **`aggregates`**: running counts and means (see below).
- **`status`**: `running | done | error` from manifest, summary, or terminal `error` event.

Replay: feed `events` from `GET /jobs/{id}` through the same reducer. Live: connect SSE after `POST` returns `job_id`.

**Expand/collapse** state stays in components (e.g. `Set` of expanded `trial_id`s). Use keyed `{#each}` in Svelte so open rows are not remounted when new events append.

---

## UI components (agreed design)

### 1. `JobLauncher`

- Load `/catalog` on mount.
- Operation toggle: run | evaluate | optimize.
- Cascading selects from catalog; text inputs for `model`, `proposer_model`; number inputs for `workers`, `steps`.
- Multi-select metrics when evaluate/optimize.
- Submit → `POST` appropriate endpoint → emit `job_id` → start SSE.
- Disable submit while a job is running (handle 409 with a clear message).

### 2. `JobManifest`

Show the launched configuration:

- Live jobs: echo the submitted form values + returned `job_id` + status badge.
- Replay jobs: `manifest` from `GET /jobs/{id}`.

Include `kind`, `status`, timestamps, and link/copy `job_id`.

### 3. `TrialRow` (single component for run **and** evaluate)

One row per `trial_id` (see replicates below). Collapsed by default; expand for detail.

**Collapsed:** short summary of inputs, output snippet or error, optional score chips.

**Expanded:** full inputs, reference, output, telemetry (tokens, latency, rendered prompt), scoring `reason`, errors.

**Color encoding (agreed):**

| Situation | Border / background |
|-----------|---------------------|
| Trial failed, or any scoring failed | **Grey** |
| Run-only success (no scorings) | **Green** |
| Evaluated success | **Red → amber → green** gradient from `score.normalized` (0–1) |

For multiple metrics per trial, pick one rule and stick to it — e.g. color from the **worst** `normalized` score, or from a designated “primary” metric.

### 4. `StepSection` (optimize only)

One panel per `step_index`, top to bottom:

```
┌─ Step N ─────────────────────────────────────────┐
│ Header: index, score, Δ vs previous step         │
│ Proposal block: thinking (collapsible sections)  │
│                 + prompt_template (monospace)    │
│ [TrialRow × …]  ← streaming, live partial stats  │
│ Footer (on `step` event): final aggregates       │
└──────────────────────────────────────────────────┘
```

- **Between steps:** show “Proposing…” spinner from `step`ₙ until `proposal`ₙ₊₁ arrives.
- **Δ score:** client-side: `step[n].score - step[n-1].score` (not in API).
- **Baseline (step 0):** `proposal.thinking` is `null`.

Run and evaluate jobs do **not** use `StepSection`; they render a flat list of `TrialRow`s (evaluate attaches scorings inside each row).

### 5. `JobSummary`

When the job finishes (`done` or `error`):

- Show `summary` from `GET /jobs/{id}` or fold client-side aggregates.
- Optimize: highlight `summary.best_step` when present (`src/promptuna/jobs.py` `fold_summary`).

### 6. Job browser (optional first slice)

`GET /jobs` → table or list → navigate to replay view using `GET /jobs/{id}`.

---

## Aggregations (agreed)

Show **live partial** aggregates while events stream; mark them as incomplete until the step/job ends.

| Metric | Update on | Notes |
|--------|-----------|-------|
| Success / fail counts | each `trial` | |
| Token / latency totals | each successful `trial` | sum `telemetry.response` |
| Per-metric running mean | each successful `scoring` | |
| Failure rates | trials / scorings | `failed / total so far` |
| Optimize step score | `step` event only | authoritative checkpoint |
| Overall mean (multi-metric) | partial OK | match server: mean of per-metric means (`fold_summary` in `jobs.py`) |

Display example: `8/12 examples · exact_match 0.75 (partial)` → drop “(partial)” when the step completes.

---

## Page layout (top → bottom)

**New job view**

1. `JobLauncher`
2. `JobManifest` (after submit)
3. Content by `kind`:
   - **run / evaluate:** trial list + live aggregate bar
   - **optimize:** `StepSection` per step
4. `JobSummary` when done

**Replay view** (`/jobs/{id}` or similar)

Same components; hydrate `EventStore` from `events` array; no SSE unless you want to re-stream a still-running job.

---

## Replicates

Datasets may run multiple replicates per example (`replicate` field). Options:

- **Simple:** one `TrialRow` per `trial_id` (current default).
- **Nicer:** group rows by `(inputs, reference)` and nest replicates inside one expander.

Start with one row per `trial_id`; refactor if fixtures show replicates matter.

---

## Suggested implementation order

1. **Scaffold SvelteKit** in `frontend/`; env var `PUBLIC_API_URL`.
2. **`EventStore` + types** mirroring envelope shapes (can codegen from OpenAPI at `/docs` if desired).
3. **`sseClient(jobId)`** — `fetch` + `ReadableStream` reader parsing `data: ` lines.
4. **`TrialRow`** + flat list for **run** (simplest path).
5. **`JobLauncher`** + manifest + evaluate (attach scorings, color encoding).
6. **`StepSection`** + optimize.
7. **Job list + replay** route.
8. Polish: 409 handling, error events, “proposing…” gap, localStorage for recent models.

---

## Key source files

| Topic | Path |
|-------|------|
| HTTP routes | `server/src/promptuna_server/main.py` |
| API models | `server/src/promptuna_server/schemas.py` |
| SSE bridge | `server/src/promptuna_server/jobs.py` |
| Event JSON | `src/promptuna/serialize.py` |
| On-disk jobs | `src/promptuna/jobs.py` |
| Optimize stream | `src/promptuna/optimize.py` |
| Thinking fields | `Thinking` in `src/promptuna/optimize.py` |
| API tests (examples) | `tests/promptuna_server/test_api.py` |
| Sample project | `samples/classify_sentiment/`, `tests/fixtures/test_project/` |

---

## Local dev

```bash
# terminal 1 — API on :6969
just server

# terminal 2 — frontend (once scaffolded)
cd frontend && npm run dev   # expect :5173
```

Integration tests patch `lmdk.complete`; for manual UI testing you need a configured model provider in `.env` (see project docs / `getting_started.py`).

---

## Out of scope for v1

- Editing prompts or projects in the browser.
- Starting more than one concurrent job (server forbids it).
- Static file serving from FastAPI (frontend is separate dev server or its own deploy).
- Authentication.

---

## Open questions (safe defaults chosen)

| Question | Decision |
|----------|----------|
| Separate run vs evaluate components? | **No** — one `TrialRow`; evaluate adds score chips. |
| Live vs end-only aggregates? | **Live partial** + final on `step` / job end. |
| When to show proposer template? | On **`proposal`**, before trials. |
| Primary metric for row color? | Worst `normalized` across metrics (document in UI if multiple). |

These can be revisited without backend changes.
