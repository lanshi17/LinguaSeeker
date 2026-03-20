# src/domain/literature/api/crossref_http/service.py
from __future__ import annotations

import asyncio
import math
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .models import ApiResponse, CrossrefMeta, CrossrefParams, CrossrefPayload

RESERVED_KEYS = {"query", "filter", "select", "rows", "cursor"}


def _normalize_select(select_val):
    if select_val is None:
        return None
    if isinstance(select_val, list):
        return ",".join([s.strip() for s in select_val if s])
    return str(select_val)


class CrossrefHttpService:
    def __init__(self, payload: CrossrefPayload):
        self.base_url = payload.base_url
        self.timeout_s = payload.timeout_s
        self.max_retries = max(0, payload.max_retries)
        self.sleep_seconds = max(0.0, payload.sleep_seconds)
        self.errors = payload.errors
        self.raw = payload.raw

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
        self, path: str, params: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
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

    def _validate(self, p: CrossrefParams) -> Tuple[Optional[str], List[str]]:
        warnings = []
        if p.rows < 1 or p.rows > 1000:
            return "rows_out_of_range_1_1000", warnings
        if p.limit is not None and p.limit < 1:
            return "limit_out_of_range", warnings
        if p.max_pages < 1:
            return "max_pages_out_of_range", warnings
        return None, warnings

    def _build_params(
        self, p: CrossrefParams, cursor: Optional[str]
    ) -> Tuple[Dict[str, Any], List[str]]:
        warnings = []
        params: Dict[str, Any] = {"rows": p.rows}

        if p.query:
            params["query"] = p.query
        if p.filter:
            params["filter"] = p.filter

        select_val = _normalize_select(p.select)
        if select_val:
            params["select"] = select_val

        if cursor:
            params["cursor"] = cursor

        # 合并扩展查询参数（如 query.title）
        if p.query_params:
            for k, v in p.query_params.items():
                if v is None:
                    continue
                if k in RESERVED_KEYS:
                    warnings.append(f"query_params_key_ignored:{k}")
                else:
                    params[k] = v
        return params, warnings

    async def search(self, payload: CrossrefPayload) -> ApiResponse:
        p = payload.params
        warnings: List[str] = []

        err, warns = self._validate(p)
        warnings.extend(warns)
        if err:
            if payload.errors == "raise":
                raise ValueError(err)
            return ApiResponse(success=False, warnings=[err] + warnings)

        # limit -> cursor 自动分页
        cursor = p.cursor
        if p.limit and not cursor:
            cursor = "*"
            warnings.append("cursor_auto_enabled")

        total_needed = p.limit or p.rows
        pages_needed = 1
        if p.limit:
            pages_needed = math.ceil(total_needed / p.rows)
            if pages_needed > p.max_pages:
                warnings.append("limit_truncated_by_max_pages")
                pages_needed = p.max_pages

        items: List[Dict[str, Any]] = []
        raw_pages: List[Dict[str, Any]] = []
        meta: Optional[CrossrefMeta] = None

        path = f"/{p.resource}"

        for i in range(pages_needed):
            params, warns = self._build_params(p, cursor)
            warnings.extend(warns)

            data, req_err = await self._request_json(path, params=params)
            if req_err:
                if payload.errors == "raise":
                    raise RuntimeError(req_err)
                warnings.append(f"page_{i}:{req_err}")
                continue

            if not data:
                continue

            msg = data.get("message") or {}
            page_items = msg.get("items") or []
            items.extend(page_items)

            if meta is None:
                meta = CrossrefMeta(
                    total_results=msg.get("total-results", 0),
                    items_per_page=msg.get("items-per-page", len(page_items)),
                    query=msg.get("query"),
                    next_cursor=msg.get("next-cursor"),
                )
            else:
                meta.next_cursor = msg.get("next-cursor") or meta.next_cursor

            if payload.raw:
                raw_pages.append(data)

            next_cursor = msg.get("next-cursor")
            if not next_cursor or len(page_items) < p.rows:
                break
            cursor = next_cursor

        if p.limit:
            items = items[: p.limit]

        return ApiResponse(
            success=True,
            items=items,
            meta=meta,
            warnings=warnings,
            raw=raw_pages if payload.raw else None,
        )
