"""Core data contracts shared across the harness.

Conceptual flow:

    Dataset -> Example
    Experiment = TargetFunction + prompt_template + LMConfig
    Trial = result of running one Experiment on one Example
    Metric = what we want to measure
    Scoring = one Metric applied to one Trial
    RunResults = all Trials and Scorings from one Experiment run

The harness keeps generation and scoring separate:
- Trials store target execution results.
- Scorings store metric results.

This module is organized in two halves:

1. Types the *user* defines or constructs when wiring up an evaluation
   (examples, targets, metrics, scales).
2. Types the *harness* produces and the user only reads (trials, scorings,
   run results).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from lmdk import CompletionRequest, CompletionResponse

# ---------------------------------------------------------------------------
# Inputs: things the user defines
# ---------------------------------------------------------------------------


@dataclass
class Example:
    """A single dataset row.

    Some metrics (e.g. "is length less than X") do not need a ground truth,
    hence ``reference`` is optional.

    Args:
        inputs: Arbitrary inputs the target needs — domain objects, raw text,
            whatever the production caller would pass. Unpacked as keyword
            arguments into the ``TargetFunction``; the keys must match the
            target's parameter names.
        reference: Expected output, if available.
    """

    inputs: dict[str, Any]
    reference: Any | None = None


Dataset = list[Example]
"""A dataset is a simple iterator of examples. In the future can contain metadata and splits."""


@dataclass
class LMConfig:
    """How to invoke a language model.

    Uniform across target, judge, and (future) optimizer call sites — none
    of them need anything more than this to dispatch a completion.

    Args:
        model: Identifier of the model to call.
        generation_kwargs: Extra arguments forwarded to the model call.

    Note:
        Structured-output schemas are intentionally *not* part of this
        config. The expected response shape is the caller's responsibility:
        a target function defines the schema it needs internally, and LLM
        judges build their own schema from the metric's scale. ``LMConfig``
        only carries what is genuinely shared across call sites.
    """

    model: str
    generation_kwargs: dict[str, Any] | None = None


class TargetFunction(Protocol):
    """The shape every function under evaluation must follow.

    A target is a function that achieves a goal using **exactly one** LM
    completion. It may run arbitrary deterministic code before the call to
    prepare the prompt (e.g. format inputs, render the template) and after
    the call to refine the model's response (e.g. parse, validate, repair).
    Chains of multiple LM calls are out of scope.

    The target may return whatever Python value is most natural for the
    downstream scorers — a bool, a string, a pydantic model, a tuple. The
    harness captures the underlying ``CompletionRequest`` /
    ``CompletionResponse`` automatically via ``lmdk.observe``, so the target
    does not need to surface them explicitly.
    """

    def __call__(  # noqa: D102
        self,
        *,
        prompt_template: str,
        config: LMConfig,
        **inputs: Any,
    ) -> Any: ...


@dataclass
class Experiment:
    """A named target plus the prompt and LM config under test.

    Args:
        name: Human-readable identifier for the experiment.
        target: The function under evaluation.
        prompt_template: Jinja-style template the target renders before
            calling the model.
        config: How to invoke the target model.
        repeats: How many times to run the target per example. LLMs are
            stochastic, so >1 yields a distribution of outputs per example
            instead of a point estimate. Each repeat becomes its own
            ``Trial`` tagged with ``replicate``.
    """

    name: str
    target: TargetFunction
    prompt_template: str
    config: LMConfig
    repeats: int = 1


# ---------------------------------------------------------------------------
# Scoring: scales, scores, scorers, metrics
# ---------------------------------------------------------------------------


class Scale(ABC):
    """Defines the set of values a score can take."""

    @abstractmethod
    def validate(self, value: int | float | str):
        """Raise an error if ``value`` does not belong to the scale."""
        ...

    @abstractmethod
    def normalize(self, value: int | float | str) -> float:
        """Map ``value`` to the ``[0, 1]`` interval."""
        ...


class Range(Scale):
    """Continuous numeric interval bounded by ``floor`` and ``ceiling``."""

    def __init__(self, floor: float, ceiling: float):
        if floor >= ceiling:
            raise ValueError("Range floor must be lower than ceiling")
        self.floor = floor
        self.ceiling = ceiling

    def validate(self, value: int | float | str):  # noqa: D102
        if isinstance(value, str):
            value = float(value)
        if not self.floor <= value <= self.ceiling:
            raise ValueError

    def normalize(self, value: int | float | str) -> float:  # noqa: D102
        if isinstance(value, str):
            value = float(value)
        return (value - self.floor) / (self.ceiling - self.floor)


class Ordinal(Scale):
    """Discrete (categorical or numerical) values ordered worst to best.

    Adjacent values are assumed equidistant when normalizing.

    Examples:
        ``["terrible", "OK", "fantastic"]`` or ``[1, 2, 3, 4, 5]``.

    Args:
        levels: Allowed values, sorted from worst to best.
    """

    def __init__(self, levels: list[str | int | float]):
        if len(levels) < 2:
            raise ValueError("Ordinal scale requires at least two levels")
        if len(set(levels)) != len(levels):
            raise ValueError("Ordinal scale levels must be unique")
        self.levels = levels

    def validate(self, value: int | float | str):  # noqa: D102
        if value not in self.levels:
            raise ValueError

    def normalize(self, value: int | float | str) -> float:  # noqa: D102
        return self.levels.index(value) / (len(self.levels) - 1)


@dataclass
class RawScore:
    """What a scorer produces, before the harness normalizes it.

    Scorers (programmatic or LLM-judge) only commit to the raw value and an
    optional rationale. The harness validates ``raw`` against the metric's
    scale and lifts a ``RawScore`` to a :class:`Score` by computing
    ``normalized``. This keeps the user-facing contract minimal and the
    downstream type (``Score.normalized``) honest (always present).

    Args:
        raw: Raw score in the metric's native scale.
        reason: Optional rationale (typically populated by LLM judges).
    """

    raw: int | float | str
    reason: str = ""


@dataclass
class Score:
    """The evaluation result for one example and one metric.

    Produced by the harness from a :class:`RawScore` plus the metric's
    scale. ``normalized`` is always populated — downstream aggregates rely
    on this invariant.

    Args:
        raw: Raw score in the metric's native scale.
        normalized: ``raw`` mapped to ``[0, 1]`` for cross-metric aggregation.
        reason: Optional rationale (typically populated by LLM judges).
    """

    raw: int | float | str
    normalized: float
    reason: str = ""


class ProgrammaticScorer(Protocol):
    """Signature of any programmatic (non-LLM) scoring function."""

    def __call__(  # noqa: D102
        self,
        output: Any,
        example: Example,
    ) -> RawScore: ...


default_judge_template = """
You will be acting as an expert judge to evaluate the result produced by an LLM-based function.
Your task is to assess and score how well the result meets the specified evaluation metric.

Here is the original prompt that was sent to the LLM:

<rendered_prompt>
{{RENDERED_PROMPT}}
</rendered_prompt>

Here is the result that was obtained from the LLM:

<output>
{{OUTPUT}}
</output>

{% if REFERENCE %}
This is the golden-standard expected reference:

<reference>
{{REFERENCE}}
</reference>
{% endif %}

And this is the specific metric you should use to evaluate the result:

<metric>
{{METRIC}}
</metric>

Now go ahead and score the result obtained by the LLM function for the given metric.""".strip()


class LLMJudgeScorer(Protocol):
    """Signature of any LLM-judge scoring function.

    Receives the rendered target prompt so the judge can reason about both
    the question and the model's answer. The judge's own prompt template
    lives on ``LLMJudgeMetric.prompt_template``; the judge's model and gen kwargs
    live on ``config``.
    """

    def __call__(  # noqa: D102
        self,
        output: Any,
        example: Example,
        metric: "LLMJudgeMetric",
        config: LMConfig,
        rendered_prompt: str,
    ) -> RawScore: ...


@dataclass
class ProgrammaticMetric:
    """A metric whose scorer is plain Python.

    Args:
        name: Unique identifier used in aggregates.
        description: Human-readable explanation of what is measured.
        scale: Scale used to validate and normalize raw scores.
        scorer: callable that produces the score for the given output.
    """

    name: str
    description: str
    scale: Scale
    scorer: ProgrammaticScorer


@dataclass
class LLMJudgeMetric:
    """A metric scored by an LLM judge.

    Args:
        name: Unique identifier used in aggregates.
        description: Human-readable explanation of what is measured. The
            default judge surfaces this to the judging model as ``METRIC``.
        scale: Scale used to validate and normalize raw scores.
        scorer: LLM-judge callable producing the score.
        config: How to invoke the judge model (model id, gen kwargs,
            optional output schema).
        prompt_template: Jinja-style template the judge renders before
            calling the model. Defaults to ``default_judge_template``.
        repeats: how many times to run the judge per trial. Captures judge
            stochasticity independently from target stochasticity. Each repeat
            becomes its own ``Scoring`` tagged with ``replicate``.
    """

    name: str
    description: str
    scale: Scale
    scorer: LLMJudgeScorer
    config: LMConfig
    prompt_template: str = default_judge_template
    repeats: int = 1


Metric = ProgrammaticMetric | LLMJudgeMetric
"""Tagged union of metric kinds.

Dispatch with ``isinstance`` — the two variants carry different state
(only ``LLMJudgeMetric`` needs a model and a judge template).
"""


# ---------------------------------------------------------------------------
# Outputs: things the harness produces (users read, rarely construct)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SuccessfulTrial:
    """A trial whose target executed without raising.

    ``output`` is whatever the target returned (free-form). ``request`` and
    ``response`` are captured automatically by the harness via
    ``lmdk.observe`` around the target call: they hold the final rendered
    prompt + kwargs and the raw LM response (latency, tokens, finish reason,
    etc.). They are ``None`` only if the target performed no completion.

    ``replicate`` is the 0-indexed repeat number; with
    ``Experiment.repeats=1`` (default) it is always ``0``.
    """

    example: Example
    output: Any
    request: CompletionRequest | None = None
    response: CompletionResponse | None = None
    replicate: int = 0

    @property
    def rendered_prompt(self) -> str:
        """The exact user prompt sent by the target.

        The harness assumes targets send exactly one user message.
        """
        assert self.request is not None, "Successful trial must carry a request"
        return self.request.prompt[0].content


@dataclass(frozen=True)
class FailedTrial:
    """A trial whose target raised. ``error`` is surfaced in aggregates."""

    example: Example
    error: Exception
    replicate: int = 0


Trial = SuccessfulTrial | FailedTrial
"""One execution of an Experiment against one Example.

A tagged union: pattern-match on ``SuccessfulTrial`` / ``FailedTrial`` (or
use ``isinstance``) to consume. The target is what's under evaluation, so
failed trials remain in ``RunResults.trials`` and count against the run.
"""


@dataclass(frozen=True)
class SuccessfulScoring:
    """A metric successfully applied to a trial, producing a ``Score``.

    Sentinel zero scores emitted for failed trials also live here: from the
    scorer's perspective a score was recorded. Callers that want to separate
    "real" scores from sentinel zeros can check ``isinstance(trial,
    FailedTrial)``.
    """

    trial: Trial
    metric: Metric
    score: Score
    replicate: int = 0


@dataclass(frozen=True)
class FailedScoring:
    """A scorer crashed (e.g. judge returned malformed output).

    Excluded from quality aggregates so a flaky judge does not bias results.
    """

    trial: Trial
    metric: Metric
    error: Exception
    replicate: int = 0


Scoring = SuccessfulScoring | FailedScoring
"""The result of applying one Metric to one Trial (tagged union)."""


@dataclass
class RunInfo:
    """Captures when an experiment was executed and against which code version."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: str | None = None  # can be a commit sha, a tag, ...


@dataclass(frozen=True)
class Aggregate:
    """Summary statistics over a set of values.

    Used wherever a single number would hide useful dispersion. ``sd`` is
    the sample standard deviation (``n-1`` denominator); it is ``0.0`` when
    ``n <= 1``, since dispersion is undefined with a single observation.
    """

    mean: float
    sd: float
    n: int


@dataclass
class RunResults:
    """Summary of one experiment run across a whole dataset.

    Results are stored along two parallel axes:

    - ``trials``: one entry per ``(example, target-replicate)``. Telemetry
      iterates this list so an example evaluated by N metrics is not
      overcounted.
    - ``scorings``: one entry per ``(trial, metric, judge-replicate)``.
      Failed trials contribute sentinel zero scores (the target is what's
      under evaluation); scorer errors contribute ``FailedScoring`` entries
      and are excluded from quality aggregates.

    Telemetry aggregates skip failed trials (those with no ``response``).
    """

    experiment: Experiment
    run: RunInfo
    trials: list[Trial]
    scorings: list[Scoring]

    # ------------------------------------------------------------------
    # Raw accessors
    # ------------------------------------------------------------------

    @property
    def successful_trials(self) -> list[SuccessfulTrial]:
        """Which trials executed without raising?"""
        return [t for t in self.trials if isinstance(t, SuccessfulTrial)]

    @property
    def successful_responses(self) -> list[CompletionResponse]:
        """What raw LM responses came back from successful trials?"""
        return [t.response for t in self.successful_trials if t.response is not None]

    @property
    def successful_scorings(self) -> list[SuccessfulScoring]:
        """Which scorings produced a score (no scorer crash)?"""
        return [r for r in self.scorings if isinstance(r, SuccessfulScoring)]

    # ------------------------------------------------------------------
    # Reliability
    # ------------------------------------------------------------------

    @property
    def failure_rate(self) -> float:
        """What fraction of target invocations crashed?"""
        return 1.0 - len(self.successful_trials) / len(self.trials) if self.trials else 0.0

    @property
    def scoring_failure_rate(self) -> float:
        """What fraction of scorings crashed in the scorer itself?"""
        if not self.scorings:
            return 0.0
        errors = sum(1 for r in self.scorings if isinstance(r, FailedScoring))
        return errors / len(self.scorings)

    # ------------------------------------------------------------------
    # Quality
    # ------------------------------------------------------------------

    @property
    def overall(self) -> Aggregate:
        """What's the headline score for the whole run, with dispersion?

        Aggregated over per-metric means so every metric carries equal
        weight regardless of how many replicates or examples it has.
        ``n`` is the number of metrics that produced at least one score.
        """
        return _aggregate(agg.mean for agg in self.per_metric().values())

    def per_example(self) -> dict[int, Aggregate]:
        """How does each example score, aggregated across metrics and replicates?

        Keyed by ``id(example)``. The mean pools every normalized score
        recorded for the example; useful to spot hard examples, but mixes
        heterogeneous metrics so interpret the dispersion with care.
        """
        scored = self.successful_scorings
        examples = {id(r.trial.example): r.trial.example for r in scored}
        return {
            ex_id: _aggregate(r.score.normalized for r in scored if r.trial.example is ex)
            for ex_id, ex in examples.items()
        }

    def per_metric(self) -> dict[str, Aggregate]:
        """How does each metric score across the dataset, aggregated across examples and replicates?

        Aggregated over per-example means so every example carries equal
        weight. The resulting ``sd`` measures **dataset heterogeneity** for
        the metric (how much examples differ), not measurement noise — see
        :meth:`replicate_noise` for that.
        """
        per_cell = self.per_example_and_metric()
        by_metric: dict[str, list[float]] = {}
        for (_ex_id, metric_name), agg in per_cell.items():
            by_metric.setdefault(metric_name, []).append(agg.mean)
        return {name: _aggregate(means) for name, means in by_metric.items()}

    def per_example_and_metric(self) -> dict[tuple[int, str], Aggregate]:
        """What's the score for each (example, metric) cell, aggregated across replicates only?

        The atomic unit of dispersion: ``sd`` here is pure measurement
        noise (target sampling x judge sampling) for one cell, with no
        dataset or metric mixing. Keyed by ``(id(example), metric.name)``.
        """
        cells: dict[tuple[int, str], list[float]] = {}
        for r in self.successful_scorings:
            key = (id(r.trial.example), r.metric.name)
            cells.setdefault(key, []).append(r.score.normalized)
        return {key: _aggregate(vals) for key, vals in cells.items()}

    def replicate_noise(self) -> dict[str, Aggregate]:
        """How noisy is each metric's measurement, on average?

        For each metric, takes the per-cell ``sd`` from
        :meth:`per_example_and_metric` and aggregates across examples. The
        resulting ``mean`` is the metric's **noise floor**; large values
        suggest bumping ``repeats`` or swapping the judge. Distinct from
        :meth:`per_metric` ``.sd``, which measures dataset heterogeneity.
        """
        per_cell = self.per_example_and_metric()
        by_metric: dict[str, list[float]] = {}
        for (_ex_id, metric_name), agg in per_cell.items():
            by_metric.setdefault(metric_name, []).append(agg.sd)
        return {name: _aggregate(sds) for name, sds in by_metric.items()}

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    @property
    def latency(self) -> float:
        """How much compute time did target calls consume in total, in seconds?

        Sum of per-trial latencies — equivalent to serial wall-clock,
        independent of how many workers actually ran the experiment.
        """
        return sum(r.latency for r in self.successful_responses)

    @property
    def output_tokens(self) -> int:
        """How many output tokens did the run produce in total?"""
        return sum(r.output_tokens for r in self.successful_responses)

    @property
    def speed(self) -> float:
        """What's the average target throughput in output tokens per second?"""
        lat = self.latency
        return self.output_tokens / lat if lat > 0 else 0.0


def _aggregate(values) -> Aggregate:
    """Return mean, sample SD and count for ``values``.

    Empty input yields ``Aggregate(0.0, 0.0, 0)``; single-element input
    yields ``sd=0.0``.
    """
    vals = list(values)
    n = len(vals)
    if n == 0:
        return Aggregate(mean=0.0, sd=0.0, n=0)
    m = sum(vals) / n
    if n == 1:
        return Aggregate(mean=m, sd=0.0, n=1)
    var = sum((v - m) ** 2 for v in vals) / (n - 1)
    return Aggregate(mean=m, sd=var**0.5, n=n)
