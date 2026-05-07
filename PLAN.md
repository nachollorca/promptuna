# Evaluation Harness Architecture and Implementation Plan

## 1. Objective, Scope, and MVP Boundaries

The goal of this package is to provide an evaluation harness for benchmarking functions that use Large Language Models (LLMs). The harness runs a target function over a dataset, evaluates each output with one or more metrics, records per-example/per-metric results, and computes normalized aggregate scores.

The MVP intentionally implements the simplest reliable path first:

- one target execution per example
- one scorer execution per metric
- one score per example/metric pair
- bounded metric scales only
- normalized scores in the `[0, 1]` range
- `lmdk` as a required runtime dependency
- target functions must return non-streaming `lmdk.CompletionResponse` objects with request metadata

All metric scores must be normalized to `[0, 1]` so that aggregation across metrics and tasks is meaningful. Therefore, every MVP scale must be bounded and capable of validating and normalizing raw score values.

Future versions may add unbounded scales, repeated target execution and repeated judging (to account for the stochastic nature of LMs), empirical/batch normalization, variance estimates, confidence intervals, richer dataset wrappers, and more advanced reporting. These are intentionally out of scope for the MVP unless explicitly noted as schema-preserving extension points.

---

## 2. Architecture Overview

The system is organized into six core modules:

1. **Core data contracts (`dataset.py`, `result.py`)**
   - Define examples, intermediate scores, final evaluation records, and aggregate summaries.
2. **Measurement scales (`scale.py`)**
   - Define the legal values a metric may return and how those values normalize to `[0, 1]`.
3. **Scorers (`scorer.py`)**
   - Extract raw metric values from outputs using either deterministic Python code or an LLM judge.
4. **Metrics (`metric.py`)**
   - Define what is being measured and compose a `Scale` with a `Scorer`.
5. **Task orchestration (`task.py`)**
   - Run target functions over examples, route outputs to metrics, capture failures, and produce records.
6. **Aggregation (`result.py` or `aggregation.py`)**
   - Compute metric-level summaries from evaluation records.

The core dependency flow should be:

```text
Example / Score / EvaluationRecord
          ↓
        Scale
          ↓
        Scorer
          ↓
        Metric
          ↓
        Task
          ↓
     Aggregation
```

Implementation should follow this dependency order so each layer can be tested before higher-level orchestration is introduced.

---

## 3. Core Data Contracts

### 3.1 Examples (`dataset.py`)

A dataset is an iterable of examples. Each `Example` separates what the target function can see from what only the evaluator can see.

```python
@dataclass(frozen=True)
class Example:
    id: str
    inputs: Mapping[str, Any]
    reference: Any | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

Fields:

- `id`: Stable identifier for debugging, tracking, grouping, and aggregation.
- `inputs`: Keyword arguments passed to the target function via `target(**example.inputs)`.
- `reference`: Optional evaluator-only expected output. This is used by reference-based metrics but must never be passed to the target function.
- `metadata`: Optional evaluator/reporting metadata. This is not passed to the target function by default.

For the first version, `Dataset` can simply mean `Iterable[Example]`. A named dataset wrapper can be added later if dataset-level metadata such as `name`, `split`, or `version` becomes necessary.

JSONL maps naturally to this shape:

```json
{"id": "qa-001", "inputs": {"question": "What is the capital of France?"}, "reference": "Paris", "metadata": {"topic": "geography"}}
```

### 3.2 Intermediate Score (`result.py`)

`Score` is the intermediate score returned by a scorer and then validated/normalized by a metric.

The MVP commits to bounded scales (§1, §4), and §4.2 enumerates exactly four shapes of legal raw values: `bool` (Binary), `str` (Binary/Ordinal categorical labels), `int` (Discrete), and `float` (Continuous). We capture this directly in the type system as a single alias used by both `Score` and `Scale`:

```python
ScoreValue = bool | int | float | str
```

Widening this alias is the explicit extension point for future unbounded or structured scales; until then, scorers cannot silently return arbitrary objects.

```python
@dataclass
class Score:
    value: ScoreValue
    reasoning: str | None = None
    normalized: float | None = None
```

Fields:

- `value`: Raw score value returned by the scorer. Must be a member of `ScoreValue`; the metric's `Scale` decides which subset is actually legal.
- `reasoning`: Optional explanation, commonly from an LLM judge but also allowed for deterministic scorers.
- `normalized`: `[0, 1]` normalized score. Scorers should normally leave this as `None`; `Metric.evaluate` populates it after scale validation.

The MVP may mutate the returned `Score` or return a new populated `Score`, but the behavior should be consistent and documented in code.

### 3.3 Evaluation Records (`result.py`)

The MVP needs a stable per-example/per-metric record shape so debugging, aggregation, and future repetition support can be added without changing the public contract.

`EvaluationRecord` carries the full `Score` object rather than unpacking its fields. This preserves the cohesion of `Score`: raw value, reasoning, and normalized value travel together by definition, and serializing a single nested object is simpler than keeping three parallel fields in sync.

Failure information is similarly bundled into a small `EvaluationError` dataclass rather than spread across parallel optional fields on the record. This mirrors the treatment of `Score`, collapses the success/failure invariant to a single `error is None` check, and gives later debugging fields (exception type, traceback, originating cause) an obvious home without widening `EvaluationRecord`.

`EvaluationError` is intentionally **not** an `Exception` subclass. Records are persisted data (JSONL, aggregation, cross-run diffs), not control-flow signals; exception machinery (`__traceback__`, `__cause__`, `*args`-based `__init__`) does not serialize cleanly and conflicts with `@dataclass(frozen=True)`. The task layer catches real exceptions at the failure site and converts them into `EvaluationError` values.

```python
@dataclass(frozen=True)
class EvaluationError:
    stage: Literal["target", "scorer", "validation", "metric"]
    message: str
    # Reserved extension points, out of MVP scope:
    # exception_type: str | None = None
    # traceback: str | None = None

@dataclass
class EvaluationRecord:
    example_id: str
    metric_name: str

    output: Any | None = None
    score: Score | None = None
    error: EvaluationError | None = None

    example_metadata: Mapping[str, Any] = field(default_factory=dict)
```

Fields:

- `example_id`: ID of the evaluated example.
- `metric_name`: Stable metric name used for grouping and aggregation.
- `output`: Extracted `CompletionResponse.output` from the target, if target execution succeeded.
- `score`: The `Score` produced by the metric for this (example, metric) cell. `None` if the record errored before a score could be produced. When present, `score.normalized` is guaranteed to be a valid `[0, 1]` float.
- `error`: An `EvaluationError` describing the failure, or `None` if the record succeeded.
- `example_metadata`: Copied from `Example.metadata` for grouping and reporting.

Invariant: exactly one of `score` and `error` is non-`None`. There is no partial state.

Error stages (`EvaluationError.stage`):

- `"target"`: Target function raised, returned the wrong type, returned a streaming response, or returned a `CompletionResponse` without request metadata.
- `"scorer"`: Deterministic scorer or stochastic judge execution failed.
- `"validation"`: Scorer returned a value that does not belong to the metric scale.
- `"metric"`: Metric configuration/data issue, such as a missing required reference.

For failed records, `score` is `None` and `error` is populated. The harness should continue evaluating remaining examples and metrics after record-level failures.

### 3.4 Aggregation Layers and Summary Types (`result.py` or `aggregation.py`)

Aggregation in this harness happens along **two explicit reduction axes** on top of the per-cell record. Each layer has its own type, and the type name itself signals the scope of the number it carries. This makes it unambiguous, at the call site, which aggregation a given value represents.

| Layer | Type               | Scope                          | Reduces over       | MVP behavior                          |
| ----- | ------------------ | ------------------------------ | ------------------ | ------------------------------------- |
| 0     | `EvaluationRecord` | one (example, metric) cell     | nothing            | holds one `Score`                     |
| 1     | `MetricSummary`    | one metric, full dataset       | examples (records) | mean of `record.score.normalized`     |
| 2     | `RunSummary`       | one run, full dataset          | metrics            | mean of `MetricSummary.mean_score`    |

All summary types use the field name `mean_score` for the headline `[0, 1]` value. Because the surrounding type already encodes the scope (`MetricSummary.mean_score` vs `RunSummary.mean_score`), no axis-specific prefix is needed.

```python
@dataclass
class MetricSummary:
    metric_name: str
    mean_score: float | None   # mean over examples, for this metric
    n_success: int
    n_errors: int

@dataclass
class RunSummary:
    mean_score: float | None   # mean over metrics, for this run
    n_metrics: int             # metrics with at least one successful record
    n_metrics_empty: int       # metrics with no successful records
```

Rules:

- Errored records are excluded from `MetricSummary.mean_score` but counted in `n_errors`.
- A metric with no successful records has `MetricSummary.mean_score = None` and contributes to `RunSummary.n_metrics_empty`, not to `RunSummary.mean_score`.
- `RunSummary.mean_score` is the unweighted arithmetic mean of the non-`None` `MetricSummary.mean_score` values. If every metric is empty, it is `None`.
- Weighted run-level aggregation (e.g. by `n_success`) is deferred to future work.

The task return value bundles all three layers:

```python
@dataclass
class EvaluationResult:
    records: list[EvaluationRecord]   # layer 0
    metrics: list[MetricSummary]      # layer 1
    run: RunSummary                   # layer 2
```

The `metrics` and `run` fields are caches of the canonical pure functions `summarize_metrics(records)` and `summarize_run(metric_summaries)` defined in §8. Callers who want custom aggregations should re-run those functions (or their own) over `records`.

---

## 4. Measurement Scales (`scale.py`)

Scales define which raw values are legal for a metric and how legal values normalize to `[0, 1]`. This module uses the Strategy pattern: a base `Scale` protocol plus concrete scale implementations.

### 4.1 Base Protocol

```python
class Scale(ABC):
    @abstractmethod
    def validate(self, value: object) -> bool: ...

    @abstractmethod
    def normalize(self, value: ScoreValue) -> float: ...

    @abstractmethod
    def format_for_prompt(self) -> str: ...
```

Expected behavior:

- `validate(value)` returns whether `value` belongs to the scale. It takes `object` (not `Any`) because its job is to vet untrusted input; callers must check the return value before treating `value` as a legal score.
- `normalize(value)` converts a valid raw value into a float in `[0, 1]`. Its parameter is typed as `ScoreValue` because, by the evaluation flow in §6.2, `normalize` only ever runs after `validate` has returned `True`.
- `format_for_prompt()` returns judge-facing instructions that describe valid values.

`normalize` may assume the value has already been validated, but defensive implementations are acceptable.

### 4.2 Concrete Scale ImplementationsIf w

#### `Binary(Scale)`

A variable that can take only one of two mutually exclusive values.

Examples:

- `True` / `False`
- `"pass"` / `"fail"`
- `"yes"` / `"no"`

Normalization maps the negative value to `0.0` and the positive value to `1.0`.

#### `Ordinal(Scale)`

A categorical scale with a clear order but unknown or non-uniform distance between categories.

Example:

```python
Ordinal(["Terrible", "Acceptable", "Perfect"])
```

Normalization:

```python
index / (len(categories) - 1)
```

#### `Discrete(Scale)`

A bounded set of fixed, evenly spaced numerical values.

Example:

```python
Discrete([1, 2, 3, 4, 5])
```

Normalization:

```python
(value - min_value) / (max_value - min_value)
```

#### `Continuous(Scale)`

A bounded numerical range with meaningful distances.

Example:

```python
Continuous(min=0.0, max=1.0)
```

Normalization:

```python
(value - min_value) / (max_value - min_value)
```

---

## 5. Scorers (`scorer.py`)

Scorers define how a raw score value is extracted from a target output. They do not define what the metric means and should not perform final normalization. They return `Score` objects that are later validated and normalized by `Metric`.

### 5.1 Base Scorer Protocol

```python
class Scorer(Protocol):
    def score(
        self,
        *,
        output: Any,
        example: Example,
        original_prompt: Sequence[Message] | None = None,
        system_instruction: str | None = None,
        scale_instructions: str | None = None,
    ) -> Score: ...
```

The scorer receives:

- `output`: Target function output extracted from `CompletionResponse.output`. Typed as `Any` deliberately, mirroring `lmdk.CompletionResponse.output`, which itself varies between a content string, a parsed `BaseModel`, a list of models, or an extracted scalar depending on whether and how a structured output schema was used. Narrowing this type in the harness would misrepresent lmdk's contract.
- `example`: Full evaluator-side example, including inputs, reference, and metadata.
- `original_prompt`: Prompt/messages sent by the target to the model, when available.
- `system_instruction`: System-level instruction sent by the target, when available.
- `scale_instructions`: Prompt-ready description of valid score values.

### 5.2 Deterministic Scorer

`DeterministicScorer` wraps an explicit Python function. There is no default scoring function; users must provide one.

MVP scoring function protocol:

```python
def scoring_fn(
    *,
    output: Any,
    example: Example,
    original_prompt: Sequence[Message] | None = None,
    system_instruction: str | None = None,
) -> Score: ...
```

The wrapper adapts this function to the common `Scorer` protocol. Deterministic scorers may use `example.inputs`, `example.reference`, and `example.metadata` as needed.

### 5.3 Stochastic Scorer

`StochasticScorer` uses an LLM judge through `lmdk.complete`.

Requirements:

- It must call `lmdk.complete(..., output_schema=...)` rather than parse free-form text.
- The structured output schema must contain at least:
  - `value`
  - `reasoning`
- It should provide a default judge prompt template.
- Users may override the prompt template.
- It performs a single judge call in the MVP.

The default prompt should be able to incorporate:

- target `output`
- `example.inputs`
- `example.reference`, if present
- `example.metadata`, if useful
- `original_prompt`
- `system_instruction`
- metric description, supplied by the metric if needed
- `scale_instructions`

The scorer returns `Score(value=..., reasoning=...)`. The metric validates `value` against the scale and computes `normalized`.

---

## 6. Metrics (`metric.py`)

A metric defines what is being measured. It composes a `Scale` with a `Scorer` and owns validation, normalization, and reference-requirement checks.

```python
@dataclass(frozen=True)
class Metric:
    name: str
    description: str
    scale: Scale
    scorer: Scorer
    requires_reference: bool = False
```

Fields:

- `name`: Stable identifier used in result records and aggregation.
- `description`: Human-readable description of what the metric measures.
- `scale`: Defines valid raw values and normalization.
- `scorer`: Extracts the raw score value.
- `requires_reference`: Whether `example.reference` is required.

### 6.1 Measurement Paradigms

Reference-free metrics evaluate the output on its own merits.

Examples:

- tone
- fluency
- concision
- toxicity
- hallucination risk when no ground truth is available

Reference-based metrics compare the output to an expected answer or ground truth.

Examples:

- exact match
- recall
- semantic similarity
- factual correctness against a reference

### 6.2 Evaluation Flow

`Metric.evaluate(...)` should perform the following steps:

1. If `requires_reference=True`, check that `example.reference` is available.
2. Call `scorer.score(...)`, passing:
   - `output`
   - `example`
   - `original_prompt`
   - `system_instruction`
   - `scale.format_for_prompt()`
3. Receive a `Score` with a raw `value`.
4. Validate `score.value` with `scale.validate(score.value)`.
5. Normalize with `scale.normalize(score.value)`.
6. Populate `score.normalized`.
7. Return the populated `Score`.

Metric-level errors should be distinguishable from scorer execution errors and validation errors so `Task` can produce precise `EvaluationError.stage` values.

---

## 7. Task Orchestration (`task.py`)

`Task` is the execution runner. It binds a dataset, a target function, and metrics into a full evaluation loop.

### 7.1 Task Inputs

A task needs:

- a dataset: `Iterable[Example]`
- a target function: called as `target(**example.inputs)`
- one or more metrics: `Sequence[Metric]`

For the MVP, the target function must return a non-streaming `lmdk.CompletionResponse` and nothing else.

The target function must call `lmdk.core.complete(..., return_request=True)` or otherwise return a `CompletionResponse` with populated request metadata. This is required so evaluators can inspect the original prompt and system instruction.

### 7.2 Execution Lifecycle

For each example:

1. Execute the target function once:

   ```python
   response = target(**example.inputs)
   ```

2. Validate the target response:
   - must be a non-streaming `lmdk.CompletionResponse`
   - must include `response.request`

3. Extract target context:
   - `output = response.output`
   - `original_prompt = response.request.prompt`
   - `system_instruction = response.request.system_instruction`

4. For each metric, call:

   ```python
   metric.evaluate(
       output=output,
       example=example,
       original_prompt=original_prompt,
       system_instruction=system_instruction,
   )
   ```

5. Convert the resulting `Score` into an `EvaluationRecord`.

6. If an error occurs, create an errored `EvaluationRecord` rather than stopping the full evaluation run.

### 7.3 Target Failures

If target execution fails for an example, the task should still create one errored record per metric so summaries report the correct number of metric-level failures.

For target failures:

- `error=EvaluationError(stage="target", message=...)`
- `output=None`
- `score=None`

### 7.4 Metric and Scorer Failures

If scoring or metric evaluation fails for one metric, other metrics for the same example should still run when possible.

Failure mapping (the task constructs `EvaluationError(stage=..., message=...)` accordingly):

- missing required reference → `stage="metric"`
- scorer function or LLM judge raises → `stage="scorer"`
- invalid raw score value → `stage="validation"`
- unexpected metric-layer issue → `stage="metric"`

### 7.5 Task Return Value

The task should return raw records along with both summary layers:

```python
metric_summaries = summarize_metrics(records)
run_summary = summarize_run(metric_summaries)
return EvaluationResult(
    records=records,
    metrics=metric_summaries,
    run=run_summary,
)
```

This keeps debugging data (layer 1), per-metric reporting (layer 2), and the single-number run headline (layer 3) together, while still allowing callers to recompute custom aggregations directly from `records`.

---

## 8. Aggregation

Aggregation operates on `EvaluationRecord` objects (and on the layer-1 outputs) and should not depend on target functions, datasets, metrics, or scorers. It is exposed as two pure functions, one per reduction axis above the per-cell record:

### 8.1 Layer 1 — `summarize_metrics`: reduce examples per metric

Groups records by `metric_name` and computes, per metric:

- `n_success`: number of records with `score is not None` and `error is None`
- `n_errors`: number of records with `error is not None`
- `mean_score`: arithmetic mean of `record.score.normalized` over successful records, or `None` if there are no successes

By the §3.3 invariant, `n_success + n_errors` equals the number of records for that metric.

```python
def summarize_metrics(records: Sequence[EvaluationRecord]) -> list[MetricSummary]:
    summaries = []
    for metric_name, group in group_by_metric(records):
        successes = [r.score.normalized for r in group if r.error is None]
        errors = [r for r in group if r.error is not None]
        summaries.append(
            MetricSummary(
                metric_name=metric_name,
                mean_score=mean(successes) if successes else None,
                n_success=len(successes),
                n_errors=len(errors),
            )
        )
    return summaries
```

### 8.2 Layer 2 — `summarize_run`: reduce metrics per run

Reduces a list of `MetricSummary` into a single `RunSummary`. Empty metrics (those with `mean_score is None`) are excluded from the mean but counted separately.

```python
def summarize_run(metric_summaries: Sequence[MetricSummary]) -> RunSummary:
    non_empty = [m.mean_score for m in metric_summaries if m.mean_score is not None]
    return RunSummary(
        mean_score=mean(non_empty) if non_empty else None,
        n_metrics=len(non_empty),
        n_metrics_empty=len(metric_summaries) - len(non_empty),
    )
```

### 8.3 Future extensions

Later aggregation can add variance, confidence intervals, per-metadata breakdowns, and weighted run aggregation. Repetition-aware reductions are also possible but are expected to be a schema change (see §10), not a drop-in extension.

---

## 9. Ordered Implementation Plan

The step-by-step, commit-sized implementation checklist lives in `TODO.md`.
This document is the design reference; `TODO.md` is the working compass.
When behavior described here changes, update this file first, then adjust
`TODO.md` to match.

---

## 10. Future Work

The following should remain out of the MVP unless needed by immediate users:

- target repetitions greater than one
- judge repetitions greater than one
- preserving multiple judge scores per output
- variance and confidence interval reporting
- repetition-aware aggregation
- unbounded scales
- empirical min/max normalization
- batch normalization after a suite completes
- richer dataset class with `name`, `split`, and `version`
- dataset loading helpers for JSONL/CSV/etc.
- metadata-based grouped summaries
- streaming target responses
- target functions that return raw values instead of `CompletionResponse`
- custom aggregation plugins

Repeated target/judge execution is deferred. Adding it will likely require evolving `EvaluationRecord.score` to hold multiple observations plus a reduction policy (and probably variance/CI fields on the summaries), and is expected to be a schema change rather than a drop-in extension.
