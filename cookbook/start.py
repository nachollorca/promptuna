import marimo

__generated_with = "0.23.6"
app = marimo.App(width="medium")


@app.cell
def _():

    return


@app.cell
def _():
    from lmeh.datatypes import Example

    dataset = [
        Example(inputs={"comment": "I think you are pretty ugly"}, reference=True),
        Example(inputs={"comment": "I love raspberry muffins"}, reference=False),
        Example(inputs={"comment": "What is wrong with ur face bro?"}, reference=True),
        Example(inputs={"comment": "Paris is the capital of Italy"}, reference=False),
        Example(inputs={"comment": "a cagar al campo chaval"}, reference=True),
    ]
    return Example, dataset


@app.cell
def _():
    from lmdk import complete, render_template

    from lmeh.datatypes import TargetConfig, TargetOutput

    def detect_hate(inputs: dict[str, str], config: TargetConfig) -> TargetOutput:
        prompt = render_template(template=config.prompt_template, COMMENT=inputs["comment"])
        response = complete(
            model=config.model,
            generation_kwargs=config.generation_kwargs,
            prompt=prompt,
            return_request=True,
            output_schema=config.output_schema,
        )
        return TargetOutput.passthrough(response=response)

    return TargetConfig, detect_hate


@app.cell
def _(TargetConfig):
    from pydantic import BaseModel, Field

    class Output(BaseModel):
        is_hate: bool
        reason: str = Field(description="The brief reason why the comment is hate speech or not")

    config = TargetConfig(
        model="mistral:mistral-small-latest",
        generation_kwargs={"temperature": 0.7},
        prompt_template="Do you think the comment '{{ COMMENT }}' is hate speech?",
        output_schema=Output,
    )
    return (config,)


@app.cell
def _(config, dataset, detect_hate):
    from lmeh.execution import run_trial

    trial = run_trial(target=detect_hate, config=config, example=dataset[0])

    print(trial.result.output)
    return (trial,)


@app.cell
def _(Example):
    from lmeh.datatypes import Metric, Ordinal, Score

    def is_correct(output: bool, example: Example) -> Score:
        raw_score = output.is_hate == example.reference
        return Score(raw=raw_score)

    correctness = Metric(
        name="correctness",
        description="whether the answer is correct or not",
        scale=Ordinal(levels=[False, True]),
        scorer=is_correct,
    )
    return (correctness,)


@app.cell
def _(correctness, trial):
    from lmeh.execution import score_metric

    scoring = score_metric(trial=trial, metric=correctness)

    print(scoring.score)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
