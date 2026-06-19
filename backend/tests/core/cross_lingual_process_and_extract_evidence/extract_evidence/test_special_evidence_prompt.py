"""Locks the gap-filling scope instruction in the special-evidence prompt."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import Track
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.prompts import (
    get_special_evidence_prompt,
)


def test_special_evidence_prompt_carries_gap_filling_scope():
    prompt = get_special_evidence_prompt(
        document_id="d1",
        track=Track.ORIGINAL,
        text="x",
        current_items_summary="A.gene_symbol: GLA",
    )
    assert "SCOPE:" in prompt
    assert "gap-filler" in prompt
    assert "NOT already represented" in prompt
