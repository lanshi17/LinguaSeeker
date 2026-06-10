from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SpecialEvidenceRecord,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import (
    EvidenceItemNormalizer,
    RawSourceNormalizer,
)


def test_raw_source_normalizer_moves_item_source_to_raw_source():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.5266dupC",
        confidence=0.9,
        source=SourceLocation(
            block_index=1,
            context_type="table",
            context_ref="Table 1",
            text_snippet="c.5266dupC",
        ),
    )

    normalized = RawSourceNormalizer().normalize_items([item])

    assert normalized[0].source is None
    assert normalized[0].raw_source is not None
    assert normalized[0].raw_source.block_index == 1


def test_raw_source_normalizer_drops_llm_not_found_items():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.NOT_FOUND,
        value=None,
        confidence=0.0,
    )

    assert RawSourceNormalizer().normalize_items([item]) == []


def test_raw_source_normalizer_moves_special_source_to_raw_source():
    record = SpecialEvidenceRecord(
        record_type="functional",
        description="Assay result",
        source=SourceLocation(
            block_index=2,
            context_type="figure",
            context_ref="Figure 1",
            text_snippet="loss of function",
        ),
    )

    normalized = RawSourceNormalizer().normalize_special_records([record])

    assert normalized[0].source is None
    assert normalized[0].raw_source is not None


def test_normalizer_preserves_same_field_in_different_groups():
    items = [
        EvidenceItem(
            field_id="A.variant_hgvs_c",
            category="A",
            field_name="HGVS coding variant",
            status=EvidenceStatus.FOUND,
            value="c.1A>G",
            confidence=0.9,
            group_id="gene=G1|variant=c.1A>G",
        ),
        EvidenceItem(
            field_id="A.variant_hgvs_c",
            category="A",
            field_name="HGVS coding variant",
            status=EvidenceStatus.FOUND,
            value="c.2A>G",
            confidence=0.9,
            group_id="gene=G1|variant=c.2A>G",
        ),
    ]

    normalized = EvidenceItemNormalizer().normalize_grouped(items)

    assert len([i for i in normalized if i.field_id == "A.variant_hgvs_c" and i.status == EvidenceStatus.FOUND]) == 2


def test_normalizer_backfills_full_catalog_per_group():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="GLA",
        confidence=0.9,
        group_id="gene=GLA|variant=__missing__",
    )

    normalized = EvidenceItemNormalizer().normalize_grouped([item])

    group_items = [i for i in normalized if i.group_id == "gene=GLA|variant=__missing__"]
    assert any(i.field_id == "A.gene_symbol" and i.status == EvidenceStatus.FOUND for i in group_items)
    assert any(i.field_id == "A.variant_hgvs_c" and i.status == EvidenceStatus.NOT_FOUND for i in group_items)


from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import FieldValueNormalizer


def test_field_value_normalizer_extracts_gene_from_related_phrase() -> None:
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="AARS2-mutation related mitochondrial disease",
        confidence=0.74,
    )

    normalized = FieldValueNormalizer.normalize_items([item])

    assert normalized[0].value == "AARS2"


def test_field_value_normalizer_preserves_plain_gene_symbol() -> None:
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="ABCA3",
        confidence=0.95,
    )

    normalized = FieldValueNormalizer.normalize_items([item])

    assert normalized[0].value == "ABCA3"


def test_field_value_normalizer_extracts_lowercase_related_gene_phrase() -> None:
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="aars2-related mitochondrial disease",
        confidence=0.74,
    )

    normalized = FieldValueNormalizer.normalize_items([item])

    assert normalized[0].value == "AARS2"


def test_field_value_normalizer_uses_token_before_relationship_hint() -> None:
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="Mito AARS2-related disease",
        confidence=0.74,
    )

    normalized = FieldValueNormalizer.normalize_items([item])

    assert normalized[0].value == "AARS2"


def test_field_value_normalizer_rejects_unknown_placeholder() -> None:
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="unknown",
        confidence=0.3,
    )

    normalized = FieldValueNormalizer.normalize_items([item])

    assert normalized[0].status == EvidenceStatus.NOT_FOUND
    assert normalized[0].value is None


def test_field_value_normalizer_rejects_none_placeholder() -> None:
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="none",
        confidence=0.3,
    )

    normalized = FieldValueNormalizer.normalize_items([item])

    assert normalized[0].status == EvidenceStatus.NOT_FOUND
    assert normalized[0].value is None


def test_field_value_normalizer_rejects_common_english_word() -> None:
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="patient",
        confidence=0.5,
    )

    normalized = FieldValueNormalizer.normalize_items([item])

    assert normalized[0].status == EvidenceStatus.NOT_FOUND
    assert normalized[0].value is None


def test_field_value_normalizer_preserves_uppercase_gene_symbol() -> None:
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="BRCA1",
        confidence=0.95,
    )

    normalized = FieldValueNormalizer.normalize_items([item])

    assert normalized[0].value == "BRCA1"
    assert normalized[0].status == EvidenceStatus.FOUND
