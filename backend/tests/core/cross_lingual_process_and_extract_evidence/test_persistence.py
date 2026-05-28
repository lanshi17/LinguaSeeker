"""Tests for document persistence service."""
from __future__ import annotations

import json
from pathlib import Path

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    ContentBlock,
    TranslationResult,
)
from src.core.cross_lingual_process_and_extract_evidence.persistence import (
    DocumentPersistenceService,
)


def _make_result(
    original: str = "原始文本内容",
    translated: str = "Original text content",
    lang: str = "zh",
) -> TranslationResult:
    return TranslationResult(
        formatted_original=original,
        translated_english=translated,
        source_language=lang,
        terminology_map={"基因": "gene"},
        translation_warnings=[],
        sentences=[],
        segments=[],
    )


class TestDocumentPersistenceService:
    def test_save_creates_json_files(self, tmp_path: Path):
        service = DocumentPersistenceService()
        result = _make_result()
        saved = service.save(result, output_dir=str(tmp_path), doc_id="doc001")

        assert saved.original_json_path.exists()
        assert saved.translated_json_path.exists()

        original = json.loads(saved.original_json_path.read_text(encoding="utf-8"))
        assert original["metadata"]["doc_id"] == "doc001"
        assert original["metadata"]["source_language"] == "zh"
        assert "blocks" in original

        translated = json.loads(saved.translated_json_path.read_text(encoding="utf-8"))
        assert translated["metadata"]["doc_id"] == "doc001"
        assert translated["metadata"]["terminology_map"] == {"基因": "gene"}
        assert "blocks" in translated

    def test_save_json_with_populated_blocks(self, tmp_path: Path):
        service = DocumentPersistenceService()
        result = TranslationResult(
            formatted_original="Title. Body text.",
            translated_english="Title. Body text.",
            source_language="en",
            terminology_map={},
            translation_warnings=[],
            sentences=[],
            segments=[],
            original_blocks=[
                ContentBlock(type="title", text="Title", text_level=1, page_idx=0),
                ContentBlock(type="text", text="Body text.", page_idx=0),
            ],
            translated_blocks=[
                ContentBlock(type="title", text="Title", text_level=1, page_idx=0),
                ContentBlock(type="text", text="Body text.", page_idx=0),
            ],
        )
        saved = service.save(result, output_dir=str(tmp_path), doc_id="doc002")

        original = json.loads(saved.original_json_path.read_text(encoding="utf-8"))
        assert original["metadata"]["block_count"] == 2
        assert original["blocks"][0]["type"] == "title"
        assert original["blocks"][0]["text"] == "Title"
        assert original["blocks"][0]["text_level"] == 1
        assert original["blocks"][1]["type"] == "text"

        translated = json.loads(saved.translated_json_path.read_text(encoding="utf-8"))
        assert translated["metadata"]["block_count"] == 2

        meta = json.loads(saved.metadata_path.read_text(encoding="utf-8"))
        assert meta["original_block_count"] == 2
        assert meta["translated_block_count"] == 2

    def test_save_creates_metadata_json(self, tmp_path: Path):
        service = DocumentPersistenceService()
        result = _make_result()
        saved = service.save(result, output_dir=str(tmp_path), doc_id="doc001")

        assert saved.metadata_path.exists()
        meta = json.loads(saved.metadata_path.read_text(encoding="utf-8"))
        assert meta["doc_id"] == "doc001"
        assert meta["source_language"] == "zh"
        assert meta["terminology_map"] == {"基因": "gene"}

    def test_save_copies_images(self, tmp_path: Path):
        # Create fake source images
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        img1 = src_dir / "fig1.png"
        img1.write_bytes(b"fake_png_1")
        img2 = src_dir / "fig2.png"
        img2.write_bytes(b"fake_png_2")

        service = DocumentPersistenceService()
        result = _make_result()
        saved = service.save(
            result,
            output_dir=str(tmp_path / "out"),
            doc_id="doc001",
            image_paths=[str(img1), str(img2)],
        )

        assert len(saved.image_paths) == 2
        for p in saved.image_paths:
            assert p.exists()
            assert p.read_bytes() in (b"fake_png_1", b"fake_png_2")
        assert saved.image_dir.exists()

    def test_save_no_images(self, tmp_path: Path):
        service = DocumentPersistenceService()
        result = _make_result()
        saved = service.save(result, output_dir=str(tmp_path), doc_id="doc001")

        assert saved.image_paths == []
        assert saved.image_dir.exists()  # dir still created

    def test_save_output_dir_structure(self, tmp_path: Path):
        service = DocumentPersistenceService()
        result = _make_result()
        saved = service.save(result, output_dir=str(tmp_path / "out"), doc_id="doc001")

        assert saved.output_dir == tmp_path / "out" / "doc001"
        assert saved.output_dir.exists()

    def test_to_output(self, tmp_path: Path):
        service = DocumentPersistenceService()
        result = _make_result()
        saved = service.save(result, output_dir=str(tmp_path), doc_id="doc001")
        output = service.to_output(result, saved)

        assert output.formatted_original == "原始文本内容"
        assert output.translated_english == "Original text content"
        assert output.output_dir == str(saved.output_dir)
        assert output.original_json_path == str(saved.original_json_path)
