from __future__ import annotations

import json
import math
import os
import re
import time
from typing import Any, Dict, Iterable, List, Literal, Optional

from pydantic import BaseModel, Field, validator


# ========== Models ==========
class SearchParams(BaseModel):
    keyword: List[str] = Field(default_factory=list)
    query: Optional[str] = None
    filters: Dict[str, Any] = Field(default_factory=dict)  # supports: is_oa
    limit: int = 50
    page: int = 1

    @validator("limit")
    def limit_range(cls, v):
        return max(1, min(v, 500))  # up to 10 pages (50/page)

    @validator("page")
    def page_min(cls, v):
        return max(1, v)


class UnpaywallPayload(BaseModel):
    action: Literal["query", "doi", "download"] = "query"

    # auth
    email: Optional[str] = None

    # query
    search_params: Optional[SearchParams] = None

    # doi query
    doi_list: List[str] = Field(default_factory=list)
    doi: Optional[str] = None

    # download
    selected_index: int = 0
    download_path: str = "./downloads"

    # runtime
    batch_size: int = 200
    sleep_seconds: float = 1.0
    progress: bool = False
    errors: Literal["raise", "ignore"] = "ignore"
    raw: bool = False


class ApiResponse(BaseModel):
    success: bool
    items: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    raw: Optional[Any] = None


class DownloadResponse(BaseModel):
    success: bool
    pdf_url: Optional[str] = None
    doc_url: Optional[str] = None
    file_path: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


# ========== Helpers ==========
def _sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name or "paper")[:120]


def _normalize_dois(dois: Iterable[str]) -> List[str]:
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
    if sp.query and sp.query.strip():
        return sp.query.strip()
    if sp.keyword:
        return " ".join([k.strip() for k in sp.keyword if k and k.strip()])
    return ""


def _ensure_credentials(email: Optional[str]):
    # lazy import to avoid hard dependency in non-api contexts
    from unpywall.utils import UnpywallCredentials

    if email:
        UnpywallCredentials(email)
        return

    if not os.getenv("UNPAYWALL_EMAIL"):
        raise ValueError("UNPAYWALL_EMAIL is required (or pass payload.email)")


def _to_records(result, raw: bool) -> List[Dict[str, Any]]:
    if raw:
        # Unpywall returns list[dict] when raw=True
        return result if isinstance(result, list) else []
    if hasattr(result, "to_dict"):
        return result.to_dict(orient="records")
    return []


# ========== Service ==========
class UnpaywallService:
    PAGE_SIZE = 50

    def __init__(self, email: Optional[str]):
        _ensure_credentials(email)
        # local import after credentials
        from unpywall import Unpywall  # noqa

        self.Unpaywall = Unpywall

    def doi_query(self, payload: UnpaywallPayload) -> ApiResponse:
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
        warnings = []
        sp = payload.search_params
        if not sp:
            return ApiResponse(success=False, warnings=["missing search_params"])

        query_str = _build_query(sp)
        if not query_str:
            return ApiResponse(success=False, warnings=["empty query"])

        # supported filter
        is_oa = None
        if sp.filters and "is_oa" in sp.filters:
            is_oa = sp.filters.get("is_oa")

        unsupported = [k for k in (sp.filters or {}).keys() if k != "is_oa"]
        if unsupported:
            warnings.append(f"unsupported_filters: {unsupported}")

        total_needed = sp.limit
        start_page = sp.page
        pages_needed = math.ceil(total_needed / self.PAGE_SIZE)
        pages_needed = min(pages_needed, 10)  # safety cap

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
        warnings = []
        doi = payload.doi

        # if doi not provided, use doi_list/selected_index or query
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

        # fetch PDF link
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


# ========== Entry ==========
async def unpaywall_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = UnpaywallPayload.model_validate(payload)
    service = UnpaywallService(email=req.email)

    if req.action == "doi":
        return service.doi_query(req).model_dump()

    if req.action == "query":
        return service.query(req).model_dump()

    if req.action == "download":
        return service.download(req).model_dump()

    return {"success": False, "warnings": ["unknown_action"]}
