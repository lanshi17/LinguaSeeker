"""Local MinerU parser via the external MinerU FastAPI service ``/file_parse`` endpoint."""
from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import httpx
from loguru import logger

from ..base import ParserStrategy
from ..contracts import DocumentMetadata, PageContent, ParseResult
from ..exceptions import MinerUAPIError
from src.utils.markdown_helpers import extract_abstract_from_markdown


class MinerULocalParser(ParserStrategy):
    """PDF parser using the external MinerU FastAPI service ``/file_parse`` endpoint.

    Uploads the raw PDF as multipart form data.  The external MinerU FastAPI service runs MinerU
    natively and returns full markdown plus a per-block ``content_list``; blocks
    are grouped by ``page_idx`` to reconstruct per-page ``PageContent`` objects.
    """

    def __init__(
        self,
        parse_url: str = "http://localhost:8004",
        model_id: str = "opendatalab/MinerU2.5-Pro-2604-1.2B",
        timeout: float = 120.0,
        dpi: int = 200,
        api_key: str = "",
    ):
        self._base_url = parse_url.rstrip("/")
        # ``model_id`` and ``dpi`` are retained for backward-compatibility — the
        # doc-parse service selects its own model and renders the PDF internally,
        # so they are no longer consulted at runtime.
        self._model_id = model_id
        self._timeout = timeout
        self._dpi = dpi
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    @property
    def name(self) -> str:
        return "mineru-local"

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse a PDF by uploading it to the MinerU service ``/file_parse`` endpoint.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            ParseResult with per-page content grouped from the ``content_list``.
        """
        logger.info(f"MinerU local parsing: {pdf_path}")

        pdf_bytes = await asyncio.to_thread(Path(pdf_path).read_bytes)
        data = await self._call_file_parse(pdf_bytes, Path(pdf_path).name)
        return self._parse_file_parse_response(data)

    async def _call_file_parse(self, pdf_bytes: bytes, filename: str) -> dict:
        """POST the PDF to ``/file_parse`` as a multipart upload and return JSON.

        Args:
            pdf_bytes: Raw PDF file content.
            filename: Original filename for the multipart upload.

        Returns:
            Parsed JSON response from the endpoint.

        Raises:
            MinerUAPIError: On HTTP status or transport errors.
        """
        files = {"file": (filename, pdf_bytes, "application/pdf")}
        form_data = {
            "return_content_list": "true",
            "return_images": "true",
            "return_md": "true",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/file_parse",
                    files=files,
                    data=form_data,
                    headers=self._headers,
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            raise MinerUAPIError(
                f"MinerU service returned {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise MinerUAPIError(f"Request to MinerU service failed: {e}") from e

    @staticmethod
    def _parse_file_parse_response(data: dict) -> ParseResult:
        """Convert a ``FileParseResponse`` dict into a ``ParseResult``.

        Args:
            data: Parsed JSON from ``/file_parse``.

        Returns:
            A ``ParseResult`` with per-page content grouped from
            ``content_list`` and images decoded from data-URIs.

        Raises:
            MinerUAPIError: If the response contains no results.
        """
        results = data.get("results") or {}
        if not results:
            raise MinerUAPIError("MinerU service returned empty results.")

        # ``results`` is keyed by the uploaded filename; take the first entry.
        file_result = next(iter(results.values()))
        md_content: str = file_result.get("md_content", "") or ""
        content_list: list[dict] = file_result.get("content_list") or []
        raw_images: dict[str, str] = file_result.get("images") or {}

        pages = MinerULocalParser._build_pages(content_list, md_content)

        metadata = DocumentMetadata(
            total_pages=len(pages),
            title=None,
            authors=[],
            abstract_text=extract_abstract_from_markdown(md_content),
        )

        return ParseResult(
            metadata=metadata,
            pages=pages,
            full_markdown=md_content,
            parser_used="mineru-local",
            images=MinerULocalParser._decode_images(raw_images),
            content_blocks=content_list,
        )

    @staticmethod
    def _build_pages(content_list: list[dict], md_content: str) -> list[PageContent]:
        """Group ``content_list`` blocks by ``page_idx`` into per-page content.

        If ``content_list`` is empty or contains no text blocks, the entire
        ``md_content`` is treated as a single page.

        Args:
            content_list: Raw MinerU content blocks with ``page_idx`` and ``text``.
            md_content: Full markdown content from the response.

        Returns:
            List of ``PageContent`` objects, one per unique page index.
        """
        if not content_list:
            return [PageContent(page_number=1, markdown=md_content)]

        pages_by_idx: dict[int, list[str]] = {}
        for block in content_list:
            page_idx = block.get("page_idx", 0)
            text = block.get("text", "")
            if text:
                pages_by_idx.setdefault(page_idx, []).append(text)

        if not pages_by_idx:
            return [PageContent(page_number=1, markdown=md_content)]

        return [
            PageContent(
                page_number=page_idx + 1,
                markdown="\n\n".join(pages_by_idx[page_idx]),
            )
            for page_idx in sorted(pages_by_idx)
        ]

    @staticmethod
    def _decode_images(images: dict[str, str]) -> dict[str, bytes]:
        """Decode base64 data-URI images from the ``/file_parse`` response.

        Args:
            images: Mapping of image name to ``data:<mime>;base64,<...>`` URI.

        Returns:
            Mapping of image name to raw bytes.
        """
        decoded: dict[str, bytes] = {}
        for name, data_uri in images.items():
            b64 = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
            try:
                decoded[name] = base64.b64decode(b64)
            except Exception:
                logger.warning(f"Failed to decode image '{name}' from file_parse response.")
        return decoded
