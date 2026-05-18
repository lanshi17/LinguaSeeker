import pytest
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.validator import (
    validate_translation_output,
    validate_segment,
    summarize_validation_error,
)


# ── validate_translation_output ────────────────────────────────────────


def test_validate_empty_translation():
    with pytest.raises(ValueError, match="empty"):
        validate_translation_output("source text", "")


def test_validate_cjk_heavy_output():
    cjk_text = "这是一段中文文本，超过百分之十的CJK字符。" * 5
    with pytest.raises(ValueError, match="non_english"):
        validate_translation_output("source", cjk_text)


def test_validate_unchanged_text():
    source = "This text should not be identical to the translation output."
    with pytest.raises(ValueError, match="unchanged"):
        validate_translation_output(source, source)


def test_validate_good_translation():
    source = "该患者携带BRCA1基因的新变异，导致蛋白质功能丧失。"
    translated = "The patient carries a novel variant in the BRCA1 gene, resulting in loss of protein function."
    # Should not raise
    validate_translation_output(source, translated)


def test_summarize_validation_error():
    exc = ValueError("translation_validation_failed: empty")
    summary = summarize_validation_error(exc)
    assert "empty" in summary


def test_summarize_unknown_error():
    exc = ValueError("something else")
    summary = summarize_validation_error(exc)
    assert "something else" in summary


# ── validate_segment ───────────────────────────────────────────────────


def test_validate_segment_empty():
    with pytest.raises(ValueError, match="empty"):
        validate_segment("source", "")


def test_validate_segment_source_language_content():
    source = "患者男性，32岁"
    translated = "患者男性，32岁，因泡沫尿1年余入院"  # Still mostly CJK
    with pytest.raises(ValueError, match="source_language_content"):
        validate_segment(source, translated)


def test_validate_segment_unchanged():
    # Source with mixed CJK/English — unchanged translation should be flagged
    # Need >5% CJK (to trigger "unchanged" check) but <15% (to not trigger "source_language_content")
    source = "The patient carries a novel BRCA1 基因变异 in the 基因 gene sequence 数据."
    with pytest.raises(ValueError, match="unchanged"):
        validate_segment(source, source)


def test_validate_segment_unchanged_english_only():
    # English-only source (author names, affiliations) — should NOT be flagged
    source = "Zhang Hong, Jiang Zuanhong, Shao Songhua"
    validate_segment(source, source)  # should not raise


def test_validate_segment_good():
    source = "患者携带BRCA1基因新变异。"
    translated = "The patient carries a novel BRCA1 variant."
    # Should not raise
    validate_segment(source, translated)


def test_validate_segment_short_english():
    """Short English segments with no source should pass."""
    validate_segment("", "Figure 1 shows the results.")
