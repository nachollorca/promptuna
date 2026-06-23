"""Exact-match metric for server API tests."""

from promptuna.evaluate import ProgrammaticMetric, Range, RawScore
from promptuna.program import Example


def exact_match_scorer(output, example: Example) -> RawScore:
    match = str(output).strip() == str(example.reference).strip()
    return RawScore(raw=1.0 if match else 0.0, reason="exact match")


exact_match = ProgrammaticMetric(
    name="exact_match",
    description="Output must match the reference answer.",
    scale=Range(0.0, 1.0),
    scorer=exact_match_scorer,
)
