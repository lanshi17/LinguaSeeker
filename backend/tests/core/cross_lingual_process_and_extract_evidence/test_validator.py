import pytest
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.validator import (
    validate_translation_output,
    summarize_validation_error,
)


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
