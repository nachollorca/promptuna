# ruff: noqa: D103, D101
"""Program and output schema for the getting started example.

Keep this in a ``.py`` module so promptuna can introspect the program source when
optimizing from a notebook — define the program here and import it.
"""

import re
from typing import Any, Literal

from lmdk import complete, render_template
from pydantic import BaseModel, Field

ALLOWED_LABELS = {"positive", "neutral", "negative"}
MAX_REVIEW_CHARS = 500


class SentimentOutput(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    reason: str = Field(description="One short sentence justifying the sentiment label.")


def classify_sentiment(
    prompt_template: str,
    model: str,
    generation_kwargs: dict | None = None,
    **inputs: Any,
) -> dict:
    # The harness unpacks ``Example.inputs`` as keyword arguments; pull ours out.
    review: str = inputs["review"]

    # Pre-processing: normalise whitespace and cap length
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

    # Post-processing: normalize the label and fall back to "neutral"
    label = (response.output.sentiment or "").strip().lower()
    if label not in ALLOWED_LABELS:
        label = "neutral"

    return {"sentiment": label, "reason": response.output.reason.strip()}
