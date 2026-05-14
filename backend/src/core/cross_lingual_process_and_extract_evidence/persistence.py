"""Local file persistence for cross-lingual documents and images."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List

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
            original.md
            translated.md
            metadata.json
            images/
                page1_fig1.png
                ...
    """

    def save(
        self,
        result: TranslationResult,
        output_dir: str,
        doc_id: str,
        image_paths: List[str] | None = None,
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

        # Write markdown files
        original_path = base / "original.md"
        original_path.write_text(result.formatted_original, encoding="utf-8")
        logger.info("Saved original markdown: {}", original_path)

        translated_path = base / "translated.md"
        translated_path.write_text(result.translated_english, encoding="utf-8")
        logger.info("Saved translated markdown: {}", translated_path)

        # Write metadata
        metadata = {
            "doc_id": doc_id,
            "source_language": result.source_language,
            "terminology_map": result.terminology_map,
            "translation_warnings": result.translation_warnings,
            "sentence_count": len(result.sentences),
            "segment_count": len(result.segments),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_path = base / "metadata.json"
        meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Saved metadata: {}", meta_path)

        # Copy images
        image_dir = base / "images"
        image_dir.mkdir(exist_ok=True)
        saved_image_paths: List[Path] = []
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
            created_at=datetime.now(timezone.utc),
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
            saved_dir=str(saved.output_dir),
            original_md_path=str(saved.original_md_path),
            translated_md_path=str(saved.translated_md_path),
            image_paths=[str(p) for p in saved.image_paths],
        )
