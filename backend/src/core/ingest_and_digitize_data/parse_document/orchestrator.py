"""Document parse orchestrator with remote-first fallback."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from .base import ParserStrategy
from .contracts import MinerULocalBatchParseResult, ParseResult
from .exceptions import MinerUAPIError, ParserExhaustedError
from src.utils.ssrf import validate_url_safe

_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
_ALLOWED_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}
_PDF_MAGIC = b"%PDF"


class DocumentParseOrchestrator(ParserStrategy):
    """Orchestrator that tries remote parser first, then falls back to local.

    Implements ParserStrategy interface for seamless integration.
    """

    def __init__(self, remote: ParserStrategy, local: ParserStrategy):
        self._remote = remote
        self._local = local

    @property
    def name(self) -> str:
        return "orchestrator"

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse PDF with remote-first fallback strategy.

        Args:
            pdf_path: URL to the PDF file or local path.

        Returns:
            ParseResult from successful parser.

        Raises:
            ParserExhaustedError: If both remote and local parsers fail.
        """
        errors: dict[str, Exception] = {}

        # Try remote first
        try:
            logger.info(f"Attempting remote parsing: {pdf_path}")
            result = await self._remote.parse(pdf_path)
            logger.info(f"Remote parsing succeeded: {pdf_path}")
            return result
        except Exception as e:
            logger.warning(f"Remote parsing failed: {e}")
            errors[self._remote.name] = e

        # Fallback to local — download URL to temp file if needed
        local_path = pdf_path
        tmp_file = None
        if pdf_path.startswith(("http://", "https://")):
            tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            local_path = tmp_file.name
            try:
                validate_url_safe(pdf_path)
                logger.info(f"Downloading PDF for local fallback: {pdf_path}")
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    async with client.stream("GET", pdf_path, timeout=120.0) as resp:
                        resp.raise_for_status()

                        # Validate redirect target
                        final_url = str(resp.url)
                        if final_url != pdf_path:
                            validate_url_safe(final_url)

                        content_type = resp.headers.get("content-type", "")
                        if content_type and not any(ct in content_type for ct in _ALLOWED_CONTENT_TYPES):
                            raise MinerUAPIError(f"Unexpected content-type for PDF download: {content_type}")

                        downloaded = 0
                        async for chunk in resp.aiter_bytes():
                            downloaded += len(chunk)
                            if downloaded > _MAX_DOWNLOAD_BYTES:
                                raise MinerUAPIError(
                                    f"Download exceeds {_MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB limit"
                                )
                            tmp_file.write(chunk)

                tmp_file.close()

                # Validate PDF signature
                with open(local_path, "rb") as f:
                    magic = f.read(4)
                if magic != _PDF_MAGIC:
                    raise MinerUAPIError(f"Downloaded file is not a PDF (magic: {magic!r})")
            except Exception as download_err:
                tmp_file.close()
                Path(local_path).unlink(missing_ok=True)
                logger.warning(f"Failed to download PDF for local fallback: {download_err}")
                errors["url-download"] = download_err
                raise ParserExhaustedError(errors=errors) from download_err

        try:
            logger.info(f"Attempting local parsing: {local_path}")
            result = await self._local.parse(local_path)
            logger.info(f"Local parsing succeeded: {local_path}")
            return result
        except Exception as e:
            logger.warning(f"Local parsing failed: {e}")
            errors[self._local.name] = e
        finally:
            if tmp_file is not None:
                Path(local_path).unlink(missing_ok=True)

        # Both failed
        raise ParserExhaustedError(errors=errors)

    async def parse_local_files(
        self,
        file_paths: list[str],
        **kwargs: Any,
    ) -> MinerULocalBatchParseResult:
        """Delegate batch local-file parsing to the remote MinerU parser.

        The MinerU batch upload API is a remote-only feature.
        """
        parser = getattr(self._remote, "parse_local_files", None)
        if parser is None:
            raise AttributeError(f"Remote parser '{self._remote.name}' does not support parse_local_files")
        return await parser(file_paths, **kwargs)
