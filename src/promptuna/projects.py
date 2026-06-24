"""Resolve on-disk project layouts into live :class:`~promptuna.program.Experiment` objects."""

from __future__ import annotations

import importlib.util
import inspect
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from promptuna.evaluate import LLMJudgeMetric, Metric, ProgrammaticMetric
from promptuna.load import load_jsonl
from promptuna.program import Example, Experiment, Program

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_projects_root: Path | None = None


class ProjectValidationError(ValueError):
    """Raised when project resolution or validation fails."""


def default_projects_root() -> Path:
    """Return the bundled ``samples/`` directory at the repository root."""
    return Path(__file__).resolve().parent.parent.parent / "samples"


def get_projects_root() -> Path:
    """Return the active projects root.

    Resolution order (highest priority first):

    1. :func:`set_projects_root` — programmatic override (typically tests)
    2. ``PROMPTUNA_PROJECTS_ROOT`` — environment variable
    3. :func:`default_projects_root` — bundled ``samples/`` in a dev checkout
    """
    if _projects_root is not None:
        return _projects_root

    env_root = os.environ.get("PROMPTUNA_PROJECTS_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    return default_projects_root()


def set_projects_root(path: Path | None) -> None:
    """Override the projects root directory programmatically."""
    global _projects_root
    _projects_root = path


def _validate_name(name: str, *, kind: str) -> None:
    if not _NAME_RE.match(name):
        raise ProjectValidationError(f"invalid {kind} name: {name!r}")


def _resolve_under_root(root: Path, *parts: str) -> Path:
    resolved = (root.joinpath(*parts)).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ProjectValidationError("path escapes project directory")
    return resolved


def resolve_project_dir(project: str) -> Path:
    """Return ``<projects_root>/<project>/`` after validating the project name."""
    _validate_name(project, kind="project")
    root = get_projects_root().resolve()
    project_dir = _resolve_under_root(root, project)
    if not project_dir.is_dir():
        raise ProjectValidationError(f"project {project!r} not found")
    return project_dir


def _load_project_module(project_dir: Path, module_basename: str) -> Any:
    path = project_dir / f"{module_basename}.py"
    if not path.is_file():
        raise ProjectValidationError(f"{module_basename}.py not found in project")

    module_name = f"_promptuna_project_{project_dir.name}_{module_basename}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ProjectValidationError(f"could not load {module_basename}.py")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _resolve_named_callable(module: Any, name: str, *, kind: str) -> Callable[..., Any]:
    if name.startswith("_"):
        raise ProjectValidationError(f"invalid {kind} name: {name!r}")
    try:
        obj = getattr(module, name)
    except AttributeError as exc:
        raise ProjectValidationError(f"{kind} {name!r} not found") from exc
    if not callable(obj):
        raise ProjectValidationError(f"{kind} {name!r} is not callable")
    return obj


def _validate_program(program: Callable[..., Any], name: str) -> Program:
    sig = inspect.signature(program)
    params = sig.parameters
    if "prompt_template" not in params or "model" not in params:
        raise ProjectValidationError(
            f"program {name!r} must accept prompt_template and model parameters"
        )
    return program  # type: ignore[return-value]


def _validate_metric(metric: Any, name: str) -> Metric:
    if not isinstance(metric, (ProgrammaticMetric, LLMJudgeMetric)):
        raise ProjectValidationError(f"metric {name!r} is not a Metric instance")
    return metric


def resolve_program(project_dir: Path, name: str) -> Program:
    """Import and validate a named program from ``programs.py``."""
    module = _load_project_module(project_dir, "programs")
    program = _resolve_named_callable(module, name, kind="program")
    return _validate_program(program, name)


def resolve_metrics(project_dir: Path, names: list[str]) -> list[Metric]:
    """Import and validate named metrics from ``metrics.py``."""
    module = _load_project_module(project_dir, "metrics")
    metrics: list[Metric] = []
    for name in names:
        if name.startswith("_"):
            raise ProjectValidationError(f"invalid metric name: {name!r}")
        try:
            metric = getattr(module, name)
        except AttributeError as exc:
            raise ProjectValidationError(f"metric {name!r} not found") from exc
        metrics.append(_validate_metric(metric, name))
    return metrics


def resolve_prompt_template(project_dir: Path, prompt: str) -> str:
    """Read ``prompts/<prompt>.jinja`` from the project."""
    _validate_name(prompt, kind="prompt")
    path = _resolve_under_root(project_dir, "prompts", f"{prompt}.jinja")
    if not path.is_file():
        raise ProjectValidationError(f"prompt {prompt!r} not found")
    return path.read_text(encoding="utf-8")


def resolve_examples(project_dir: Path, examples: str) -> list[Example]:
    """Load ``data/<examples>.jsonl`` via :func:`promptuna.load.load_jsonl`."""
    _validate_name(examples, kind="examples")
    path = _resolve_under_root(project_dir, "data", f"{examples}.jsonl")
    if not path.is_file():
        raise ProjectValidationError(f"dataset {examples!r} not found")
    loaded = load_jsonl(path)
    if not loaded:
        raise ProjectValidationError(f"dataset {examples!r} is empty")
    return loaded


def build_experiment(
    *,
    project: str,
    program: str,
    prompt: str,
    model: str,
    examples: str,
    metrics: list[str] | None = None,
) -> tuple[Experiment, list[Example], list[Metric] | None]:
    """Validate project selections and build an :class:`Experiment` plus dataset."""
    project_dir = resolve_project_dir(project)
    resolved_program = resolve_program(project_dir, program)
    prompt_template = resolve_prompt_template(project_dir, prompt)
    example_rows = resolve_examples(project_dir, examples)
    resolved_metrics = resolve_metrics(project_dir, metrics) if metrics is not None else None

    experiment = Experiment(
        program=resolved_program,
        prompt_template=prompt_template,
        model=model,
    )
    return experiment, example_rows, resolved_metrics
