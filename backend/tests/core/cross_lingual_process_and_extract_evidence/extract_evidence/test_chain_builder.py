from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SourcePrecision,
    SpecialEvidenceRecord,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import EvidenceChainBuilder


def _found(field_id: str, value: str, group_id: str) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id.split(".")[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.9,
        group_id=group_id,
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=len(value),
            context_type="text",
            context_ref="",
            text_snippet=value,
            source_precision=SourcePrecision.EXACT,
        ),
    )


def test_chain_builder_creates_full_chain_per_variant_group():
    group_id = "gene=BRCA1|variant=c.5266dupC"
    items = [
        _found("A.gene_symbol", "BRCA1", group_id),
        _found("A.variant_hgvs_c", "c.5266dupC", group_id),
        _found("B.disease_diagnosis", "Breast cancer", group_id),
    ]

    chains = EvidenceChainBuilder().build(items, [])

    assert len(chains) == 1
    assert chains[0].chain_id == group_id
    assert chains[0].chain_level == "full"


def test_chain_builder_aggregates_case_ids():
    group_id = "gene=BRCA1|variant=c.5266dupC"
    items = [
        _found("A.gene_symbol", "BRCA1", group_id),
        _found("A.variant_hgvs_c", "c.5266dupC", group_id),
        _found("B.disease_diagnosis", "Breast cancer", group_id),
        _found("B.case_id", "case-1", group_id),
        _found("B.case_id", "case-2", group_id),
    ]

    chains = EvidenceChainBuilder().build(items, [])

    assert chains[0].case_ids == ["case-1", "case-2"]


def test_chain_builder_builds_partial_and_singleton_levels():
    partial_group = "gene=BRCA1|variant=c.5266dupC"
    singleton_group = "gene=GLA|variant=__missing__"
    items = [
        _found("A.gene_symbol", "BRCA1", partial_group),
        _found("A.variant_hgvs_c", "c.5266dupC", partial_group),
        _found("A.gene_symbol", "GLA", singleton_group),
    ]

    chains = EvidenceChainBuilder().build(items, [])

    levels = {chain.chain_id: chain.chain_level for chain in chains}
    assert levels[partial_group] == "partial"
    assert levels[singleton_group] == "singleton"


def test_chain_builder_attaches_special_evidence_ids():
    group_id = "gene=BRCA1|variant=c.5266dupC"
    items = [
        _found("A.gene_symbol", "BRCA1", group_id),
        _found("A.variant_hgvs_c", "c.5266dupC", group_id),
        _found("B.disease_diagnosis", "Breast cancer", group_id),
    ]
    records = [
        SpecialEvidenceRecord(record_type="functional", description="Assay", group_id=group_id),
        SpecialEvidenceRecord(record_type="authority", description="ClinVar", group_id=group_id),
    ]

    chains = EvidenceChainBuilder().build(items, records)

    assert chains[0].special_evidence_ids == ["special-0", "special-1"]
