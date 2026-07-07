"""Public service interface for document parsing."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.rust_io import files_io
from loguru import logger

from .contracts import (
    DedupResult,
    MinerULocalBatchParseResult,
    MinerULocalBatchSaveResult,
    ParseAndSaveResult,
    ParseResult,
    SavedFiles,
)

if TYPE_CHECKING:
    from .orchestrator import DocumentParseOrchestrator


class ParseDocumentService:
    """High-level facade for document parsing operations."""

    def __init__(self, orchestrator: DocumentParseOrchestrator):
        self._orchestrator = orchestrator

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse a PDF file and return structured results.

        Args:
            pdf_path: Path to the PDF file (local path or URL).

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
        batch = await self.parse_local_files(file_paths, **kwargs)
        saved = {}
        for name, result in batch.results.items():
            saved[name] = await self.save(result, output_dir)
        return MinerULocalBatchSaveResult(
            batch_id=batch.batch_id,
            parse_result=batch,
            saved_files=saved,
        )

    async def save(self, result: ParseResult, output_dir: str) -> SavedFiles:
        """Save parsed result to files.

        Writes markdown, metadata JSON, and decodes images to the output directory.

        Args:
            result: ParseResult from a previous parse() call.
            output_dir: Directory to write output files.

        Returns:
            SavedFiles with paths to written files.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        created_at = datetime.now(timezone.utc)

        md_path = out / "output.md"
        md_path.write_text(result.full_markdown, encoding="utf-8")

        meta = {
            "parser_used": result.parser_used,
            "page_count": len(result.pages),
            "metadata": result.metadata.model_dump(),
            "saved_at": created_at.isoformat(),
        }
        meta_path = out / "metadata.json"
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        images_dir: Path | None = None
        if result.images:
            images_dir = out / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            for name, data in result.images.items():
                try:
                    if isinstance(data, str):
                        import base64

                        data = base64.b64decode(data.split(",", 1)[-1])
                    img_path = images_dir / Path(name).name
                    img_path.write_bytes(data)
                except Exception as exc:
                    logger.warning(f"Failed to decode image {name}: {exc}")

        return SavedFiles(
            md_path=md_path,
            metadata_path=meta_path,
            output_dir=out,
            created_at=created_at,
            images_dir=images_dir,
        )

    async def dedup(
        self,
        file_paths: list[str],
        known_hashes: list[str] | None = None,
    ) -> list[DedupResult]:
        """Check if files are duplicates based on content hash.

        Args:
            file_paths: List of file paths to check.
            known_hashes: Optional hashes to treat as already seen.

        Returns:
            List of DedupResult with hash and duplicate status.
        """
        known = set(known_hashes or [])
        seen_hashes: set[str] = set()
        results: list[DedupResult] = []
        for fp in file_paths:
            try:
                checker = getattr(files_io, "check_duplicate", None)
                if checker is not None and known_hashes is not None:
                    duplicate = checker(fp, list(known | seen_hashes))
                    sha = duplicate.get("hash", "")
                    is_dup = duplicate.get("is_duplicate", sha in known or sha in seen_hashes)
                else:
                    sha = files_io.sha256_file(fp)
                    is_dup = sha in known or sha in seen_hashes
                if sha:
                    seen_hashes.add(sha)
                results.append(DedupResult(file_path=fp, hash=sha, is_duplicate=is_dup))
            except Exception as exc:
                logger.warning(f"Dedup hash failed for {fp}: {exc}")
                results.append(DedupResult(file_path=fp, hash="", is_duplicate=False))
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
