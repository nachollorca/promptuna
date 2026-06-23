"""Minimal echo program for server API tests."""

from lmdk import complete, render_template


def echo(prompt_template: str, model: str, **inputs):
    prompt = render_template(prompt_template, **inputs)
    response = complete(model=model, prompt=prompt)
    return response.content
