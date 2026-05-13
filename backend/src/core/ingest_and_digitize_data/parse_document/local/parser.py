"""Local MinerU parser via model-server VLM endpoint."""
from __future__ import annotations

import asyncio

import httpx
from loguru import logger
from PIL import Image

from ..base import ParserStrategy
from ..contracts import (
    DocumentMetadata,
    PageContent,
    ParseResult,
    pages_from_raw,
)
from ..exceptions import MinerUAPIError
from .helpers import image_to_base64, pdf_to_images


class MinerULocalParser(ParserStrategy):
    """PDF parser using local model-server VLM endpoint.

    Converts each PDF page to an image, sends to model-server's
    /v1/chat/completions endpoint, and aggregates page results.
    """

    def __init__(
        self,
        model_server_url: str = "http://localhost:8001",
        model_id: str = "opendatalab/MinerU2.5-Pro-2604-1.2B",
        timeout: float = 120.0,
        dpi: int = 200,
    ):
        self._base_url = model_server_url.rstrip("/")
        self._model_id = model_id
        self._timeout = timeout
        self._dpi = dpi

    @property
    def name(self) -> str:
        return "mineru-local"

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse PDF by converting pages to images and calling model-server."""
        logger.info(f"MinerU local parsing: {pdf_path}")

        images = await asyncio.to_thread(pdf_to_images, pdf_path, self._dpi)
        logger.info(f"Converted {len(images)} pages to images")

        pages: list[PageContent] = []
        full_markdown_parts: list[str] = []

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for i, image in enumerate(images, start=1):
                logger.info(f"Processing page {i}/{len(images)}")
                page = await self._extract_page(client, i, image)
                pages.append(page)
                full_markdown_parts.append(page.markdown)

        metadata = DocumentMetadata(
            total_pages=len(pages),
            title=None,
            authors=[],
            abstract_text=None,
        )

        return ParseResult(
            metadata=metadata,
            pages=pages,
            full_markdown="\n\n".join(full_markdown_parts),
            parser_used=self.name,
        )

    async def _extract_page(
        self,
        client: httpx.AsyncClient,
        page_number: int,
        image: Image.Image,
    ) -> PageContent:
        """Extract content from a single page image via model-server."""
        b64 = image_to_base64(image)

        payload = {
            "model": self._model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract this document page as markdown."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
        }

        try:
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions",
                json=payload,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise MinerUAPIError(
                f"Model-server returned {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise MinerUAPIError(f"Request to model-server failed: {e}") from e

        data = resp.json()
        return self._parse_page_response(page_number, data)

    @staticmethod
    def _parse_page_response(page_number: int, data: dict) -> PageContent:
        """Convert model-server VLM response to PageContent.

        Supports two response formats:
        - VLMExtractResponse: {"full_markdown": "...", "pages": [...]}
        - OpenAI chat completions: {"choices": [{"message": {"content": "..."}}]}
        """
        # Try VLMExtractResponse format first
        full_markdown = data.get("full_markdown", "")
        pages_data = data.get("pages", [])

        if pages_data:
            page = pages_data[0]
            markdown = page.get("markdown", full_markdown)
            figures_raw = page.get("figures", [])
            tables_raw = page.get("tables", [])
        elif full_markdown:
            markdown = full_markdown
            figures_raw = []
            tables_raw = []
        else:
            # Fallback: try OpenAI chat completions format
            choices = data.get("choices", [])
            if choices and isinstance(choices, list):
                message = choices[0].get("message", {})
                markdown = message.get("content", "")
            else:
                markdown = ""
            figures_raw = []
            tables_raw = []

        if not markdown:
            logger.warning(
                f"Model-server returned empty markdown for page {page_number}. "
                f"Response keys: {list(data.keys())}"
            )

        raw_page = {
            "page_number": page_number,
            "markdown": markdown,
            "figures": figures_raw,
            "tables": tables_raw,
        }
        return pages_from_raw([raw_page])[0]
