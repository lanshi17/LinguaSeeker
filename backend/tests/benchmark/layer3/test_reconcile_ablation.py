"""Tests for offline cross-track reconcile ablation reports."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.analysis.reconcile.ablation import (
    AblationConfig,
    AblationStrategy,
    build_extracted_items,
    run_ablation,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SourcePrecision,
    Track,
)
from src.core.standardize_entities_and_align_knowledge.context_pack.contracts import (
    DiseaseContext,
    GeneContext,
    TargetContextPack,
)


def _source(precision: SourcePrecision) -> SourceLocation:
    return SourceLocation(
        span_id=f"{precision.value}-span",
        page=1,
        start_offset=0,
        end_offset=8,
        context_type="text",
        context_ref="Results",
        text_snippet="evidence",
        source_precision=precision,
    )


def _item(
    *,
    field_id: str,
    value: str,
    confidence: float = 0.8,
    source: SourceLocation | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id.split(".", maxsplit=1)[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=confidence,
        source=source,
    )


def _result(track: Track, items: list[EvidenceItem]) -> EvidenceExtractionResult:
    return EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc-ablation",
        track=track,
        evidence_items=items,
    )


def _dual_result() -> DualEvidenceExtractionResult:
    return DualEvidenceExtractionResult(
        document_id="doc-ablation",
        original_result=_result(
            Track.ORIGINAL,
            [
                _item(field_id="A.gene_symbol", value="BRCA2", confidence=1.0),
                _item(
                    field_id="B.disease_diagnosis",
                    value="Breast cancer",
                    confidence=0.7,
                    source=_source(SourcePrecision.EXACT),
                ),
            ],
        ),
        translated_result=_result(
            Track.TRANSLATED,
            [
                _item(
                    field_id="A.gene_symbol",
                    value="BRCA1",
                    confidence=0.4,
                    source=_source(SourcePrecision.EXACT),
                ),
                _item(field_id="B.disease_diagnosis", value="Breast carcinoma", confidence=0.7),
            ],
        ),
    )


def _context() -> TargetContextPack:
    return TargetContextPack(
        entry_id="clingen_test",
        gene=GeneContext(symbol="BRCA1", hgnc_id=None, aliases=("BRCA1",)),
        disease=DiseaseContext(
            label="Breast cancer",
            mondo_id=None,
            aliases=("Breast cancer", "breast cancer"),
            ancestor_labels=(),
        ),
        moi="AD",
        source_pmid=None,
        source_pmc=None,
    )


def test_dual_union_strategy_returns_both_track_items() -> None:
    items = build_extracted_items(_dual_result(), AblationStrategy.DUAL_UNION)

    assert [item["value"] for item in items] == [
        "BRCA2",
        "Breast cancer",
        "BRCA1",
        "Breast carcinoma",
    ]


def test_grounded_hard_rule_prefers_grounded_candidate_per_field() -> None:
    items = build_extracted_items(_dual_result(), AblationStrategy.GROUNDED_HARD_RULE)

    by_field = {str(item["field_id"]): item for item in items}
    assert by_field["A.gene_symbol"]["value"] == "BRCA1"
    assert by_field["A.gene_symbol"]["source_span"]["source_precision"] == "exact"
    assert by_field["B.disease_diagnosis"]["value"] == "Breast cancer"


def test_source_grounded_reconcile_strategy_uses_weighted_reconcile() -> None:
    items = build_extracted_items(_dual_result(), AblationStrategy.SOURCE_GROUNDED_RECONCILE)

    by_field = {str(item["field_id"]): item for item in items}
    assert by_field["A.gene_symbol"]["value"] == "BRCA1"
    assert by_field["B.disease_diagnosis"]["value"] == "Breast cancer"


def test_context_verifier_reconcile_strategy_uses_target_safe_context() -> None:
    result = DualEvidenceExtractionResult(
        document_id="doc-ablation",
        original_result=_result(
            Track.ORIGINAL,
            [
                _item(
                    field_id="A.gene_disease_relationship",
                    value="associated",
                    confidence=0.7,
                    source=SourceLocation(
                        span_id="causal-span",
                        page=1,
                        start_offset=0,
                        end_offset=60,
                        context_type="text",
                        context_ref="Results",
                        text_snippet="Pathogenic variants in BRCA1 cause Breast cancer.",
                        source_precision=SourcePrecision.EXACT,
                    ),
                )
            ],
        ),
        translated_result=_result(Track.TRANSLATED, []),
    )

    items = build_extracted_items(
        result,
        AblationStrategy.CONTEXT_VERIFIER_RECONCILE,
        context_pack=_context(),
    )

    assert items[0]["value"] == "causative"


def test_context_verifier_reconcile_exposes_score_components() -> None:
    result = DualEvidenceExtractionResult(
        document_id="doc-ablation",
        original_result=_result(
            Track.ORIGINAL,
            [
                _item(
                    field_id="A.gene_disease_relationship",
                    value="associated",
                    confidence=0.7,
                    source=SourceLocation(
                        span_id="causal-span",
                        page=1,
                        start_offset=0,
                        end_offset=60,
                        context_type="text",
                        context_ref="Results",
                        text_snippet="Pathogenic variants in BRCA1 cause Breast cancer.",
                        source_precision=SourcePrecision.EXACT,
                    ),
                )
            ],
        ),
        translated_result=_result(Track.TRANSLATED, []),
    )

    items = build_extracted_items(
        result,
        AblationStrategy.CONTEXT_VERIFIER_RECONCILE,
        context_pack=_context(),
    )

    assert items[0]["best_score"] > 0
    assert items[0]["source_score"] == 1.0
    assert items[0]["confidence_score"] == 0.7
    assert items[0]["verifier_support_score"] > 0
    assert items[0]["target_specificity_score"] == 1.0
    assert items[0]["contradiction_penalty"] == 0.0
    assert items[0]["accepted_track"] == "original"
    assert items[0]["normalized_value"] == "causative"


def test_run_ablation_compares_all_strategies_on_same_entries(tmp_path: Path) -> None:
    entry_id = "clingen_test"
    entry_dir = tmp_path / entry_id
    artifact_dir = entry_dir / "preprocessed" / "phase_2"
    artifact_dir.mkdir(parents=True)
    (tmp_path / "selection.json").write_text(
        json.dumps(
            [
                {
                    "entry_id": entry_id,
                    "gene_symbol": "BRCA1",
                    "disease_label": "Breast cancer",
                    "classification": "definitive",
                    "moi": "AD",
                }
            ]
        ),
        encoding="utf-8",
    )
    (entry_dir / "expected.json").write_text(
        json.dumps(
            {
                "expected_evidence": [
                    {"field_id": "A.gene_symbol", "value": "BRCA1"},
                    {"field_id": "B.disease_diagnosis", "value": "Breast cancer"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "extraction_result.json").write_text(
        _dual_result().model_dump_json(),
        encoding="utf-8",
    )

    report = run_ablation(
        AblationConfig(
            ground_truth_dir=tmp_path,
            reports_dir=tmp_path / "reports",
            save_report=False,
        )
    )

    assert [strategy.strategy for strategy in report.strategies] == [
        AblationStrategy.DUAL_UNION,
        AblationStrategy.GROUNDED_HARD_RULE,
        AblationStrategy.SOURCE_GROUNDED_RECONCILE,
        AblationStrategy.CONTEXT_VERIFIER_RECONCILE,
    ]
    by_strategy = {strategy.strategy: strategy for strategy in report.strategies}
    assert by_strategy[AblationStrategy.DUAL_UNION].aggregates["overall"]["false_positives"] == 2
    assert by_strategy[AblationStrategy.GROUNDED_HARD_RULE].aggregates["overall"]["f1"] == 1.0
    assert by_strategy[AblationStrategy.SOURCE_GROUNDED_RECONCILE].total_entries == 1
    assert by_strategy[AblationStrategy.SOURCE_GROUNDED_RECONCILE].status_counts == {"completed": 1}
    assert by_strategy[AblationStrategy.CONTEXT_VERIFIER_RECONCILE].status_counts == {"completed": 1}


def test_run_ablation_counts_missing_artifacts(tmp_path: Path) -> None:
    entry_id = "clingen_missing"
    entry_dir = tmp_path / entry_id
    entry_dir.mkdir()
    (tmp_path / "selection.json").write_text(
        json.dumps([{"entry_id": entry_id, "gene_symbol": "BRCA1"}]),
        encoding="utf-8",
    )
    (entry_dir / "expected.json").write_text(
        json.dumps({"expected_evidence": [{"field_id": "A.gene_symbol", "value": "BRCA1"}]}),
        encoding="utf-8",
    )

    report = run_ablation(
        AblationConfig(
            ground_truth_dir=tmp_path,
            reports_dir=tmp_path / "reports",
            save_report=False,
        )
    )

    assert report.strategies[0].status_counts == {"missing_artifact": 1}
