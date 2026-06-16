"""Local MinerU parser — HTTP client for the MinerU API server."""
from __future__ import annotations

import base64
import re
from pathlib import Path

import httpx
from loguru import logger

from ..base import ParserStrategy
from ..contracts import (
    DocumentMetadata,
    PageContent,
    ParseResult,
)
from ..exceptions import MinerUAPIError


def _extract_abstract_from_markdown(text: str) -> str | None:
    """Extract abstract text from markdown content."""
    if not text:
        return None
    pattern = (
        r"(?:^|\n)\s*(?:#{1,3}\s*)?(?:\*\*)?"
        r"(?:Abstract|ABSTRACT|摘要|【摘要】)"
        r"(?:\*\*)?\s*(?::\s*)?\n"
        r"(.*?)(?=\n\s*(?:#{1,3}\s*)?(?:\*\*)?"
        r"(?:Introduction|INTRODUCTION|引言|关键词|Keywords|KEYWORDS|Background|BACKGROUND|1\s*[\.\)])|\Z)"
    )
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if m:
        abstract = m.group(1).strip()
        abstract = re.sub(r"\n\s*[\*\-]\s*$", "", abstract).strip()
        if len(abstract) > 30:
            return abstract
    return None


class MinerULocalParser(ParserStrategy):
    """PDF parser using a locally deployed MinerU API server.

    The MinerU API server (``mineru-api-server`` from the ``mineru`` package)
    handles the full parsing pipeline: PDF rendering, layout detection, VLM
    inference, table structure recognition, and formula OCR.

    This parser uploads a PDF to ``POST /file_parse`` and maps the JSON
    response back to our ``ParseResult`` contract.
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8001",
        timeout: float = 600.0,
        backend: str = "vlm",
    ):
        self._api_url = api_url.rstrip("/")
        self._timeout = timeout
        self._backend = backend

    @property
    def name(self) -> str:
        return "mineru-local"

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse a PDF via the MinerU API server.

        Args:
            pdf_path: Local path to the PDF file.

        Returns:
            ParseResult with metadata, pages, and full markdown.

        Raises:
            MinerUAPIError: On API errors or connection failures.
        """
        logger.info(f"MinerU local parsing via API server: {pdf_path}")

        file_path = Path(pdf_path)
        if not file_path.exists():
            raise MinerUAPIError(f"PDF file does not exist: {pdf_path}")

        file_data = file_path.read_bytes()

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._api_url}/file_parse",
                    data={
                        "backend": self._backend,
                        "return_content_list": "true",
                        "return_images": "true",
                        "return_md": "true",
                    },
                    files={"file": (file_path.name, file_data, "application/pdf")},
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise MinerUAPIError(
                f"MinerU API server returned {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise MinerUAPIError(f"Failed to connect to MinerU API server: {e}") from e

        data = resp.json()
        results = data.get("results", {})
        if not results:
            raise MinerUAPIError(f"No results returned by MinerU API for: {pdf_path}")

        file_name = file_path.name
        file_result = results.get(file_name)
        if file_result is None:
            file_result = next(iter(results.values()))

        return self._build_result_from_response(file_name, file_result)

    @staticmethod
    def _build_result_from_response(file_name: str, file_result: dict) -> ParseResult:
        """Map MinerU API file result to ParseResult."""
        full_markdown = file_result.get("md_content", "")
        content_list = file_result.get("content_list", [])
        raw_images = file_result.get("images", {})

        images: dict[str, bytes] = {}
        for img_name, img_data_uri in raw_images.items():
            if isinstance(img_data_uri, str) and img_data_uri.startswith("data:"):
                match = re.match(r"data:[^;]+;base64,(.+)", img_data_uri)
                if match:
                    images[img_name] = base64.b64decode(match.group(1))

        max_page_idx = 0
        for block in content_list:
            page_idx = block.get("page_idx", 0)
            max_page_idx = max(max_page_idx, page_idx)

        total_pages = max_page_idx + 1 if content_list else 1

        pages: list[PageContent] = []
        for i in range(total_pages):
            pages.append(PageContent(page_number=i + 1, markdown=""))

        if not pages:
            pages = [PageContent(page_number=1, markdown=full_markdown)]

        abstract = _extract_abstract_from_markdown(full_markdown)

        metadata = DocumentMetadata(
            total_pages=total_pages,
            title=None,
            authors=[],
            abstract_text=abstract,
        )

        return ParseResult(
            metadata=metadata,
            pages=pages,
            full_markdown=full_markdown,
            parser_used="mineru-local",
            images=images,
            content_blocks=content_list,
        )
