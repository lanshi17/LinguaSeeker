"""Tests for translation validation threshold."""

import pytest


def test_short_technical_text_not_flagged_as_unchanged():
    """Short texts with many shared technical terms should not be flagged as unchanged.

    This tests the scenario where the LLM returns a translation that shares many
    tokens with the source (gene names, mutation notation) but is genuinely
    translated. The source must be English (to pass the CJK check) and the
    translation must also be English (to pass the language detection check).
    """
    from src.core.cross_lingual_translation.translate.validator.core import (
        validate_translation_output,
    )

    # Short English text with technical terms — translation keeps most tokens
    source = "BRCA1 gene mutation c.5266dupC (p.Gln1756ProfsTer74) was identified."
    translated = "BRCA1 gene mutation c.5266dupC (p.Gln1756ProfsTer74) has been identified in the patient."

    # Should NOT raise ValueError — short text with shared terms
    try:
        validate_translation_output(source, translated)
    except Exception as e:
        pytest.fail(f"Should not raise for genuine translation with shared terms: {e}")


def test_long_unchanged_text_still_flagged():
    """Long non-English texts that are genuinely unchanged should still be flagged.

    The unchanged check intentionally skips English sources (translating an
    English document produces similar text by design) and short texts (shared
    technical terms inflate similarity).  It also skips nothing for length on
    long inputs, so a long non-English source echoed verbatim must be flagged.
    A non-CJK language is used because echoed CJK text is rejected earlier by
    the CJK-ratio check as ``non_english_output`` rather than ``unchanged``.
    """
    from src.core.cross_lingual_translation.translate.validator.core import (
        validate_translation_output,
    )

    # A long Spanish text echoed verbatim (no translation performed)
    source = (
        "El gen BRCA1 es un gen supresor de tumores que produce una proteina "
        "implicada en la reparacion del ADN. Las mutaciones de este gen se "
        "asocian con un mayor riesgo de cancer de mama y de ovario. "
        * 3
    )
    translated = source  # Exactly the same

    with pytest.raises(ValueError, match="unchanged"):
        validate_translation_output(source, translated)
