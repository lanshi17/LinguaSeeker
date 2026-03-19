# src/domain/literature/api/unpaywall/service.py
from __future__ import annotations

import json
import math
import os
import re
import time
from typing import Any, Dict, Iterable, List, Literal, Optional

from .models import (
    ApiResponse,
    DownloadResponse,
    SearchParams,
    UnpaywallPayload,
)


def _sanitize_filename(name: str) -> str:
    """Sanitize filename by removing invalid characters."""
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name or "paper")[:120]


def _normalize_dois(dois: Iterable[str]) -> List[str]:
    """Normalize and deduplicate DOI list."""
    seen = set()
    result = []
    for d in dois or []:
        if not d:
            continue
        dd = d.strip().lower()
        if dd and dd not in seen:
            seen.add(dd)
            result.append(dd)
    return result


def _build_query(sp: SearchParams) -> str:
    """Build query string from SearchParams."""
    if sp.query and sp.query.strip():
        return sp.query.strip()
    if sp.keyword:
        return " ".join([k.strip() for k in sp.keyword if k and k.strip()])
    return ""


def _ensure_credentials(email: Optional[str]):
    """Ensure Unpaywall credentials are available."""
    from unpywall.utils import UnpaywallCredentials

    if email:
        UnpaywallCredentials(email)
        return

    if not os.getenv("UNPAYWALL_EMAIL"):
        raise ValueError("UNPAYWALL_EMAIL is required (or pass payload.email)")


def _to_records(result: Any, raw: bool) -> List[Dict[str, Any]]:
    """Convert result to list of dict records."""
    if raw:
        return result if isinstance(result, list) else []
    if hasattr(result, "to_dict"):
        return result.to_dict(orient="records")
    return []


class UnpaywallService:
    """Service for interacting with Unpaywall API via unpywall library."""

    PAGE_SIZE = 50

    def __init__(self, email: Optional[str] = None):
        """
        Initialize UnpaywallService.

        Args:
            email: Email for Unpaywall API authentication.
        """
        _ensure_credentials(email)
        from unpywall import Unpywall

        self.Unpaywall = Unpywall

    def doi_query(self, payload: UnpaywallPayload) -> ApiResponse:
        """Query Unpaywall by DOI list."""
        warnings = []
        dois = _normalize_dois(payload.doi_list)
        if payload.doi:
            dois = _normalize_dois([payload.doi])

        if not dois:
            return ApiResponse(success=False, warnings=["doi_list/doi is empty"])

        all_items: List[Dict[str, Any]] = []
        for i in range(0, len(dois), payload.batch_size):
            batch = dois[i : i + payload.batch_size]
            res = self.Unpaywall.doi(
                dois=batch,
                progress=payload.progress,
                errors=payload.errors,
                raw=payload.raw,
            )
            all_items.extend(_to_records(res, payload.raw))
            time.sleep(payload.sleep_seconds)

        return ApiResponse(
            success=True,
            items=all_items,
            warnings=warnings,
            raw=all_items if payload.raw else None,
        )

    def query(self, payload: UnpaywallPayload) -> ApiResponse:
        """Search Unpaywall with query parameters."""
        warnings = []
        sp = payload.search_params
        if not sp:
            return ApiResponse(success=False, warnings=["missing search_params"])

        query_str = _build_query(sp)
        if not query_str:
            return ApiResponse(success=False, warnings=["empty query"])

        is_oa = None
        if sp.filters and "is_oa" in sp.filters:
            is_oa = sp.filters.get("is_oa")

        unsupported = [k for k in (sp.filters or {}).keys() if k != "is_oa"]
        if unsupported:
            warnings.append(f"unsupported_filters: {unsupported}")

        total_needed = sp.limit
        start_page = sp.page
        pages_needed = math.ceil(total_needed / self.PAGE_SIZE)
        pages_needed = min(pages_needed, 10)

        all_items: List[Dict[str, Any]] = []

        for i in range(pages_needed):
            page = start_page + i
            res = self.Unpaywall.query(
                query=query_str,
                is_oa=is_oa,
                page=page,
                progress=payload.progress,
                errors=payload.errors,
                raw=payload.raw,
            )
            batch_items = _to_records(res, payload.raw)
            all_items.extend(batch_items)
            if len(batch_items) < self.PAGE_SIZE:
                break
            time.sleep(payload.sleep_seconds)

        all_items = all_items[:total_needed]
        return ApiResponse(
            success=True,
            items=all_items,
            warnings=warnings,
            raw=all_items if payload.raw else None,
        )

    def download(self, payload: UnpaywallPayload) -> DownloadResponse:
        """Download PDF for a DOI."""
        warnings = []
        doi = payload.doi

        if not doi and payload.doi_list:
            dois = _normalize_dois(payload.doi_list)
            if 0 <= payload.selected_index < len(dois):
                doi = dois[payload.selected_index]

        if not doi and payload.search_params:
            qres = self.query(payload)
            if not qres.items:
                return DownloadResponse(success=False, warnings=["no_search_results"])
            idx = payload.selected_index
            if 0 <= idx < len(qres.items):
                doi = qres.items[idx].get("doi")

        if not doi:
            return DownloadResponse(success=False, warnings=["missing doi"])

        pdf_url = self.Unpaywall.get_pdf_link(doi)
        doc_url = None
        if not pdf_url:
            doc_url = self.Unpaywall.get_doc_link(doi)
            return DownloadResponse(
                success=False, pdf_url=None, doc_url=doc_url, warnings=["pdf_not_found"]
            )

        os.makedirs(payload.download_path, exist_ok=True)
        filename = _sanitize_filename(doi.replace("/", "_")) + ".pdf"
        file_path = os.path.join(payload.download_path, filename)

        try:
            handle = self.Unpaywall.download_pdf_handle(doi)
            with open(file_path, "wb") as f:
                f.write(handle.read())
        except Exception as e:
            return DownloadResponse(success=False, warnings=[f"download_failed: {e}"])

        return DownloadResponse(
            success=True,
            pdf_url=pdf_url,
            doc_url=doc_url,
            file_path=file_path,
            warnings=warnings,
        )
