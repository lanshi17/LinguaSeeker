"""Tests for prompt-only model sweep runner."""
from __future__ import annotations

from pathlib import Path

from benchmark.layer3.baselines.model_sweep_contracts import PromptModelSpec, PromptModelSweepManifest
from benchmark.layer3.baselines.prompt_model_sweep import build_baseline_config


def test_build_baseline_config_records_model_metadata(tmp_path: Path) -> None:
    manifest = PromptModelSweepManifest(
        run_label="prompt_frontier_20260615",
        prompt_mode="citation_required",
        temperature=0.0,
        max_tokens=4096,
        input_max_chars=50000,
        models=(),
    )
    spec = PromptModelSpec(
        baseline_id="B6_GPT5_PROMPT_CITE",
        baseline_name="GPT-5 prompt-only citation-required",
        provider_family="openai",
        model="gpt-5",
    )

    config = build_baseline_config(
        manifest=manifest,
        spec=spec,
        ground_truth_dir=tmp_path / "gt",
        reports_dir=tmp_path / "reports",
        entry_ids=("clingen_000",),
        limit=None,
        save_report=True,
    )

    assert config.baseline_id == "B6_GPT5_PROMPT_CITE"
    assert config.metadata["model"] == "gpt-5"
    assert config.metadata["prompt_mode"] == "citation_required"
    assert config.metadata["run_label"] == "prompt_frontier_20260615"
