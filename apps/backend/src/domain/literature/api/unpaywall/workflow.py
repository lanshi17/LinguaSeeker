# src/domain/literature/api/unpaywall_http/service.py
from __future__ import annotations

import asyncio
import math
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .schemas import ApiResponse, DownloadResponse, SearchParams, UnpaywallPayload


def _sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name or "paper")[:120]


def _normalize_dois(dois: List[str]) -> List[str]:
    seen = set()
    res = []
    for d in dois or []:
        dd = (d or "").strip().lower()
        if dd and dd not in seen:
            seen.add(dd)
            res.append(dd)
    return res


def _build_query(sp: SearchParams) -> str:
    if sp.query and sp.query.strip():
        return sp.query.strip()
    if sp.keyword:
        return " ".join([k.strip() for k in sp.keyword if k and k.strip()])
    return ""


def _simplify_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    best = rec.get("best_oa_location") or {}
    return {
        "doi": rec.get("doi"),
        "title": rec.get("title"),
        "oa_status": rec.get("oa_status"),
        "published_date": rec.get("published_date"),
        "journal_name": rec.get("journal_name"),
        "best_pdf_url": best.get("url_for_pdf"),
        "best_doc_url": best.get("url"),
    }


def _extract_links(
    rec: Dict[str, Any],
) -> Tuple[Optional[str], Optional[str], List[str]]:
    all_links = []
    best = rec.get("best_oa_location") or {}
    pdf = best.get("url_for_pdf")
    doc = best.get("url")

    for loc in rec.get("oa_locations") or []:
        if loc.get("url_for_pdf"):
            all_links.append(loc["url_for_pdf"])
        if loc.get("url"):
            all_links.append(loc["url"])

    if not pdf:
        for loc in rec.get("oa_locations") or []:
            if loc.get("url_for_pdf"):
                pdf = loc["url_for_pdf"]
                break

    if not doc and best.get("url"):
        doc = best.get("url")
    if not doc:
        for loc in rec.get("oa_locations") or []:
            if loc.get("url"):
                doc = loc["url"]
                break

    return pdf, doc, list(dict.fromkeys(all_links))


class UnpaywallHttpService:
    PAGE_SIZE = 50

    def __init__(self, payload: UnpaywallPayload):
        self.email = payload.email or os.getenv("UNPAYWALL_EMAIL")
        if not self.email:
            raise ValueError("UNPAYWALL_EMAIL is required (or pass payload.email)")

        self.base_url = payload.base_url
        self.timeout_s = payload.timeout_s
        self.max_retries = max(0, payload.max_retries)
        self.sleep_seconds = max(0.0, payload.sleep_seconds)
        self.errors = payload.errors
        self.raw = payload.raw

        headers = {}
        if payload.user_agent:
            headers["User-Agent"] = payload.user_agent

        self._client = httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout_s, headers=headers
        )
        self._last_call_ts = 0.0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._client.aclose()

    async def _throttle(self):
        if self.sleep_seconds <= 0:
            return
        now = time.monotonic()
        elapsed = now - self._last_call_ts
        if elapsed < self.sleep_seconds:
            await asyncio.sleep(self.sleep_seconds - elapsed)
        self._last_call_ts = time.monotonic()

    async def _request_json(
        self, path: str, params: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        params = {**params, "email": self.email}
        backoff = 1.0
        for attempt in range(self.max_retries + 1):
            await self._throttle()
            try:
                resp = await self._client.get(path, params=params)
                if resp.status_code == 404:
                    return None, "not_found"
                resp.raise_for_status()
                return resp.json(), None
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 10)
                    continue
                return None, f"http_{status}"
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 10)
                    continue
                return None, f"request_error:{e}"

        return None, "unknown_error"

    async def doi_query(self, payload: UnpaywallPayload) -> ApiResponse:
        warnings = []
        dois = _normalize_dois(payload.doi_list)
        if payload.doi:
            dois = _normalize_dois([payload.doi])

        if not dois:
            return ApiResponse(success=False, warnings=["doi_list/doi is empty"])

        items = []
        for d in dois:
            data, err = await self._request_json(f"/{d}", params={})
            if err:
                if self.errors == "raise":
                    raise RuntimeError(err)
                warnings.append(f"{d}:{err}")
                continue
            items.append(data if payload.raw else _simplify_record(data))

        return ApiResponse(
            success=True,
            items=items,
            warnings=warnings,
            raw=items if payload.raw else None,
        )

    async def query(self, payload: UnpaywallPayload) -> ApiResponse:
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
        pages_needed = math.ceil(total_needed / self.PAGE_SIZE)
        pages_needed = min(pages_needed, 10)

        items = []
        for i in range(pages_needed):
            page = sp.page + i
            params = {"query": query_str, "page": page}
            if is_oa is not None:
                params["is_oa"] = is_oa

            data, err = await self._request_json("/search", params=params)
            if err:
                if self.errors == "raise":
                    raise RuntimeError(err)
                warnings.append(f"page_{page}:{err}")
                continue

            results = data.get("results") or []
            for r in results:
                rec = r.get("response") if isinstance(r, dict) else None
                if rec is None and isinstance(r, dict):
                    rec = r
                if not rec:
                    continue
                items.append(rec if payload.raw else _simplify_record(rec))

            if len(results) < self.PAGE_SIZE:
                break

        items = items[:total_needed]
        return ApiResponse(
            success=True,
            items=items,
            warnings=warnings,
            raw=items if payload.raw else None,
        )

    async def download(self, payload: UnpaywallPayload) -> DownloadResponse:
        warnings = []
        doi = payload.doi

        if not doi and payload.doi_list:
            dois = _normalize_dois(payload.doi_list)
            if 0 <= payload.selected_index < len(dois):
                doi = dois[payload.selected_index]

        if not doi and payload.search_params:
            qres = await self.query(payload)
            if not qres.items:
                return DownloadResponse(success=False, warnings=["no_search_results"])
            idx = payload.selected_index
            if 0 <= idx < len(qres.items):
                doi = qres.items[idx].get("doi")

        if not doi:
            return DownloadResponse(success=False, warnings=["missing doi"])

        data, err = await self._request_json(f"/{doi}", params={})
        if err or not data:
            return DownloadResponse(
                success=False, warnings=[f"doi_lookup_failed:{err}"]
            )

        pdf_url, doc_url, _ = _extract_links(data)
        if not pdf_url:
            return DownloadResponse(
                success=False, pdf_url=None, doc_url=doc_url, warnings=["pdf_not_found"]
            )

        os.makedirs(payload.download_path, exist_ok=True)
        filename = _sanitize_filename(doi.replace("/", "_")) + ".pdf"
        file_path = os.path.join(payload.download_path, filename)

        try:
            async with self._client.stream(
                "GET", pdf_url, follow_redirects=True
            ) as resp:
                resp.raise_for_status()
                with open(file_path, "wb") as f:
                    async for chunk in resp.aiter_bytes():
                        f.write(chunk)
        except Exception as e:
            return DownloadResponse(success=False, warnings=[f"download_failed:{e}"])

        return DownloadResponse(
            success=True,
            pdf_url=pdf_url,
            doc_url=doc_url,
            file_path=file_path,
            warnings=warnings,
        )
        # src/domain/literature/api/unpaywall_http/workflow.py
        from typing import Any, Dict

        from .schemas import UnpaywallPayload
        from .service import UnpaywallHttpService

        async def unpaywall_http_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
            req = UnpaywallPayload.model_validate(payload)
            async with UnpaywallHttpService(req) as svc:
                if req.action == "query":
                    return (await svc.query(req)).model_dump()
                if req.action == "doi":
                    return (await svc.doi_query(req)).model_dump()
                if req.action == "download":
                    return (await svc.download(req)).model_dump()
            return {"success": False, "warnings": ["unknown_action"]}
