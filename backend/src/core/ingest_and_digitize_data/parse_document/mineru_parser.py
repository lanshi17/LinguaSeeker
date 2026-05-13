"""MinerU API parser implementation via rust_io.net."""
from __future__ import annotations

import asyncio
import json
import tempfile
import zipfile
from collections import defaultdict
from html.parser import HTMLParser
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


class _TableParser(HTMLParser):
    """HTML table parser that extracts rows and detects <th> header rows."""

    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self.has_th: bool = False
        self._current_row: list[str] = []
        self._current_cell = ""
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag in ("td", "th"):
            self._in_cell = True
            self._current_cell = ""
            if tag == "th":
                self.has_th = True
        elif tag == "tr":
            self._current_row = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._in_cell = False
            self._current_row.append(self._current_cell.strip())
        elif tag == "tr" and self._current_row:
            self.rows.append(self._current_row)

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell += data


def _html_table_to_markdown(html: str) -> str:
    """Convert HTML <table> to markdown table format."""
    parser = _TableParser()
    parser.feed(html)

    if not parser.rows:
        return ""

    col_count = max(len(row) for row in parser.rows)
    for row in parser.rows:
        while len(row) < col_count:
            row.append("")

    lines = []
    lines.append("| " + " | ".join(parser.rows[0]) + " |")
    lines.append("| " + " | ".join(["---"] * col_count) + " |")
    for row in parser.rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _html_table_to_structured(html: str) -> tuple[list[str], list[list[str]]]:
    """Extract headers and data rows from HTML <table>.

    Returns (headers, rows) where headers is the first row and rows is the rest.
    """
    parser = _TableParser()
    parser.feed(html)

    if not parser.rows:
        return [], []

    headers = parser.rows[0]
    rows = parser.rows[1:]
    return headers, rows


def _block_to_markdown(block: dict) -> str:
    """Convert a single content_list block to markdown."""
    block_type = block.get("type", "text")

    if block_type == "text":
        text = block.get("text", "")
        level = block.get("text_level")
        if level and isinstance(level, int) and 1 <= level <= 6:
            return f"{'#' * level} {text}"
        return text

    if block_type == "image":
        caption = block.get("image_caption", [])
        img_path = block.get("img_path", "")
        caption_text = caption[0] if caption else ""
        footnote = block.get("image_footnote", [])
        parts = []
        if img_path:
            parts.append(f"![{caption_text}]({img_path})")
        elif caption_text:
            parts.append(caption_text)
        if footnote:
            parts.append(f"*{footnote[0]}*")
        return "\n\n".join(parts)

    if block_type == "table":
        parts = []
        caption = block.get("table_caption", [])
        if caption:
            parts.append(f"**{caption[0]}**")

        table_body = block.get("table_body", "")
        if table_body:
            md_table = _html_table_to_markdown(table_body)
            if md_table:
                parts.append(md_table)

        footnote = block.get("table_footnote", [])
        if footnote:
            parts.append(f"*{footnote[0]}*")

        return "\n\n".join(parts)

    return ""


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
        return "mineru-remote"

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
        json_files = list(extract_dir.rglob("*.json"))
        md_files = list(extract_dir.rglob("*.md"))

        # Priority 1: *_content_list.json (new MinerU format with structured blocks)
        content_list_files = [f for f in extract_dir.rglob("*_content_list.json")]
        full_md_path = extract_dir / "full.md"
        full_markdown = full_md_path.read_text(encoding="utf-8") if full_md_path.exists() else ""

        if content_list_files:
            try:
                data = json.loads(content_list_files[0].read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    return self._parse_content_list_json(data, full_markdown)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        # Priority 2: layout.json with pdf_info
        for jf in json_files:
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "pdf_info" in data:
                    return self._parse_content_json(data, md_files)
                elif isinstance(data, list) and len(data) > 0:
                    content_data = {"pages": data}
                    return self._parse_content_json(content_data, md_files)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

        # Priority 3: markdown files
        if md_files:
            return self._parse_markdown_files(md_files)

        # Priority 4: full.md only
        if full_markdown:
            return _MinerURawResult(
                state="done",
                total_pages=1,
                title=None,
                authors=[],
                abstract=None,
                pages=[_MinerUPageData(page_number=1, markdown=full_markdown, figures=[], tables=[])],
                full_markdown=full_markdown,
            )

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

    def _parse_content_list_json(self, content_list: list[dict], full_markdown: str) -> _MinerURawResult:
        """Parse MinerU *_content_list.json with text, image, table blocks."""
        pages_map: dict[int, list[dict]] = defaultdict(list)
        for item in content_list:
            if item.get("type") == "discarded":
                continue
            page_idx = item.get("page_idx", 0)
            pages_map[page_idx].append(item)

        if not pages_map:
            return _MinerURawResult(
                state="done",
                total_pages=1,
                title=None,
                authors=[],
                abstract=None,
                pages=[_MinerUPageData(page_number=1, markdown=full_markdown, figures=[], tables=[])],
                full_markdown=full_markdown,
            )

        pages: list[_MinerUPageData] = []
        full_parts: list[str] = []
        for page_idx in sorted(pages_map.keys()):
            page_number = page_idx + 1
            parts: list[str] = []
            figures: list[dict] = []
            tables: list[dict] = []
            for block in pages_map[page_idx]:
                block_type = block.get("type", "text")
                md = _block_to_markdown(block)
                if md:
                    parts.append(md)
                if block_type == "image":
                    caption = block.get("image_caption", [])
                    figures.append({"index": len(figures) + 1, "caption": caption[0] if caption else ""})
                elif block_type == "table":
                    table_body = block.get("table_body", "")
                    headers, rows = _html_table_to_structured(table_body) if table_body else ([], [])
                    tables.append({"index": len(tables) + 1, "headers": headers, "rows": rows})

            page_md = "\n\n".join(parts)
            full_parts.append(page_md)
            pages.append(_MinerUPageData(
                page_number=page_number,
                markdown=page_md,
                figures=figures,
                tables=tables,
            ))

        return _MinerURawResult(
            state="done",
            total_pages=len(pages),
            title=None,
            authors=[],
            abstract=None,
            pages=pages,
            full_markdown="\n\n".join(full_parts),
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
