from src.core.cross_lingual_process_and_extract_evidence.contracts import (
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
        original_md_path=Path("/tmp/out/original.md"),
        translated_md_path=Path("/tmp/out/translated.md"),
        metadata_path=Path("/tmp/out/metadata.json"),
        image_dir=Path("/tmp/out/images"),
        image_paths=[Path("/tmp/out/images/fig1.png")],
        output_dir=Path("/tmp/out"),
        created_at=datetime.now(timezone.utc),
    )
    assert saved.original_md_path.name == "original.md"
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
        original_md_path="/tmp/out/original.md",
        translated_md_path="/tmp/out/translated.md",
        image_paths=["/tmp/out/images/fig1.png"],
    )
    assert out.source_language == "zh"
    assert out.terminology_map["基因"] == "gene"
    assert len(out.image_paths) == 1


def test_pipeline_state_image_paths():
    """PipelineState carries image_paths from upstream."""
    state = PipelineState(pages=[], image_paths=["/data/img1.png", "/data/img2.png"])
    assert len(state.image_paths) == 2
