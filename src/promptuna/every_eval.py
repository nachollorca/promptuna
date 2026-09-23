"""Export a persisted promptuna job to the Every Eval Ever (EEE) schema.

EEE (https://github.com/evaleval/every_eval_ever) stores one evaluation as a pair
of files: an aggregate ``<uuid>.json`` and an instance-level
``<uuid>_samples.jsonl`` companion. :func:`export_every_eval` derives both from a
job archive (:mod:`promptuna.jobs`) — ``manifest.json`` plus ``events.jsonl`` —
and writes them under the datastore layout
``data/<collection>/<developer>/<model>/``.

What a job cannot know is a parameter, not a guess: who publishes the record, and
whether the model's weights are available. Both default to ``unknown``.
"""

import hashlib
import json
import re
import statistics
import uuid as uuid_module
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from promptuna.jobs import load_events, load_manifest

EEE_SCHEMA_VERSION = "0.3.0"

# The EEE schema rejects unknown keys inside `generation_args`.
_GENERATION_ARG_KEYS = (
    "temperature",
    "top_p",
    "top_k",
    "max_tokens",
    "execution_command",
    "reasoning",
    "max_attempts",
)

_UNSAFE_PATH_CHARS = re.compile(r'[<>:"\\|?*\x00-\x1f]')


def export_every_eval(
    job_dir: Path,
    out_dir: Path,
    *,
    collection: str | None = None,
    organization: str = "promptuna",
    evaluator_relationship: str = "first_party",
    deployment_type: str = "unknown",
    model_availability: str = "unknown",
    lower_is_better: bool = False,
    log_uuid: str | None = None,
) -> Path:
    """Write one job archive as an EEE aggregate + samples pair.

    Returns the aggregate JSON path. ``log_uuid`` must be a UUID4 when given;
    pass a fixed one to make re-exports land on the same datastore path.
    """
    manifest = load_manifest(job_dir)
    events = load_events(job_dir)

    project = str(manifest["project"])
    evaluation_name = f"{project}_{manifest['program']}"
    model_id = _model_id(manifest, events)
    collection_name, developer, model_name = _datastore_path(collection or project, model_id)
    file_uuid = log_uuid or str(uuid_module.uuid4())
    retrieved = _unix_now()
    evaluation_id = f"{evaluation_name}/{model_id}/{retrieved}"

    trials, scorings = _index(events)
    model_dir = out_dir / "data" / collection_name / developer / model_name
    model_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    generation_config = _generation_config(trials, manifest)
    for (step, metric_name), group in sorted(_by_step_and_metric(scorings).items()):
        name = evaluation_name if step == 0 else f"{evaluation_name}_step{step}"
        result_id = f"{name}:{metric_name}"
        metric = group[0]["metric"]
        results.append(
            _evaluation_result(
                name=name,
                result_id=result_id,
                metric=metric,
                payloads=group,
                lower_is_better=lower_is_better,
                generation_config=generation_config,
            )
        )
        rows.extend(
            _instance_rows(
                trial=trials[(step, payload["trial_id"])],
                payload=payload,
                evaluation_name=name,
                result_id=result_id,
                evaluation_id=evaluation_id,
                model_id=model_id,
            )
            for payload in group
        )

    aggregate: dict[str, Any] = {
        "schema_version": EEE_SCHEMA_VERSION,
        "evaluation_id": evaluation_id,
        "evaluation_timestamp": _unix_from_iso(manifest.get("started_at")),
        "retrieved_timestamp": retrieved,
        "source_metadata": _source_metadata(manifest, organization, evaluator_relationship),
        "eval_library": {
            "name": "promptuna",
            "version": str(manifest.get("promptuna_version") or "unknown"),
            "additional_details": {"promptuna.job_kind": str(manifest["kind"])},
        },
        "model_info": {
            "name": str(manifest["model"]),
            "id": model_id,
            "developer": developer,
            "additional_details": {
                "deployment_type": deployment_type,
                "model_availability": model_availability,
                "promptuna.model_string": str(manifest["model"]),
            },
        },
        "evaluation_results": results,
    }

    aggregate_path = model_dir / f"{file_uuid}.json"
    if rows:
        samples_path = model_dir / f"{file_uuid}_samples.jsonl"
        samples_path.write_text("".join(_dump(row) + "\n" for row in rows), encoding="utf-8")
        aggregate["detailed_evaluation_results"] = {
            "format": "jsonl",
            "file_path": _repo_path(collection_name, developer, model_name, samples_path.name),
            "hash_algorithm": "sha256",
            "checksum": hashlib.sha256(samples_path.read_bytes()).hexdigest(),
            "total_rows": len(rows),
        }

    aggregate_path.write_text(_dump(aggregate, indent=2) + "\n", encoding="utf-8")
    return aggregate_path


def _dump(payload: Any, indent: int | None = None) -> str:
    return json.dumps(payload, indent=indent, sort_keys=indent is not None, allow_nan=False)


def _unix_now() -> str:
    return str(datetime.now(UTC).timestamp())


def _unix_from_iso(timestamp: Any) -> str | None:
    if not timestamp:
        return None
    return str(datetime.fromisoformat(str(timestamp)).timestamp())


def _model_id(manifest: dict[str, Any], events: list[dict[str, Any]]) -> str:
    """Prefer the model id the API actually served the completion with."""
    for event in events:
        request = event.get("payload", {}).get("telemetry", {}).get("request")
        if request and request.get("model_id"):
            return str(request["model_id"])
    return str(manifest["model"]).split(":", 1)[-1]


def _component(value: str) -> str:
    """Coerce one identity string into a portable path component."""
    cleaned = _UNSAFE_PATH_CHARS.sub("-", value.strip()).rstrip(". ")
    return cleaned or "unknown"


def _datastore_path(collection: str, model_id: str) -> tuple[str, str, str]:
    """Mirror EEE's collection/developer/model layout (slashes become underscores)."""
    parts = [part for part in model_id.split("/") if part]
    if len(parts) >= 2:
        developer, name = parts[0], "_".join(parts[1:])
    else:
        developer, name = "unknown", parts[0]
    return (
        _component(collection.replace("/", "_")),
        _component(developer),
        _component(name),
    )


def _repo_path(collection: str, developer: str, model: str, filename: str) -> str:
    return f"data/{collection}/{developer}/{model}/{filename}"


def _source_metadata(
    manifest: dict[str, Any], organization: str, evaluator_relationship: str
) -> dict[str, Any]:
    details = {
        "promptuna.job_id": str(manifest["job_id"]),
        "promptuna.program": str(manifest["program"]),
        "promptuna.prompt": str(manifest["prompt"]),
        "promptuna.dataset_path": str(manifest["dataset_path"]),
        "promptuna.dataset_sha256": str(manifest["dataset_sha256"]),
        "promptuna.workers": str(manifest["workers"]),
        "promptuna.repeats": str(manifest["repeats"]),
    }
    return {
        "source_name": str(manifest["project"]),
        "source_type": "evaluation_run",
        "source_organization_name": organization,
        "evaluator_relationship": evaluator_relationship,
        "additional_details": details,
    }


def _index(events: list[dict[str, Any]]) -> tuple[dict, list]:
    """Split events into trials keyed by ``(step, trial_id)`` and successful scorings."""
    trials: dict[tuple[int, str], dict[str, Any]] = {}
    scorings: list[tuple[int, dict[str, Any]]] = []
    for event in events:
        payload = event["payload"]
        if event["type"] == "trial":
            trials[(event["step_index"], payload["trial_id"])] = payload
        elif event["type"] == "scoring" and payload["status"] == "success":
            scorings.append((event["step_index"], payload))
    return trials, scorings


def _by_step_and_metric(
    scorings: list[tuple[int, dict[str, Any]]],
) -> dict[tuple[int, str], list[dict[str, Any]]]:
    """Pool replicates: one aggregate result per step and metric."""
    groups: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for step, payload in scorings:
        groups.setdefault((step, payload["metric"]["name"]), []).append(payload)
    return groups


def _generation_config(
    trials: dict[tuple[int, str], dict[str, Any]], manifest: dict[str, Any]
) -> dict[str, Any] | None:
    request = next(
        (
            payload["telemetry"]["request"]
            for payload in trials.values()
            if payload.get("telemetry", {}).get("request")
        ),
        None,
    )
    if request is None:
        return None
    kwargs = request.get("generation_kwargs") or {}
    known = {key: kwargs[key] for key in _GENERATION_ARG_KEYS if key in kwargs}
    extra = {key: value for key, value in kwargs.items() if key not in known}
    config: dict[str, Any] = {
        "generation_args": known,
        "additional_details": {
            "promptuna.prompt_name": str(manifest["prompt"]),
            "promptuna.program": str(manifest["program"]),
        },
    }
    if request.get("system_instruction"):
        config["additional_details"]["promptuna.system_instruction"] = str(
            request["system_instruction"]
        )
    if extra:
        config["additional_details"]["promptuna.generation_kwargs"] = json.dumps(
            extra, sort_keys=True, default=str
        )
    return config


def _metric_config(metric: dict[str, Any], *, lower_is_better: bool) -> dict[str, Any]:
    scale = metric.get("scale") or {}
    kind = scale.get("kind")
    details = {
        "promptuna.metric_kind": str(metric["kind"]),
        "promptuna.metric_scale": json.dumps(scale, sort_keys=True),
    }
    config: dict[str, Any] = {
        "metric_id": f"promptuna.{metric['name']}",
        "metric_name": str(metric["name"]),
        "evaluation_description": str(metric["description"]),
        "lower_is_better": lower_is_better,
        "additional_details": details,
    }
    if kind == "ordinal":
        config["score_type"] = "levels"
        config["level_names"] = [str(level) for level in scale["levels"]]
        config["has_unknown_level"] = False
    else:
        # Old archives carry no scale; normalized scores are always in [0, 1].
        config["score_type"] = "continuous"
        config["min_score"] = float(scale["floor"]) if kind == "range" else 0.0
        config["max_score"] = float(scale["ceiling"]) if kind == "range" else 1.0
        if kind != "range":
            details["promptuna.metric_scale_assumed"] = "[0, 1]"
    return config


def _native_score(scale: dict[str, Any], payload: dict[str, Any]) -> float:
    """Score on the metric's own scale, which is what EEE reports."""
    raw, normalized = payload["score"]["raw"], float(payload["score"]["normalized"])
    if scale.get("kind") == "ordinal":
        levels = scale["levels"]
        return float(levels.index(raw)) if raw in levels else normalized
    if scale.get("kind") == "range":
        try:
            return float(raw)
        except (TypeError, ValueError):
            return normalized
    return normalized


def _evaluation_result(
    *,
    name: str,
    result_id: str,
    metric: dict[str, Any],
    payloads: list[dict[str, Any]],
    lower_is_better: bool,
    generation_config: dict[str, Any] | None,
) -> dict[str, Any]:
    scale = metric.get("scale") or {}
    natives = [_native_score(scale, payload) for payload in payloads]
    normalized = [float(payload["score"]["normalized"]) for payload in payloads]
    mean = statistics.fmean(natives)
    sd = statistics.stdev(natives) if len(natives) > 1 else 0.0
    details = {
        "promptuna.normalized_mean": str(statistics.fmean(normalized)),
        "promptuna.scorings": str(len(natives)),
    }
    score_details: dict[str, Any] = {"score": mean, "details": details}
    if len(natives) > 1:
        score_details["uncertainty"] = {
            "standard_deviation": sd,
            "num_samples": len(natives),
            "standard_error": {
                "value": sd / len(natives) ** 0.5,
                "method": "analytic",
            },
        }
    result: dict[str, Any] = {
        "evaluation_result_id": result_id,
        "evaluation_name": name,
        "source_data": {
            "dataset_name": name,
            "source_type": "other",
        },
        "metric_config": _metric_config(metric, lower_is_better=lower_is_better),
        "score_details": score_details,
    }
    if generation_config is not None:
        result["generation_config"] = generation_config
    return result


def _references(reference: Any) -> list[str]:
    if reference is None:
        return []
    if isinstance(reference, (list, tuple)):
        return [str(item) for item in reference]
    return [str(reference)]


def _raw_input(inputs: dict[str, Any]) -> str:
    if len(inputs) == 1 and isinstance((value := next(iter(inputs.values()))), str):
        return value
    return json.dumps(inputs, sort_keys=True, default=str)


def _instance_rows(
    *,
    trial: dict[str, Any],
    payload: dict[str, Any],
    evaluation_name: str,
    result_id: str,
    evaluation_id: str,
    model_id: str,
) -> dict[str, Any]:
    standard = trial["example"]
    inputs = standard["inputs"]
    raw = _raw_input(inputs) if isinstance(inputs, dict) else str(inputs)
    references = _references(standard["reference"])
    telemetry = trial.get("telemetry", {})
    response = telemetry.get("response") or {}
    scale = payload["metric"].get("scale") or {}
    normalized = float(payload["score"]["normalized"])

    row: dict[str, Any] = {
        "schema_version": EEE_SCHEMA_VERSION,
        "evaluation_id": evaluation_id,
        "model_id": model_id,
        "evaluation_name": evaluation_name,
        "evaluation_result_id": result_id,
        "sample_id": str(trial["trial_id"]),
        "sample_hash": hashlib.sha256((raw + "".join(references)).encode()).hexdigest(),
        "interaction_type": "single_turn",
        "input": {
            "raw": raw,
            "formatted": telemetry.get("rendered_prompt"),
            "reference": references,
        },
        "output": {"raw": [response["content"]] if response.get("content") else []},
        "answer_attribution": [
            {
                "turn_idx": 0,
                "source": "output.raw",
                "extracted_value": str(payload["score"]["raw"]),
                "extraction_method": str(payload["metric"]["kind"]),
                "is_terminal": True,
            }
        ],
        "evaluation": {
            "score": _native_score(scale, payload),
            "is_correct": normalized >= 1.0,
        },
        "metadata": {
            "promptuna.replicate": str(trial["replicate"]),
            "promptuna.trial_status": str(trial["status"]),
            "promptuna.normalized_score": str(normalized),
        },
    }
    if payload["score"].get("reason"):
        row["metadata"]["promptuna.reason"] = str(payload["score"]["reason"])

    if response.get("input_tokens") is not None and response.get("output_tokens") is not None:
        row["token_usage"] = {
            "input_tokens": int(response["input_tokens"]),
            "output_tokens": int(response["output_tokens"]),
            "total_tokens": int(response["input_tokens"]) + int(response["output_tokens"]),
        }
    if response.get("latency") is not None:
        row["performance"] = {"latency_ms": float(response["latency"]) * 1000.0}
    if trial["status"] == "failed":
        row["error"] = str(trial.get("error", {}).get("message", "trial failed"))
    return row
