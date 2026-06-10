from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import EVIDENCE_FIELD_SPECS
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.prompts import (
    build_block_prompt_text,
    get_catalog_extraction_prompt,
    get_evidence_map_prompt,
)


def test_evidence_map_prompt_defaults_to_relevant_before_task():
    """DEFAULT instruction must appear before TASK so FAST models see it first."""
    prompt = get_evidence_map_prompt(document_id="doc-1", track=Track.ORIGINAL, text="BRCA1")
    default_pos = prompt.index("DEFAULT")
    task_pos = prompt.index("TASK")
    assert default_pos < task_pos, "DEFAULT must appear before TASK in the prompt"


def test_evidence_map_prompt_has_uncertainty_safety_net():
    """Prompt must include an explicit 'if unsure, set TRUE' safety net."""
    prompt = get_evidence_map_prompt(document_id="doc-1", track=Track.ORIGINAL, text="BRCA1")
    assert "unsure" in prompt.lower()
    assert "true" in prompt.lower()


def test_evidence_map_prompt_lists_not_relevant_categories():
    """Prompt must enumerate the three NOT_RELEVANT categories."""
    prompt = get_evidence_map_prompt(document_id="doc-1", track=Track.ORIGINAL, text="BRCA1")
    lower = prompt.lower()
    assert "methodological" in lower or "statistical methods" in lower
    assert "editorial" in lower or "letter" in lower or "comment" in lower
    assert "unrelated" in lower


def test_evidence_map_prompt_contains_document_id():
    prompt = get_evidence_map_prompt(document_id="doc-1", track=Track.ORIGINAL, text="BRCA1")
    assert "doc-1" in prompt


def test_evidence_map_prompt_requests_json_object():
    prompt = get_evidence_map_prompt(document_id="doc-1", track=Track.ORIGINAL, text="BRCA1")

    assert "json" in prompt.lower()
    assert '"relevant": true' in prompt.lower()
    assert '"gene_terms"' in prompt


def test_catalog_prompt_includes_catalog_field_ids():
    prompt = get_catalog_extraction_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="BRCA1",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="relevant",
    )

    assert "A.variant_type" in prompt
    assert "status" in prompt
    assert "not_found" in prompt


def test_catalog_prompt_defines_ocr_gap_and_external_completion_boundaries():
    prompt = get_catalog_extraction_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="BRCA1",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="relevant",
    )

    assert "ocr_gap" in prompt
    assert "Do not invent external database values" in prompt
    assert "baseline biochemical markers" in prompt
    assert "treatment response" in prompt
    assert "diagnosis_sufficiency" in prompt


def test_catalog_prompt_requires_verbatim_source_snippets():
    prompt = get_catalog_extraction_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="BRCA1",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="relevant",
    )

    assert "snippet must be a verbatim" in prompt.lower()
    assert "copy punctuation exactly" in prompt.lower()


def test_build_block_prompt_text_uses_original_block_indices_and_captions():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(type="header", page_idx=0, text="Header"),
            ContentBlock(
                type="table",
                page_idx=1,
                table_caption=["Table 1. Variants"],
                table_body="BRCA1 c.5266dupC",
            ),
        ],
    )

    text = build_block_prompt_text(doc)

    assert "[Block 0 | text | page 1]" in text
    assert "[Block 1 | table | page 2 | caption: Table 1. Variants]" in text
    assert "BRCA1 c.5266dupC" in text


def test_catalog_prompt_uses_block_sources_without_offsets():
    prompt = get_catalog_extraction_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="[Block 1 | table | page 2]\nBRCA1",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="relevant",
    )

    assert "block_index" in prompt
    assert "Do not calculate character offsets" in prompt
    assert "raw source" not in prompt.lower()


def test_special_evidence_prompt_requires_verbatim_snippets():
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.prompts import get_special_evidence_prompt

    prompt = get_special_evidence_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="BRCA1",
        current_items_summary="A.gene_symbol: BRCA1",
    )

    assert "reuse exact document wording" in prompt.lower()
    assert "copy punctuation exactly" in prompt.lower()


def test_build_block_prompt_text_can_select_original_block_indices():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="Title"),
            ContentBlock(type="text", page_idx=1, text="BRCA1 c.5266dupC"),
            ContentBlock(type="table", page_idx=2, table_body="GLA c.1000G>A"),
        ],
    )

    text = build_block_prompt_text(doc, block_indices=(1, 2))

    assert "[Block 0" not in text
    assert "[Block 1 | text | page 2]" in text
    assert "[Block 2 | table | page 3]" in text


def test_catalog_prompt_distinguishes_age_of_onset_from_milestones() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="started sitting with support at the age of 15 months; referred at 17 months",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="AARS2 case",
    )

    assert "Do NOT use developmental milestones as B.age_of_onset" in prompt
    assert "referral, diagnosis, first symptoms, or presentation age" in prompt


def test_catalog_prompt_requires_named_prediction_tools() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="functional analysis by in silico tools",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="AARS2 case",
    )

    assert "Computational predictions support PP3/BP4 only" in prompt
    assert "Do not treat in silico predictions as F.functional_result" in prompt
    assert "E.prediction_tools_list requires named tools" in prompt


def test_catalog_prompt_requires_gene_symbol_from_disease_prefix() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="AARS2-mutation related mitochondrial disease",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="AARS2 case",
    )

    assert "A.gene_symbol" in prompt
    assert "AARS2-related" in prompt
    assert "must extract the gene symbol independently" in prompt
    assert "must not leave A.gene_symbol as not_found" in prompt


def test_catalog_prompt_relationship_distinguishes_established_from_preliminary() -> None:
    prompt = get_catalog_extraction_prompt(
        document_id="doc",
        track=Track.ORIGINAL,
        text="AARS1 causes Charcot-Marie-Tooth disease",
        catalog=EVIDENCE_FIELD_SPECS,
        evidence_map_summary="AARS1 case",
    )

    assert "known disease gene" in prompt
    assert "established causal relationship" in prompt
    assert "Do not choose associated merely because the sentence contains associated" in prompt
