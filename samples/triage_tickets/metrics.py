"""Metrics for the triage_tickets reference project."""

from promptuna.evaluate import Ordinal, ProgrammaticMetric, RawScore
from promptuna.program import Example


def _field_match(field: str):
    def scorer(output: dict, example: Example) -> RawScore:
        assert example.reference is not None, "triage_tickets rows require a reference"
        got, expected = output[field], example.reference[field]
        if got == expected:
            return RawScore(raw=True, reason=f"{field} '{got}' matches the support lead.")
        return RawScore(
            raw=False, reason=f"Assigned {field} '{got}', support lead chose '{expected}'."
        )

    return scorer


priority_match = ProgrammaticMetric(
    name="priority_match",
    description="Whether the assigned priority matches the support lead's choice for the ticket.",
    scale=Ordinal(levels=[False, True]),
    scorer=_field_match("priority"),
)

team_match = ProgrammaticMetric(
    name="team_match",
    description="Whether the ticket is routed to the team the support lead chose.",
    scale=Ordinal(levels=[False, True]),
    scorer=_field_match("team"),
)
