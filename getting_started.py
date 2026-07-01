# ruff: noqa: E501
"""Getting started with promptuna.

Walk through a small but realistic example:

1. We have a task that we want to solve
2. We gather example data for the problem
3. We define the program (function) that uses an LM to solve that problem
4. We choose the LM and prompt that we want to test against the task
5. We define some metrics (programmatic or LLM as a judge) that measure how well or bad our program + LM + template solve the problem
6. We run the experiment: execute the program for all the examples and score all the metrics
7. Finally, we have an LM optimizer run the experiment, change the prompt template, and keep
   iterating to try and improve the metric scores over the examples
"""

import os

import logfire

from promptuna.evaluate import SuccessfulScoring, evaluate, score_metric
from promptuna.optimize import optimize
from promptuna.program import Experiment
from promptuna.projects import (
    resolve_examples,
    resolve_metrics,
    resolve_program,
    resolve_project_dir,
    resolve_prompt_template,
)
from promptuna.report import render_history, render_run
from promptuna.run import SuccessfulTrial, run_trial

# configure a simple exporter for the telemetry traces.
logfire.configure(
    token=os.environ["LOGFIRE_TOKEN"],
    service_name="ai-assist-demo",
    scrubbing=False,
    send_to_logfire=True,
)

# ## Dataset
# The task is product review sentiment analysis: given a customer review, predict whether the
# sentiment is positive, neutral, or negative, and produce a short justification for the call.
# Sentiment labels are always the English strings positive, neutral, or negative — even when
# the review itself is in another language.
#
# We start with the partial dataset (`data/partial.jsonl`): nine labelled reviews, mostly
# English plus one each in Spanish, German, French, and Italian. The `reference` field is the
# ground-truth label. Later we switch to `data/full.jsonl` for the optimization section.

project_dir = resolve_project_dir("classify_sentiment")
examples = resolve_examples(project_dir, "partial")

# ## Target Function
# Now we define the program — the thing we actually want to evaluate.
#
# Note that it is not just a thin wrapper around complete(): each program makes exactly one LM
# completion, wrapped in a deterministic scaffold — code before the call (input shaping,
# template rendering) and after (parsing, coercion, fallbacks). In production, users rarely hit
# the raw completion; they hit the completion plus its scaffold. The harness evaluates that
# full product.
#
# The function must adhere to the Program protocol: take its named inputs, the prompt template,
# and a model id, then return whatever the downstream scorers should consume. The harness unpacks
# Example.inputs as keyword arguments, so the parameter names must match the dict keys.
# The program lives in samples/classify_sentiment/programs.py (`v1`) — keeping it in a .py
# module (rather than defining it here) lets promptuna introspect the program source when
# optimizing. Its output schema is declared inside the function body.

classify_sentiment = resolve_program(project_dir, "v1")

# ## Knobs
# The two sweepable axes are the prompt template and the model. We load `prompts/english.jinja`,
# which asks the model to write the reason in the same language as the review.

prompt_template = resolve_prompt_template(project_dir, "english")
model = "mistral:mistral-small-latest"

# ## Trial
# With these ingredients, we can already run a trial: execute the program on one example with
# the model under test.

trial = run_trial(
    program=classify_sentiment,
    prompt_template=prompt_template,
    model=model,
    example=examples[0],
)

assert isinstance(trial, SuccessfulTrial)
print("Trial output:", trial.output)

# ## Metrics
# Now that our trial ran successfully, we can jump into quality measurements.
#
# ### Programmatic Metrics
# First, a simple deterministic check: does the predicted label match the ground truth? No LLM
# judge needed — a ProgrammaticMetric whose scorer follows the ProgrammaticScorer protocol is the
# right artifact. We declare the value space with an Ordinal scale. See
# samples/classify_sentiment/metrics.py for the full definition.

label_correctness, reason_language = resolve_metrics(
    project_dir, ["label_correctness", "reason_language"]
)

# Now we score the trial against the metric.

scoring = score_metric(trial=trial, metric=label_correctness)
assert isinstance(scoring, SuccessfulScoring)
print("Label correctness score:", scoring.score)

# ### LLM as Judge Metrics
# The label check is cheap and exact, but it says nothing about whether the justification is
# written in the same language as the review. The baseline prompt asks for that; we score it
# with an LLMJudgeMetric using the built-in default_llm_judge — the judge template is fixed,
# and the metric description tells it what to check. See samples/classify_sentiment/metrics.py
# as reason_language.

language_scoring = score_metric(trial=trial, metric=reason_language)
assert isinstance(language_scoring, SuccessfulScoring)
print("Reason language score:", language_scoring.score)

# ## Experiment
# Finally, we can wire it all together into an experiment: run classify_sentiment against every
# example and score both metrics on each output.

experiment = Experiment(
    program=classify_sentiment,
    prompt_template=prompt_template,
    model=model,
)

results = evaluate(
    experiment=experiment,
    examples=examples,
    metrics=[label_correctness, reason_language],
    workers=5,
)

# And a rendering utility renders the results.

report = render_run(results)
print(report)
print("---")

# ## Optimizer
#
# The harness can also search for a better prompt template. optimize() evaluates the experiment's
# current template as a baseline, then repeatedly asks a proposer model to rewrite the template
# from the full trajectory and re-scores each candidate. The archive keeps every checkpoint;
# OptimizationResult.best is the highest-scoring step (not necessarily the last).
#
# In our simple example, the baseline already scores well on the easy reviews in partial — and
# the vague prompt ("classify the sentiment, the labels are positive / neutral / negative")
# captures everything they need. There's nothing for the optimizer to win. To create some
# difficulty, we switch to the full dataset: reviews whose correct label depends on a labelling
# rubric the baseline prompt never states, including harder English cases and more multilingual
# reviews. The optimizer can only rewrite the prompt template, and it sees the weakest examples
# plus the scorer reasoning each step — so it can infer the rubric from the failures and encode
# it into a better prompt.
#
# What success looks like: the baseline prompt should now score noticeably below 1.0 on these
# (conflating logistics with the product, getting fooled by sarcasm, scattering the mixed cases,
# mistaking faint praise or backhanded compliments). A well-optimized prompt — one that spells out
# "focus on the product, watch for sarcasm/negation, reserve neutral for balanced or factual
# reviews, and read the overall verdict not just individual adjectives" — should recover most of
# that gap, though reaching a perfect score is harder now.

examples = resolve_examples(project_dir, "full")

optimization = optimize(
    experiment=experiment,
    examples=examples,
    metrics=[label_correctness, reason_language],
    proposer_model="vertex:gemini-3.5-flash",
    steps=4,
    workers=5,
)

baseline = optimization.steps[0]
best = optimization.best

print(f"Baseline score: {baseline.score:.4f}")
print(f"Best score:     {best.score:.4f} (step {optimization.steps.index(best)})")
print()
print("Best prompt template:")
print(best.prompt_template)

# This is the complete trajectory:

history = render_history(steps=optimization.steps)
print(history)
