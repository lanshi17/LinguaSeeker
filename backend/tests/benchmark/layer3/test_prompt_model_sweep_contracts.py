"""Tests for prompt-only model sweep manifest contracts."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.analysis.baselines.model_sweep_contracts import (
    PromptModelSpec,
    load_prompt_model_sweep_manifest,
)


def test_load_prompt_model_sweep_manifest_keeps_model_aliases(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_label": "prompt_frontier_20260615",
                "release_cohort": "frontier_2025q3_q4_aug07_sep30",
                "provider_gateway": "integrated_openai_compatible_supplier",
                "call_interface": "openai_chat_completions",
                "prompt_mode": "citation_required",
                "temperature": 0.0,
                "max_tokens": 4096,
                "input_max_chars": 50000,
                "models": [
                    {
                        "baseline_id": "B6_GPT5_PROMPT_CITE",
                        "baseline_name": "GPT-5 prompt-only citation-required",
                        "provider_family": "openai",
                        "model": "gpt-5",
                        "release_date": "2025-08-07",
                        "release_notes_url": "https://openai.com/index/introducing-gpt-5-for-developers/",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = load_prompt_model_sweep_manifest(manifest_path)

    assert manifest.run_label == "prompt_frontier_20260615"
    assert manifest.release_cohort == "frontier_2025q3_q4_aug07_sep30"
    assert manifest.provider_gateway == "integrated_openai_compatible_supplier"
    assert manifest.call_interface == "openai_chat_completions"
    assert manifest.prompt_mode == "citation_required"
    assert manifest.models == (
        PromptModelSpec(
            baseline_id="B6_GPT5_PROMPT_CITE",
            baseline_name="GPT-5 prompt-only citation-required",
            provider_family="openai",
            model="gpt-5",
            release_date="2025-08-07",
            release_notes_url="https://openai.com/index/introducing-gpt-5-for-developers/",
        ),
    )


def test_load_prompt_model_sweep_manifest_rejects_duplicate_baseline_ids(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_label": "bad",
                "prompt_mode": "citation_required",
                "models": [
                    {
                        "baseline_id": "B6",
                        "baseline_name": "one",
                        "provider_family": "x",
                        "model": "m1",
                    },
                    {
                        "baseline_id": "B6",
                        "baseline_name": "two",
                        "provider_family": "x",
                        "model": "m2",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate baseline_id"):
        load_prompt_model_sweep_manifest(manifest_path)
