"""Programs for the classify_sentiment reference project."""

import re
from typing import Any, Literal

from lmdk import complete, render_template
from pydantic import BaseModel, Field

ALLOWED_LABELS = {"positive", "neutral", "negative"}
MAX_REVIEW_CHARS = 500


class SentimentOutput(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    reason: str = Field(description="One short sentence justifying the sentiment label.")


def v1(
    prompt_template: str,
    model: str,
    generation_kwargs: dict | None = None,
    **inputs: Any,
) -> dict:
    review: str = inputs["review"]

    cleaned = re.sub(r"\s+", " ", review).strip()
    if len(cleaned) > MAX_REVIEW_CHARS:
        cleaned = cleaned[:MAX_REVIEW_CHARS] + "…"

    prompt = render_template(template=prompt_template, REVIEW=cleaned)
    response = complete(
        model=model,
        generation_kwargs=generation_kwargs,
        prompt=prompt,
        output_schema=SentimentOutput,
    )

    label = (response.output.sentiment or "").strip().lower()
    if label not in ALLOWED_LABELS:
        label = "neutral"

    return {"sentiment": label, "reason": response.output.reason.strip()}
