"""Programs for the classify_sentiment reference project."""

import re
from typing import Any, Literal

from lmdk import complete, render_template
from pydantic import BaseModel, Field

ALLOWED_LABELS = frozenset({"positive", "neutral", "negative"})


def v1(
    prompt_template: str,
    model: str,
    generation_kwargs: dict | None = None,
    **inputs: Any,
) -> dict:
    """Baseline scaffold: inline cleanup and schema-constrained parsing."""

    class SentimentOutput(BaseModel):
        sentiment: Literal["positive", "neutral", "negative"]
        reason: str = Field(
            description=(
                "One short sentence justifying the sentiment label, "
                "in the same language as the review."
            )
        )

    review = re.sub(r"\s+", " ", inputs["review"]).strip()

    prompt = render_template(template=prompt_template, REVIEW=review)
    response = complete(
        model=model,
        generation_kwargs=generation_kwargs,
        prompt=prompt,
        output_schema=SentimentOutput,
    )

    label = response.output.sentiment.strip().lower()
    if label not in ALLOWED_LABELS:
        label = "neutral"

    return {"sentiment": label, "reason": response.output.reason.strip()}


def v2(
    prompt_template: str,
    model: str,
    generation_kwargs: dict | None = None,
    **inputs: Any,
) -> dict:
    """Hardened scaffold: richer cleanup, loose schema, alias repair."""

    class LooseSentiment(BaseModel):
        sentiment: str
        reason: str = Field(
            description=(
                "One short sentence justifying the sentiment label, "
                "in the same language as the review."
            )
        )

    # Preprocess: collapse whitespace, tame repeated punctuation, cap length.
    review = re.sub(r"\s+", " ", inputs["review"]).strip()
    review = re.sub(r"([!?.]){2,}", r"\1", review)
    if len(review) > 1000:
        review = review[:1000] + "…"

    prompt = render_template(template=prompt_template, REVIEW=review)
    response = complete(
        model=model,
        generation_kwargs=generation_kwargs,
        prompt=prompt,
        output_schema=LooseSentiment,
    )

    # Postprocess: map common aliases, then fall back to neutral.
    label_aliases = {
        "pos": "positive",
        "positive.": "positive",
        "neg": "negative",
        "negative.": "negative",
        "neu": "neutral",
        "mixed": "neutral",
    }
    raw_label = response.output.sentiment.strip().lower()
    label = label_aliases.get(raw_label, raw_label)
    if label not in ALLOWED_LABELS:
        label = "neutral"

    return {"sentiment": label, "reason": response.output.reason.strip()}
