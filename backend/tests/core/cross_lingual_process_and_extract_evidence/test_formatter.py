from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.formatter import (
    MarkdownFormatter,
    extract_sentences,
    build_page_offset_map,
    _format_markdown,
)
from src.core.cross_lingual_process_and_extract_evidence.contracts import ContentBlock, FormattedDocument


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


def test_format_markdown_default_empty_blocks():
    pages = [{"page_number": 1, "markdown": "Some text."}]
    result = _format_markdown(pages)
    assert result.original_blocks == []


def test_format_markdown_with_content_blocks():
    pages = [{"page_number": 1, "markdown": "Title. Body text."}]
    content_blocks = [
        {"type": "title", "text": "Title", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "Body text.", "page_idx": 0},
    ]
    result = _format_markdown(pages, content_blocks=content_blocks)

    assert len(result.original_blocks) == 2
    assert isinstance(result.original_blocks[0], ContentBlock)
    assert result.original_blocks[0].type == "title"
    assert result.original_blocks[0].text == "Title"
    assert result.original_blocks[0].text_level == 1
    assert result.original_blocks[1].type == "text"
    assert result.original_blocks[1].text == "Body text."


def test_markdown_formatter_format_with_content_blocks():
    formatter = MarkdownFormatter()
    pages = [{"page_number": 1, "markdown": "Content."}]
    content_blocks = [
        {"type": "text", "text": "Content.", "page_idx": 0},
    ]
    result = formatter.format(pages, content_blocks=content_blocks)

    assert isinstance(result, FormattedDocument)
    assert len(result.original_blocks) == 1
    assert result.original_blocks[0].type == "text"
