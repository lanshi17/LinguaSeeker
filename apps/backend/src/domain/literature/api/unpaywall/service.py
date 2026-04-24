# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportMissingImports=false, reportRedeclaration=false, reportFunctionMemberAccess=false, reportPossiblyUnboundVariable=false, reportReturnType=false

# src/domain/literature/api/unpaywall/service.py
from __future__ import annotations

import math
import os
import re
import time
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin

import requests

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


def _resolve_email(email: Optional[str]) -> Optional[str]:
    """Resolve Unpaywall email from payload/env."""
    resolved = (email or os.getenv("UNPAYWALL_EMAIL") or "").strip()
    return resolved or None


def _build_query(sp: SearchParams) -> str:
    """Build query string from SearchParams."""
    if sp.query and sp.query.strip():
        return sp.query.strip()
    if sp.keyword:
        return " ".join([k.strip() for k in sp.keyword if k and k.strip()])
    return ""


def _to_records(result: Any, raw: bool) -> List[Dict[str, Any]]:
    """Convert result to list of dict records."""
    if isinstance(result, dict):
        return [result]
    if raw:
        return result if isinstance(result, list) else []
    if hasattr(result, "to_dict"):
        return result.to_dict(orient="records")
    return []


def _pick_nested(mapping: Dict[str, Any], *path: str) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_pdf_links_from_html(html: str) -> List[str]:
    if not html:
        return []
    links = re.findall(
        r"""href\s*=\s*["']([^"']+\.pdf(?:\?[^"']*)?)["']""",
        html,
        flags=re.IGNORECASE,
    )
    links.extend(
        re.findall(
            r"""href\s*=\s*["']([^"']*type=printable[^"']*)["']""",
            html,
            flags=re.IGNORECASE,
        )
    )
    links.extend(
        re.findall(
            r"""meta\s+name\s*=\s*["']citation_pdf_url["']\s+content\s*=\s*["']([^"']+)["']""",
            html,
            flags=re.IGNORECASE,
        )
    )
    dedup: List[str] = []
    seen = set()
    for link in links:
        if link not in seen:
            seen.add(link)
            dedup.append(link)
    return dedup


def _dedupe_warnings(warnings: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in warnings:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


class _UnpaywallHttpClient:
    """HTTP fallback client when unpywall is unavailable."""

    CROSSREF_API = "https://api.crossref.org/works"
    UNPAYWALL_API = "https://api.unpaywall.org/v2/{doi}"

    def __init__(self, email: Optional[str]):
        self.email = email
        self.session = requests.Session()
        if email:
            ua = f"ACMG-Lingua/0.1.0 (+mailto:{email}; +https://github.com/yangzhaonan/ACMG-Lingua)"
        else:
            ua = "ACMG-Lingua/0.1.0 (+https://github.com/yangzhaonan/ACMG-Lingua)"
        self.session.headers.update(
            {
                "User-Agent": ua,
                "Accept": "application/json",
            }
        )

    def _get_unpaywall_record(self, doi: str) -> Optional[Dict[str, Any]]:
        if not self.email:
            return None
        resp = self.session.get(
            self.UNPAYWALL_API.format(doi=doi),
            params={"email": self.email},
            timeout=30,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data
        return None

    def fetch_by_dois(self, dois: List[str]) -> tuple[List[Dict[str, Any]], List[str]]:
        items: List[Dict[str, Any]] = []
        warnings: List[str] = []
        if not self.email:
            warnings.append("missing_unpaywall_email:crossref_only")
            return items, warnings
        for doi in dois:
            try:
                record = self._get_unpaywall_record(doi)
                if record:
                    items.append(record)
                else:
                    warnings.append(f"doi_not_found:{doi}")
            except Exception as exc:
                warnings.append(f"doi_fetch_failed:{doi}:{exc}")
        return items, warnings

    def fetch_crossref_by_dois(
        self, dois: List[str]
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        items: List[Dict[str, Any]] = []
        warnings: List[str] = []
        for doi in dois:
            try:
                resp = self.session.get(
                    f"{self.CROSSREF_API}/{doi}",
                    timeout=30,
                )
                if resp.status_code == 404:
                    warnings.append(f"doi_not_found:{doi}")
                    continue
                resp.raise_for_status()
                payload = resp.json()
                message = payload.get("message") if isinstance(payload, dict) else {}
                if isinstance(message, dict):
                    message.setdefault("doi", doi)
                    items.append(message)
            except Exception as exc:
                warnings.append(f"doi_crossref_failed:{doi}:{exc}")
        return items, warnings

    def search_crossref(
        self, query: str, limit: int, page: int
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        warnings: List[str] = []
        rows = min(max(limit * 2, 20), 100)
        offset = max(page - 1, 0) * rows
        crossref_resp = self.session.get(
            self.CROSSREF_API,
            params={
                "query": query,
                "rows": rows,
                "offset": offset,
                "select": "DOI,title,author,container-title,published-print,published-online,URL",
            },
            timeout=30,
        )
        crossref_resp.raise_for_status()
        payload = crossref_resp.json()
        message = payload.get("message") if isinstance(payload, dict) else {}
        works = message.get("items") if isinstance(message, dict) else []
        if not isinstance(works, list):
            works = []
        return works[:limit], warnings

    def search(
        self,
        query: str,
        limit: int,
        page: int,
        is_oa: Optional[bool] = None,
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        warnings: List[str] = []
        if not self.email:
            items, base_warnings = self.search_crossref(query, limit, page)
            return items, warnings + base_warnings + [
                "missing_unpaywall_email:crossref_only"
            ]

        # Crossref provides robust keyword retrieval; Unpaywall enriches OA status/PDF URL.
        rows = min(max(limit * 2, 20), 100)
        offset = max(page - 1, 0) * rows
        crossref_resp = self.session.get(
            self.CROSSREF_API,
            params={
                "query": query,
                "rows": rows,
                "offset": offset,
                "select": "DOI,title,author,container-title,published-print,published-online,URL",
            },
            timeout=30,
        )
        crossref_resp.raise_for_status()
        payload = crossref_resp.json()
        message = payload.get("message") if isinstance(payload, dict) else {}
        works = message.get("items") if isinstance(message, dict) else []
        dois = _normalize_dois([str(item.get("DOI") or "") for item in works or []])
        if not dois:
            return [], warnings

        enriched, fetch_warnings = self.fetch_by_dois(dois)
        warnings.extend(fetch_warnings)
        if is_oa is not None:
            enriched = [
                item for item in enriched if bool(item.get("is_oa")) is bool(is_oa)
            ]
        return enriched[:limit], warnings

    @staticmethod
    def extract_links(record: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        best = record.get("best_oa_location") or {}
        pdf_url = (
            _pick_nested(best, "url_for_pdf")
            or _pick_nested(best, "url")
            or record.get("oa_url")
        )
        doc_url = (
            _pick_nested(best, "url") or record.get("doi_url") or record.get("url")
        )
        if not pdf_url:
            for location in record.get("oa_locations") or []:
                if not isinstance(location, dict):
                    continue
                pdf_url = location.get("url_for_pdf") or location.get("url")
                if pdf_url:
                    doc_url = location.get("url") or doc_url
                    break
        return pdf_url, doc_url


class UnpaywallService:
    """Service for interacting with Unpaywall API via unpywall library."""

    PAGE_SIZE = 50

    def __init__(self, email: Optional[str] = None):
        """
        Initialize UnpaywallService.

        Args:
            email: Email for Unpaywall API authentication.
        """
        self._email = _resolve_email(email)
        self._runtime_warnings: List[str] = []
        self._http = _UnpaywallHttpClient(self._email)
        self._use_library = False
        self.Unpaywall = None
        if not self._email:
            self._runtime_warnings.append("missing_unpaywall_email:crossref_only")
        try:
            from unpywall import Unpywall
            from unpywall.utils import UnpaywallCredentials

            if self._email:
                UnpaywallCredentials(self._email)
                self.Unpaywall = Unpywall
                self._use_library = True
        except ModuleNotFoundError:
            self._runtime_warnings.append("unpywall_not_installed:fallback_http")

    def doi_query(self, payload: UnpaywallPayload) -> ApiResponse:
        """Query Unpaywall by DOI list."""
        warnings = list(self._runtime_warnings)
        dois = _normalize_dois(payload.doi_list)
        if payload.doi:
            dois = _normalize_dois([payload.doi])

        if not dois:
            return ApiResponse(success=False, warnings=["doi_list/doi is empty"])

        if self._use_library:
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
        else:
            if self._email:
                all_items, http_warnings = self._http.fetch_by_dois(dois)
            else:
                all_items, http_warnings = self._http.fetch_crossref_by_dois(dois)
            warnings.extend(http_warnings)

        return ApiResponse(
            success=bool(all_items),
            items=all_items,
            warnings=_dedupe_warnings(warnings),
            raw=all_items if payload.raw else None,
        )

    def query(self, payload: UnpaywallPayload) -> ApiResponse:
        """Search Unpaywall with query parameters."""
        warnings = list(self._runtime_warnings)
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
        if self._use_library:
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
        else:
            for i in range(pages_needed):
                page = start_page + i
                try:
                    batch_items, batch_warnings = self._http.search(
                        query=query_str,
                        limit=min(self.PAGE_SIZE, total_needed),
                        page=page,
                        is_oa=is_oa,
                    )
                    warnings.extend(batch_warnings)
                    all_items.extend(batch_items)
                    if len(batch_items) < self.PAGE_SIZE:
                        break
                    time.sleep(payload.sleep_seconds)
                except Exception as exc:
                    warnings.append(f"query_failed:{exc}")
                    break

        all_items = all_items[:total_needed]
        return ApiResponse(
            success=bool(all_items),
            items=all_items,
            warnings=_dedupe_warnings(warnings),
            raw=all_items if payload.raw else None,
        )

    def download(self, payload: UnpaywallPayload) -> DownloadResponse:
        """Download PDF for a DOI."""
        warnings = list(self._runtime_warnings)
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

        pdf_url: Optional[str] = None
        doc_url: Optional[str] = None

        if self._use_library:
            pdf_url = self.Unpaywall.get_pdf_link(doi)
            if not pdf_url:
                doc_url = self.Unpaywall.get_doc_link(doi)
        else:
            try:
                record = self._http._get_unpaywall_record(doi)
                if record:
                    pdf_url, doc_url = self._http.extract_links(record)
            except Exception as exc:
                warnings.append(f"download_lookup_failed:{exc}")

        if not pdf_url:
            if not self._email:
                try:
                    if self._email:
                        ua = f"ACMG-Lingua/0.1.0 (+mailto:{self._email}; +https://github.com/yangzhaonan/ACMG-Lingua)"
                    else:
                        ua = "ACMG-Lingua/0.1.0 (+https://github.com/yangzhaonan/ACMG-Lingua)"
                    landing = requests.get(
                        f"https://doi.org/{doi}",
                        timeout=60,
                        allow_redirects=True,
                        headers={
                            "Accept": "text/html,application/xhtml+xml",
                            "User-Agent": ua,
                        },
                    )
                    if landing.ok:
                        doc_url = str(landing.url)
                        if landing.content.startswith(b"%PDF"):
                            pdf_url = doc_url
                        else:
                            for link in _extract_pdf_links_from_html(
                                landing.text or ""
                            ):
                                absolute = urljoin(doc_url, link)
                                probe = requests.get(
                                    absolute, timeout=60, allow_redirects=True
                                )
                                if probe.ok and probe.content.startswith(b"%PDF"):
                                    pdf_url = absolute
                                    break
                except Exception as exc:
                    warnings.append(f"doi_landing_probe_failed:{exc}")

        if not pdf_url:
            return DownloadResponse(
                success=False,
                pdf_url=None,
                doc_url=doc_url,
                warnings=_dedupe_warnings(
                    warnings
                    + (
                        ["missing_unpaywall_email:download_limited"]
                        if not self._email
                        else []
                    )
                    + ["pdf_not_found"]
                ),
            )

        os.makedirs(payload.download_path, exist_ok=True)
        filename = _sanitize_filename(doi.replace("/", "_")) + ".pdf"
        file_path = os.path.join(payload.download_path, filename)

        try:
            if self._use_library:
                handle = self.Unpaywall.download_pdf_handle(doi)
                with open(file_path, "wb") as f:
                    f.write(handle.read())
            else:
                response = requests.get(pdf_url, timeout=60, allow_redirects=True)
                response.raise_for_status()
                content = response.content
                content_type = response.headers.get("content-type", "").lower()
                if not content.startswith(b"%PDF"):
                    if "html" in content_type:
                        extra_links = _extract_pdf_links_from_html(
                            response.text if response.text else ""
                        )
                        for link in extra_links:
                            nested = requests.get(
                                link, timeout=60, allow_redirects=True
                            )
                            nested.raise_for_status()
                            if nested.content.startswith(b"%PDF"):
                                pdf_url = link
                                content = nested.content
                                break
                    if not content.startswith(b"%PDF"):
                        return DownloadResponse(
                            success=False,
                            pdf_url=pdf_url,
                            doc_url=doc_url,
                            warnings=warnings + ["download_not_pdf"],
                        )
                with open(file_path, "wb") as f:
                    f.write(content)
        except Exception as e:
            return DownloadResponse(
                success=False,
                warnings=_dedupe_warnings(warnings + [f"download_failed: {e}"]),
            )

        return DownloadResponse(
            success=True,
            pdf_url=pdf_url,
            doc_url=doc_url,
            file_path=file_path,
            warnings=_dedupe_warnings(warnings),
        )
