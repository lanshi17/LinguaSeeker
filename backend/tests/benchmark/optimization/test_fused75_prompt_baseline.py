"""Tests for fused-75 prompt-engineering baseline metadata."""

from __future__ import annotations

from benchmark.optimization.fused75.run_baseline_prompt import DEFAULT_PROMPT_BASELINE_MODEL


def test_fused75_prompt_baseline_defaults_to_first_dataset_gpt5_name() -> None:
    assert DEFAULT_PROMPT_BASELINE_MODEL == "gpt-5-2025-08-07"
