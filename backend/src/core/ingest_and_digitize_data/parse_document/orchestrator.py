"""Document parse orchestrator with remote-first fallback."""
from __future__ import annotations

import ipaddress
import socket
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger

from .base import ParserStrategy
from .contracts import MinerULocalBatchParseResult, ParseResult
from .exceptions import MinerUAPIError, ParserExhaustedError

_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
_ALLOWED_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}
_PDF_MAGIC = b"%PDF"


def _is_private_ip(hostname: str) -> bool:
    """Return True if *hostname* resolves to a private/reserved IP address."""
    try:
        addrinfos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return True  # treat unresolvable hosts as unsafe

    for _family, _type, _proto, _canonname, sockaddr in addrinfos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            return True
    return False


def _validate_url_safe(url: str) -> None:
    """Raise MinerUAPIError if *url* targets a private/reserved IP."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise MinerUAPIError(f"Unsupported URL scheme: {parsed.scheme}")
    hostname = parsed.hostname or ""
    if not hostname or _is_private_ip(hostname):
        raise MinerUAPIError(f"URL targets a private/reserved address: {url}")


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
                _validate_url_safe(pdf_path)
                logger.info(f"Downloading PDF for local fallback: {pdf_path}")
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    async with client.stream("GET", pdf_path, timeout=120.0) as resp:
                        resp.raise_for_status()

                        # Validate redirect target
                        final_url = str(resp.url)
                        if final_url != pdf_path:
                            _validate_url_safe(final_url)

                        content_type = resp.headers.get("content-type", "")
                        if content_type and not any(
                            ct in content_type for ct in _ALLOWED_CONTENT_TYPES
                        ):
                            raise MinerUAPIError(
                                f"Unexpected content-type for PDF download: {content_type}"
                            )

                        downloaded = 0
                        async for chunk in resp.ait_bytes():
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
                    raise MinerUAPIError(
                        f"Downloaded file is not a PDF (magic: {magic!r})"
                    )
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
            raise AttributeError(
                f"Remote parser '{self._remote.name}' does not support parse_local_files"
            )
        return await parser(file_paths, **kwargs)
