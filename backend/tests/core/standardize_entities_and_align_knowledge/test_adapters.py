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
                    chain_id="chain-1",
                    gene_text="BRCA1",
                    disease_text="Breast cancer",
                    variant_text="NM_007294.4:c.5266dup",
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
        result, source_document_id="source-1", processing_run_id="run-1",
    )

    assert [candidate.entity_type for candidate in output.candidates] == [
        EntityType.GENE, EntityType.DISEASE, EntityType.VARIANT,
    ]
    variant_candidate = output.candidates[2]
    assert variant_candidate.metadata["gene_symbol"] == "BRCA1"


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
                    field_name="HPO terms",
                    status=EvidenceStatus.FOUND,
                    value=["HP:0001250", "Seizure"],
                    confidence=0.95,
                ),
                EvidenceItem(
                    field_id="B.clinical_phenotypes",
                    category="B",
                    field_name="Clinical phenotypes",
                    status=EvidenceStatus.FOUND,
                    value="Developmental delay",
                    confidence=0.9,
                ),
                EvidenceItem(
                    field_id="A.gene_symbol",
                    category="A",
                    field_name="Gene symbol",
                    status=EvidenceStatus.FOUND,
                    value="BRCA1",
                    confidence=0.99,
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
        result, source_document_id="source-2", processing_run_id="run-2",
    )

    phenotype_texts = [candidate.raw_text for candidate in output.candidates if candidate.entity_type == EntityType.PHENOTYPE]
    assert phenotype_texts == ["HP:0001250", "Seizure", "Developmental delay"]


def test_dual_result_adapter_deduplicates_same_chain_across_tracks() -> None:
    """The adapter keeps one candidate when original and translated tracks repeat the same chain text."""
    chain = EvidenceChain(chain_id="chain-dedup", gene_text="GAA", disease_text="Pompe disease")
    result = DualEvidenceExtractionResult(
        document_id="doc-dedup",
        original_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-dedup",
            track=Track.ORIGINAL,
            evidence_chains=[chain],
        ),
        translated_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-dedup",
            track=Track.TRANSLATED,
            evidence_chains=[chain],
        ),
    )

    adapter = DualResultAdapter()
    output = adapter.to_standardization_input(
        result, source_document_id="source-dedup", processing_run_id="run-dedup",
    )

    gene_candidates = [c for c in output.candidates if c.entity_type == EntityType.GENE]
    assert len(gene_candidates) == 1
    assert gene_candidates[0].raw_text == "GAA"
    assert gene_candidates[0].track == "original"


def test_dual_result_adapter_splits_chinese_compound_phenotypes() -> None:
    """The adapter splits 顿号-separated Chinese phenotype strings into individual candidates."""
    result = DualEvidenceExtractionResult(
        document_id="doc-zh",
        original_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-zh",
            track=Track.ORIGINAL,
            evidence_items=[
                EvidenceItem(
                    field_id="B.clinical_phenotypes",
                    category="B",
                    field_name="Clinical phenotypes",
                    status=EvidenceStatus.FOUND,
                    value="水肿、蛋白尿、心律失常",
                    confidence=0.9,
                ),
            ],
        ),
        translated_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-zh",
            track=Track.TRANSLATED,
        ),
    )

    adapter = DualResultAdapter()
    output = adapter.to_standardization_input(
        result, source_document_id="source-zh", processing_run_id="run-zh",
    )

    phenotype_texts = [c.raw_text for c in output.candidates if c.entity_type == EntityType.PHENOTYPE]
    assert phenotype_texts == ["水肿", "蛋白尿", "心律失常"]


def test_dual_result_adapter_splits_english_comma_phenotypes() -> None:
    """The adapter splits comma-separated English phenotype strings into individual candidates."""
    result = DualEvidenceExtractionResult(
        document_id="doc-en",
        original_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-en",
            track=Track.ORIGINAL,
            evidence_items=[
                EvidenceItem(
                    field_id="B.clinical_phenotypes",
                    category="B",
                    field_name="Clinical phenotypes",
                    status=EvidenceStatus.FOUND,
                    value="edema,proteinuria,arrhythmia",
                    confidence=0.9,
                ),
            ],
        ),
        translated_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-en",
            track=Track.TRANSLATED,
        ),
    )

    adapter = DualResultAdapter()
    output = adapter.to_standardization_input(
        result, source_document_id="s1", processing_run_id="r1",
    )
    phenotype_texts = [c.raw_text for c in output.candidates if c.entity_type == EntityType.PHENOTYPE]
    assert phenotype_texts == ["edema", "proteinuria", "arrhythmia"]


def test_dual_result_adapter_carries_target_and_phenotype_evidence() -> None:
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        DualEvidenceExtractionResult,
        EvidenceExtractionResult,
        EvidenceExtractionStatus,
        EvidenceItem,
        EvidenceRole,
        EvidenceStatus,
        ExtractionTarget,
        Track,
    )
    target = ExtractionTarget(gene_symbol="AARS2", disease_name="AARS2-related leukodystrophy")
    result = DualEvidenceExtractionResult(
        document_id="doc-target",
        original_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-target",
            track=Track.ORIGINAL,
            extraction_target=target,
            phenotype_evidence=[
                EvidenceItem(
                    field_id="B.disease_diagnosis",
                    category="B",
                    field_name="Disease diagnosis",
                    status=EvidenceStatus.FOUND,
                    value="COXPD8",
                    confidence=0.9,
                    group_id="gene=AARS2|variant=__missing__",
                    evidence_role=EvidenceRole.PHENOTYPE,
                )
            ],
        ),
        translated_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-target",
            track=Track.TRANSLATED,
            extraction_target=target,
        ),
    )

    output = DualResultAdapter().to_standardization_input(
        result,
        source_document_id="source",
        processing_run_id="run",
    )

    assert output.extraction_target == target
    assert any(candidate.raw_text == "COXPD8" for candidate in output.candidates)
