"""MinerU API parser implementation via rust_io.net."""
from __future__ import annotations

import asyncio
import json
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import TypedDict

import httpx
from loguru import logger

import rust_io.net as net_io

from .base import ParserStrategy
from .contracts import (
    DocumentMetadata,
    ParseResult,
    pages_from_raw,
)
from .exceptions import MinerUAPIError, MinerUTimeoutError


class _MinerUPageData(TypedDict):
    page_number: int
    markdown: str
    figures: list[dict]
    tables: list[dict]


class _MinerURawResult(TypedDict):
    state: str
    total_pages: int
    title: str | None
    authors: list[str]
    abstract: str | None
    pages: list[_MinerUPageData]
    full_markdown: str


class MinerUParser(ParserStrategy):
    """PDF parser using MinerU API via Rust net-io layer.

    MinerU uses an async task-based API:
    1. Create task with PDF URL -> get task_id
    2. Poll for task completion -> get zip URL
    3. Download and extract zip -> parse content
    """

    def __init__(
        self,
        api_token: str,
        poll_interval: float = 2.0,
        max_poll_attempts: int = 150,
    ):
        self._api_token = api_token
        self._poll_interval = poll_interval
        self._max_poll_attempts = max_poll_attempts

    @property
    def name(self) -> str:
        return "mineru"

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse PDF via MinerU API.

        Args:
            pdf_path: URL to the PDF file (S3/MinIO or public URL).

        Returns:
            ParseResult with metadata, pages, and full markdown.

        Raises:
            MinerUAPIError: On API errors or task failure.
            MinerUTimeoutError: On polling timeout.
        """
        logger.info(f"MinerU parsing: {pdf_path}")

        task_id = await self._create_task(pdf_path)
        logger.info(f"MinerU task created: {task_id}")

        zip_url = await self._poll_result(task_id)
        logger.info(f"MinerU task done, downloading zip from: {zip_url}")

        result_data = await self._download_and_parse_zip(zip_url)

        return self._build_result(result_data)

    async def _create_task(self, pdf_path: str) -> str:
        """Create MinerU parsing task and return task_id."""
        try:
            response = await net_io.mineru_create_task(
                url=pdf_path,
                token=self._api_token,
                enable_formula=True,
                enable_table=True,
            )
        except Exception as e:
            raise MinerUAPIError(f"Failed to create task: {e}") from e

        # Response format: {"code": 0, "data": {"task_id": "..."}, "msg": "ok"}
        data = response.get("data", {})
        task_id = data.get("task_id") if isinstance(data, dict) else None
        if not task_id:
            raise MinerUAPIError(f"No task_id in response: {response}")

        return task_id

    async def _poll_result(self, task_id: str) -> str:
        """Poll for task result until completion or timeout.

        Returns:
            URL to the zip file containing parsed results.
        """
        for attempt in range(self._max_poll_attempts):
            try:
                response = await net_io.mineru_get_result(
                    task_id=task_id,
                    token=self._api_token,
                )
            except Exception as e:
                raise MinerUAPIError(f"Failed to get result: {e}") from e

            # Response format: {"code": 0, "data": {"state": "...", ...}, "msg": "ok"}
            data = response.get("data", {})
            if not isinstance(data, dict):
                raise MinerUAPIError(f"Invalid response format: {response}")

            state = data.get("state", "")

            if state == "done":
                zip_url = data.get("full_zip_url")
                if not zip_url:
                    raise MinerUAPIError(f"No zip URL in done response: {data}")
                return zip_url
            elif state == "failed":
                error_msg = data.get("err_msg", "Unknown error")
                raise MinerUAPIError(f"Task failed: {error_msg}")
            elif state in ("pending", "running", "converting"):
                logger.debug(f"Task {task_id} state: {state}, waiting...")
                await asyncio.sleep(self._poll_interval)
            else:
                raise MinerUAPIError(f"Unknown task state: {state}")

        raise MinerUTimeoutError(total_timeout=self._poll_interval * self._max_poll_attempts)

    async def _download_and_parse_zip(self, zip_url: str) -> _MinerURawResult:
        """Download zip file and extract parsed content."""
        async with httpx.AsyncClient() as client:
            response = await client.get(zip_url, timeout=120.0)
            response.raise_for_status()

        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "result.zip"
            zip_path.write_bytes(response.content)

            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(tmp_dir)

            return self._parse_extracted_content(Path(tmp_dir))

    def _parse_extracted_content(self, extract_dir: Path) -> _MinerURawResult:
        """Parse extracted zip content into structured result."""
        # Look for content_list.json or similar
        json_files = list(extract_dir.rglob("*.json"))
        md_files = list(extract_dir.rglob("*.md"))

        # Try to find structured content
        content_data = None
        for jf in json_files:
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "pdf_info" in data:
                    content_data = data
                    break
                elif isinstance(data, list) and len(data) > 0:
                    # Might be content list
                    content_data = {"pages": data}
                    break
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

        if content_data:
            return self._parse_content_json(content_data, md_files)
        elif md_files:
            # Fallback: use markdown files directly
            return self._parse_markdown_files(md_files)
        else:
            raise MinerUAPIError(f"No parseable content found in zip. Files: {list(extract_dir.rglob('*'))}")

    def _parse_content_json(self, data: dict, md_files: list[Path]) -> _MinerURawResult:
        """Parse MinerU content_list.json format."""
        pdf_info = data.get("pdf_info", [])
        if not pdf_info:
            # Try alternative format
            pages_data = data.get("pages", [])
            if pages_data:
                return _MinerURawResult(
                    state="done",
                    total_pages=len(pages_data),
                    title=data.get("title"),
                    authors=data.get("authors", []),
                    abstract=data.get("abstract"),
                    pages=pages_data,
                    full_markdown="\n\n".join(p.get("markdown", "") for p in pages_data),
                )
            raise MinerUAPIError(f"Unexpected JSON structure: {list(data.keys())}")

        # Parse pdf_info format
        pages = []
        full_markdown_parts = []
        for i, page_info in enumerate(pdf_info, start=1):
            page_md = page_info.get("page_content", "")
            if not page_md:
                # Try alternative key
                page_md = page_info.get("markdown", "")
            full_markdown_parts.append(page_md)
            pages.append({
                "page_number": i,
                "markdown": page_md,
                "figures": [],
                "tables": [],
            })

        return _MinerURawResult(
            state="done",
            total_pages=len(pages),
            title=data.get("title"),
            authors=data.get("authors", []),
            abstract=data.get("abstract"),
            pages=pages,
            full_markdown="\n\n".join(full_markdown_parts),
        )

    def _parse_markdown_files(self, md_files: list[Path]) -> _MinerURawResult:
        """Parse markdown files as fallback."""
        pages = []
        full_markdown_parts = []
        for i, md_file in enumerate(sorted(md_files), start=1):
            content = md_file.read_text(encoding="utf-8")
            full_markdown_parts.append(content)
            pages.append({
                "page_number": i,
                "markdown": content,
                "figures": [],
                "tables": [],
            })

        return _MinerURawResult(
            state="done",
            total_pages=len(pages),
            title=None,
            authors=[],
            abstract=None,
            pages=pages,
            full_markdown="\n\n".join(full_markdown_parts),
        )

    def _build_result(self, data: _MinerURawResult) -> ParseResult:
        """Convert MinerU response to ParseResult."""
        metadata = DocumentMetadata(
            total_pages=data.get("total_pages", 1),
            title=data.get("title"),
            authors=data.get("authors", []),
            abstract_text=data.get("abstract"),
        )

        return ParseResult(
            metadata=metadata,
            pages=pages_from_raw(data.get("pages", [])),
            full_markdown=data.get("full_markdown", ""),
            parser_used=self.name,
        )
