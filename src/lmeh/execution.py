"""Acts upon the data contracts.

Two entry points:

- :func:`run_experiment` blocks and returns a fully-populated :class:`RunResults`.
- :func:`stream_experiment` yields :class:`Trial` and :class:`Scoring` items
  as soon as they are ready, so callers can render progress or persist
  partial results and survive mid-run crashes.

Both share the same threaded engine. ``run_trial`` and ``score_metric`` are
total functions: they never raise, instead wrapping failures into
``FailedTrial`` / ``FailedScoring`` so the executor loop stays simple.
"""

from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor, as_completed

from lmdk import observe

from .datatypes import (
    Example,
    Experiment,
    FailedScoring,
    FailedTrial,
    LLMJudgeMetric,
    LMConfig,
    Metric,
    ProgrammaticMetric,
    RunInfo,
    RunResults,
    Score,
    Scoring,
    SuccessfulScoring,
    SuccessfulTrial,
    TargetFunction,
    Trial,
)


def run_experiment(
    experiment: Experiment,
    examples: list[Example],
    metrics: list[Metric],
    workers: int = 1,
) -> RunResults:
    """Run ``experiment`` over ``examples`` and score every ``metric``.

    Blocks until the whole run is done. For incremental consumption use
    :func:`stream_experiment`.
    """
    trials: list[Trial] = []
    scorings: list[Scoring] = []
    for item in stream_experiment(experiment, examples, metrics, workers=workers):
        if isinstance(item, (SuccessfulTrial, FailedTrial)):
            trials.append(item)
        else:
            scorings.append(item)
    return RunResults(
        experiment=experiment,
        run=RunInfo(),
        trials=trials,
        scorings=scorings,
    )


def stream_experiment(
    experiment: Experiment,
    examples: list[Example],
    metrics: list[Metric],
    workers: int = 1,
) -> Iterator[Trial | Scoring]:
    """Run the experiment, yielding trials and scorings as they land.

    Order is not deterministic: items arrive in completion order. A trial is
    always yielded before any of its scorings.

    The same thread pool is shared between target calls and LLM-judge
    scorers so workers stay saturated: scoring for an example starts as soon
    as its trial completes, without waiting for the rest of the examples.
    Programmatic scorers run inline on the consumer thread (they are
    cheap and not I/O-bound).
    """
    _validate_run(experiment=experiment, examples=examples, metrics=metrics)

    if not examples:
        return

    with ThreadPoolExecutor(max_workers=max(workers, 1)) as pool:
        trial_futures = _submit_trials(pool, experiment, examples)
        score_futures: list[Future[Scoring]] = []

        for fut in as_completed(trial_futures):
            trial = fut.result()  # run_trial never raises
            yield trial
            yield from _dispatch_scorings(pool, trial, metrics, score_futures)

        for fut in as_completed(score_futures):
            yield fut.result()  # score_metric never raises


def _submit_trials(
    pool: ThreadPoolExecutor,
    experiment: Experiment,
    examples: list[Example],
) -> dict[Future[Trial], Example]:
    """Submit one trial future per ``(example, replicate)`` pair."""
    return {
        pool.submit(
            run_trial,
            experiment.target,
            experiment.prompt_template,
            experiment.config,
            ex,
            replicate=r,
        ): ex
        for ex in examples
        for r in range(experiment.repeats)
    }


def _dispatch_scorings(
    pool: ThreadPoolExecutor,
    trial: Trial,
    metrics: list[Metric],
    score_futures: list[Future[Scoring]],
) -> Iterator[Scoring]:
    """Score ``trial`` against every metric.

    Programmatic metrics run inline and are yielded immediately (deterministic
    and cheap, so repeats are ignored). LLM-judge metrics are stochastic and
    I/O-bound: each replicate is offloaded to ``pool`` and appended to
    ``score_futures`` for the caller to drain later.
    """
    for metric in metrics:
        if isinstance(metric, ProgrammaticMetric):
            yield score_metric(trial, metric)
        else:
            for r in range(metric.repeats):
                score_futures.append(pool.submit(score_metric, trial, metric, replicate=r))


def run_trial(
    target: TargetFunction,
    prompt_template: str,
    config: LMConfig,
    example: Example,
    replicate: int = 0,
) -> Trial:
    """Execute ``target`` against one ``example``.

    ``example.inputs`` is unpacked as keyword arguments, so the target's
    parameter names must match the dict keys.

    Total function: any exception raised by the target is captured into a
    :class:`FailedTrial`. The target is what is under evaluation, so its
    failures are data, not bugs in the harness.
    """
    try:
        with observe() as obs:
            output = target(prompt_template=prompt_template, config=config, **example.inputs)

        assert len(obs.records) == 1, "The target function must call `complete` exactly one time"
        last = obs.records[-1] if obs.records else None
        return SuccessfulTrial(
            example=example,
            output=output,
            request=last.request if last else None,
            response=last.response if last else None,
            replicate=replicate,
        )
    except Exception as err:
        return FailedTrial(example=example, error=err, replicate=replicate)


def score_metric(trial: Trial, metric: Metric, replicate: int = 0) -> Scoring:
    """Apply ``metric`` to ``trial``.

    Total function: any exception (scorer crash, malformed judge output,
    out-of-scale value) is captured into a :class:`FailedScoring`.

    Failed trials short-circuit to a sentinel zero score so they still
    contribute to quality aggregates — the target is what is under
    evaluation.
    """
    if isinstance(trial, FailedTrial):
        return SuccessfulScoring(
            trial=trial,
            metric=metric,
            score=Score(raw=0, normalized=0.0, reason=f"trial failed: {trial.error!r}"),
            replicate=replicate,
        )

    try:
        if isinstance(metric, ProgrammaticMetric):
            raw_score = metric.scorer(trial.output, trial.example)
        else:  # LLMJudgeMetric
            raw_score = metric.scorer(
                trial.output,
                trial.example,
                metric,
                metric.config,
                trial.rendered_prompt,
            )
        metric.scale.validate(raw_score.raw)
        score = Score(
            raw=raw_score.raw,
            normalized=metric.scale.normalize(raw_score.raw),
            reason=raw_score.reason,
        )
        return SuccessfulScoring(trial=trial, metric=metric, score=score, replicate=replicate)
    except Exception as err:
        return FailedScoring(trial=trial, metric=metric, error=err, replicate=replicate)


def _validate_run(
    experiment: Experiment,
    examples: list[Example],
    metrics: list[Metric],
) -> None:
    """Preflight checks. Raise ``ValueError`` on the first problem found.

    Catches configuration mistakes cheaply, before any LM call is made.
    Does not perform any network I/O.
    """
    _validate_examples(examples)
    _validate_metrics(metrics)
    _validate_experiment(experiment)


def _validate_examples(examples: list[Example]) -> None:
    if not examples:
        raise ValueError("examples is empty")

    has_ref = [ex.reference is not None for ex in examples]
    if any(has_ref) and not all(has_ref):
        raise ValueError(
            "examples mix rows with and without `reference`; "
            "make this all-or-nothing so reference-dependent metrics are unambiguous"
        )


def _validate_metrics(metrics: list[Metric]) -> None:
    if not metrics:
        raise ValueError("no metrics provided")

    names = [m.name for m in metrics]
    if len(set(names)) != len(names):
        raise ValueError(f"metric names must be unique, got {names!r}")

    for m in metrics:
        if isinstance(m, LLMJudgeMetric):
            if not m.config.model:
                raise ValueError(f"metric {m.name!r}: config.model is empty")
            if not m.prompt_template:
                raise ValueError(f"metric {m.name!r}: prompt_template is empty")
            if m.repeats < 1:
                raise ValueError(f"metric {m.name!r}: repeats must be >= 1, got {m.repeats}")


def _validate_experiment(experiment: Experiment) -> None:
    if not experiment.prompt_template:
        raise ValueError("experiment.prompt_template is empty")
    cfg = experiment.config
    if not cfg.model:
        raise ValueError("experiment.config.model is empty")
    if experiment.repeats < 1:
        raise ValueError(f"experiment.repeats must be >= 1, got {experiment.repeats}")
