"""MinerU API parser implementation via rust_io.net."""
from __future__ import annotations

import asyncio
from typing import TypedDict

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

        result_data = await self._poll_result(task_id)

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

        task_id = response.get("task_id")
        if not task_id:
            raise MinerUAPIError(f"No task_id in response: {response}")

        return task_id

    async def _poll_result(self, task_id: str) -> _MinerURawResult:
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
                self._validate_response(response)
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

    @staticmethod
    def _validate_response(data: dict) -> None:
        """Validate critical fields in MinerU response.

        Raises MinerUAPIError if the response is malformed.
        """
        if "total_pages" not in data:
            raise MinerUAPIError("Malformed response: missing 'total_pages'")
        if not data.get("pages"):
            raise MinerUAPIError("Malformed response: empty 'pages'")

    def _build_result(self, data: _MinerURawResult) -> ParseResult:
        """Convert MinerU response to ParseResult."""
        metadata = DocumentMetadata(
            total_pages=data["total_pages"],
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
