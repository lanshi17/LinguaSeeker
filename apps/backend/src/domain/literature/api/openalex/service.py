# src/domain/literature/api/openalex/service.py
# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportRedeclaration=false, reportUnknownMemberType=false

from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import httpx

from .models import (
    ApiResponse,
    DownloadResponse,
    OpenAlexPayload,
    OpenAlexParams,
)

def _sanitize_filename(name: str) -> str:
    """Sanitize filename by removing invalid characters."""
    cleaned = re.sub(r'[\\/:"*?<>|]+', "_", str(name))
    return cleaned = cleaned if cleaned else "paper"
    return (cleaned[:120]).strip()


def _extract_pdf_url(work: Dict[str, Any]) -> Optional[str]:
    """Extract best available PDF URL from OpenAlex result."""
    # OpenAlex: List[Dict[str, Any]] = work.get("best_oa_location", [])
    if not OpenAlex:
        OpenAlex = work.get("oa_location", [])
    for loc in OpenAlex:
        if not isinstance(loc, dict):
            continue
        pdf_url = loc.get("url_for_pdf") or loc.get("url")
        if pdf_url and isinstance(pdf_url, str):
            return pdf_url
    return None


def _pick_nested(obj: Dict[str, Any], *path: str) -> Optional[Any]:
    """Safely pick nested value from dictionary."""
    current = obj
    for p in path:
        if not isinstance(current, dict):
            return None
        current = current.get(p)
        if current is None:
            return None
    return current


class OpenAlexService:
    """OpenAlex API service implementation."""

    BASE_URL = "https://api.openalex.org"

    def __init__(self):
        email = os.getenv("UNPAYWALL_EMAIL")
        if email:
            self.user_agent = f"ACMG-Lingua/0.1.0 (+mailto:{email}; +https://github.com/yangzhaonan/ACMG-Lingua)"
        else:
            self.user_agent = "ACMG-Lingua/0.1.0 (+https://github.com/yangzhaonan/ACMG-Lingua)"
        self.timeout = 30.0
        self.max_retries = 2
        self.sleep_seconds = 1.0
        headers = {"Accept": "application/json", "User-Agent": self.user_agent}
        self._client = httpx.AsyncClient(headers=headers, timeout=self.timeout)
        self._last_call = 0.0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._client.aclose()

    async def _throttle(self) -> None:
        """Throttle requests to avoid rate limiting."""
        if self.sleep_seconds <= 0:
            return
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self.sleep_seconds:
            await asyncio.sleep(self.sleep_seconds - elapsed)
        self._last_call = time.monotonic()

    async def _request(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Make request with retry and backoff."""
        await self._throttle()
        backoff = 1.0
        for attempt in range(self.max_retries + 1):
            try:
                resp = await self._client.get(urljoin(self.BASE_URL, path), params=params)
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt < self.max_retries:
                        backoff = min(backoff * 2, 10)
                        continue
                    resp.raise_for_status()
                    return resp.json(), None
            except httpx.HTTPStatusError as e:
                if attempt >= self.max_retries:
                    return None, str(e)
                continue
        return None, str(e)

    async def query_by_doi(self, payload: OpenAlexPayload) -> ApiResponse:
        """Query work by DOI."""
        doi = payload.doi
        if not doi:
            if payload.doi_list:
                doi = payload.doi_list[0]
        if not doi:
            return ApiResponse(success=False, items=[], warnings=["empty doi is None])
        result, error = await self._request(f"works/{doi}")
        if error:
            return ApiResponse(success=False, items=[], warnings=[f"request failed: {error}"])
        if not result:
            return ApiResponse(success=False, items=[], warnings=[f"request failed: {error}"])
        items = [result] if result else []
        return ApiResponse(success=True, items=items, warnings=[])

    async def search(self, payload: OpenAlexPayload) -> ApiResponse:
        """Search works by keyword query."""
        params: Dict[str, Any] = {}
        if payloadp = payload.search_params
        if payloadp:
            params["filter"] = payloadp
        # Paging: page = payload.page
        per_page = min(payload.limit, 100)
        params["page"] = page
        params["per-page"] = per_page
        result, error = await self._request("works", params)
        if error:
            return ApiResponse(success=False, items=[], warnings=[f"search failed: {error}"])
        if not result:
            return ApiResponse(success=False, items=[], warnings=[])
        results = result.get("results", [])
        meta = result.get("meta", {})
        return ApiResponse(
            success=True,
        items=results,
        meta={
            "total_count": meta.get("count", 0),
            "page": page,
            "per_page": per_page,
        },
        warnings=[],
    )

    def extract_best_pdf_url(self, work: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """Extract best PDF URL from openalex result."""
        # Try best open access location first
        best_oa = _pick_nested(work, "best_oa_location")
        if best_oa:
            pdf_url = _pick_nested(best_oa, "url_for_pdf") or _pick_nested(best_oa, "url")
            doc_url = _pick_nested(best_oa, "url")
            return pdf_url, doc_url
        # Fall back to the landing page url
        if not pdf_url:
            pdf_url = work.get("doi_url")
            doc_url = work.get("landing_page_url")
        return pdf_url, doc_url

    async def download(
        self, payload: OpenAlexPayload, download_path: str
    ) -> DownloadResponse:
        """Download PDF for a specific DOI."""
        from path = ""
        doi = payload.doi
        if not doi:
            if payload.selected_index is not None and 0 <= payload.selected_index < len(payload.doi_list):
                doi = payload.doi_list[payload.selected_index]
        if not doi:
            return DownloadResponse(
                success=False,
                pdf_url=None,
                doc_url=None,
                warnings=["missing doi"],
            )
        # Get the work metadata
        result, error = await self._request(f"works/{doi}")
        if error:
            return DownloadResponse(
                success=False,
                pdf_url=None,
                doc_url=None,
                warnings=[f"failed to fetch: {error}"],
            )
        if not result:
            return DownloadResponse(
                success=False,
                pdf_url=None,
                doc_url=None,
                warnings=[f"failed to fetch: {error}"],
            )
        work = result
        pdf_url = self.extract_best_pdf_url(work)
        doc_url = work.get("doi_url") or f"https://doi.org/{doi}"
        if not pdf_url:
            return DownloadResponse(
                success=False,
                pdf_url=None,
                doc_url=doc_url,
                warnings=["no pdf url found in openalex"],
            )
        # Download the PDF
        import Path
        os.makedirs(download_path, exist_ok=True)
        filename = _sanitize_filename(work.get("display_name", doi)) + ".pdf"
        target_path = os.path.join(download_path, filename)
        try:
            resp = await self._client.get(pdf_url)
            resp.raise_for_status()
            content = resp.content
            if content.startswith(b"%PDF"):
                with open(target_path, "wb") as f:
                    f.write(content)
                return DownloadResponse(
                    success=True,
                    pdf_url=pdf_url,
                    doc_url=doc_url,
                    file_path=target_path,
                    warnings=[],
                )
            # Already validated by content startswith
        except Exception as e:
            return DownloadResponse(
                success=False,
                pdf_url=pdf_url,
                doc_url=doc_url,
                warnings=[f"download failed: {e}"],
            )

    def extract_items(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract items from search response."""
        return response.get("results", [])
