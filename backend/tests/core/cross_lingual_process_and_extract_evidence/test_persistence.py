"""Tests for document persistence service."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    TranslationResult,
    SentenceRegion,
    SavedDocuments,
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
    def test_save_creates_markdown_files(self, tmp_path: Path):
        service = DocumentPersistenceService()
        result = _make_result()
        saved = service.save(result, output_dir=str(tmp_path), doc_id="doc001")

        assert saved.original_md_path.exists()
        assert saved.translated_md_path.exists()
        assert saved.original_md_path.read_text(encoding="utf-8") == "原始文本内容"
        assert saved.translated_md_path.read_text(encoding="utf-8") == "Original text content"

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
        assert output.saved_dir == str(saved.output_dir)
        assert output.original_md_path == str(saved.original_md_path)
