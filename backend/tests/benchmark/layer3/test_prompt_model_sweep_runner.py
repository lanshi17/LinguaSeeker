"""Tests for prompt-only model sweep runner."""
from __future__ import annotations

from pathlib import Path

from benchmark.layer3.baselines.model_sweep_contracts import PromptModelSpec, PromptModelSweepManifest
import pytest

from benchmark.layer3.baselines.prompt_model_sweep import (
    build_baseline_config,
    build_extractor,
    run_model_sweep,
)


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
    assert config.metadata["release_cohort"] == ""
    assert config.metadata["release_date"] == ""
    assert config.metadata["release_notes_url"] == ""
    assert config.metadata["prompt_mode"] == "citation_required"
    assert config.metadata["run_label"] == "prompt_frontier_20260615"
    assert config.metadata["provider_gateway"] == "integrated_openai_compatible_supplier"
    assert config.metadata["call_interface"] == "openai_chat_completions"


def test_build_extractor_uses_manifest_input_max_chars(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_make_extractor(**kwargs):  # noqa: ANN001
        calls.append(kwargs)
        return object()

    monkeypatch.setattr("benchmark.layer3.baselines.prompt_model_sweep.make_extractor", fake_make_extractor)
    manifest = PromptModelSweepManifest(
        run_label="prompt_frontier_20260615",
        prompt_mode="citation_required",
        temperature=0.0,
        max_tokens=4096,
        input_max_chars=12000,
        models=(),
    )
    spec = PromptModelSpec(
        baseline_id="B6_GPT5_PROMPT_CITE",
        baseline_name="GPT-5 prompt-only citation-required",
        provider_family="openai",
        model="gpt-5",
    )

    build_extractor(manifest=manifest, spec=spec)

    assert calls == [
        {
            "mode": "citation_required",
            "model_override": "gpt-5",
            "temperature": 0.0,
            "max_tokens_override": 4096,
            "input_max_chars": 12000,
            "use_raw_client": True,
        }
    ]


def test_build_extractor_uses_raw_client_by_default(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_make_extractor(**kwargs):  # noqa: ANN001
        calls.append(kwargs)
        return object()

    monkeypatch.setattr("benchmark.layer3.baselines.prompt_model_sweep.make_extractor", fake_make_extractor)
    manifest = PromptModelSweepManifest(
        run_label="prompt_frontier_20260615",
        prompt_mode="citation_required",
        temperature=0.0,
        max_tokens=4096,
        input_max_chars=12000,
        models=(),
    )
    spec = PromptModelSpec(
        baseline_id="B6_GPT5_PROMPT_CITE",
        baseline_name="GPT-5 prompt-only citation-required",
        provider_family="openai",
        model="gpt-5",
    )

    build_extractor(manifest=manifest, spec=spec)

    assert calls[0]["use_raw_client"] is True


@pytest.mark.asyncio
async def test_run_model_sweep_continues_after_model_failure(monkeypatch, tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        """
        {
          "run_label": "prompt_frontier_20260615",
          "prompt_mode": "citation_required",
          "models": [
            {"baseline_id": "B6", "baseline_name": "bad", "provider_family": "x", "model": "bad-model"},
            {"baseline_id": "B7", "baseline_name": "good", "provider_family": "x", "model": "good-model"}
          ]
        }
        """,
        encoding="utf-8",
    )
    calls: list[str] = []

    def fake_build_extractor(*, manifest, spec):  # noqa: ANN001
        if spec.model == "bad-model":
            raise RuntimeError("provider unavailable")
        return type("Extractor", (), {"extract": object()})()

    async def fake_run_baseline_evaluation(config, extractor):  # noqa: ANN001, ARG001
        calls.append(config.baseline_id)
        return type("Report", (), {"report_path": tmp_path / f"{config.baseline_id}.json"})()

    monkeypatch.setattr("benchmark.layer3.baselines.prompt_model_sweep.build_extractor", fake_build_extractor)
    monkeypatch.setattr(
        "benchmark.layer3.baselines.prompt_model_sweep.run_baseline_evaluation",
        fake_run_baseline_evaluation,
    )

    reports = await run_model_sweep(manifest_path=manifest_path, continue_on_error=True)

    assert calls == ["B7"]
    assert reports == [tmp_path / "B7.json"]
