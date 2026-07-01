"""Tests for fused-75 pipeline run contracts."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from benchmark.optimization.fused75.run_contracts import (
    PipelineFlag,
    PipelineRunArtifactStatus,
    PipelineRunMetric,
    PipelineRunReport,
    PipelineVariantConfig,
    PipelineVariantDecision,
)


def _variant_config() -> PipelineVariantConfig:
    return PipelineVariantConfig(
        variant_id="contextual-reconcile-baseline",
        git_commit="a" * 40,
        dataset_split="dev",
        pipeline_flags=(
            PipelineFlag(key="use_contextual_reconcile", value=True),
            PipelineFlag(key="max_candidates", value=5),
        ),
        model_config_names=("REASONING_LLM_MODEL", "LLM_MODEL"),
    )


def _metric() -> PipelineRunMetric:
    return PipelineRunMetric(
        runtime_seconds=12.5,
        llm_call_count=7,
        prompt_token_count=1000,
        completion_token_count=250,
        total_token_count=1250,
        precision=0.8,
        recall=0.75,
        f1=0.774,
        source_visible_f1=0.812,
    )


def test_variant_config_sorts_flags_and_model_config_names_for_stable_output() -> None:
    config = PipelineVariantConfig(
        variant_id="variant-a",
        git_commit="b" * 40,
        dataset_split="test",
        pipeline_flags=(
            PipelineFlag(key="zeta", value=False),
            PipelineFlag(key="alpha", value="enabled"),
        ),
        model_config_names=("REASONING_LLM_MODEL", "LLM_MODEL"),
    )

    payload = config.model_dump(mode="json")

    assert payload["pipeline_flags"] == [
        {"key": "alpha", "value": "enabled"},
        {"key": "zeta", "value": False},
    ]
    assert payload["model_config_names"] == ["LLM_MODEL", "REASONING_LLM_MODEL"]


@pytest.mark.parametrize("dataset_split", ("dev", "test", "auto_pool"))
def test_variant_config_accepts_supported_dataset_splits(dataset_split: str) -> None:
    config = PipelineVariantConfig(
        variant_id="variant-a",
        git_commit="c" * 40,
        dataset_split=dataset_split,
        pipeline_flags=(),
        model_config_names=("LLM_MODEL",),
    )

    assert config.dataset_split == dataset_split


def test_variant_config_rejects_invalid_dataset_split() -> None:
    with pytest.raises(ValidationError, match="dataset_split"):
        PipelineVariantConfig(
            variant_id="variant-a",
            git_commit="d" * 40,
            dataset_split="adjudication_dev",
            pipeline_flags=(),
            model_config_names=("LLM_MODEL",),
        )


def test_metric_rejects_negative_runtime_calls_and_tokens() -> None:
    with pytest.raises(ValidationError, match="runtime_seconds"):
        PipelineRunMetric(
            runtime_seconds=-0.1,
            llm_call_count=0,
            prompt_token_count=0,
            completion_token_count=0,
            total_token_count=0,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            source_visible_f1=0.0,
        )


def test_metric_rejects_token_total_mismatch() -> None:
    with pytest.raises(ValidationError, match="total_token_count"):
        PipelineRunMetric(
            runtime_seconds=1.0,
            llm_call_count=1,
            prompt_token_count=10,
            completion_token_count=5,
            total_token_count=99,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            source_visible_f1=0.0,
        )


@pytest.mark.parametrize("field_name", ("precision", "recall", "f1", "source_visible_f1"))
def test_metric_rejects_scores_outside_unit_interval(field_name: str) -> None:
    payload = {
        "runtime_seconds": 1.0,
        "llm_call_count": 1,
        "prompt_token_count": 10,
        "completion_token_count": 5,
        "total_token_count": 15,
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
        "source_visible_f1": 0.5,
    }
    payload[field_name] = 1.01

    with pytest.raises(ValidationError, match=field_name):
        PipelineRunMetric(**payload)


@pytest.mark.parametrize("decision", ("accepted", "rejected", "checkpoint_only"))
def test_decision_accepts_supported_values(decision: str) -> None:
    result = PipelineVariantDecision(decision=decision, reason="meets gate")

    assert result.decision == decision


def test_decision_rejects_invalid_value() -> None:
    with pytest.raises(ValidationError, match="decision"):
        PipelineVariantDecision(decision="promoted", reason="bad value")


def test_report_serializes_deterministically_without_public_bare_dict_helper() -> None:
    report = PipelineRunReport(
        config=_variant_config(),
        metric=_metric(),
        decision=PipelineVariantDecision(decision="checkpoint_only", reason="record dev checkpoint"),
        artifact_status=PipelineRunArtifactStatus(
            expected_entry_count=2,
            evaluated_entry_count=1,
            missing_artifact_entry_ids=("fused_001",),
        ),
    )

    first_payload = report.to_stable_json()
    second_payload = report.to_stable_json()
    decoded = json.loads(first_payload)

    assert first_payload == second_payload
    assert list(decoded) == ["artifact_status", "config", "decision", "metric"]
    assert decoded["config"]["git_commit"] == "a" * 40
    assert decoded["metric"]["source_visible_f1"] == 0.812
    assert decoded["artifact_status"]["evaluated_entry_count"] == 1


def test_artifact_status_rejects_inconsistent_counts() -> None:
    with pytest.raises(ValidationError, match="artifact counts"):
        PipelineRunArtifactStatus(
            expected_entry_count=3,
            evaluated_entry_count=1,
            missing_artifact_entry_ids=("fused_001",),
        )
