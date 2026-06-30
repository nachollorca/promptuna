"""Metrics for the classify_sentiment reference project."""

from promptuna.evaluate import (
    LLMJudgeMetric,
    Ordinal,
    ProgrammaticMetric,
    RawScore,
    default_llm_judge,
)
from promptuna.program import Example


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

reason_language = LLMJudgeMetric(
    name="reason_language",
    description=(
        "Whether the reason field in the output is written in the same language as the "
        "product review in the rendered prompt. Ignore whether the sentiment label is correct."
    ),
    scale=Ordinal(levels=[False, True]),
    scorer=default_llm_judge,
    model="mistral:mistral-medium-latest",
)
