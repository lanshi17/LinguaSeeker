"""MinerU API parser implementation via rust_io.net."""
from __future__ import annotations

import asyncio

from loguru import logger

import rust_io.net as net_io

from .base import ParserStrategy
from .contracts import (
    DocumentMetadata,
    FigurePosition,
    PageContent,
    ParseResult,
    TableStructure,
)
from .exceptions import MinerUAPIError, MinerUTimeoutError


class MinerUParser(ParserStrategy):
    """PDF parser using MinerU API via Rust net-io layer.

    MinerU uses an async task-based API:
    1. Create task with PDF URL -> get task_id
    2. Poll for task completion -> get parsed result
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

    async def parse(self, pdf_url: str) -> ParseResult:
        """Parse PDF via MinerU API.

        Args:
            pdf_url: URL to the PDF file (S3/MinIO or public URL).

        Returns:
            ParseResult with metadata, pages, and full markdown.

        Raises:
            MinerUAPIError: On API errors or task failure.
            MinerUTimeoutError: On polling timeout.
        """
        logger.info(f"MinerU parsing: {pdf_url}")

        task_id = await self._create_task(pdf_url)
        logger.info(f"MinerU task created: {task_id}")

        result_data = await self._poll_result(task_id)

        return self._build_result(result_data)

    async def _create_task(self, pdf_url: str) -> str:
        """Create MinerU parsing task and return task_id."""
        try:
            response = await net_io.mineru_create_task(
                url=pdf_url,
                token=self._api_token,
                enable_formula=True,
                enable_table=True,
            )
        except Exception as e:
            raise MinerUAPIError(f"Failed to create task: {e}") from e

        task_id = response.get("task_id")
        if not task_id:
            raise MinerUAPIError(f"No task_id in response: {response}")

        return task_id

    async def _poll_result(self, task_id: str) -> dict:
        """Poll for task result until completion or timeout."""
        for attempt in range(self._max_poll_attempts):
            try:
                response = await net_io.mineru_get_result(
                    task_id=task_id,
                    token=self._api_token,
                )
            except Exception as e:
                raise MinerUAPIError(f"Failed to get result: {e}") from e

            state = response.get("state", "")

            if state == "done":
                return response
            elif state == "failed":
                error_msg = response.get("error", "Unknown error")
                raise MinerUAPIError(f"Task failed: {error_msg}")
            elif state in ("pending", "running", "converting"):
                logger.debug(f"Task {task_id} state: {state}, waiting...")
                await asyncio.sleep(self._poll_interval)
            else:
                raise MinerUAPIError(f"Unknown task state: {state}")

        raise MinerUTimeoutError(timeout=self._poll_interval * self._max_poll_attempts)

    def _build_result(self, data: dict) -> ParseResult:
        """Convert MinerU response to ParseResult."""
        metadata = DocumentMetadata(
            total_pages=data.get("total_pages", 1),
            title=data.get("title"),
            authors=data.get("authors", []),
            abstract_text=data.get("abstract"),
        )

        pages = []
        for page_data in data.get("pages", []):
            figures = [
                FigurePosition(
                    page=page_data["page_number"],
                    index=f.get("index", 1),
                    caption=f.get("caption"),
                )
                for f in page_data.get("figures", [])
            ]
            tables = [
                TableStructure(
                    page=page_data["page_number"],
                    index=t.get("index", 1),
                    headers=t.get("headers", []),
                    rows=t.get("rows", []),
                )
                for t in page_data.get("tables", [])
            ]
            pages.append(
                PageContent(
                    page_number=page_data["page_number"],
                    markdown=page_data.get("markdown", ""),
                    figures=figures,
                    tables=tables,
                )
            )

        return ParseResult(
            metadata=metadata,
            pages=pages,
            full_markdown=data.get("full_markdown", ""),
            parser_used=self.name,
        )
