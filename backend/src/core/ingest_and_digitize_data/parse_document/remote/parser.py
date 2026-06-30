"""Remote MinerU parser via cloud API."""
from __future__ import annotations

import asyncio
import json
import tempfile
import zipfile
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import TypedDict, cast

import httpx
from loguru import logger

from src.utils.rust_io import net_io
from src.utils.markdown_helpers import extract_abstract_from_markdown

from ..base import ParserStrategy
from ..common.converters import block_to_markdown, html_table_to_structured
from ..contracts import (
    DocumentMetadata,
    MinerUBatchStatus,
    MinerUExtraFormat,
    MinerULocalBatchOptions,
    MinerULocalBatchParseResult,
    MinerULocalBatchUploadResult,
    MinerUModelVersion,
    ParseResult,
    pages_from_raw,
)
from ..exceptions import MinerUAPIError, MinerUTimeoutError


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
    images: dict[str, bytes]
    raw_blocks: list[dict]


class MinerURemoteParser(ParserStrategy):
    """PDF parser using MinerU cloud API via Rust net-io layer.

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

    def _validate_local_batch_inputs(self, file_paths: list[str], data_ids: list[str] | None) -> None:
        """Validate MinerU local-file batch constraints before API calls."""
        if not file_paths:
            raise MinerUAPIError("MinerU local batch requires at least one file")
        if len(file_paths) > 50:
            raise MinerUAPIError("MinerU local batch cannot exceed 50 files")
        if data_ids is not None and len(data_ids) != len(file_paths):
            raise MinerUAPIError("data_ids length must match file_paths length")

        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                raise MinerUAPIError(f"Local file does not exist: {file_path}")
            if not path.is_file():
                raise MinerUAPIError(f"Local path is not a file: {file_path}")

    def _require_success_response(self, response: Mapping[str, object], operation: str) -> Mapping[str, object]:
        """Return response data or raise a MinerUAPIError."""
        code = response.get("code")
        if code not in (0, "0"):
            message = response.get("msg", "unknown MinerU error")
            raise MinerUAPIError(f"{operation} failed: {message}")

        data = response.get("data", {})
        if not isinstance(data, Mapping):
            raise MinerUAPIError(f"{operation} returned invalid data: {response}")
        return cast(Mapping[str, object], data)

    async def upload_local_files(
        self,
        file_paths: list[str],
        *,
        model_version: MinerUModelVersion = "vlm",
        enable_formula: bool | None = True,
        enable_table: bool | None = True,
        language: str | None = "ch",
        data_ids: list[str] | None = None,
        is_ocr: bool | None = None,
        page_ranges: str | None = None,
        callback: str | None = None,
        seed: str | None = None,
        extra_formats: list[MinerUExtraFormat] | None = None,
        timeout_ms: int | None = None,
        proxy: str | None = None,
    ) -> MinerULocalBatchUploadResult:
        """Upload local files through MinerU batch upload URLs."""
        options = MinerULocalBatchOptions(
            model_version=model_version,
            enable_formula=enable_formula,
            enable_table=enable_table,
            language=language,
            data_ids=data_ids,
            is_ocr=is_ocr,
            page_ranges=page_ranges,
            callback=callback,
            seed=seed,
            extra_formats=extra_formats,
            timeout_ms=timeout_ms,
            proxy=proxy,
        )
        self._validate_local_batch_inputs(file_paths, options.data_ids)

        if net_io is None:
            raise RuntimeError("net_io extension is required for MinerU batch parsing but is not installed")

        try:
            response = await net_io.mineru_upload_local_files(
                file_paths=file_paths,
                token=self._api_token,
                model_version=options.model_version,
                enable_formula=options.enable_formula,
                enable_table=options.enable_table,
                language=options.language,
                data_ids=options.data_ids,
                is_ocr=options.is_ocr,
                page_ranges=options.page_ranges,
                callback=options.callback,
                seed=options.seed,
                extra_formats=options.extra_formats,
                timeout_ms=options.timeout_ms,
                proxy=options.proxy,
            )
        except Exception as e:
            raise MinerUAPIError(f"Failed to upload local files: {e}") from e

        data = self._require_success_response(response, "MinerU local batch upload")
        batch_id = data.get("batch_id")
        file_urls = data.get("file_urls")
        if not isinstance(batch_id, str) or not isinstance(file_urls, list):
            raise MinerUAPIError(f"Invalid upload response: {response}")

        return MinerULocalBatchUploadResult(
            batch_id=batch_id,
            file_paths=file_paths,
            file_urls=file_urls,
            trace_id=response.get("trace_id"),
            message=response.get("msg", "ok"),
        )

    async def poll_batch_result(
        self,
        batch_id: str,
        *,
        timeout_ms: int | None = None,
        proxy: str | None = None,
    ) -> MinerUBatchStatus:
        """Fetch the current MinerU batch status once."""
        if net_io is None:
            raise RuntimeError("net_io extension is required but is not installed")

        try:
            response = await net_io.mineru_batch_result(
                batch_id=batch_id,
                token=self._api_token,
                timeout_ms=timeout_ms,
                proxy=proxy,
            )
        except Exception as e:
            raise MinerUAPIError(f"Failed to get batch result: {e}") from e

        data = self._require_success_response(response, "MinerU batch result")
        return MinerUBatchStatus.model_validate(data)

    async def poll_batch_until_terminal(
        self,
        batch_id: str,
        *,
        timeout_ms: int | None = None,
        proxy: str | None = None,
    ) -> MinerUBatchStatus:
        """Poll MinerU batch status until every file is done or failed."""
        for _attempt in range(self._max_poll_attempts):
            status = await self.poll_batch_result(batch_id, timeout_ms=timeout_ms, proxy=proxy)
            if status.is_terminal:
                return status
            await asyncio.sleep(self._poll_interval)

        raise MinerUTimeoutError(total_timeout=self._poll_interval * self._max_poll_attempts)

    async def parse_local_files(
        self,
        file_paths: list[str],
        *,
        model_version: MinerUModelVersion = "vlm",
        enable_formula: bool | None = True,
        enable_table: bool | None = True,
        language: str | None = "ch",
        data_ids: list[str] | None = None,
        is_ocr: bool | None = None,
        page_ranges: str | None = None,
        callback: str | None = None,
        seed: str | None = None,
        extra_formats: list[MinerUExtraFormat] | None = None,
        timeout_ms: int | None = None,
        proxy: str | None = None,
    ) -> MinerULocalBatchParseResult:
        """Upload local files, wait for MinerU completion, and parse completed zips."""
        upload = await self.upload_local_files(
            file_paths,
            model_version=model_version,
            enable_formula=enable_formula,
            enable_table=enable_table,
            language=language,
            data_ids=data_ids,
            is_ocr=is_ocr,
            page_ranges=page_ranges,
            callback=callback,
            seed=seed,
            extra_formats=extra_formats,
            timeout_ms=timeout_ms,
            proxy=proxy,
        )
        status = await self.poll_batch_until_terminal(upload.batch_id, timeout_ms=timeout_ms, proxy=proxy)

        parsed: dict[str, ParseResult] = {}
        for item in status.extract_result:
            if item.state != "done":
                logger.warning(f"MinerU batch file failed or incomplete: {item.file_name}: {item.err_msg}")
                continue
            if not item.full_zip_url:
                raise MinerUAPIError(f"Done batch item has no full_zip_url: {item.file_name}")
            raw = await self._download_and_parse_zip(item.full_zip_url)
            parsed[item.file_name] = self._build_result(raw)

        return MinerULocalBatchParseResult(batch_id=upload.batch_id, status=status, results=parsed)

    async def _create_task(self, pdf_path: str) -> str:
        """Create MinerU parsing task and return task_id."""
        if net_io is None:
            raise RuntimeError("net_io extension is required but is not installed")

        try:
            response = await net_io.mineru_create_task(
                url=pdf_path,
                token=self._api_token,
                enable_formula=True,
                enable_table=True,
            )
        except Exception as e:
            raise MinerUAPIError(f"Failed to create task: {e}") from e

        data = self._require_success_response(response, "MinerU create task")
        task_id = data.get("task_id")
        if not task_id:
            raise MinerUAPIError(f"No task_id in response: {response}")

        return task_id

    async def _poll_result(self, task_id: str) -> str:
        """Poll for task result until completion or timeout.

        Returns:
            URL to the zip file containing parsed results.
        """
        if net_io is None:
            raise RuntimeError("net_io extension is required but is not installed")

        for _attempt in range(self._max_poll_attempts):
            try:
                response = await net_io.mineru_get_result(
                    task_id=task_id,
                    token=self._api_token,
                )
            except Exception as e:
                raise MinerUAPIError(f"Failed to get result: {e}") from e

            data = self._require_success_response(response, "MinerU get result")
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

    def _collect_images(self, extract_dir: Path) -> dict[str, bytes]:
        """Collect image files from extracted zip directory.

        Searches for ``images/`` directories at any nesting level to handle
        layouts where the zip root contains a subdirectory (e.g.
        ``some-root/images/fig.jpg``).
        """
        images: dict[str, bytes] = {}
        for images_dir in extract_dir.rglob("images"):
            if not images_dir.is_dir():
                continue
            for img_file in images_dir.iterdir():
                if img_file.is_file():
                    rel_path = f"images/{img_file.name}"
                    images[rel_path] = img_file.read_bytes()
        return images

    def _parse_extracted_content(self, extract_dir: Path) -> _MinerURawResult:
        """Parse extracted zip content into structured result."""
        json_files = list(extract_dir.rglob("*.json"))
        md_files = list(extract_dir.rglob("*.md"))
        images = self._collect_images(extract_dir)

        # Priority 1: *_content_list.json (new MinerU format with structured blocks)
        content_list_files = [f for f in extract_dir.rglob("*_content_list.json")]
        full_md_path = extract_dir / "full.md"
        full_markdown = full_md_path.read_text(encoding="utf-8") if full_md_path.exists() else ""

        if content_list_files:
            try:
                data = json.loads(content_list_files[0].read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    result = self._parse_content_list_json(data, full_markdown)
                    result["images"] = images
                    return result
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        # Priority 2: layout.json with pdf_info
        for jf in json_files:
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "pdf_info" in data:
                    result = self._parse_content_json(data, md_files)
                    result["images"] = images
                    return result
                elif isinstance(data, list) and len(data) > 0:
                    content_data = {"pages": data}
                    result = self._parse_content_json(content_data, md_files)
                    result["images"] = images
                    return result
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

        # Priority 3: markdown files
        if md_files:
            result = self._parse_markdown_files(md_files)
            result["images"] = images
            return result

        # Priority 4: full.md only
        if full_markdown:
            abstract = extract_abstract_from_markdown(full_markdown)
            return _MinerURawResult(
                state="done",
                total_pages=1,
                title=None,
                authors=[],
                abstract=abstract,
                pages=[_MinerUPageData(page_number=1, markdown=full_markdown, figures=[], tables=[])],
                full_markdown=full_markdown,
                images=images,
                raw_blocks=[],
            )

        raise MinerUAPIError(f"No parseable content found in zip. Files: {list(extract_dir.rglob('*'))}")

    def _parse_content_json(self, data: dict, md_files: list[Path]) -> _MinerURawResult:
        """Parse MinerU content_list.json format."""
        pdf_info = data.get("pdf_info", [])
        if not pdf_info:
            # Try alternative format
            pages_data = data.get("pages", [])
            if pages_data:
                abstract = data.get("abstract")
                if not abstract:
                    combined_md = "\n\n".join(p.get("markdown", "") for p in pages_data)
                    abstract = extract_abstract_from_markdown(combined_md)
                return _MinerURawResult(
                    state="done",
                    total_pages=len(pages_data),
                    title=data.get("title"),
                    authors=data.get("authors", []),
                    abstract=abstract,
                    pages=pages_data,
                    full_markdown="\n\n".join(p.get("markdown", "") for p in pages_data),
                    raw_blocks=[],
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

        abstract = data.get("abstract")
        if not abstract:
            combined_md = "\n\n".join(full_markdown_parts)
            abstract = extract_abstract_from_markdown(combined_md)

        return _MinerURawResult(
            state="done",
            total_pages=len(pages),
            title=data.get("title"),
            authors=data.get("authors", []),
            abstract=abstract,
            pages=pages,
            full_markdown="\n\n".join(full_markdown_parts),
            raw_blocks=[],
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

        combined_markdown = "\n\n".join(full_markdown_parts)
        abstract = extract_abstract_from_markdown(combined_markdown)

        return _MinerURawResult(
            state="done",
            total_pages=len(pages),
            title=None,
            authors=[],
            abstract=abstract,
            pages=pages,
            full_markdown=combined_markdown,
            raw_blocks=[],
        )

    def _parse_content_list_json(self, content_list: list[dict], full_markdown: str) -> _MinerURawResult:
        """Parse MinerU *_content_list.json with text, image, table blocks."""
        raw_blocks = [b for b in content_list if b.get("type") != "discarded"]

        pages_map: dict[int, list[dict]] = defaultdict(list)
        for item in raw_blocks:
            page_idx = item.get("page_idx", 0)
            pages_map[page_idx].append(item)

        if not pages_map:
            abstract = extract_abstract_from_markdown(full_markdown)
            return _MinerURawResult(
                state="done",
                total_pages=1,
                title=None,
                authors=[],
                abstract=abstract,
                pages=[_MinerUPageData(page_number=1, markdown=full_markdown, figures=[], tables=[])],
                full_markdown=full_markdown,
                raw_blocks=raw_blocks,
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
                md = block_to_markdown(block)
                if md:
                    parts.append(md)
                if block_type == "image":
                    caption = block.get("image_caption", [])
                    img_path = block.get("img_path")
                    figures.append({
                        "index": len(figures) + 1,
                        "caption": str(caption[0]) if caption else "",
                        "img_path": img_path,
                    })
                elif block_type == "table":
                    table_body = block.get("table_body", "")
                    headers, rows = html_table_to_structured(table_body) if table_body else ([], [])
                    tables.append({"index": len(tables) + 1, "headers": headers, "rows": rows})

            page_md = "\n\n".join(parts)
            full_parts.append(page_md)
            pages.append(_MinerUPageData(
                page_number=page_number,
                markdown=page_md,
                figures=figures,
                tables=tables,
            ))

        combined_markdown = "\n\n".join(full_parts)
        abstract = extract_abstract_from_markdown(combined_markdown)
        if not abstract and full_markdown:
            abstract = extract_abstract_from_markdown(full_markdown)

        return _MinerURawResult(
            state="done",
            total_pages=len(pages),
            title=None,
            authors=[],
            abstract=abstract,
            pages=pages,
            full_markdown=combined_markdown,
            raw_blocks=raw_blocks,
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
            images=data.get("images", {}),
            content_blocks=data.get("raw_blocks", []),
        )
