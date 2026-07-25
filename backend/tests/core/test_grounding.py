"""Tests for evidence grounding fuzzy match."""


def test_ground_one_matches_ellipsis_snippet_fuzzy():
    """Snippets with '...' should match by verifying each fragment appears in order."""
    from src.core.evidence_extraction.core import _fuzzy_ellipsis_match

    snippet = "M1 nonsense variant ... producing truncated protein"
    doc_text = "M1 nonsense variant c.477G>A(p.Trp159Ter) resulted in the 159th codon changing from encoded tryptophan to terminating codon, producing truncated protein"

    assert _fuzzy_ellipsis_match(snippet, doc_text) is True


def test_ground_one_rejects_genuinely_missing_snippet():
    """Snippets not in document should still be rejected."""
    from src.core.evidence_extraction.core import _fuzzy_ellipsis_match

    snippet = "completely fabricated ... evidence text"
    doc_text = "Real document text about a different topic"

    assert _fuzzy_ellipsis_match(snippet, doc_text) is False


def test_fuzzy_ellipsis_match_with_multiple_fragments():
    """Multiple ellipsis-separated fragments should all be found in order."""
    from src.core.evidence_extraction.core import _fuzzy_ellipsis_match

    snippet = "BRCA1 ... pathogenic variant ... classification"
    doc_text = "BRCA1 is a tumor suppressor gene. A pathogenic variant c.5266dupC was identified. This supports a classification of pathogenic."

    assert _fuzzy_ellipsis_match(snippet, doc_text) is True


def test_fuzzy_ellipsis_match_rejects_out_of_order():
    """Fragments found in wrong order should be rejected."""
    from src.core.evidence_extraction.core import _fuzzy_ellipsis_match

    snippet = "classification ... pathogenic variant"
    doc_text = "A pathogenic variant was identified. This supports a classification of pathogenic."

    assert _fuzzy_ellipsis_match(snippet, doc_text) is False
