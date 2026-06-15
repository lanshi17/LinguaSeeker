"""Tests for prompt-only model baseline paper tables."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.layer3.analysis.prompt_model_baseline_tables import build_prompt_model_table


def test_build_prompt_model_table_combines_extraction_and_traceability(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline_b6.json"
    traceability_path = tmp_path / "traceability_b6.json"
    baseline_path.write_text(
        json.dumps(
            {
                "baseline_id": "B6_GPT5_PROMPT_CITE",
                "baseline_name": "GPT-5 prompt-only citation-required",
                "config": {
                    "release_cohort": "frontier_2025q3_q4_aug07_sep30",
                    "provider_gateway": "integrated_openai_compatible_supplier",
                    "call_interface": "openai_chat_completions",
                    "model": "gpt-5",
                    "release_date": "2025-08-07",
                    "release_notes_url": "https://openai.com/index/introducing-gpt-5-for-developers/",
                    "provider_family": "openai",
                    "prompt_mode": "citation_required",
                },
                "total_entries": 30,
                "total_duration_s": 300.0,
                "aggregates": {"overall": {"precision": 0.9, "recall": 0.8, "f1": 0.8471}},
                "per_entry": [],
            }
        ),
        encoding="utf-8",
    )
    traceability_path.write_text(
        json.dumps(
            {
                "strategy_or_baseline_id": "B6_GPT5_PROMPT_CITE",
                "overall": {
                    "traceability": {
                        "citation_validity_rate": 0.75,
                        "hallucinated_citation_rate": 0.25,
                        "span_boundary_f1": 0.7,
                        "evidence_support_rate": 0.8,
                        "traceable_f1": 0.6353,
                        "cross_lingual_consistency": None,
                    }
                },
                "counts": {"citation_total": 10},
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )

    table = build_prompt_model_table(
        baseline_report_paths=(baseline_path,),
        traceability_report_paths=(traceability_path,),
        candidate_f1=0.9474,
        candidate_traceable_f1=0.9474,
    )

    row = table.rows[0]
    assert row["baseline_id"] == "B6_GPT5_PROMPT_CITE"
    assert row["release_cohort"] == "frontier_2025q3_q4_aug07_sep30"
    assert row["provider_gateway"] == "integrated_openai_compatible_supplier"
    assert row["call_interface"] == "openai_chat_completions"
    assert row["release_date"] == "2025-08-07"
    assert row["model"] == "gpt-5"
    assert row["f1"] == 0.8471
    assert row["delta_f1_vs_ours"] == -0.1003
    assert row["traceable_f1"] == 0.6353
