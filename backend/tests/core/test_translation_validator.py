"""Tests for translation validation threshold."""

import pytest


def test_short_technical_text_not_flagged_as_unchanged():
    """Short texts with many shared technical terms should not be flagged as unchanged.

    This tests the scenario where the LLM returns a translation that shares many
    tokens with the source (gene names, mutation notation) but is genuinely
    translated. The source must be English (to pass the CJK check) and the
    translation must also be English (to pass the language detection check).
    """
    from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.validator.core import validate_translation_output

    # Short English text with technical terms — translation keeps most tokens
    source = "BRCA1 gene mutation c.5266dupC (p.Gln1756ProfsTer74) was identified."
    translated = "BRCA1 gene mutation c.5266dupC (p.Gln1756ProfsTer74) has been identified in the patient."

    # Should NOT raise ValueError — short text with shared terms
    try:
        validate_translation_output(source, translated)
    except Exception as e:
        pytest.fail(f"Should not raise for genuine translation with shared terms: {e}")


def test_long_unchanged_text_still_flagged():
    """Long texts that are genuinely unchanged should still be flagged."""
    from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.validator.core import validate_translation_output

    # A long text that is identical (or nearly so) should be caught
    source = "The BRCA1 gene is a tumor suppressor gene that produces a protein involved in DNA repair. Mutations in this gene are associated with increased risk of breast and ovarian cancer. " * 3
    translated = source  # Exactly the same

    with pytest.raises(ValueError, match="unchanged"):
        validate_translation_output(source, translated)
