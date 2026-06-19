"""Reusable builders and fakes for promptuna tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import lmdk
from lmdk import CompletionRequest, CompletionResponse, UserMessage, render_template
from lmdk.observe import _current_observer

from promptuna.evaluate import (
    LLMJudgeMetric,
    ProgrammaticMetric,
    Range,
    RawScore,
    RunInfo,
    RunResults,
    Score,
    SuccessfulScoring,
)
from promptuna.program import Example, Experiment, LMConfig
from promptuna.run import SuccessfulTrial


def echo_program(prompt_template: str, config: LMConfig, **inputs: Any) -> str:
    """Minimal program: render the template and call the model once."""
    prompt = render_template(prompt_template, **inputs)
    response = lmdk.complete(model=config.model, prompt=prompt)
    return response.content


def exact_match_scorer(output: Any, example: Example) -> RawScore:
    match = str(output).strip() == str(example.reference).strip()
    return RawScore(raw=1.0 if match else 0.0, reason="exact match")


def fake_complete(
    model: str,
    prompt: str | list[UserMessage],
    **kwargs: Any,
) -> CompletionResponse:
    """Stand-in for lmdk.complete that avoids network calls in tests."""
    observer = _current_observer()
    messages = [UserMessage(content=prompt)] if isinstance(prompt, str) else prompt
    request = CompletionRequest(
        model_id=model.split(":", maxsplit=1)[-1],
        prompt=messages,
        system_instruction=kwargs.get("system_instruction"),
        output_schema=kwargs.get("output_schema"),
        generation_kwargs=kwargs.get("generation_kwargs") or {"temperature": 0},
    )
    parsed = None
    if schema := kwargs.get("output_schema"):
        parsed = schema(raw=1.0, reason="looks good")
    response = CompletionResponse(
        content="4",
        input_tokens=3,
        output_tokens=1,
        latency=0.25,
        parsed=parsed,
    )
    if observer is not None:
        observer._record(request, response)
    return response


def fake_complete_factory(content: str) -> Any:
    """Build a context manager that patches complete to return ``content``."""

    def _complete(
        model: str,
        prompt: str | list[UserMessage],
        **kwargs: Any,
    ) -> CompletionResponse:
        observer = _current_observer()
        messages = [UserMessage(content=prompt)] if isinstance(prompt, str) else prompt
        request = CompletionRequest(
            model_id=model.split(":", maxsplit=1)[-1],
            prompt=messages,
            system_instruction=kwargs.get("system_instruction"),
            output_schema=kwargs.get("output_schema"),
            generation_kwargs=kwargs.get("generation_kwargs") or {"temperature": 0},
        )
        parsed = None
        if schema := kwargs.get("output_schema"):
            parsed = schema(raw=1.0, reason="ok")
        response = CompletionResponse(
            content=content,
            input_tokens=1,
            output_tokens=2,
            latency=0.1,
            parsed=parsed,
        )
        if observer is not None:
            observer._record(request, response)
        return response

    return patch("lmdk.complete", side_effect=_complete)


def make_trial(
    example: Example,
    *,
    output: Any = "4",
    rendered_prompt: str = "Answer: 2+2?",
    output_schema: Any = None,
    replicate: int = 0,
) -> SuccessfulTrial:
    request = CompletionRequest(
        model_id="model",
        prompt=[UserMessage(content=rendered_prompt)],
        system_instruction=None,
        output_schema=output_schema,
        generation_kwargs={"temperature": 0},
    )
    response = CompletionResponse(
        content=str(output),
        input_tokens=5,
        output_tokens=2,
        latency=0.2,
    )
    return SuccessfulTrial(
        example=example,
        output=output,
        request=request,
        response=response,
        replicate=replicate,
    )


def make_run_results(
    experiment: Experiment,
    examples: list[Example],
    metric: ProgrammaticMetric,
    *,
    scores: list[float],
) -> RunResults:
    trials = [make_trial(ex) for ex in examples]
    scorings = [
        SuccessfulScoring(
            trial=trial,
            metric=metric,
            score=Score(raw=score, normalized=score, reason=f"score {score}"),
        )
        for trial, score in zip(trials, scores, strict=True)
    ]
    return RunResults(
        experiment=experiment,
        run=RunInfo(),
        trials=trials,
        scorings=scorings,
    )


def make_llm_judge_metric(lm_config: LMConfig) -> LLMJudgeMetric:
    def judge(
        output: Any,
        example: Example,
        metric: LLMJudgeMetric,
        config: LMConfig,
        rendered_prompt: str,
    ) -> RawScore:
        return RawScore(raw=1.0, reason="judge approved")

    return LLMJudgeMetric(
        name="quality",
        description="Rate answer quality.",
        scale=Range(0.0, 1.0),
        scorer=judge,
        config=lm_config,
        prompt_template="Judge {{ OUTPUT }}",
    )
