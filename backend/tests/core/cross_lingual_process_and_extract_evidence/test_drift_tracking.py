"""Tests for character drift tracking between raw, formatted, and translated text."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    OriginalLayoutReport,
    SegmentDrift,
    SentenceDrift,
    SentenceRegion,
    TranslatedLayoutReport,
    TranslationResult,
    TranslationSegment,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.formatter import (
    compute_format_drift,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.postprocess import (
    compute_translation_drift,
)


class TestComputeFormatDrift:
    """Tests for format drift computation."""

    def test_no_drift_when_identical(self):
        """When raw and formatted are identical, drift should be 0."""
        text = "First sentence. Second sentence."
        sentences = [
            SentenceRegion(page=1, start_offset=0, end_offset=15, text="First sentence."),
            SentenceRegion(page=1, start_offset=16, end_offset=32, text="Second sentence."),
        ]
        drifts = compute_format_drift(text, sentences)
        assert len(drifts) == 2
        assert drifts[0].drift == 0
        assert drifts[1].drift == 0

    def test_drift_from_whitespace_normalization(self):
        """Whitespace normalization should cause positive drift."""
        raw = "First sentence.   \n\n\n\nSecond sentence."
        formatted = "First sentence.\n\nSecond sentence."
        sentences = [
            SentenceRegion(page=1, start_offset=0, end_offset=15, text="First sentence."),
            SentenceRegion(page=1, start_offset=17, end_offset=34, text="Second sentence."),
        ]
        drifts = compute_format_drift(raw, sentences)
        assert len(drifts) == 2
        # First sentence starts at same position
        assert drifts[0].raw_start == 0
        # Second sentence should have shifted due to whitespace collapse
        assert drifts[1].drift < 0  # formatted position is earlier

    def test_drift_preserves_page_info(self):
        """Drift entries should preserve page numbers from sentences."""
        text = "Page one content. Page two content."
        sentences = [
            SentenceRegion(page=1, start_offset=0, end_offset=17, text="Page one content."),
            SentenceRegion(page=2, start_offset=18, end_offset=35, text="Page two content."),
        ]
        drifts = compute_format_drift(text, sentences)
        assert drifts[0].page == 1
        assert drifts[1].page == 2

    def test_empty_sentences(self):
        """Empty sentences list should return empty drifts."""
        drifts = compute_format_drift("some text", [])
        assert drifts == []

    def test_single_sentence(self):
        """Single sentence should produce one drift entry."""
        text = "Only one sentence here."
        sentences = [
            SentenceRegion(page=1, start_offset=0, end_offset=23, text="Only one sentence here."),
        ]
        drifts = compute_format_drift(text, sentences)
        assert len(drifts) == 1
        assert drifts[0].sentence_index == 0


class TestComputeTranslationDrift:
    """Tests for translation drift computation."""

    def test_equal_length_segments(self):
        """Equal length segments should have zero length drift."""
        # Both 12 chars
        source = ["Hello world!", "Goodbye worl"]
        translated = ["Hola mundo!!", "Adios mundo!"]
        drifts = compute_translation_drift(source, translated)
        assert len(drifts) == 2
        assert drifts[0].length_drift == 0
        assert drifts[1].length_drift == 0

    def test_expansion_drift(self):
        """Longer translation should show positive length drift."""
        source = ["Short."]
        translated = ["This is a much longer translation."]
        drifts = compute_translation_drift(source, translated)
        assert len(drifts) == 1
        assert drifts[0].length_drift > 0
        assert drifts[0].translated_length > drifts[0].source_length

    def test_contraction_drift(self):
        """Shorter translation should show negative length drift."""
        source = ["This is a very long source sentence."]
        translated = ["Short."]
        drifts = compute_translation_drift(source, translated)
        assert len(drifts) == 1
        assert drifts[0].length_drift < 0

    def test_offset_tracking(self):
        """Offsets should accumulate correctly across segments."""
        source = ["First.", "Second.", "Third."]
        translated = ["Primero.", "Segundo.", "Tercero."]
        drifts = compute_translation_drift(source, translated)

        # First segment starts at 0
        assert drifts[0].source_start == 0
        assert drifts[0].translated_start == 0

        # Second segment starts after first + "\n\n"
        assert drifts[1].source_start == len("First.") + 2
        assert drifts[1].translated_start == len("Primero.") + 2

    def test_empty_segments(self):
        """Empty segment lists should return empty drifts."""
        drifts = compute_translation_drift([], [])
        assert drifts == []

    def test_mismatched_lengths(self):
        """Mismatched segment counts should handle gracefully."""
        source = ["One.", "Two."]
        translated = ["Only one translation."]
        drifts = compute_translation_drift(source, translated)
        assert len(drifts) == 2
        assert drifts[1].translated_text == ""


class TestOriginalLayoutReport:
    """Tests for OriginalLayoutReport serialization."""

    def test_to_dict_structure(self):
        """to_dict should return correct structure with metadata."""
        report = OriginalLayoutReport(
            doc_id="test-123",
            source_language="zh",
            raw_text_length=1000,
            formatted_text_length=950,
            sentence_count=10,
            page_count=3,
            sentences=[{"index": 0, "page": 1, "start_offset": 0, "end_offset": 50, "length": 50, "text": "test"}],
            format_drifts=[
                SentenceDrift(
                    sentence_index=0, page=1,
                    raw_start=0, raw_end=55,
                    formatted_start=0, formatted_end=50,
                    drift=-5, text="test",
                ),
            ],
        )
        d = report.to_dict()

        assert d["metadata"]["doc_id"] == "test-123"
        assert d["metadata"]["source_language"] == "zh"
        assert d["metadata"]["sentence_count"] == 10
        assert len(d["sentences"]) == 1
        assert len(d["format_drifts"]) == 1
        assert d["format_drifts"][0]["drift"] == -5


class TestTranslatedLayoutReport:
    """Tests for TranslatedLayoutReport serialization."""

    def test_to_dict_structure(self):
        """to_dict should return correct structure with metadata."""
        report = TranslatedLayoutReport(
            doc_id="test-456",
            source_language="zh",
            formatted_text_length=950,
            translated_text_length=1100,
            segment_count=5,
            terminology_map={"基因": "gene"},
            translation_warnings=["warning1"],
            segments=[{"index": 0, "source_length": 100, "translated_length": 120}],
            translation_drifts=[
                SegmentDrift(
                    segment_index=0,
                    source_start=0, source_end=100,
                    translated_start=0, translated_end=120,
                    source_length=100, translated_length=120,
                    length_drift=20,
                    source_text="source", translated_text="translated",
                ),
            ],
        )
        d = report.to_dict()

        assert d["metadata"]["doc_id"] == "test-456"
        assert d["metadata"]["terminology_count"] == 1
        assert d["metadata"]["warning_count"] == 1
        assert len(d["segments"]) == 1
        assert len(d["translation_drifts"]) == 1
        assert d["translation_drifts"][0]["length_drift"] == 20


class TestPersistenceSavesLayoutJson:
    """Tests for persistence service saving structured JSON files."""

    def test_save_creates_original_json(self, tmp_path):
        """save() should create original.json with structured blocks."""
        from src.core.cross_lingual_process_and_extract_evidence.persistence import (
            DocumentPersistenceService,
        )

        result = TranslationResult(
            formatted_original="Test content.",
            translated_english="Translated content.",
            source_language="en",
            terminology_map={},
            translation_warnings=[],
            sentences=[
                SentenceRegion(page=1, start_offset=0, end_offset=12, text="Test content."),
            ],
            segments=[],
        )

        service = DocumentPersistenceService()
        saved = service.save(result, str(tmp_path), "test-doc")

        original_path = saved.output_dir / "original.json"
        assert original_path.exists()

        data = json.loads(original_path.read_text())
        assert "metadata" in data
        assert "blocks" in data
        assert data["metadata"]["doc_id"] == "test-doc"

    def test_save_creates_translated_json(self, tmp_path):
        """save() should create translated.json with structured blocks."""
        from src.core.cross_lingual_process_and_extract_evidence.persistence import (
            DocumentPersistenceService,
        )

        result = TranslationResult(
            formatted_original="Source text.",
            translated_english="Translated text.",
            source_language="zh",
            terminology_map={"测试": "test"},
            translation_warnings=[],
            sentences=[],
            segments=[
                TranslationSegment(
                    index=0,
                    source_text="Source text.",
                    translated_text="Translated text.",
                ),
            ],
        )

        service = DocumentPersistenceService()
        saved = service.save(result, str(tmp_path), "test-doc")

        translated_path = saved.output_dir / "translated.json"
        assert translated_path.exists()

        data = json.loads(translated_path.read_text())
        assert "metadata" in data
        assert "blocks" in data
        assert data["metadata"]["terminology_map"]["测试"] == "test"

    def test_save_metadata_includes_block_counts(self, tmp_path):
        """save() should include block counts in metadata.json."""
        from src.core.cross_lingual_process_and_extract_evidence.persistence import (
            DocumentPersistenceService,
        )

        result = TranslationResult(
            formatted_original="Test.",
            translated_english="Test.",
            source_language="en",
            terminology_map={},
            translation_warnings=[],
            sentences=[],
            segments=[],
        )

        service = DocumentPersistenceService()
        saved = service.save(result, str(tmp_path), "test-doc")

        meta_path = saved.output_dir / "metadata.json"
        data = json.loads(meta_path.read_text())

        assert "original_block_count" in data
        assert "translated_block_count" in data
        assert data["original_block_count"] == 0
        assert data["translated_block_count"] == 0
