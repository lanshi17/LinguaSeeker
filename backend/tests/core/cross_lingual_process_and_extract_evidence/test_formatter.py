from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.formatter import (
    extract_sentences,
    build_page_offset_map,
    _format_markdown,
)
from src.core.cross_lingual_process_and_extract_evidence.contracts import FormattedDocument


def test_extract_sentences_basic():
    text = "First sentence. Second sentence."
    sentences = extract_sentences(text)
    assert len(sentences) == 2
    assert sentences[0].text == "First sentence."
    assert sentences[1].text == "Second sentence."


def test_extract_sentences_with_page_map():
    text = "Hello world. Goodbye world."
    page_map = {0: 1, 13: 1}  # char offset -> page number
    sentences = extract_sentences(text, page_map)
    assert all(s.page == 1 for s in sentences)


def test_build_page_offset_map():
    pages = [
        {"page_number": 1, "markdown": "Page one content."},
        {"page_number": 2, "markdown": "Page two content."},
    ]
    offset_map = build_page_offset_map(pages)
    assert 0 in offset_map
    assert offset_map[0] == 1


def test_format_markdown_returns_formatted_document():
    pages = [
        {"page_number": 1, "markdown": "Some content about genes."},
    ]
    result = _format_markdown(pages)
    assert isinstance(result, FormattedDocument)
    assert result.formatted_markdown != ""
    assert result.metadata["page_count"] == 1
