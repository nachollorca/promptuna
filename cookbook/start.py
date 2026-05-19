import marimo

__generated_with = "0.23.6"
app = marimo.App(
    width="medium",
    css_file="/home/nacho/.config/marimo/catppuccin-latte-mocha.css",
    auto_download=["ipynb"],
)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Get started
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Let's walk through a small but realistic example. The task is **product review sentiment analysis**: given a customer review, predict whether the sentiment is `positive`, `neutral`, or `negative`, and produce a short justification for the call.

    We start with a tiny labelled dataset. The `reference` is the ground-truth label.
    """)
    return


@app.cell
def _():
    from lmeh.datatypes import Example

    dataset = [
        Example(
            inputs={"review": "Battery lasts two full days and the screen is gorgeous. Best phone I've owned."},
            reference="positive",
        ),
        Example(
            inputs={"review": "It works. Setup was fine, nothing surprising, nothing to complain about."},
            reference="neutral",
        ),
        Example(
            inputs={"review": "Stopped charging after three weeks. Support never replied. Avoid."},
            reference="negative",
        ),
        Example(
            inputs={"review": "    Camera   is   AMAZING!!!   colors pop, low-light is great.\n\n\nHighly recommend."},
            reference="positive",
        ),
        Example(
            inputs={"review": "Arrived on time. Packaging was a bit beaten up but the product itself looks ok."},
            reference="neutral",
        ),
    ]
    return Example, dataset


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Now we define the target function — the **thing we actually want to evaluate**. Note that it is not just a thin wrapper around `complete()`: there can be real pre- and post-processing around the model call. That's intentional. In production, what users hit is rarely the raw completion; it's the completion plus the glue around it. The harness lets us evaluate that full product.

    The function must adhere to the `TargetFunction` protocol: take its **named inputs**, the **prompt template**, and an **LM config**, then return whatever the downstream scorers should consume. The harness unpacks `Example.inputs` as keyword arguments, so the parameter names must match the dict keys.

    The underlying `CompletionRequest` / `CompletionResponse` are captured automatically (via `lmdk.observe`) and attached to the trial — the target doesn't need to surface them.
    """)
    return


@app.cell
def _():
    import re

    from lmdk import complete, render_template

    from lmeh.datatypes import LMConfig

    ALLOWED_LABELS = {"positive", "neutral", "negative"}
    MAX_REVIEW_CHARS = 500

    def classify_sentiment(review: str, prompt_template: str, config: LMConfig) -> dict:
        # Pre-processing: normalise whitespace and cap length
        cleaned = re.sub(r"\s+", " ", review).strip()
        if len(cleaned) > MAX_REVIEW_CHARS:
            cleaned = cleaned[:MAX_REVIEW_CHARS] + "…"

        # Call the model with lmdk.complete
        prompt = render_template(template=prompt_template, REVIEW=cleaned)
        response = complete(
            model=config.model,
            generation_kwargs=config.generation_kwargs,
            prompt=prompt,
            output_schema=config.output_schema,
        )

        # Post-processing: normalize the label and fall back to"neutral"
        label = (response.output.sentiment or "").strip().lower()
        if label not in ALLOWED_LABELS:
            label = "neutral"

        # Return arbitrary format that will be downstream consumed
        return {"sentiment": label, "reason": response.output.reason.strip()}

    return LMConfig, classify_sentiment


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Now, lets define the moving parts under test. The three sweepable axes are the **prompt template**, the **LM config** (model, generation kwargs, optional output schema), and the target function itself.
    """)
    return


@app.cell
def _(LMConfig):
    from typing import Literal

    from pydantic import BaseModel, Field

    class Output(BaseModel):
        sentiment: Literal["positive", "neutral", "negative"]
        reason: str = Field(description="One short sentence justifying the sentiment label.")

    prompt_template = """Your task is to classify the sentiment of this product review:

    {{ REVIEW }}

    The possible labels are 'positive', 'neutral' and 'negative'
    """

    config = LMConfig(
        model="mistral:mistral-small-latest",
        generation_kwargs={"temperature": 0.2},
        output_schema=Output,
    )
    return config, prompt_template


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    With these ingredients, we can already run a trial: execute the target function on one example with the config under test.
    """)
    return


@app.cell
def _(classify_sentiment, config, dataset, prompt_template):
    from lmeh.execution import run_trial

    trial = run_trial(
        target=classify_sentiment,
        prompt_template=prompt_template,
        config=config,
        example=dataset[0],
    )

    trial.output
    return (trial,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Now that our trial ran successfully, we can jump into quality measurements.

    First, a simple deterministic check: does the predicted label match the ground truth? No LLM judge needed — a `ProgrammaticMetric` whose scorer follows the `ProgrammaticScorer` protocol is the right tool. We declare the value space with an `Ordinal` scale.
    """)
    return


@app.cell
def _(Example):
    from lmeh.datatypes import Ordinal, ProgrammaticMetric, Score

    def label_match(output: dict, example: Example) -> Score:
        predicted = output["sentiment"]
        expected = example.reference
        if predicted == expected:
            return Score(raw=True, reason=f"Predicted '{predicted}' matches reference.")
        return Score(
            raw=False,
            reason=f"Predicted '{predicted}', expected '{expected}'.",
        )

    label_correctness = ProgrammaticMetric(
        name="label_correctness",
        description="Whether the predicted sentiment label matches the ground-truth label.",
        scale=Ordinal(levels=[False, True]),
        scorer=label_match,
    )
    return Ordinal, label_correctness


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Now we score the trial against the metric.
    """)
    return


@app.cell
def _(label_correctness, trial):
    from lmeh.execution import score_metric

    scoring = score_metric(trial=trial, metric=label_correctness)
    scoring.score
    return (score_metric,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The label check is cheap and exact, but it tells us nothing about the *reason* the model produced — and a good sentiment classifier should be able to justify its call. That's a subjective, open-ended judgement with no ground truth, which is exactly where an LLM judge earns its keep.

    We define an `LLMJudgeMetric` that grades the quality of the justification. It carries its own `LMConfig` and judge prompt template. We use the built-in `default_llm_judge`, which feeds the judge the rendered prompt, the target's output, the reference, and the metric description.
    """)
    return


@app.cell
def _(LMConfig, Ordinal):
    from lmeh.datatypes import LLMJudgeMetric
    from lmeh.judges import default_llm_judge

    description = """Rate how well the 'reason' field justifies the predicted sentiment label given the original review. A good reason cites concrete cues from the review and is consistent with the predicted label. Score 'good' if the justification is grounded and coherent, 'poor' otherwise.
    """

    reason_quality = LLMJudgeMetric(
        name="reason_quality",
        description=description,
        scale=Ordinal(levels=["poor", "good"]),
        scorer=default_llm_judge,
        config=LMConfig(
            model="mistral:mistral-medium-latest",
            generation_kwargs={"temperature": 0.1},
        ),
    )
    return (reason_quality,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Let's see what the judge thinks about the system output on our first trial.
    """)
    return


@app.cell
def _(reason_quality, score_metric, trial):
    judge_scoring = score_metric(trial=trial, metric=reason_quality)
    judge_scoring.score
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Finally, we can wire it all together into an experiment: run `classify_sentiment` against every example in the dataset and score both metrics on each output.
    """)
    return


@app.cell
def _(
    classify_sentiment,
    config,
    dataset,
    label_correctness,
    prompt_template,
    reason_quality,
):
    from lmeh.datatypes import Experiment
    from lmeh.execution import run_experiment

    experiment = Experiment(
        name="sentiment-baseline",
        target=classify_sentiment,
        prompt_template=prompt_template,
        config=config,
    )

    results = run_experiment(
        experiment=experiment,
        dataset=dataset,
        metrics=[label_correctness, reason_quality],
        workers=5,
    )
    return (results,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    And a reporting utility renders the results.
    """)
    return


@app.cell
def _(mo, results):
    from lmeh.reporting import markdown_report

    mo.md(markdown_report(results))
    return


if __name__ == "__main__":
    app.run()
