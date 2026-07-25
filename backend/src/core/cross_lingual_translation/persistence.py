"""Local file persistence for cross-lingual documents and images."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from src.utils.rust_io import files_io

from .contracts import (
    CrossLingualOutput,
    SavedDocuments,
    TranslationAlignmentChunk,
    TranslationResult,
)


def _write_json(path: Path, data: str) -> None:
    """Write JSON string to file, using rust_io when available, stdlib otherwise.

    Rust-backed IO exceptions (RuntimeError from panics, SystemError from PyO3
    internals) are normalized to OSError for consistent I/O error handling.
    MemoryError and other critical exceptions propagate unchanged.
    """
    if files_io is not None:
        try:
            files_io.File(str(path)).write(data)
        except OSError:
            raise
        except (RuntimeError, SystemError) as e:
            # PyO3 native exceptions (e.g. Rust panic, IOError from tokio)
            # are not OSError subclasses — wrap them for consistent handling.
            raise OSError(f"Failed to write {path}: {e}") from e
    else:
        path.write_text(data, encoding="utf-8")


def _find_text_after(text: str, needle: str, cursor: int) -> int:
    """Find text at or after cursor, falling back to a global search."""
    if not needle:
        return -1
    start = text.find(needle, max(cursor, 0))
    if start >= 0:
        return start
    return text.find(needle)


def _build_translation_alignment(result: TranslationResult) -> list[TranslationAlignmentChunk]:
    """Build deterministic source-English alignment from translation segments."""
    alignment: list[TranslationAlignmentChunk] = []
    source_cursor = 0
    english_cursor = 0
    for idx, segment in enumerate(result.segments, start=1):
        chunk_id = segment.chunk_id or f"c_{idx:04d}"

        if segment.source_start_offset >= 0 and segment.source_end_offset >= segment.source_start_offset:
            original_start = segment.source_start_offset
            original_end = segment.source_end_offset
        elif segment.source_bbox is not None:
            original_start = segment.source_bbox.start_offset
            original_end = segment.source_bbox.end_offset
        else:
            original_start = _find_text_after(result.formatted_original, segment.source_text, source_cursor)
            original_end = original_start + len(segment.source_text) if original_start >= 0 else -1

        if segment.translated_start_offset >= 0 and segment.translated_end_offset >= segment.translated_start_offset:
            english_start = segment.translated_start_offset
            english_end = segment.translated_end_offset
        else:
            english_start = _find_text_after(result.translated_english, segment.translated_text, english_cursor)
            english_end = english_start + len(segment.translated_text) if english_start >= 0 else -1

        if original_end >= 0:
            source_cursor = original_end
        if english_end >= 0:
            english_cursor = english_end

        alignment.append(
            TranslationAlignmentChunk(
                chunk_id=chunk_id,
                original_text=segment.source_text,
                english_text=segment.translated_text,
                original_start_offset=original_start,
                original_end_offset=original_end,
                english_start_offset=english_start,
                english_end_offset=english_end,
                page=segment.source_bbox.page if segment.source_bbox is not None else 1,
                block_index=segment.index,
                span_pairs=segment.span_pairs,
            )
        )
    return alignment


class DocumentPersistenceService:
    """Persists TranslationResult to local filesystem.

    Output structure::

        <output_dir>/<doc_id>/
            original.json         # Structured blocks
            translated.json       # Structured blocks with translations
            metadata.json         # Document metadata
            images/
                page1_fig1.png
                ...
    """

    def save(
        self,
        result: TranslationResult,
        output_dir: str,
        doc_id: str,
        image_paths: list[str] | None = None,
    ) -> SavedDocuments:
        """Save translation result and images to local directory.

        Args:
            result: The TranslationResult from the pipeline.
            output_dir: Root output directory.
            doc_id: Unique document identifier (used as subdirectory name).
            image_paths: Optional list of source image file paths to copy.

        Returns:
            SavedDocuments with paths to all saved files.
        """
        base = Path(output_dir) / doc_id
        base.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)

        # Save original.json — always include formatted_text so the evidence
        # viewer can use it as the authoritative full text (source-span offsets
        # are relative to this text).
        original_path = base / "original.json"
        original_data: dict = {
            "metadata": {
                "doc_id": doc_id,
                "source_language": result.source_language,
                "block_count": len(result.original_blocks),
            },
            "blocks": [b.to_dict() for b in result.original_blocks],
            "formatted_text": result.formatted_original,
        }
        _write_json(original_path, json.dumps(original_data, ensure_ascii=False, indent=2))
        logger.info("Saved original JSON: {}", original_path)

        # Save translated.json — always include formatted_text (the
        # authoritative translated text used during extraction).
        translated_path = base / "translated.json"
        translation_alignment = _build_translation_alignment(result)
        translation_alignment_payload = [chunk.model_dump(mode="json") for chunk in translation_alignment]
        translated_data: dict = {
            "metadata": {
                "doc_id": doc_id,
                "source_language": result.source_language,
                "block_count": len(result.translated_blocks),
                "terminology_map": result.terminology_map,
                "translation_warnings": result.translation_warnings,
                "translation_alignment": translation_alignment_payload,
            },
            "blocks": [b.to_dict() for b in result.translated_blocks],
            "formatted_text": result.translated_english,
        }
        _write_json(translated_path, json.dumps(translated_data, ensure_ascii=False, indent=2))
        logger.info("Saved translated JSON: {}", translated_path)

        # Compute translation drift from segments
        source_parts = [seg.source_text for seg in result.segments]
        translated_parts = [seg.translated_text for seg in result.segments]
        from .translate.postprocess import compute_translation_drift

        translation_drifts = compute_translation_drift(
            source_parts,
            translated_parts,
        )

        # Save metadata.json (enhanced with drift info)
        metadata = {
            "doc_id": doc_id,
            "source_language": result.source_language,
            "terminology_map": result.terminology_map,
            "translation_warnings": result.translation_warnings,
            "sentence_count": len(result.sentences),
            "segment_count": len(result.segments),
            "original_block_count": len(result.original_blocks),
            "translated_block_count": len(result.translated_blocks),
            "translation_alignment": translation_alignment_payload,
            "translation_drifts": [
                {
                    "segment_index": d.segment_index,
                    "source_length": d.source_length,
                    "translated_length": d.translated_length,
                    "length_drift": d.length_drift,
                    "source_text": d.source_text,
                    "translated_text": d.translated_text,
                }
                for d in translation_drifts
            ],
            "created_at": now.isoformat(),
        }
        meta_path = base / "metadata.json"
        _write_json(meta_path, json.dumps(metadata, ensure_ascii=False, indent=2))
        logger.info("Saved metadata: {}", meta_path)

        # Copy images
        image_dir = base / "images"
        image_dir.mkdir(exist_ok=True)
        saved_image_paths: list[Path] = []
        for src in image_paths or []:
            src_path = Path(src)
            if not src_path.exists():
                logger.warning("Image not found, skipping: {}", src)
                continue
            dst = image_dir / src_path.name
            if src_path.resolve() == dst.resolve():
                saved_image_paths.append(dst)
                continue
            shutil.copy2(src_path, dst)
            saved_image_paths.append(dst)
            logger.debug("Copied image: {} -> {}", src_path, dst)

        if saved_image_paths:
            logger.info("Copied {} images to {}", len(saved_image_paths), image_dir)

        return SavedDocuments(
            original_json_path=original_path,
            translated_json_path=translated_path,
            metadata_path=meta_path,
            image_dir=image_dir,
            image_paths=saved_image_paths,
            output_dir=base,
            created_at=now,
        )

    @staticmethod
    def to_output(
        result: TranslationResult,
        saved: SavedDocuments,
    ) -> CrossLingualOutput:
        """Convert to downstream output contract."""
        return CrossLingualOutput(
            formatted_original=result.formatted_original,
            translated_english=result.translated_english,
            source_language=result.source_language,
            terminology_map=result.terminology_map,
            translation_warnings=result.translation_warnings,
            output_dir=str(saved.output_dir),
            original_json_path=str(saved.original_json_path),
            translated_json_path=str(saved.translated_json_path),
            image_paths=[str(p) for p in saved.image_paths],
        )
