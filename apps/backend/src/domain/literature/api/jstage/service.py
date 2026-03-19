# src/domain/literature/api/jstage_http/service.py
from __future__ import annotations

import asyncio
import math
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .schemas import ApiResponse, JStageMeta, JStageParams, JStagePayload

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "prism": "http://prismstandard.org/namespaces/basic/2.0/",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}


def _parse_status(root: ET.Element) -> Tuple[Optional[str], Optional[str]]:
    status = root.findtext(".//atom:result/atom:status", namespaces=NS)
    message = root.findtext(".//atom:result/atom:message", namespaces=NS)
    return status, message


def _extract_link(entry: ET.Element) -> str:
    for link in entry.findall("atom:link", NS):
        href = link.attrib.get("href")
        if href:
            return href
    return ""


def _parse_volume_entries(root: ET.Element) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in root.findall("atom:entry", NS):
        items.append(
            {
                "material_title_ja": entry.findtext(
                    "atom:material_title/atom:ja", default="", namespaces=NS
                ),
                "material_title_en": entry.findtext(
                    "atom:material_title/atom:en", default="", namespaces=NS
                ),
                "volume": entry.findtext("prism:volume", default="", namespaces=NS),
                "number": entry.findtext("prism:number", default="", namespaces=NS),
                "pubyear": entry.findtext("atom:pubyear", default="", namespaces=NS),
                "issn": entry.findtext("prism:issn", default="", namespaces=NS),
                "eissn": entry.findtext("prism:eIssn", default="", namespaces=NS),
                "link": _extract_link(entry),
            }
        )
    return items


def _parse_article_entries(root: ET.Element) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in root.findall("atom:entry", NS):
        items.append(
            {
                "article_title_ja": entry.findtext(
                    "atom:article_title/atom:ja", default="", namespaces=NS
                ),
                "article_title_en": entry.findtext(
                    "atom:article_title/atom:en", default="", namespaces=NS
                ),
                "material_title_ja": entry.findtext(
                    "atom:material_title/atom:ja", default="", namespaces=NS
                ),
                "material_title_en": entry.findtext(
                    "atom:material_title/atom:en", default="", namespaces=NS
                ),
                "issn": entry.findtext("prism:issn", default="", namespaces=NS),
                "eissn": entry.findtext("prism:eIssn", default="", namespaces=NS),
                "volume": entry.findtext("prism:volume", default="", namespaces=NS),
                "number": entry.findtext("prism:number", default="", namespaces=NS),
                "starting_page": entry.findtext(
                    "prism:startingPage", default="", namespaces=NS
                ),
                "ending_page": entry.findtext(
                    "prism:endingPage", default="", namespaces=NS
                ),
                "pubyear": entry.findtext("atom:pubyear", default="", namespaces=NS),
                "doi": entry.findtext("prism:doi", default="", namespaces=NS),
                "link": _extract_link(entry),
            }
        )
    return items


class JStageHttpService:
    def __init__(self, payload: JStagePayload):
        self.base_url = payload.base_url
        self.timeout_s = payload.timeout_s
        self.max_retries = max(0, payload.max_retries)
        self.sleep_seconds = max(0.0, payload.sleep_seconds)
        self.errors = payload.errors
        self.raw = payload.raw

        headers = {"Accept": "application/xml"}
        if payload.user_agent:
            headers["User-Agent"] = payload.user_agent

        self._client = httpx.AsyncClient(timeout=self.timeout_s, headers=headers)
        self._last_call_ts = 0.0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._client.aclose()

    async def _throttle(self):
        if self.sleep_seconds <= 0:
            return
        now = time.monotonic()
        if now - self._last_call_ts < self.sleep_seconds:
            await asyncio.sleep(self.sleep_seconds - (now - self._last_call_ts))
        self._last_call_ts = time.monotonic()

    async def _request_text(
        self, params: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        backoff = 1.0
        for attempt in range(self.max_retries + 1):
            await self._throttle()
            try:
                resp = await self._client.get(self.base_url, params=params)
                resp.raise_for_status()
                # 确保 UTF‑8
                if not resp.encoding:
                    resp.encoding = "utf-8"
                return resp.text, None
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

    def _build_params_volumes(self, p: JStageParams) -> Dict[str, Any]:
        params = {"service": "2"}
        if p.material:
            params["material"] = p.material
        if p.issn:
            params["issn"] = p.issn
        if p.cdjournal:
            params["cdjournal"] = p.cdjournal
        if p.pubyearfrom:
            params["pubyearfrom"] = p.pubyearfrom
        if p.pubyearto:
            params["pubyearto"] = p.pubyearto
        if p.volorder:
            params["volorder"] = p.volorder
        return params

    def _build_params_articles(
        self, p: JStageParams, start: int, count: int
    ) -> Dict[str, Any]:
        params = {"service": "3", "start": str(start), "count": str(count)}
        if p.material:
            params["material"] = p.material
        if p.article:
            params["article"] = p.article
        if p.author:
            params["author"] = p.author
        if p.keyword:
            params["keyword"] = p.keyword
        if p.issn:
            params["issn"] = p.issn
        if p.cdjournal:
            params["cdjournal"] = p.cdjournal
        if p.sortflg:
            params["sortflg"] = p.sortflg
        return params

    async def fetch_volumes(self, payload: JStagePayload) -> ApiResponse:
        p = payload.params
        warnings: List[str] = []

        params = self._build_params_volumes(p)
        xml_text, err = await self._request_text(params)
        if err:
            if payload.errors == "raise":
                raise RuntimeError(err)
            return ApiResponse(success=False, warnings=[err])

        root = ET.fromstring(xml_text or "")
        status, message = _parse_status(root)
        if status != "0":
            if status == "ERR_001":
                return ApiResponse(
                    success=True,
                    items=[],
                    meta=JStageMeta(status=status, message=message),
                    warnings=["no_results"],
                    raw=xml_text if payload.raw else None,
                )
            if payload.errors == "raise":
                raise RuntimeError(f"{status}:{message}")
            return ApiResponse(
                success=False,
                warnings=[f"{status}:{message}"],
                raw=xml_text if payload.raw else None,
            )

        items = _parse_volume_entries(root)
        return ApiResponse(
            success=True,
            items=items,
            meta=JStageMeta(status=status, message=message),
            warnings=warnings,
            raw=xml_text if payload.raw else None,
        )

    async def fetch_articles(self, payload: JStagePayload) -> ApiResponse:
        p = payload.params
        warnings: List[str] = []

        count = p.count
        if count > 1000:
            warnings.append("count_truncated_to_1000")
            count = 1000

        total_needed = p.limit or count
        pages_needed = math.ceil(total_needed / count)
        pages_needed = min(pages_needed, p.max_pages)
        if p.limit and pages_needed < math.ceil(total_needed / count):
            warnings.append("limit_truncated_by_max_pages")

        items: List[Dict[str, Any]] = []
        raw_pages: List[str] = []
        meta: Optional[JStageMeta] = None

        for i in range(pages_needed):
            start = p.start + i * count
            params = self._build_params_articles(p, start=start, count=count)
            xml_text, err = await self._request_text(params)
            if err:
                if payload.errors == "raise":
                    raise RuntimeError(err)
                warnings.append(f"page_{i}:{err}")
                continue

            root = ET.fromstring(xml_text or "")
            status, message = _parse_status(root)
            if status != "0":
                if status == "ERR_001":
                    warnings.append("no_results")
                    break
                if payload.errors == "raise":
                    raise RuntimeError(f"{status}:{message}")
                warnings.append(f"{status}:{message}")
                break

            page_items = _parse_article_entries(root)
            items.extend(page_items)

            if meta is None:
                total_results = root.findtext(
                    ".//opensearch:totalResults", namespaces=NS
                )
                meta = JStageMeta(
                    status=status,
                    message=message,
                    total_results=int(total_results)
                    if total_results and total_results.isdigit()
                    else None,
                    start=start,
                    count=count,
                )

            if payload.raw:
                raw_pages.append(xml_text or "")

            if len(page_items) < count or len(items) >= total_needed:
                break

        if p.limit:
            items = items[: p.limit]

        return ApiResponse(
            success=True,
            items=items,
            meta=meta,
            warnings=warnings,
            raw=raw_pages if payload.raw else None,
        )
