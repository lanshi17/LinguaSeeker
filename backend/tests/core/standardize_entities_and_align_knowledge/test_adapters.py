"""Tests for adapting Phase 2 dual extraction output into Phase 3 input."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
    EvidenceChain,
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    Track,
)
from src.core.standardize_entities_and_align_knowledge.adapters import DualResultAdapter
from src.core.standardize_entities_and_align_knowledge.contracts import EntityType


def test_dual_result_adapter_extracts_chain_candidates() -> None:
    """The adapter turns evidence-chain fields into gene/disease/variant candidates."""
    result = DualEvidenceExtractionResult(
        document_id="doc-1",
        original_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-1",
            track=Track.ORIGINAL,
            evidence_chains=[
                EvidenceChain(
                    chain_id="gene=BRCA1|variant=c.5946del",
                    gene_text="BRCA1",
                    disease_text="Breast cancer",
                    variant_text="c.5946del",
                ),
            ],
        ),
        translated_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-1",
            track=Track.TRANSLATED,
        ),
    )

    adapter = DualResultAdapter()
    output = adapter.to_standardization_input(
        result,
        source_document_id="source-1",
        processing_run_id="run-1",
    )

    assert [candidate.entity_type for candidate in output.candidates] == [
        EntityType.GENE,
        EntityType.DISEASE,
        EntityType.VARIANT,
    ]


def test_dual_result_adapter_extracts_phenotypes_from_supported_fields() -> None:
    """The adapter extracts phenotype candidates from phenotype-bearing evidence fields."""
    result = DualEvidenceExtractionResult(
        document_id="doc-2",
        original_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-2",
            track=Track.ORIGINAL,
            evidence_items=[
                EvidenceItem(
                    field_id="B.hpo_terms",
                    category="B",
                    field_name="HPO phenotype terms",
                    status=EvidenceStatus.FOUND,
                    value=["HP:0001250", "Seizure"],
                    confidence=0.9,
                    group_id="gene=SCN1A|variant=__missing__",
                ),
                EvidenceItem(
                    field_id="B.clinical_phenotypes",
                    category="B",
                    field_name="Key clinical phenotypes",
                    status=EvidenceStatus.FOUND,
                    value="Developmental delay",
                    confidence=0.9,
                    group_id="gene=SCN1A|variant=__missing__",
                ),
            ],
        ),
        translated_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-2",
            track=Track.TRANSLATED,
        ),
    )

    adapter = DualResultAdapter()
    output = adapter.to_standardization_input(
        result,
        source_document_id="source-2",
        processing_run_id="run-2",
    )

    phenotype_texts = [candidate.raw_text for candidate in output.candidates if candidate.entity_type == EntityType.PHENOTYPE]
    assert phenotype_texts == ["HP:0001250", "Seizure", "Developmental delay"]


def test_dual_result_adapter_deduplicates_same_chain_across_tracks() -> None:
    """The adapter keeps one candidate when original and translated tracks repeat the same chain text."""
    chain = EvidenceChain(
        chain_id="gene=BRCA1|variant=c.5946del",
        gene_text="BRCA1",
        disease_text="Breast cancer",
        variant_text="c.5946del",
    )
    result = DualEvidenceExtractionResult(
        document_id="doc-3",
        original_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-3",
            track=Track.ORIGINAL,
            evidence_chains=[chain],
        ),
        translated_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-3",
            track=Track.TRANSLATED,
            evidence_chains=[chain],
        ),
    )

    output = DualResultAdapter().to_standardization_input(
        result,
        source_document_id="source-3",
        processing_run_id="run-3",
    )

    gene_candidates = [candidate for candidate in output.candidates if candidate.entity_type == EntityType.GENE]
    assert len(gene_candidates) == 1
    assert gene_candidates[0].track == "original"
