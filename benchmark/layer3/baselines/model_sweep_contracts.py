"""Typed contracts for prompt-only frontier model sweep baselines."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal, Mapping, cast

PromptMode = Literal["citation_required", "direct_json"]


@dataclass(frozen=True)
class PromptModelSpec:
    """One provider model evaluated under an identical prompt-only baseline."""

    baseline_id: str
    baseline_name: str
    provider_family: str
    model: str
    release_date: str = ""
    release_notes_url: str = ""


@dataclass(frozen=True)
class PromptModelSweepManifest:
    """Configuration for one prompt-only model sweep."""

    run_label: str
    prompt_mode: PromptMode
    temperature: float
    max_tokens: int
    input_max_chars: int
    models: tuple[PromptModelSpec, ...]
    release_cohort: str = ""
    provider_gateway: str = "integrated_openai_compatible_supplier"
    call_interface: str = "openai_chat_completions"


def load_prompt_model_sweep_manifest(path: Path) -> PromptModelSweepManifest:
    """Load and validate a prompt-only model sweep manifest."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object in {path}")
    models = tuple(_parse_model_spec(item) for item in _list(payload.get("models")))
    _validate_unique_baseline_ids(models)
    return PromptModelSweepManifest(
        run_label=str(payload.get("run_label") or path.stem),
        prompt_mode=_prompt_mode(payload.get("prompt_mode")),
        temperature=float(payload.get("temperature", 0.0)),
        max_tokens=int(payload.get("max_tokens", 4096)),
        input_max_chars=int(payload.get("input_max_chars", 50000)),
        models=models,
        release_cohort=str(payload.get("release_cohort") or ""),
        provider_gateway=str(payload.get("provider_gateway") or "integrated_openai_compatible_supplier"),
        call_interface=str(payload.get("call_interface") or "openai_chat_completions"),
    )


def _parse_model_spec(raw: object) -> PromptModelSpec:
    if not isinstance(raw, Mapping):
        raise ValueError("Each model entry must be an object")
    return PromptModelSpec(
        baseline_id=str(raw.get("baseline_id") or "").strip(),
        baseline_name=str(raw.get("baseline_name") or "").strip(),
        provider_family=str(raw.get("provider_family") or "").strip(),
        model=str(raw.get("model") or "").strip(),
        release_date=str(raw.get("release_date") or "").strip(),
        release_notes_url=str(raw.get("release_notes_url") or "").strip(),
    )


def _validate_unique_baseline_ids(models: tuple[PromptModelSpec, ...]) -> None:
    seen: set[str] = set()
    for model in models:
        if not model.baseline_id:
            raise ValueError("baseline_id is required")
        if not model.baseline_name:
            raise ValueError(f"baseline_name is required for {model.baseline_id}")
        if not model.model:
            raise ValueError(f"model is required for {model.baseline_id}")
        if model.baseline_id in seen:
            raise ValueError(f"Duplicate baseline_id: {model.baseline_id}")
        seen.add(model.baseline_id)


def _prompt_mode(value: object) -> PromptMode:
    text = str(value or "citation_required")
    if text not in {"citation_required", "direct_json"}:
        raise ValueError(f"Unsupported prompt_mode: {text}")
    return cast(PromptMode, text)


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []
