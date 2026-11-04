"""Program for the triage_tickets reference project."""

from typing import Literal

from lmdk import complete, render_template
from pydantic import BaseModel


class Triage(BaseModel):
    priority: Literal["P0", "P1", "P2", "P3"]
    team: Literal["billing", "accounts", "platform", "security", "product"]


def v1(
    prompt_template: str,
    model: str,
    plan: str,
    ticket: str,
    generation_kwargs: dict | None = None,
) -> dict:
    """Render the ticket, ask for a structured triage, return it as a dict."""
    prompt = render_template(
        template=prompt_template,
        PLAN=plan,
        TICKET=ticket.strip(),
    )
    response = complete(
        model=model,
        generation_kwargs=generation_kwargs,
        prompt=prompt,
        output_schema=Triage,
    )
    return response.output.model_dump()
