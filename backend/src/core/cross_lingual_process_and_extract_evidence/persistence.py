"""Local file persistence for cross-lingual documents and images."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from .contracts import (
    CrossLingualOutput,
    OriginalLayoutReport,
    SavedDocuments,
    SentenceDrift,
    SentenceRegion,
    SegmentDrift,
    TranslatedLayoutReport,
    TranslationResult,
)
from .cross_lingual.format.formatter import compute_format_drift
from .cross_lingual.translate.translator import MultiStageTranslator


class DocumentPersistenceService:
    """Persists TranslationResult to local filesystem.

    Output structure::

        <output_dir>/<doc_id>/
            original.md
            translated.md
            metadata.json
            original_layout.json      # Layout + drift for formatted original
            translated_layout.json    # Layout + drift for translated text
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
        raw_markdown: str = "",
    ) -> SavedDocuments:
        """Save translation result and images to local directory.

        Args:
            result: The TranslationResult from the pipeline.
            output_dir: Root output directory.
            doc_id: Unique document identifier (used as subdirectory name).
            image_paths: Optional list of source image file paths to copy.
            raw_markdown: Original raw text before formatting (for drift computation).

        Returns:
            SavedDocuments with paths to all saved files.
        """
        base = Path(output_dir) / doc_id
        base.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)

        # Write markdown files
        original_path = base / "original.md"
        original_path.write_text(result.formatted_original, encoding="utf-8")
        logger.info("Saved original markdown: {}", original_path)

        translated_path = base / "translated.md"
        translated_path.write_text(result.translated_english, encoding="utf-8")
        logger.info("Saved translated markdown: {}", translated_path)

        # Build and save original layout report
        original_layout_path = base / "original_layout.json"
        self._save_original_layout(
            result, doc_id, raw_markdown, original_layout_path,
        )

        # Build and save translated layout report
        translated_layout_path = base / "translated_layout.json"
        self._save_translated_layout(result, doc_id, translated_layout_path)

        # Write metadata
        metadata = {
            "doc_id": doc_id,
            "source_language": result.source_language,
            "terminology_map": result.terminology_map,
            "translation_warnings": result.translation_warnings,
            "sentence_count": len(result.sentences),
            "segment_count": len(result.segments),
            "created_at": now.isoformat(),
        }
        meta_path = base / "metadata.json"
        meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
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
            shutil.copy2(src_path, dst)
            saved_image_paths.append(dst)
            logger.debug("Copied image: {} -> {}", src_path, dst)

        if saved_image_paths:
            logger.info("Copied {} images to {}", len(saved_image_paths), image_dir)

        return SavedDocuments(
            original_md_path=original_path,
            translated_md_path=translated_path,
            metadata_path=meta_path,
            image_dir=image_dir,
            image_paths=saved_image_paths,
            output_dir=base,
            created_at=now,
        )

    def _save_original_layout(
        self,
        result: TranslationResult,
        doc_id: str,
        raw_markdown: str,
        output_path: Path,
    ) -> None:
        """Build and save original layout report with format drift."""
        # Build sentence layout entries
        sentences: list[dict] = []
        for idx, sent in enumerate(result.sentences):
            sentences.append({
                "index": idx,
                "page": sent.page,
                "start_offset": sent.start_offset,
                "end_offset": sent.end_offset,
                "length": sent.span,
                "text": sent.text[:200],  # Truncate for readability
            })

        # Compute format drift if raw text is available
        format_drifts: list[SentenceDrift] = []
        if raw_markdown:
            format_drifts = compute_format_drift(raw_markdown, result.sentences)

        report = OriginalLayoutReport(
            doc_id=doc_id,
            source_language=result.source_language,
            raw_text_length=len(raw_markdown),
            formatted_text_length=len(result.formatted_original),
            sentence_count=len(result.sentences),
            page_count=max((s.page for s in result.sentences), default=0),
            sentences=sentences,
            format_drifts=format_drifts,
        )

        output_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Saved original layout: {}", output_path)

    def _save_translated_layout(
        self,
        result: TranslationResult,
        doc_id: str,
        output_path: Path,
    ) -> None:
        """Build and save translated layout report with translation drift."""
        # Build segment layout entries
        segments: list[dict] = []
        source_parts: list[str] = []
        translated_parts: list[str] = []

        for seg in result.segments:
            src_text = seg.source_text
            tr_text = seg.translated_text
            source_parts.append(src_text)
            translated_parts.append(tr_text)

            segments.append({
                "index": seg.index,
                "source_length": len(src_text),
                "translated_length": len(tr_text),
                "length_drift": len(tr_text) - len(src_text),
                "source_bbox": {
                    "page": seg.source_bbox.page,
                    "start_offset": seg.source_bbox.start_offset,
                    "end_offset": seg.source_bbox.end_offset,
                } if seg.source_bbox else None,
                "source_text": src_text[:200],
                "translated_text": tr_text[:200],
            })

        # Compute translation drift
        translation_drifts = MultiStageTranslator.compute_translation_drift(
            source_parts, translated_parts,
        )

        report = TranslatedLayoutReport(
            doc_id=doc_id,
            source_language=result.source_language,
            formatted_text_length=len(result.formatted_original),
            translated_text_length=len(result.translated_english),
            segment_count=len(result.segments),
            terminology_map=result.terminology_map,
            translation_warnings=result.translation_warnings,
            segments=segments,
            translation_drifts=translation_drifts,
        )

        output_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Saved translated layout: {}", output_path)

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
            original_md_path=str(saved.original_md_path),
            translated_md_path=str(saved.translated_md_path),
            image_paths=[str(p) for p in saved.image_paths],
        )
