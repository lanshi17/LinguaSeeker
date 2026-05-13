from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.segmenter import (
    estimate_tokens,
    segment_text,
)


def test_estimate_tokens_ascii():
    assert estimate_tokens("hello world") > 0


def test_estimate_tokens_cjk():
    assert estimate_tokens("你好世界") > 0


def test_segment_text_short():
    text = "Short sentence."
    segments = segment_text(text, max_tokens=8192)
    assert len(segments) == 1
    assert segments[0] == text


def test_segment_text_multiple_paragraphs():
    para1 = "First paragraph with enough content to be its own segment."
    para2 = "Second paragraph with enough content to be its own segment."
    text = f"{para1}\n\n{para2}"
    segments = segment_text(text, max_tokens=20)
    assert len(segments) >= 2


def test_segment_text_preserves_structure():
    text = "# Heading\n\nParagraph one.\n\nParagraph two."
    segments = segment_text(text, max_tokens=8192)
    assert len(segments) == 1
    assert "# Heading" in segments[0]
