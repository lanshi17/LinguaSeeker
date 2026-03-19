# src/domain/literature/api/pmc_http/service.py
from __future__ import annotations

import asyncio
import math
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles
import httpx

from .schemas import ApiResponse, PmcMeta, PmcParams, PmcPayload


def _normalize_pmcid(pmcid: str) -> str:
    s = (pmcid or "").strip().upper()
    return s if s.startswith("PMC") else f"PMC{s}"


def _s3_to_https(url: str, s3_http_base: str) -> str:
    if url.startswith("s3://pmc-oa-opendata/"):
        return url.replace("s3://pmc-oa-opendata/", s3_http_base.rstrip("/") + "/")
    return url


def _parse_versions_from_xml(xml_text: str) -> List[str]:
    # Handle namespace or no-namespace
    versions = []
    try:
        root = ET.fromstring(xml_text)
        for elem in root.iter():
            tag = elem.tag.split("}")[-1]  # remove namespace
            if tag == "Prefix" and elem.text:
                val = elem.text.strip().rstrip("/")
                if val.startswith("PMC") and "." in val:
                    versions.append(val)
    except ET.ParseError:
        return []
    return list(dict.fromkeys(versions))


def _choose_latest_version(versions: List[str]) -> Optional[str]:
    best = None
    best_num = -1
    for v in versions:
        parts = v.split(".")
        if len(parts) == 2 and parts[1].isdigit():
            num = int(parts[1])
            if num > best_num:
                best_num = num
                best = v
    return best


class PmcHttpService:
    def __init__(self, payload: PmcPayload):
        self.esearch_base = payload.esearch_base.rstrip("/")
        self.s3_http_base = payload.s3_http_base.rstrip("/")
        self.timeout_s = payload.timeout_s
        self.max_retries = max(0, payload.max_retries)
        self.sleep_seconds = max(0.0, payload.sleep_seconds)
        self.errors = payload.errors
        self.raw = payload.raw

        headers = {"Accept": "application/json"}
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
        elapsed = now - self._last_call_ts
        if elapsed < self.sleep_seconds:
            await asyncio.sleep(self.sleep_seconds - elapsed)
        self._last_call_ts = time.monotonic()

    async def _request_json(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        backoff = 1.0
        for attempt in range(self.max_retries + 1):
            await self._throttle()
            try:
                resp = await self._client.get(url, params=params)
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

    async def _request_text(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        backoff = 1.0
        for attempt in range(self.max_retries + 1):
            await self._throttle()
            try:
                resp = await self._client.get(url, params=params)
                if resp.status_code == 400:
                    return None, "bad_request"
                resp.raise_for_status()
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

    def _build_term(
        self, term: str, require_open_access: bool, warnings: List[str]
    ) -> str:
        if require_open_access:
            if (
                "open_access[filter]" not in term
                and "author_manuscript[filter]" not in term
            ):
                warnings.append("open_access_filter_appended")
                return f"{term} AND (open_access[filter] OR author_manuscript[filter])"
        return term

    def _validate(self, action: str, p: PmcParams) -> Optional[str]:
        if action == "search":
            if not p.term:
                return "missing_term"
        if action in {"list_versions", "metadata"}:
            if not p.pmcid:
                return "missing_pmcid"
        if action == "download":
            if not (p.pmcid or p.pmcids):
                return "missing_pmcid_or_pmcids"
            if not p.file_types:
                return "missing_file_types"
        return None

    async def search(self, payload: PmcPayload) -> ApiResponse:
        p = payload.params
        warnings: List[str] = []

        err = self._validate("search", p)
        if err:
            if payload.errors == "raise":
                raise ValueError(err)
            return ApiResponse(success=False, warnings=[err])

        term = self._build_term(p.term or "", p.require_open_access, warnings)

        url = f"{self.esearch_base}/esearch.fcgi"

        total_needed = p.limit or p.retmax
        pages_needed = 1
        if p.limit:
            pages_needed = math.ceil(total_needed / p.retmax)
            pages_needed = min(pages_needed, p.max_pages)
            if pages_needed < math.ceil(total_needed / p.retmax):
                warnings.append("limit_truncated_by_max_pages")

        items: List[Dict[str, Any]] = []
        raw_pages: List[Dict[str, Any]] = []
        meta: Optional[PmcMeta] = None

        for i in range(pages_needed):
            retstart = p.retstart + i * p.retmax
            params = {
                "db": "pmc",
                "term": term,
                "retmax": p.retmax,
                "retstart": retstart,
                "format": "json",
            }
            data, err = await self._request_json(url, params=params)
            if err:
                if payload.errors == "raise":
                    raise RuntimeError(err)
                warnings.append(f"page_{i}:{err}")
                continue

            esr = (data or {}).get("esearchresult") or {}
            idlist = esr.get("idlist") or []
            for pid in idlist:
                items.append({"pmcid": _normalize_pmcid(pid)})

            if meta is None:
                meta = PmcMeta(
                    count=int(esr.get("count") or 0),
                    retmax=int(esr.get("retmax") or p.retmax),
                    retstart=int(esr.get("retstart") or retstart),
                    term=term,
                )

            if payload.raw:
                raw_pages.append(data)

            if len(idlist) < p.retmax or len(items) >= total_needed:
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

    async def list_versions(self, payload: PmcPayload) -> ApiResponse:
        p = payload.params
        warnings: List[str] = []

        err = self._validate("list_versions", p)
        if err:
            if payload.errors == "raise":
                raise ValueError(err)
            return ApiResponse(success=False, warnings=[err])

        pmcid = _normalize_pmcid(p.pmcid or "")
        params = {"list-type": "2", "prefix": f"{pmcid}.", "delimiter": "/"}
        url = f"{self.s3_http_base}/"

        text, req_err = await self._request_text(url, params=params)
        if req_err:
            if payload.errors == "raise":
                raise RuntimeError(req_err)
            return ApiResponse(success=False, warnings=[req_err])

        versions = _parse_versions_from_xml(text or "")
        if not versions:
            warnings.append("no_versions_found")

        items = [{"version": v, "pmcid": pmcid} for v in versions]
        return ApiResponse(
            success=True,
            items=items,
            meta=PmcMeta(pmcid=pmcid),
            warnings=warnings,
            raw=text if payload.raw else None,
        )

    async def fetch_metadata(self, payload: PmcPayload) -> ApiResponse:
        p = payload.params
        warnings: List[str] = []

        err = self._validate("metadata", p)
        if err:
            if payload.errors == "raise":
                raise ValueError(err)
            return ApiResponse(success=False, warnings=[err])

        pmcid = _normalize_pmcid(p.pmcid or "")

        version = p.version
        if version is None:
            # choose latest
            versions_resp = await self.list_versions(payload)
            if not versions_resp.items:
                return ApiResponse(success=False, warnings=["no_versions_found"])
            latest = _choose_latest_version(
                [it["version"] for it in versions_resp.items]
            )
            if not latest:
                return ApiResponse(success=False, warnings=["no_versions_found"])
            version = int(latest.split(".")[1])

        ver = f"{pmcid}.{version}"
        url = f"{self.s3_http_base}/{ver}/{ver}.json"
        data, req_err = await self._request_json(url)
        if req_err:
            if payload.errors == "raise":
                raise RuntimeError(req_err)
            return ApiResponse(success=False, warnings=[req_err])

        meta = PmcMeta(
            pmcid=pmcid, version=version, license_code=(data or {}).get("license_code")
        )
        return ApiResponse(
            success=True,
            items=[data],
            meta=meta,
            warnings=warnings,
            raw=data if payload.raw else None,
        )

    async def _download_file(
        self, url: str, out_path: Path
    ) -> Tuple[int, Optional[str]]:
        backoff = 1.0
        for attempt in range(self.max_retries + 1):
            await self._throttle()
            try:
                async with self._client.stream("GET", url) as resp:
                    if resp.status_code == 404:
                        return 0, "http_404"
                    resp.raise_for_status()
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    total = 0
                    async with aiofiles.open(out_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                            if not chunk:
                                continue
                            await f.write(chunk)
                            total += len(chunk)
                    return total, None
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 10)
                    continue
                return 0, f"http_{status}"
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 10)
                    continue
                return 0, f"request_error:{e}"
        return 0, "unknown_error"

    async def download(self, payload: PmcPayload) -> ApiResponse:
        p = payload.params
        warnings: List[str] = []

        err = self._validate("download", p)
        if err:
            if payload.errors == "raise":
                raise ValueError(err)
            return ApiResponse(success=False, warnings=[err])

        pmcids = p.pmcids or ([p.pmcid] if p.pmcid else [])
        pmcids = [_normalize_pmcid(pid) for pid in pmcids]

        file_key_map = {"pdf": "pdf_url", "xml": "xml_url", "txt": "text_url"}

        sem = asyncio.Semaphore(p.download_concurrency)
        results: List[Dict[str, Any]] = []
        raw_meta_list: List[Dict[str, Any]] = []

        async def handle_one(pmcid: str):
            nonlocal results, raw_meta_list, warnings

            version = p.version
            if version is None:
                # auto latest
                temp_payload = PmcPayload(
                    action="list_versions",
                    params=PmcParams(pmcid=pmcid),
                    esearch_base=payload.esearch_base,
                    s3_http_base=payload.s3_http_base,
                    timeout_s=payload.timeout_s,
                    max_retries=payload.max_retries,
                    sleep_seconds=payload.sleep_seconds,
                    errors=payload.errors,
                    raw=False,
                )
                versions_resp = await self.list_versions(temp_payload)
                if not versions_resp.items:
                    warnings.append(f"{pmcid}:no_versions_found")
                    return
                latest = _choose_latest_version(
                    [it["version"] for it in versions_resp.items]
                )
                if not latest:
                    warnings.append(f"{pmcid}:no_versions_found")
                    return
                version = int(latest.split(".")[1])

            ver = f"{pmcid}.{version}"
            meta_url = f"{self.s3_http_base}/{ver}/{ver}.json"
            meta_data, err = await self._request_json(meta_url)
            if err or not meta_data:
                warnings.append(f"{pmcid}:{err or 'metadata_empty'}")
                return

            raw_meta_list.append(meta_data)

            # build download targets
            targets: List[Tuple[str, str]] = []
            for ft in p.file_types:
                if ft == "media":
                    for u in meta_data.get("media_urls", []) or []:
                        targets.append(("media", _s3_to_https(u, self.s3_http_base)))
                else:
                    key = file_key_map.get(ft)
                    u = meta_data.get(key)
                    if u:
                        targets.append((ft, _s3_to_https(u, self.s3_http_base)))
                    else:
                        warnings.append(f"{pmcid}:{ft}_url_missing")

            for ftype, url in targets:
                filename = url.split("/")[-1].split("?")[0]
                out_path = Path(p.out_dir) / ver / filename

                if not p.download:
                    results.append(
                        {
                            "pmcid": pmcid,
                            "version": version,
                            "type": ftype,
                            "url": url,
                            "path": None,
                            "bytes": 0,
                        }
                    )
                    continue

                async with sem:
                    size, ferr = await self._download_file(url, out_path)
                    if ferr:
                        warnings.append(f"{pmcid}:{ftype}:{ferr}")
                        if payload.errors == "raise":
                            raise RuntimeError(ferr)
                    results.append(
                        {
                            "pmcid": pmcid,
                            "version": version,
                            "type": ftype,
                            "url": url,
                            "path": str(out_path),
                            "bytes": size,
                        }
                    )

        for pid in pmcids:
            await handle_one(pid)

        return ApiResponse(
            success=True,
            items=results,
            meta=None,
            warnings=warnings,
            raw=raw_meta_list if payload.raw else None,
        )
