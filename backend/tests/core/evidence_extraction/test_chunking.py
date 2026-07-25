from src.core.evidence_extraction.infrastructure.chunking import (
    DEFAULT_INPUT_BUDGET_TOKENS,
    build_block_prompt_chunks,
    build_text_prompt_chunks,
    merge_evidence_maps,
    merge_sparse_evidence_items,
    merge_special_evidence_records,
)
from src.core.evidence_extraction.contracts import (
    ContentBlock,
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SpecialEvidenceRecord,
    Track,
    TrackDocument,
)


def test_text_prompt_chunks_respect_token_budget():
    text = "\n\n".join(f"Paragraph {idx}. " + ("A" * 80) for idx in range(30))

    chunks = build_text_prompt_chunks(
        text,
        input_budget_tokens=80,
        prompt_overhead_tokens=10,
    )

    assert len(chunks) > 1
    assert [chunk.index for chunk in chunks] == list(range(1, len(chunks) + 1))
    assert all(chunk.total == len(chunks) for chunk in chunks)
    assert "".join(chunk.text.replace("\n\n", "") for chunk in chunks).replace(" ", "")


def test_text_prompt_chunks_keep_short_text_single_chunk():
    chunks = build_text_prompt_chunks(
        "BRCA1 c.5266dupC was identified.",
        input_budget_tokens=DEFAULT_INPUT_BUDGET_TOKENS,
        prompt_overhead_tokens=20,
    )

    assert len(chunks) == 1
    assert chunks[0].index == 1
    assert chunks[0].total == 1
    assert chunks[0].text == "BRCA1 c.5266dupC was identified."


def test_merge_evidence_maps_stable_deduplicates_terms():
    merged = merge_evidence_maps(
        [
            DocumentEvidenceMap(
                relevant=False,
                disease_terms=["Fabry disease"],
                gene_terms=["GLA"],
                structure_hints=["Table 1"],
            ),
            DocumentEvidenceMap(
                relevant=True,
                disease_terms=["Fabry disease", "cardiomyopathy"],
                gene_terms=["GLA", "BRCA1"],
                variant_terms=["c.1000G>A"],
                structure_hints=["Table 1", "Figure 2"],
            ),
        ]
    )

    assert merged.relevant is True
    assert merged.disease_terms == ["Fabry disease", "cardiomyopathy"]
    assert merged.gene_terms == ["GLA", "BRCA1"]
    assert merged.variant_terms == ["c.1000G>A"]
    assert merged.structure_hints == ["Table 1", "Figure 2"]


def test_block_prompt_chunks_preserve_original_indices():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="A" * 120),
            ContentBlock(type="text", page_idx=1, text="B" * 120),
            ContentBlock(type="table", page_idx=2, table_body="C" * 120),
        ],
    )

    chunks = build_block_prompt_chunks(
        doc,
        input_budget_tokens=80,
        prompt_overhead_tokens=10,
    )

    assert len(chunks) > 1
    joined = "\n".join(chunk.text for chunk in chunks)
    assert "[Block 0 | text | page 1]" in joined
    assert "[Block 1 | text | page 2]" in joined
    assert "[Block 2 | table | page 3]" in joined
    assert sorted(index for chunk in chunks for index in chunk.block_indices) == [0, 1, 2]


def test_text_prompt_chunks_include_seam_context():
    """Chunks should include neighboring context so evidence at boundaries isn't lost."""
    text = "AAA " + ("X" * 200) + "\n\n" + "BBB " + ("Y" * 200)

    chunks = build_text_prompt_chunks(
        text,
        input_budget_tokens=80,
        prompt_overhead_tokens=0,
        seam_context_chars=20,
    )

    assert len(chunks) >= 2
    joined_all = "\n".join(chunk.text for chunk in chunks)
    # Seam markers should be present
    assert "PREVIOUS" in joined_all or "NEXT" in joined_all


def test_block_prompt_chunks_include_seam_context():
    """Block chunks should include neighboring context across block boundaries."""
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="GLA c.1000G>A " + ("A" * 120)),
            ContentBlock(type="text", page_idx=1, text="BRCA1 c.5266dupC " + ("B" * 120)),
        ],
    )

    chunks = build_block_prompt_chunks(
        doc,
        input_budget_tokens=80,
        prompt_overhead_tokens=0,
        seam_context_chars=20,
    )

    assert len(chunks) >= 2
    joined_all = "\n".join(chunk.text for chunk in chunks)
    # Both gene symbols should appear in the combined output
    assert "GLA" in joined_all
    assert "BRCA1" in joined_all
    # Seam markers should be present
    assert "PREVIOUS" in joined_all or "NEXT" in joined_all


def _item(field_id: str, value: str, confidence: float) -> EvidenceItem:
    category, field_name = field_id.split(".", maxsplit=1)
    return EvidenceItem(
        field_id=field_id,
        category=category,
        field_name=field_name,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=confidence,
        raw_source=SourceLocation(
            block_index=0,
            context_type="text",
            context_ref="",
            text_snippet=value,
        ),
    )


def test_merge_sparse_evidence_items_keeps_best_duplicate():
    low = _item("A.gene_symbol", "GLA", 0.6)
    high = _item("A.gene_symbol", "GLA", 0.9)
    other = _item("A.variant_hgvs_c", "c.1000G>A", 0.8)

    merged = merge_sparse_evidence_items([low, high, other])

    assert len(merged) == 2
    assert merged[0].field_id == "A.gene_symbol"
    assert merged[0].confidence == 0.9
    assert merged[1].field_id == "A.variant_hgvs_c"


def test_merge_special_evidence_records_deduplicates_same_source():
    source = SourceLocation(
        block_index=0,
        context_type="text",
        context_ref="",
        text_snippet="Functional assay showed reduced activity.",
    )
    first = SpecialEvidenceRecord(
        record_type="functional",
        description="Reduced activity",
        evidence_field_ids=["H.functional_assay"],
        raw_source=source,
        confidence=0.7,
    )
    second = first.model_copy(update={"confidence": 0.9})

    merged = merge_special_evidence_records([first, second])

    assert len(merged) == 1
    assert merged[0].confidence == 0.9
