"""Local file persistence for cross-lingual documents and images."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from .contracts import (
    CrossLingualOutput,
    SavedDocuments,
    TranslationResult,
)


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

        # Save original.json (structured blocks)
        original_path = base / "original.json"
        original_data = {
            "metadata": {
                "doc_id": doc_id,
                "source_language": result.source_language,
                "block_count": len(result.original_blocks),
            },
            "blocks": [b.to_dict() for b in result.original_blocks],
        }
        original_path.write_text(
            json.dumps(original_data, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        logger.info("Saved original JSON: {}", original_path)

        # Save translated.json (structured blocks with translations)
        translated_path = base / "translated.json"
        translated_data = {
            "metadata": {
                "doc_id": doc_id,
                "source_language": result.source_language,
                "block_count": len(result.translated_blocks),
                "terminology_map": result.terminology_map,
                "translation_warnings": result.translation_warnings,
            },
            "blocks": [b.to_dict() for b in result.translated_blocks],
        }
        translated_path.write_text(
            json.dumps(translated_data, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        logger.info("Saved translated JSON: {}", translated_path)

        # Compute translation drift from segments
        source_parts = [seg.source_text for seg in result.segments]
        translated_parts = [seg.translated_text for seg in result.segments]
        from .cross_lingual.translate.postprocess import compute_translation_drift
        translation_drifts = compute_translation_drift(
            source_parts, translated_parts,
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
