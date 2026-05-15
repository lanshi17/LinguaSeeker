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
