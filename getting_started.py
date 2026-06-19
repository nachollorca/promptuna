# ruff: noqa: E501, D103
"""Getting started with promptuna.

Walk through a small but realistic example:

1. We have a task that we want to solve
2. We gather example data for the problem
3. We define the program (function) that uses an LM to solve that problem
4. We choose the LM and prompt that we want to test against the task
5. We define some metrics (programmatic or LLM as a judge) that measure how well or
   bad our program + LM + template solve the problem
6. We run the experiment: execute the program for all the examples and score all the metrics
7. Finally, we have an LM optimizer run the experiment, change the prompt template, and keep
   iterating to try and improve the metric scores over the examples
"""

import os
import re
from typing import Literal

import logfire
from lmdk import complete, render_template
from pydantic import BaseModel, Field

from promptuna.evaluate import (
    LLMJudgeMetric,
    Ordinal,
    ProgrammaticMetric,
    RawScore,
    default_llm_judge,
    run_experiment,
    score_metric,
)
from promptuna.optimize import optimize, render_history
from promptuna.program import Example, Experiment, LMConfig
from promptuna.report import render_run
from promptuna.run import run_trial

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
#
# We start with a tiny labelled dataset. The `reference` is the ground-truth label.

examples = [
    Example(
        inputs={
            "review": "Battery lasts two full days and the screen is gorgeous. Best phone I've owned."
        },
        reference="positive",
    ),
    Example(
        inputs={
            "review": "It works. Setup was fine, nothing surprising, nothing to complain about."
        },
        reference="positive",
    ),
    Example(
        inputs={"review": "Stopped charging after three weeks. Support never replied. Avoid."},
        reference="negative",
    ),
    Example(
        inputs={
            "review": "    Camera   is   AMAZING!!!   colors pop, low-light is great.\n\n\nHighly recommend."
        },
        reference="positive",
    ),
    Example(
        inputs={
            "review": "Arrived on time. Packaging was a bit beaten up but the product itself looks ok."
        },
        reference="neutral",
    ),
]

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
# and an LM config, then return whatever the downstream scorers should consume. The harness unpacks
# Example.inputs as keyword arguments, so the parameter names must match the dict keys.

ALLOWED_LABELS = {"positive", "neutral", "negative"}
MAX_REVIEW_CHARS = 500


def classify_sentiment(review: str, prompt_template: str, config: LMConfig) -> dict:
    # Scaffold (pre): normalise whitespace and cap length
    cleaned = re.sub(r"\s+", " ", review).strip()
    if len(cleaned) > MAX_REVIEW_CHARS:
        cleaned = cleaned[:MAX_REVIEW_CHARS] + "…"

    # Define the output schema expected from the model
    class Output(BaseModel):
        sentiment: Literal["positive", "neutral", "negative"]
        reason: str = Field(description="One short sentence justifying the sentiment label.")

    # Call the model with lmdk.complete
    prompt = render_template(template=prompt_template, REVIEW=cleaned)
    response = complete(
        model=config.model,
        generation_kwargs=config.generation_kwargs,
        prompt=prompt,
        output_schema=Output,
    )

    # Scaffold (post): normalize the label and fall back to "neutral"
    label = (response.output.sentiment or "").strip().lower()
    if label not in ALLOWED_LABELS:
        label = "neutral"

    # Return arbitrary format that will be downstream consumed
    return {"sentiment": label, "reason": response.output.reason.strip()}


# ## Knobs
# Now, lets define the moving parts under test. The two sweepable axes are the prompt template
# and the LM config (model, generation kwargs).

prompt_template = """Your task is to classify the sentiment of this product review:

{{ REVIEW }}

The possible labels are 'positive', 'neutral' and 'negative'
"""

config = LMConfig(
    model="mistral:mistral-small-latest",
    generation_kwargs={"temperature": 0.1},
)

# ## Trial
# With these ingredients, we can already run a trial: execute the program on one example with
# the config under test.

trial = run_trial(
    program=classify_sentiment,
    prompt_template=prompt_template,
    config=config,
    example=examples[0],
)

print("Trial output:", trial.output)

# ## Metrics
# Now that our trial ran successfully, we can jump into quality measurements.
#
# ### Programmatic Metrics
# First, a simple deterministic check: does the predicted label match the ground truth? No LLM
# judge needed — a ProgrammaticMetric whose scorer follows the ProgrammaticScorer protocol is the
# right artifact. We declare the value space with an Ordinal scale.


def label_match(output: dict, example: Example) -> RawScore:
    predicted = output["sentiment"]
    expected = example.reference
    if predicted == expected:
        return RawScore(raw=True, reason=f"Predicted '{predicted}' matches reference.")
    return RawScore(
        raw=False,
        reason=f"Predicted '{predicted}', expected '{expected}'.",
    )


label_correctness = ProgrammaticMetric(
    name="label_correctness",
    description="Whether the predicted sentiment label matches the ground-truth label.",
    scale=Ordinal(levels=[False, True]),
    scorer=label_match,
)

# Now we score the trial against the metric.

scoring = score_metric(trial=trial, metric=label_correctness)
print("Label correctness score:", scoring.score)

# ### LLM as Judge Metrics
# The label check is cheap and exact, but it tells us nothing about the reason the model produced
# — and a good sentiment classifier should be able to justify its call. That's a subjective,
# open-ended judgement with no ground truth, which is exactly where an LLM judge earns its keep.
#
# We define an LLMJudgeMetric that grades the quality of the justification. It carries its own
# LMConfig and judge prompt template. We use the built-in default_llm_judge, which feeds the judge
# the rendered prompt, the program's output, the reference, and the metric description.

reason_quality = LLMJudgeMetric(
    name="reason_quality",
    description="Rates how well the 'reason' field justifies the predicted sentiment label given the original review.",
    scale=Ordinal(levels=["poor", "good"]),
    scorer=default_llm_judge,
    config=LMConfig(
        model="mistral:mistral-medium-latest",
        generation_kwargs={"temperature": 0.1},
    ),
)

# Let's see what the judge thinks about the system output on our first trial.

judge_scoring = score_metric(trial=trial, metric=reason_quality)
print("Reason quality score:", judge_scoring.score)

# ## Experiment
# Finally, we can wire it all together into an experiment: run classify_sentiment against every
# example and score both metrics on each output.

experiment = Experiment(
    program=classify_sentiment,
    prompt_template=prompt_template,
    config=config,
)

results = run_experiment(
    experiment=experiment,
    examples=examples,
    metrics=[label_correctness, reason_quality],
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
# In our simple example, the baseline already scores well — the five reviews above are easy, and
# the vague prompt ("classify the sentiment, the labels are positive / neutral / negative")
# captures everything they need. There's nothing for the optimizer to win. To create some
# difficulty, we extend the dataset with reviews whose correct label depends on a labelling rubric
# the baseline prompt never states. The optimizer can only rewrite the prompt template, and it
# sees the weakest examples plus the judge's reasoning each step — so it can infer the rubric from
# the failures and encode it into a better prompt.
#
# What success looks like: the baseline prompt should now score noticeably below 1.0 on these
# (conflating logistics with the product, getting fooled by sarcasm, scattering the mixed cases,
# mistaking faint praise or backhanded compliments). A well-optimized prompt — one that spells out
# "focus on the product, watch for sarcasm/negation, reserve neutral for balanced or factual
# reviews, and read the overall verdict not just individual adjectives" — should recover most of
# that gap, though reaching a perfect score is harder now.

ambiguous_examples = [
    # Aspect scoping: the PRODUCT is great, only shipping/packaging is bad.
    Example(
        inputs={
            "review": "Took almost a month to arrive and the box was crushed in transit, but the espresso machine itself is superb — rich crema every single morning."
        },
        reference="positive",
    ),
    # Aspect scoping: shipping/service is great, the PRODUCT is the letdown.
    Example(
        inputs={
            "review": "Lightning-fast shipping and the courier was lovely, but the earbuds crackle in one ear and the battery dies within an hour. The product is a letdown."
        },
        reference="negative",
    ),
    # Sarcasm: every surface word is positive, the intent is the opposite.
    Example(
        inputs={
            "review": "Oh brilliant, another 'waterproof' watch that died the first time it saw rain. Worth every penny, truly."
        },
        reference="negative",
    ),
    # Negation: positive-sounding vocabulary, flipped by 'not'.
    Example(
        inputs={
            "review": "Don't believe the glowing reviews — this is not the durable, premium knife they promise. It chipped on day two."
        },
        reference="negative",
    ),
    # Neutral = genuinely mixed, real pros and cons that roughly balance.
    Example(
        inputs={
            "review": "The fabric is soft and the colour is lovely, but it shrank in the first wash and the stitching is already loose. Hard to call it good or bad."
        },
        reference="neutral",
    ),
    # Neutral = purely factual, no evaluation at all.
    Example(
        inputs={
            "review": "It's a 2-metre USB-C cable, black, exactly as pictured. Bought it to replace a lost one."
        },
        reference="neutral",
    ),
    # Counter-case: a minor gripe must NOT tip a clearly positive review into 'neutral'.
    Example(
        inputs={
            "review": "Runs a touch warm under heavy load, but honestly this laptop is phenomenal — fast, silent, and the display is stunning. No regrets."
        },
        reference="positive",
    ),
    # Mixed but lopsided: real pros exist, yet the reviewer still recommends against buying.
    Example(
        inputs={
            "review": "Looks premium and the unboxing was nice, but the firmware is buggy, key features are missing, and I already filed a return."
        },
        reference="negative",
    ),
    # Mixed but lopsided: setup friction must NOT erase a clearly positive verdict.
    Example(
        inputs={
            "review": "Setup took longer than expected and the manual is confusing, yet once running it's quiet, fast, and exactly what I needed."
        },
        reference="positive",
    ),
    # Faint praise: lukewarm approval with no real enthusiasm — neutral, not positive.
    Example(
        inputs={
            "review": "For a cheap desk fan it moves air. Nothing remarkable, nothing terrible — just adequate."
        },
        reference="neutral",
    ),
    # Backhanded compliment: polite wording, negative verdict about the product.
    Example(
        inputs={
            "review": "I suppose it's impressive that it lasted a whole week before the handle fell off."
        },
        reference="negative",
    ),
    # Contrastive 'despite': surface positives must not outweigh a broken core product.
    Example(
        inputs={
            "review": "Despite the gorgeous aesthetics and premium materials, it overheats after ten minutes and smells like burning plastic."
        },
        reference="negative",
    ),
    # Negated complaint: 'can't fault X' is mild approval of the product, not neutral.
    Example(
        inputs={
            "review": "Really can't fault the battery life on this thing — easily gets through two days of heavy use."
        },
        reference="positive",
    ),
    # Aspect scoping: a great deal on a bad product is still negative.
    Example(
        inputs={
            "review": "Amazing Black Friday price, but the tablet stutters, the screen flickers, and I regret keeping it."
        },
        reference="negative",
    ),
]

examples = examples + ambiguous_examples

optimization = optimize(
    experiment=experiment,
    examples=examples,
    metrics=[label_correctness, reason_quality],
    proposer_config=LMConfig(
        model="vertex:gemini-3.5-flash",
        generation_kwargs={"temperature": 0.1},
    ),
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
print(history.replace("<template>", "**Template**:\n\n```").replace("</template>", "```"))
