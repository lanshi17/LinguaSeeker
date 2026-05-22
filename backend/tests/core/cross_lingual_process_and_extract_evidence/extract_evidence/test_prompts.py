from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import EVIDENCE_FIELD_SPECS
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import Track
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.prompts import (
    get_catalog_extraction_prompt,
    get_evidence_map_prompt,
)


def test_evidence_map_prompt_mentions_no_scoring():
    prompt = get_evidence_map_prompt(document_id="doc-1", track=Track.ORIGINAL, text="BRCA1")
    assert "Do not score" in prompt
    assert "doc-1" in prompt


def test_evidence_map_prompt_requests_json_object():
    prompt = get_evidence_map_prompt(document_id="doc-1", track=Track.ORIGINAL, text="BRCA1")

    assert "json" in prompt.lower()
    assert '"relevant": false' in prompt.lower()
    assert '"gene_terms": []' in prompt


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
