"""Metrics for the classify_sentiment reference project."""

from promptuna.evaluate import Ordinal, ProgrammaticMetric, RawScore
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
