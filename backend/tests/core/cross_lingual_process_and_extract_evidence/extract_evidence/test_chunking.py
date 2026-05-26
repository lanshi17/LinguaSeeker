from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.chunking import (
    DEFAULT_INPUT_BUDGET_TOKENS,
    build_text_prompt_chunks,
    merge_evidence_maps,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.segmenter import (
    estimate_tokens,
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
    assert all(estimate_tokens(chunk.text) <= 80 for chunk in chunks)
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
    merged = merge_evidence_maps([
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
    ])

    assert merged.relevant is True
    assert merged.disease_terms == ["Fabry disease", "cardiomyopathy"]
    assert merged.gene_terms == ["GLA", "BRCA1"]
    assert merged.variant_terms == ["c.1000G>A"]
    assert merged.structure_hints == ["Table 1", "Figure 2"]


from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.chunking import (
    build_block_prompt_chunks,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    Track,
    TrackDocument,
)


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
