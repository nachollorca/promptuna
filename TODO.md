# Implementation TODO

This file tracks commit-sized tasks for the MVP described in `PLAN2.md`.
Each top-level section is intended to land as a single commit. Check items
off as you go. If something deviates from `PLAN2.md`, update the plan first.

Conventions:
- Package lives under `src/lmeh/` (already scaffolded).
- All scores normalized to `[0, 1]`.
- No streaming, single target call, single judge call (MVP).
- `lmdk` is a required runtime dependency; tests should mock it where possible.

---

## Commit 1 — Package skeleton

- [ ] Create empty modules under `src/lmeh/`:
  - [ ] `dataset.py`
  - [ ] `result.py`
  - [ ] `scale.py`
  - [ ] `scorer.py`
  - [ ] `metric.py`
  - [ ] `task.py`
- [ ] Ensure `src/lmeh/__init__.py` exists (leave exports for Commit 10).
- [ ] Mirror module layout under `tests/` with empty `test_*.py` placeholders.
- [ ] Confirm `pyproject.toml` declares `lmdk` as a runtime dependency.
- [ ] `pytest` runs (collects zero or trivial tests) cleanly.

## Commit 2 — Core data contracts

- [ ] `dataset.py`: implement `Example` (frozen dataclass) per §3.1.
- [ ] `result.py`:
  - [ ] `Score` (mutable; `normalized` may be set by `Metric.evaluate`).
  - [ ] `EvaluationRecord` carrying `score: Score | None` (not unpacked).
  - [ ] `MetricSummary`, `RunSummary`, `EvaluationResult`.
- [ ] Tests:
  - [ ] Construction + defaults for each type.
  - [ ] `Example` immutability.
  - [ ] Invariant from §3.3: `score is not None` XOR `error_stage is not None`
        (enforce via `__post_init__` or a constructor helper).
  - [ ] `target_repetition` / `judge_repetition` default to `0`.

## Commit 3 — Measurement scales

- [ ] `scale.py`: abstract `Scale` with `validate`, `normalize`, `format_for_prompt`.
- [ ] Implement `Binary`, `Ordinal`, `Discrete`, `Continuous` per §4.2.
- [ ] Constructor validation:
  - [ ] `Ordinal`: reject empty / single-element categories.
  - [ ] `Discrete`: require ≥2 evenly spaced values.
  - [ ] `Continuous`: reject `min >= max`.
- [ ] Tests per scale:
  - [ ] valid + invalid values
  - [ ] normalization at min, max, midpoint
  - [ ] `format_for_prompt()` returns a non-empty string mentioning the legal values
  - [ ] invalid constructor args raise
- [ ] No `lmdk` import in this module.

## Commit 4 — Scorer protocol + DeterministicScorer

- [ ] `scorer.py`:
  - [ ] `Scorer` ABC/Protocol per §5.1.
  - [ ] `DeterministicScorer` wrapping a user function (no default fn).
- [ ] Tests:
  - [ ] User function receives expected kwargs (`output`, `example`,
        `original_prompt`, `system_instruction`).
  - [ ] Returns `Score`.
  - [ ] Exceptions propagate (so `Task` can map to `error_stage="scorer"`).

## Commit 5 — Metric

- [ ] `metric.py`: `Metric` dataclass + `evaluate(...)` per §6.2.
- [ ] Distinguishable error types/signals for:
  - [ ] missing reference (when `requires_reference=True`)
  - [ ] scorer raised
  - [ ] scale validation failed
- [ ] On success: populate `Score.normalized` and return it.
- [ ] Tests with `DeterministicScorer` covering:
  - [ ] happy path on each scale
  - [ ] missing-reference path
  - [ ] scorer-raises path
  - [ ] invalid-raw-value path

## Commit 6 — Aggregation

- [ ] In `result.py` (or new `aggregation.py`):
  - [ ] `summarize_metrics(records) -> list[MetricSummary]`
  - [ ] `summarize_run(metric_summaries) -> RunSummary`
- [ ] Tests for `summarize_metrics`:
  - [ ] all-success, mixed, all-error groups
  - [ ] grouping across multiple metrics
  - [ ] `n_success + n_errors == len(group)`
  - [ ] all-error metric → `mean_score is None`
- [ ] Tests for `summarize_run`:
  - [ ] unweighted mean over non-empty metrics
  - [ ] empties excluded from mean, counted in `n_metrics_empty`
  - [ ] all-empty → `mean_score is None`
  - [ ] empty input → `mean_score is None`, both counts zero

## Commit 7 — Task orchestration (happy path)

- [ ] `task.py`: `Task` + `Task.run()` per §7.
- [ ] Per example:
  - [ ] call `target(**example.inputs)`
  - [ ] validate non-streaming `lmdk.CompletionResponse` with `response.request`
  - [ ] extract `output`, `original_prompt`, `system_instruction`
  - [ ] run each metric, build `EvaluationRecord`
- [ ] Return `EvaluationResult(records, metrics, run)` using the §8 helpers.
- [ ] Tests use a fake `CompletionResponse` (or minimal stub) — no live LLM.

## Commit 8 — Task error handling

- [ ] Map failures to `error_stage` per §7.4:
  - [ ] target raises / wrong type / streaming / missing `request`
        → one `error_stage="target"` record per metric, `output=None`,
        `score=None`.
  - [ ] missing required reference → `error_stage="metric"`.
  - [ ] scorer raises → `error_stage="scorer"`.
  - [ ] invalid raw score → `error_stage="validation"`.
  - [ ] unexpected metric error → `error_stage="metric"`.
- [ ] One metric failing must not block other metrics for the same example.
- [ ] One example failing must not stop the run.
- [ ] Tests for every bullet above.

## Commit 9 — StochasticScorer

- [ ] `StochasticScorer` in `scorer.py` using `lmdk.complete(..., output_schema=...)`.
- [ ] Structured schema with at least `value` and `reasoning`.
- [ ] Default prompt template incorporating: target `output`, `example.inputs`,
      optional `reference`/`metadata`, `original_prompt`, `system_instruction`,
      metric description, `scale_instructions`.
- [ ] Allow user-provided prompt template override.
- [ ] Single judge call (MVP); returns `Score(value=..., reasoning=...)` —
      metric does validation + normalization.
- [ ] Tests with mocked `lmdk.complete`:
  - [ ] schema is passed
  - [ ] response is decoded into `Score`
  - [ ] custom template is honored
  - [ ] judge errors propagate as exceptions

## Commit 10 — Public API + examples

- [ ] `src/lmeh/__init__.py` exports:
  - [ ] `Example`
  - [ ] `Score`, `EvaluationRecord`, `MetricSummary`, `RunSummary`, `EvaluationResult`
  - [ ] `Scale`, `Binary`, `Ordinal`, `Discrete`, `Continuous`
  - [ ] `Scorer`, `DeterministicScorer`, `StochasticScorer`
  - [ ] `Metric`
  - [ ] `Task`
  - [ ] `summarize_metrics`, `summarize_run` (if public)
- [ ] `examples/` minimal end-to-end with a deterministic metric:
  - [ ] tiny dataset
  - [ ] target returning a `CompletionResponse`
  - [ ] task execution
  - [ ] prints `MetricSummary` and `RunSummary`
- [ ] Optional second example for `StochasticScorer` (gated on env / opt-in).

## Commit 11 — Documentation and polish

- [ ] Update `README.md` covering:
  - [ ] target function requirements (non-streaming, `request` populated)
  - [ ] reference-free vs reference-based metrics
  - [ ] scale normalization guarantees ([0, 1])
  - [ ] error handling semantics + `error_stage` taxonomy
  - [ ] MVP limitations
  - [ ] reserved `target_repetition` / `judge_repetition` for future work
- [ ] Pass: type hints, public names, exceptions, docstrings on public API.

---

## Out of scope (do NOT implement in MVP)

Tracked here so they are not picked up accidentally; see PLAN2.md §10.

- repeated target/judge executions and repetition-aware aggregation
- variance / confidence intervals
- unbounded scales, empirical/batch normalization
- richer `Dataset` class, JSONL/CSV loaders
- metadata-grouped summaries, weighted run aggregation
- streaming responses, raw-value targets
- custom aggregation plugins
