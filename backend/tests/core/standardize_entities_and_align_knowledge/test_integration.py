"""Integration-style tests for the Phase 3 facade wiring."""
from __future__ import annotations

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
    EvidenceChain,
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    Track,
)
from src.core.standardize_entities_and_align_knowledge import api as api_module
from src.core.standardize_entities_and_align_knowledge.contracts import (
    EntityMatch,
    EntityType,
    TerminologyCandidate,
)


class FakeRepository:
    """In-memory repository used to exercise facade wiring end to end."""

    def __init__(self, lookup):
        self._lookup = lookup
        self.normalized: list[EntityMatch] = []
        self.run_items: list[tuple[object, tuple[EntityMatch, ...]]] = []
        self.bindings: list[tuple[object, tuple[EntityMatch, ...], tuple[str, ...]]] = []
        self.canonical: list[tuple[object, tuple[EntityMatch, ...], tuple[str, ...]]] = []

    async def find_alias_candidates(self, entity_type, raw_text):
        return self._lookup.get((entity_type, raw_text), ())

    async def upsert_normalized_entity(self, match):
        self.normalized.append(match)
        if match.external_id:
            return f"entity:{match.external_id}"
        return f"entity:raw:{match.candidate.candidate_id}"

    async def persist_run_evidence(self, input_data, matches):
        self.run_items.append((input_data, matches))
        return tuple(f"run-item-{index}" for index, _ in enumerate(matches, start=1))

    async def persist_bindings(self, input_data, matches, entity_ids):
        self.bindings.append((input_data, matches, entity_ids))

    async def upsert_canonical_evidence(self, input_data, matches, entity_ids):
        self.canonical.append((input_data, matches, entity_ids))


def build_minimal_dual_result(*, gene: str, disease: str, variant: str, phenotype: str) -> DualEvidenceExtractionResult:
    """Build a minimal dual-track extraction result for facade integration tests."""
    original = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc-1",
        track=Track.ORIGINAL,
        evidence_chains=[
            EvidenceChain(
                chain_id="gene=BRCA1|variant=rs80359550",
                gene_text=gene,
                disease_text=disease,
                variant_text=variant,
            ),
        ],
        evidence_items=[
            EvidenceItem(
                field_id="B.clinical_phenotypes",
                category="B",
                field_name="Key clinical phenotypes",
                status=EvidenceStatus.FOUND,
                value=phenotype,
                confidence=0.9,
                group_id="gene=BRCA1|variant=rs80359550",
            ),
        ],
    )
    translated = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc-1",
        track=Track.TRANSLATED,
        evidence_chains=[
            EvidenceChain(
                chain_id="gene=BRCA1|variant=rs80359550",
                gene_text=gene,
                disease_text=disease,
                variant_text=variant,
            ),
        ],
    )
    return DualEvidenceExtractionResult(
        document_id="doc-1",
        original_result=original,
        translated_result=translated,
    )


def build_service_with_fake_repository(monkeypatch: pytest.MonkeyPatch) -> api_module.EntityStandardizationService:
    """Create the facade service with an in-memory repository implementation."""
    lookup = {
        (EntityType.GENE, "BRCA1"): (
            TerminologyCandidate(
                entry_id="gene-1",
                entity_type=EntityType.GENE,
                source_db="HGNC",
                external_id="HGNC:1100",
                display_name="BRCA1",
                normalized_alias="brca1",
                alias_type="primary",
            ),
        ),
        (EntityType.DISEASE, "Breast cancer"): (
            TerminologyCandidate(
                entry_id="disease-1",
                entity_type=EntityType.DISEASE,
                source_db="OMIM",
                external_id="OMIM:114480",
                display_name="Breast cancer",
                normalized_alias="breast cancer",
                alias_type="name",
            ),
        ),
        (EntityType.VARIANT, "rs80359550"): (
            TerminologyCandidate(
                entry_id="variant-1",
                entity_type=EntityType.VARIANT,
                source_db="ClinVar",
                external_id="ClinVarVariation:12345",
                display_name="rs80359550",
                normalized_alias="rs80359550",
                alias_type="rsid",
            ),
        ),
        (EntityType.PHENOTYPE, "Breast carcinoma"): (
            TerminologyCandidate(
                entry_id="phenotype-1",
                entity_type=EntityType.PHENOTYPE,
                source_db="HPO",
                external_id="HP:0100013",
                display_name="Breast carcinoma",
                normalized_alias="breast carcinoma",
                alias_type="name",
            ),
        ),
    }

    monkeypatch.setattr(api_module, "StandardizationRepository", FakeRepository)
    return api_module.EntityStandardizationService(cfg=object(), session=lookup)


@pytest.mark.asyncio
async def test_dual_result_standardization_pipeline_standardizes_gene_variant_disease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The facade wires adapter, matcher, and service to standardize a minimal dual result."""
    result = build_minimal_dual_result(
        gene="BRCA1",
        disease="Breast cancer",
        variant="rs80359550",
        phenotype="Breast carcinoma",
    )
    service = build_service_with_fake_repository(monkeypatch)

    output = await service.run_dual_result(
        result,
        source_document_id="source-1",
        processing_run_id="run-1",
    )

    assert output.standardized_count == 4  # gene + disease + variant + phenotype
    assert output.ambiguous_count == 0


@pytest.mark.asyncio
async def test_dual_result_standardization_pipeline_reports_unmapped_and_ambiguous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The facade preserves mixed match statuses and still persists all candidates."""
    result = build_minimal_dual_result(
        gene="BRCA1",
        disease="Breast cancer",
        variant="rs80359550",
        phenotype="Unmapped phenotype",
    )
    lookup = {
        (EntityType.GENE, "BRCA1"): (
            TerminologyCandidate(
                entry_id="gene-1",
                entity_type=EntityType.GENE,
                source_db="HGNC",
                external_id="HGNC:1100",
                display_name="BRCA1",
                normalized_alias="brca1",
                alias_type="primary",
            ),
        ),
        (EntityType.DISEASE, "Breast cancer"): (
            TerminologyCandidate(
                entry_id="disease-1",
                entity_type=EntityType.DISEASE,
                source_db="OMIM",
                external_id="OMIM:114480",
                display_name="Breast cancer",
                normalized_alias="breast cancer",
                alias_type="name",
            ),
            TerminologyCandidate(
                entry_id="disease-2",
                entity_type=EntityType.DISEASE,
                source_db="OMIM",
                external_id="OMIM:999999",
                display_name="Another breast cancer",
                normalized_alias="breast cancer",
                alias_type="name",
            ),
        ),
        (EntityType.VARIANT, "rs80359550"): (
            TerminologyCandidate(
                entry_id="variant-1",
                entity_type=EntityType.VARIANT,
                source_db="ClinVar",
                external_id="ClinVarVariation:12345",
                display_name="rs80359550",
                normalized_alias="rs80359550",
                alias_type="rsid",
            ),
        ),
    }
    created_repositories: list[FakeRepository] = []

    def _factory(session_lookup):
        repo = FakeRepository(session_lookup)
        created_repositories.append(repo)
        return repo

    monkeypatch.setattr(api_module, "StandardizationRepository", _factory)
    service = api_module.EntityStandardizationService(cfg=object(), session=lookup)

    output = await service.run_dual_result(
        result,
        source_document_id="source-2",
        processing_run_id="run-2",
    )

    assert output.standardized_count == 2
    assert output.ambiguous_count == 1
    assert output.unmapped_count == 1
    repo = created_repositories[0]
    assert len(repo.normalized) == 4
    assert repo.run_items
    assert repo.bindings
    assert repo.canonical
