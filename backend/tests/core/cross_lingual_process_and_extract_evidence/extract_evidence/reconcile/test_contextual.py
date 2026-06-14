"""Tests for contextual verifier-driven reconcile."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SourcePrecision,
    Track,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.contextual import (
    reconcile_with_context,
)
from src.core.standardize_entities_and_align_knowledge.context_pack.contracts import (
    DiseaseContext,
    GeneContext,
    TargetContextPack,
)


def _source(snippet: str, precision: SourcePrecision = SourcePrecision.EXACT) -> SourceLocation:
    return SourceLocation(
        span_id=f"{precision.value}-span",
        page=1,
        start_offset=0,
        end_offset=len(snippet),
        context_type="text",
        context_ref="Results",
        text_snippet=snippet,
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
        document_id="doc-contextual-reconcile",
        track=track,
        evidence_items=items,
    )


def _context() -> TargetContextPack:
    return TargetContextPack(
        entry_id="clingen_024",
        gene=GeneContext(symbol="TLR5", hgnc_id=None, aliases=("TLR5",)),
        disease=DiseaseContext(
            label="systemic lupus erythematosus",
            mondo_id=None,
            aliases=("systemic lupus erythematosus", "SLE"),
            ancestor_labels=(),
        ),
        moi="AD",
        source_pmid=None,
        source_pmc=None,
    )


def _indirect_context() -> TargetContextPack:
    return TargetContextPack(
        entry_id="clingen_020",
        gene=GeneContext(symbol="GJA1", hgnc_id=None, aliases=("GJA1",)),
        disease=DiseaseContext(
            label="congenital heart disease",
            mondo_id=None,
            aliases=("congenital heart disease", "TOF"),
            ancestor_labels=(),
        ),
        moi="AD",
        source_pmid=None,
        source_pmc=None,
    )


def test_contextual_reconcile_uses_verifier_to_override_relationship_label() -> None:
    original = _result(
        Track.ORIGINAL,
        [
            _item(
                field_id="A.gene_disease_relationship",
                value="associated",
                confidence=0.7,
                source=_source(
                    "Pathogenic variants in TLR5 cause systemic lupus erythematosus "
                    "through altered innate immune signaling."
                ),
            )
        ],
    )
    translated = _result(Track.TRANSLATED, [])

    output = reconcile_with_context(original, translated, _context())

    accepted = output.result.evidence_items[0]
    assert accepted.value == "causative"
    assert output.decisions[0].accepted_score is not None
    assert output.decisions[0].accepted_score.verifier_support_score >= 0.75
    assert output.decisions[0].accepted_score.target_specificity_score == 1.0
    assert "verifier relationship override" in accepted.inference_basis


def test_contextual_reconcile_penalizes_non_target_disease_candidate() -> None:
    original = _result(
        Track.ORIGINAL,
        [
            _item(
                field_id="B.disease_diagnosis",
                value="influenza",
                confidence=0.95,
                source=_source("TLR5 is discussed across influenza, RSV, COVID-19, and Crohn's disease."),
            )
        ],
    )
    translated = _result(
        Track.TRANSLATED,
        [
            _item(
                field_id="B.disease_diagnosis",
                value="systemic lupus erythematosus",
                confidence=0.5,
                source=_source("TLR5 signaling is discussed in systemic lupus erythematosus."),
            )
        ],
    )

    output = reconcile_with_context(original, translated, _context())

    accepted = output.result.evidence_items[0]
    assert accepted.value == "systemic lupus erythematosus"
    assert output.decisions[0].accepted_score is not None
    assert output.decisions[0].accepted_score.target_specificity_score == 1.0
    assert output.result.discarded_evidence[0].value == "influenza"


def test_contextual_reconcile_turns_indirect_relationship_evidence_into_uncertain() -> None:
    original = _result(
        Track.ORIGINAL,
        [
            _item(
                field_id="A.gene_disease_relationship",
                value="associated",
                confidence=0.7,
                source=_source(
                    "This evidence suggests that transcriptional repression of these polarity "
                    "regulators may contribute to TOF pathogenesis."
                ),
            )
        ],
    )
    translated = _result(Track.TRANSLATED, [])

    output = reconcile_with_context(original, translated, _indirect_context())

    accepted = output.result.evidence_items[0]
    assert accepted.value == "uncertain"
