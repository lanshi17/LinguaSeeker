"""Public service interface for document parsing."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.utils.rust_io import files_io
from loguru import logger

from .base import ParserStrategy
from .contracts import (
    DedupResult,
    MinerULocalBatchParseResult,
    MinerULocalBatchSaveResult,
    ParseAndSaveResult,
    ParseResult,
    SavedFiles,
)


class ParseDocumentService:
    """High-level facade for document parsing operations."""

    def __init__(self, orchestrator: ParserStrategy):
        self._orchestrator = orchestrator

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse a PDF file and return structured results.

        Args:
            pdf_path: URL to the PDF file (S3/MinIO or public URL).

        Returns:
            ParseResult with metadata, pages, and full markdown.
        """
        return await self._orchestrator.parse(pdf_path)

    async def parse_local_files(self, file_paths: list[str], **kwargs: object) -> MinerULocalBatchParseResult:
        """Parse local files through a MinerU remote batch upload workflow."""
        parser = getattr(self._orchestrator, "parse_local_files", None)
        if parser is None:
            raise AttributeError("Configured parser does not support parse_local_files")
        return await parser(file_paths, **kwargs)

    async def parse_local_files_and_save(
        self,
        file_paths: list[str],
        output_dir: str,
        **kwargs: object,
    ) -> MinerULocalBatchSaveResult:
        """Parse local files as a MinerU batch and save each completed result."""
        parse_result = await self.parse_local_files(file_paths, **kwargs)
        root = Path(output_dir)
        saved: dict[str, SavedFiles] = {}
        for file_name, result in parse_result.results.items():
            file_output_dir = root / Path(file_name).stem
            saved[file_name] = await self.save(result, str(file_output_dir))
        return MinerULocalBatchSaveResult(
            batch_id=parse_result.batch_id,
            parse_result=parse_result,
            saved_files=saved,
        )

    async def save(self, result: ParseResult, output_dir: str) -> SavedFiles:
        """Save parsed result to files.

        Args:
            result: ParseResult to save.
            output_dir: Directory to save output files.

        Returns:
            SavedFiles with paths to saved files.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        md_path = output_path / "output.md"
        files_io.File(str(md_path)).write(result.full_markdown)
        logger.info(f"Saved markdown to {md_path}")

        meta_path = output_path / "metadata.json"
        combined_meta = result.metadata.model_dump()
        combined_meta["pages"] = [p.model_dump() for p in result.pages]
        combined_meta["content_blocks"] = result.content_blocks
        files_io.File(str(meta_path)).write(json.dumps(combined_meta, indent=2))
        logger.info(f"Saved metadata to {meta_path}")

        images_dir: Path | None = None
        if result.images:
            images_dir = output_path / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            for rel_path, img_bytes in result.images.items():
                img_file = images_dir / Path(rel_path).name
                img_file.write_bytes(img_bytes)
            logger.info(f"Saved {len(result.images)} images to {images_dir}")

        return SavedFiles(
            md_path=md_path,
            metadata_path=meta_path,
            output_dir=output_path,
            created_at=datetime.now(timezone.utc),
            images_dir=images_dir,
        )

    async def dedup(
        self,
        file_paths: list[str],
        known_hashes: list[str],
    ) -> list[DedupResult]:
        """Check if files are duplicates based on content hash.

        Args:
            file_paths: List of file paths to check.
            known_hashes: List of known content hashes.

        Returns:
            List of DedupResult for each file.
        """
        results = []
        for file_path in file_paths:
            raw = files_io.check_duplicate(file_path, known_hashes)
            results.append(DedupResult(
                file_path=file_path,
                hash=raw.get("hash", ""),
                is_duplicate=raw.get("is_duplicate", False),
            ))
        return results

    async def parse_and_save(
        self,
        pdf_path: str,
        output_dir: str,
    ) -> ParseAndSaveResult:
        """Parse PDF and save output to files.

        Args:
            pdf_path: URL to the PDF file.
            output_dir: Directory to save output files.

        Returns:
            ParseAndSaveResult with parse result and saved file info.
        """
        parse_result = await self.parse(pdf_path)
        saved_files = await self.save(parse_result, output_dir)

        return ParseAndSaveResult(
            metadata=parse_result.metadata,
            pages=parse_result.pages,
            full_markdown=parse_result.full_markdown,
            parser_used=parse_result.parser_used,
            images=parse_result.images,
            content_blocks=parse_result.content_blocks,
            saved_files=saved_files,
        )
