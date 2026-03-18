# src/domain/literature/api/doaj_http/service.py
from __future__ import annotations

import asyncio
import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx

from .schemas import ApiResponse, DoajMeta, DoajPayload, DoajSearchParams


def _validate_query(q: str) -> Optional[str]:
    if "*" in q:
        return "wildcard '*' not allowed"
    if "~" in q:
        return "fuzzy/proximity '~' not allowed"
    if re.search(r"/.+?/", q):
        return "regex '/.../' not allowed"
    return None


def _extract_identifier(bib: Dict[str, Any], id_type: str) -> Optional[str]:
    for it in bib.get("identifier") or []:
        if (it.get("type") or "").lower() == id_type:
            return it.get("id")
    return None


def _extract_issns(bib: Dict[str, Any]) -> List[str]:
    out = []
    for it in bib.get("identifier") or []:
        t = (it.get("type") or "").lower()
        if t in ("issn", "pissn", "eissn"):
            if it.get("id"):
                out.append(it["id"])
    return list(dict.fromkeys(out))


def _simplify_article(rec: Dict[str, Any]) -> Dict[str, Any]:
    bib = rec.get("bibjson") or {}
    journal = bib.get("journal") or {}
    links = [l.get("url") for l in (bib.get("link") or []) if l.get("url")]

    return {
        "id": rec.get("id"),
        "title": bib.get("title"),
        "year": bib.get("year"),
        "doi": _extract_identifier(bib, "doi"),
        "journal_title": journal.get("title"),
        "publisher": journal.get("publisher"),
        "issns": _extract_issns(bib),
        "links": links,
        "keywords": bib.get("keywords") or [],
    }


def _simplify_journal(rec: Dict[str, Any]) -> Dict[str, Any]:
    bib = rec.get("bibjson") or {}
    license_types = [l.get("type") for l in (bib.get("license") or []) if l.get("type")]
    return {
        "id": rec.get("id"),
        "title": bib.get("title"),
        "publisher": bib.get("publisher"),
        "country": bib.get("country"),
        "issns": _extract_issns(bib),
        "license_types": list(dict.fromkeys(license_types)),
        "keywords": bib.get("keywords") or [],
    }


class DoajHttpService:
    def __init__(self, payload: DoajPayload):
        self.base_url = payload.base_url
        self.timeout_s = payload.timeout_s
        self.max_retries = max(0, payload.max_retries)
        self.sleep_seconds = max(0.0, payload.sleep_seconds)
        self.errors = payload.errors
        self.raw = payload.raw
        self.strict_query = payload.strict_query

        headers = {"Accept": "application/json"}
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
        self,
        resource: str,
        search_query: str,
        page: int,
        page_size: int,
        sort: Optional[str],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        encoded_query = quote(search_query, safe="")
        path = f"/search/{resource}/{encoded_query}"
        params = {"page": page, "pageSize": page_size}
        if sort:
            params["sort"] = sort

        backoff = 1.0
        for attempt in range(self.max_retries + 1):
            await self._throttle()
            try:
                resp = await self._client.get(path, params=params)
                if resp.status_code == 400:
                    return None, "bad_request"
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

    async def search(self, payload: DoajPayload) -> ApiResponse:
        sp: DoajSearchParams = payload.search_params
        warnings = []

        # ✅ strict_query 关闭时不校验
        if self.strict_query:
            qerr = _validate_query(sp.search_query)
            if qerr:
                if self.errors == "raise":
                    raise ValueError(qerr)
                return ApiResponse(success=False, warnings=[qerr])

        total_needed = sp.limit or sp.page_size
        pages_needed = 1
        if sp.limit:
            pages_needed = math.ceil(total_needed / sp.page_size)
            pages_needed = min(pages_needed, sp.max_pages)

        items: List[Dict[str, Any]] = []
        raw_pages: List[Dict[str, Any]] = []
        meta: Optional[DoajMeta] = None

        for i in range(pages_needed):
            page = sp.page + i
            data, err = await self._request_json(
                resource=sp.resource,
                search_query=sp.search_query,
                page=page,
                page_size=sp.page_size,
                sort=sp.sort,
            )
            if err:
                if self.errors == "raise":
                    raise RuntimeError(err)
                warnings.append(f"page_{page}:{err}")
                continue

            if data is None:
                continue

            if meta is None:
                meta = DoajMeta(
                    page=data.get("page", page),
                    page_size=data.get("pageSize", sp.page_size),
                    total=data.get("total", 0),
                    query=data.get("query", sp.search_query),
                    timestamp=data.get("timestamp"),
                )

            results = data.get("results") or []
            if payload.raw:
                # ✅ raw=true：保留全量响应（含 page/total/timestamp）
                items.extend(results)
                raw_pages.append(data)
            else:
                if sp.resource == "articles":
                    items.extend([_simplify_article(r) for r in results])
                else:
                    items.extend([_simplify_journal(r) for r in results])

            if len(results) < sp.page_size:
                break

        items = items[:total_needed]
        return ApiResponse(
            success=True,
            items=items,
            meta=meta,
            warnings=warnings,
            raw=raw_pages if payload.raw else None,
        )
