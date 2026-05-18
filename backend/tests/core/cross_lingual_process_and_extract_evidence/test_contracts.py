from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    ContentBlock,
    PipelineState,
    SentenceRegion,
    FormattedDocument,
    TranslationSegment,
    TranslationResult,
)


def test_sentence_region_span():
    region = SentenceRegion(
        page=1,
        start_offset=0,
        end_offset=50,
        text="Hello world.",
    )
    assert region.span == 50


def test_formatted_document_from_pages():
    pages = [
        {"page_number": 1, "markdown": "First page content."},
        {"page_number": 2, "markdown": "Second page content."},
    ]
    doc = FormattedDocument.from_pages(pages, formatted_markdown="First page content.\n\nSecond page content.")
    assert doc.source_language == ""
    assert len(doc.sentences) == 0
    assert "First page" in doc.formatted_markdown


def test_translation_segment_defaults():
    seg = TranslationSegment(
        index=0,
        source_text="Original text.",
        translated_text="Translated text.",
    )
    assert seg.source_bbox is None


def test_translation_result_fields():
    result = TranslationResult(
        formatted_original="原文",
        translated_english="English",
        source_language="zh",
        terminology_map={"基因": "gene"},
        translation_warnings=[],
        sentences=[],
        segments=[],
    )
    assert result.formatted_original == "原文"
    assert result.translated_english == "English"
    assert result.source_language == "zh"


def test_pipeline_state_defaults():
    state = PipelineState(pages=[{"page_number": 1, "markdown": "test"}])
    assert state.source_language == ""
    assert state.needs_translation is True
    assert state.formatted is None
    assert state.translation_result is None


def test_pipeline_state_rejects_missing_pages():
    import pytest
    with pytest.raises(Exception):
        PipelineState()  # pages is required


def test_saved_documents_fields():
    """SavedDocuments tracks output file paths."""
    from pathlib import Path
    from datetime import datetime, timezone

    from src.core.cross_lingual_process_and_extract_evidence.contracts import SavedDocuments

    saved = SavedDocuments(
        original_json_path=Path("/tmp/out/original.json"),
        translated_json_path=Path("/tmp/out/translated.json"),
        metadata_path=Path("/tmp/out/metadata.json"),
        image_dir=Path("/tmp/out/images"),
        image_paths=[Path("/tmp/out/images/fig1.png")],
        output_dir=Path("/tmp/out"),
        created_at=datetime.now(timezone.utc),
    )
    assert saved.original_json_path.name == "original.json"
    assert len(saved.image_paths) == 1


def test_cross_lingual_output_fields():
    """CrossLingualOutput is the downstream contract."""
    from src.core.cross_lingual_process_and_extract_evidence.contracts import CrossLingualOutput

    out = CrossLingualOutput(
        formatted_original="原始文本",
        translated_english="Original text",
        source_language="zh",
        terminology_map={"基因": "gene"},
        translation_warnings=[],
        output_dir="/tmp/out",
        original_json_path="/tmp/out/original.json",
        translated_json_path="/tmp/out/translated.json",
        image_paths=["/tmp/out/images/fig1.png"],
    )
    assert out.source_language == "zh"
    assert out.terminology_map["基因"] == "gene"
    assert len(out.image_paths) == 1


def test_pipeline_state_image_paths():
    """PipelineState carries image_paths from upstream."""
    state = PipelineState(pages=[], image_paths=["/data/img1.png", "/data/img2.png"])
    assert len(state.image_paths) == 2


# ── ContentBlock tests ────────────────────────────────────────────────────


def test_contentblock_text():
    block = ContentBlock(type="text", text="Hello world", page_idx=0, bbox=[0, 0, 100, 20])
    assert block.type == "text"
    assert block.text == "Hello world"
    assert block.text_level is None


def test_contentblock_title():
    block = ContentBlock(type="title", text="Chapter 1", text_level=1, page_idx=0)
    assert block.type == "title"
    assert block.text_level == 1


def test_contentblock_image():
    block = ContentBlock(
        type="image",
        img_path="images/fig1.jpg",
        content="A diagram",
        image_caption=["Fig. 1"],
        image_footnote=["Source: ..."],
        sub_type="diagram",
        page_idx=1,
    )
    assert block.img_path == "images/fig1.jpg"
    assert block.image_caption == ["Fig. 1"]


def test_contentblock_table():
    block = ContentBlock(
        type="table",
        table_body="<table><tr><td>1</td></tr></table>",
        table_caption=["Table 1"],
        table_footnote=["* p<0.05"],
        page_idx=2,
    )
    assert block.table_body.startswith("<table>")


def test_contentblock_equation():
    block = ContentBlock(type="equation", text="E=mc^2", text_format="latex", page_idx=0)
    assert block.text_format == "latex"


def test_contentblock_code():
    block = ContentBlock(
        type="code",
        code_body="print('hello')",
        code_caption=["Listing 1"],
        code_sub_type="code",
        page_idx=0,
    )
    assert block.code_body == "print('hello')"


def test_contentblock_list():
    block = ContentBlock(
        type="list",
        list_sub_type="text",
        list_items=["Item 1", "Item 2"],
        page_idx=0,
    )
    assert len(block.list_items) == 2


def test_contentblock_chart():
    block = ContentBlock(
        type="chart",
        img_path="images/chart.png",
        content="Bar chart",
        chart_caption=["Chart 1"],
        chart_footnote=[],
        sub_type="bar",
        page_idx=3,
    )
    assert block.sub_type == "bar"


def test_contentblock_header_footer():
    header = ContentBlock(type="header", text="Page Header", page_idx=0)
    footer = ContentBlock(type="footer", text="Page 1", page_idx=0)
    assert header.text == "Page Header"
    assert footer.text == "Page 1"


def test_contentblock_to_dict_text():
    block = ContentBlock(type="text", text="Hello", page_idx=0, bbox=[0, 0, 100, 20])
    d = block.to_dict()
    assert d == {"type": "text", "page_idx": 0, "bbox": [0, 0, 100, 20], "text": "Hello"}


def test_contentblock_to_dict_title_with_level():
    block = ContentBlock(type="title", text="Ch1", text_level=1, page_idx=0)
    d = block.to_dict()
    assert d["text_level"] == 1


def test_contentblock_to_dict_image_omits_empty_lists():
    block = ContentBlock(type="image", img_path="a.jpg", page_idx=0)
    d = block.to_dict()
    assert "image_caption" not in d
    assert "image_footnote" not in d


def test_contentblock_to_dict_image_includes_nonempty_lists():
    block = ContentBlock(type="image", image_caption=["Fig 1"], page_idx=0)
    d = block.to_dict()
    assert d["image_caption"] == ["Fig 1"]


def test_contentblock_to_dict_table_omits_empty_lists():
    block = ContentBlock(type="table", table_body="<table/>", page_idx=0)
    d = block.to_dict()
    assert "table_caption" not in d
    assert "table_footnote" not in d


def test_contentblock_to_dict_table_with_text():
    block = ContentBlock(type="table", table_body="<table/>", text="Inline text", page_idx=0)
    d = block.to_dict()
    assert d["text"] == "Inline text"


def test_contentblock_to_dict_list_omits_empty_sub_type():
    block = ContentBlock(type="list", list_items=["a", "b"], page_idx=0)
    d = block.to_dict()
    assert "sub_type" not in d


def test_contentblock_to_dict_list_with_sub_type():
    block = ContentBlock(type="list", list_sub_type="ref_text", list_items=["a"], page_idx=0)
    d = block.to_dict()
    assert d["sub_type"] == "ref_text"


def test_contentblock_to_dict_chart():
    block = ContentBlock(type="chart", chart_caption=["C1"], page_idx=0)
    d = block.to_dict()
    assert d["chart_caption"] == ["C1"]
    assert "chart_footnote" not in d


def test_contentblock_to_dict_code_omits_empty_caption():
    block = ContentBlock(type="code", code_body="x=1", page_idx=0)
    d = block.to_dict()
    assert "code_caption" not in d


def test_contentblock_to_dict_header():
    block = ContentBlock(type="header", text="Header", page_idx=0)
    d = block.to_dict()
    assert d == {"type": "header", "page_idx": 0, "text": "Header"}


def test_contentblock_from_mineru_block_text():
    raw = {"type": "text", "text": "Hello", "page_idx": 0, "bbox": [0, 0, 100, 20]}
    block = ContentBlock.from_mineru_block(raw)
    assert block.type == "text"
    assert block.text == "Hello"
    assert block.bbox == [0, 0, 100, 20]


def test_contentblock_from_mineru_block_image():
    raw = {
        "type": "image",
        "img_path": "images/a.jpg",
        "content": "desc",
        "image_caption": ["Fig 1"],
        "sub_type": "photo",
        "page_idx": 1,
    }
    block = ContentBlock.from_mineru_block(raw)
    assert block.img_path == "images/a.jpg"
    assert block.sub_type == "photo"


def test_contentblock_from_mineru_block_missing_optional_keys():
    raw = {"type": "text", "text": "minimal"}
    block = ContentBlock.from_mineru_block(raw)
    assert block.page_idx == 0
    assert block.bbox == []
    assert block.text_level is None


def test_contentblock_from_mineru_block_code_sub_type():
    raw = {"type": "code", "code_body": "x=1", "sub_type": "algorithm"}
    block = ContentBlock.from_mineru_block(raw)
    assert block.code_sub_type == "algorithm"
    assert block.sub_type == ""


def test_contentblock_from_mineru_block_list_sub_type():
    raw = {"type": "list", "list_items": ["a"], "sub_type": "ref_text"}
    block = ContentBlock.from_mineru_block(raw)
    assert block.list_sub_type == "ref_text"
    assert block.sub_type == ""


def test_contentblock_round_trip_text():
    block = ContentBlock(type="text", text="Hello", page_idx=0, bbox=[0, 0, 100, 20])
    d = block.to_dict()
    restored = ContentBlock.from_mineru_block(d)
    assert restored.type == block.type
    assert restored.text == block.text
    assert restored.page_idx == block.page_idx
    assert restored.bbox == block.bbox


def test_contentblock_round_trip_image():
    block = ContentBlock(
        type="image",
        img_path="images/a.jpg",
        content="desc",
        image_caption=["Fig 1"],
        page_idx=1,
    )
    d = block.to_dict()
    restored = ContentBlock.from_mineru_block(d)
    assert restored.img_path == block.img_path
    assert restored.image_caption == block.image_caption


def test_contentblock_round_trip_table():
    block = ContentBlock(
        type="table",
        table_body="<table/>",
        table_caption=["T1"],
        page_idx=2,
    )
    d = block.to_dict()
    restored = ContentBlock.from_mineru_block(d)
    assert restored.table_body == block.table_body
    assert restored.table_caption == block.table_caption


def test_contentblock_default_blocks_empty():
    doc = FormattedDocument(formatted_markdown="text")
    assert doc.original_blocks == []

    result = TranslationResult(
        formatted_original="原文",
        translated_english="English",
        source_language="zh",
        terminology_map={},
        translation_warnings=[],
        sentences=[],
        segments=[],
    )
    assert result.original_blocks == []
    assert result.translated_blocks == []
