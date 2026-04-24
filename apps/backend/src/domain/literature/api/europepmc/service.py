# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportMissingImports=false, reportRedeclaration=false, reportFunctionMemberAccess=false, reportPossiblyUnboundVariable=false, reportReturnType=false

# src/domain/literature/api/europepmc/service.py
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
    EuropePmcPayload,
    SearchParams,
)

from src.config import get_user_agent


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


class EuropePmcService:
    """Europe PMC API service for literature acquisition."""

    EUROPEPMC_API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    EUROPEPMC_REST_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    PAGE_SIZE = 50

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": get_user_agent(),
                "Accept": "application/json",
            }
        )
        self._runtime_warnings: List[str] = []

    def query(self, payload: EuropePmcPayload) -> ApiResponse:
        """Execute search query against Europe PMC API."""
        warnings = list(self._runtime_warnings)
        all_items: List[Dict[str, Any]] = []

        query = _build_query(payload.search_params) if payload.search_params else ""
        if not query and not payload.doi and not payload.doi_list:
            return ApiResponse(
                success=False,
                items=[],
                warnings=warnings + ["empty query or no DOIs provided"],
            )

        # Handle single DOI case
        if payload.doi:
            try:
                search_query = f"DOI:{payload.doi}"
                params = {
                    "query": search_query,
                    "format": "json",
                    "pageSize": 1,
                }
                resp = self.session.get(self.EUROPEPMC_API_URL, params=params, timeout=30)
                if resp.status_code == 404:
                    warnings.append(f"doi_not_found:{payload.doi}")
                    return ApiResponse(
                        success=False,
                        items=[],
                        warnings=warnings,
                        raw=None if not payload.raw else [resp.json()] if resp.ok else None,
                    )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("resultList", {}).get("result", [])
                if results:
                    all_items.extend(results)
            except Exception as exc:
                warnings.append(f"doi_query_failed:{payload.doi}:{exc}")
                return ApiResponse(
                    success=False,
                    items=[],
                    warnings=warnings,
                )

            return ApiResponse(
                success=bool(all_items),
                items=all_items,
                warnings=_dedupe_warnings(warnings),
                raw=data if payload.raw else None,
            )

        # Handle DOI list case
        if payload.doi_list:
            dois = _normalize_dois(payload.doi_list)
            for doi in dois:
                try:
                    search_query = f"DOI:{doi}"
                    params = {
                        "query": search_query,
                        "format": "json",
                        "pageSize": 1,
                    }
                    resp = self.session.get(self.EUROPEPMC_API_URL, params=params, timeout=30)
                    resp.raise_for_status()
                    data = resp.json()
                    results = data.get("resultList", {}).get("result", [])
                    if results:
                        all_items.extend(results)
                    time.sleep(payload.sleep_seconds)
                except Exception as exc:
                    warnings.append(f"doi_fetch_failed:{doi}:{exc}")

            return ApiResponse(
                success=bool(all_items),
                items=all_items,
                warnings=_dedupe_warnings(warnings),
                raw=data if payload.raw else None,
            )

        # Search query case
        if payload.search_params:
            sp = payload.search_params
            total_needed = sp.limit * sp.page
            page = 1
            all_items = []

            while len(all_items) < total_needed:
                try:
                    params = {
                        "query": query,
                        "format": "json",
                        "pageSize": min(self.PAGE_SIZE, total_needed - len(all_items)),
                        "offset": (page - 1) * self.PAGE_SIZE,
                    }
                    # Add any custom filters
                    if sp.filters:
                        for key, value in sp.filters.items():
                            params[key] = value

                    resp = self.session.get(self.EUROPEPMC_API_URL, params=params, timeout=30)
                    resp.raise_for_status()
                    data = resp.json()
                    results = data.get("resultList", {}).get("result", [])
                    warnings.extend(warnings)
                    all_items.extend(results)
                    if len(results) < self.PAGE_SIZE:
                        break
                    time.sleep(payload.sleep_seconds)
                    page += 1
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

        return ApiResponse(
            success=False,
            items=[],
            warnings=_dedupe_warnings(warnings),
        )

    def fetch_by_dois(self, dois: List[str], payload: EuropePmcPayload) -> ApiResponse:
        """Fetch multiple DOIs at once."""
        warnings = list(self._runtime_warnings)
        all_items: List[Dict[str, Any]] = []

        if not dois:
            return ApiResponse(
                success=False,
                items=[],
                warnings=warnings + ["no DOIs provided"],
            )

        for doi in dois:
            try:
                search_query = f"DOI:{doi}"
                params = {
                    "query": search_query,
                    "format": "json",
                    "pageSize": 1,
                }
                resp = self.session.get(self.EUROPEPMC_API_URL, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("resultList", {}).get("result", [])
                if results:
                    all_items.extend(results)
                time.sleep(payload.sleep_seconds)
            except Exception as exc:
                warnings.append(f"doi_fetch_failed:{doi}:{exc}")

        return ApiResponse(
            success=bool(all_items),
            items=all_items,
            warnings=_dedupe_warnings(warnings),
            raw=data if payload.raw else None,
        )

    def download(self, payload: EuropePmcPayload) -> DownloadResponse:
        """Download PDF for a DOI from Europe PMC."""
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

        # First search Europe PMC for the DOI
        try:
            search_query = f"DOI:{doi}"
            params = {
                "query": search_query,
                "format": "json",
                "pageSize": 1,
            }
            resp = self.session.get(self.EUROPEPMC_API_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("resultList", {}).get("result", [])

            if results:
                result = results[0]
                pmcid = result.get("pmcid")
                # Europe PMC provides full text access for open access articles
                if pmcid and result.get("hasFullText") == "Y":
                    # Get PDF link
                    pdf_url = f"{self.EUROPEPMC_REST_URL}/{pmcid}/fulltext/pdf"
                    doc_url = f"{self.EUROPEPMC_REST_URL}/{pmcid}/fulltext/text"
        except Exception as exc:
            warnings.append(f"download_lookup_failed:{exc}")

        # Fallback: try DOI landing page if no PDF found from Europe PMC
        if not pdf_url:
            try:
                landing = requests.get(
                    f"https://doi.org/{doi}",
                    timeout=60,
                    allow_redirects=True,
                    headers={
                        "Accept": "text/html,application/xhtml+xml",
                        "User-Agent": get_user_agent(),
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
                    + ["pdf_not_found"]
                ),
            )

        os.makedirs(payload.download_path, exist_ok=True)
        filename = _sanitize_filename(doi.replace("/", "_")) + ".pdf"
        file_path = os.path.join(payload.download_path, filename)

        try:
            response = self.session.get(pdf_url, timeout=60, allow_redirects=True)
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("content-type", "").lower()

            if not content.startswith(b"%PDF"):
                if "html" in content_type:
                    extra_links = _extract_pdf_links_from_html(
                        response.text if response.text else ""
                    )
                    for link in extra_links:
                        nested = self.session.get(
                            urljoin(pdf_url, link), timeout=60, allow_redirects=True
                        )
                        nested.raise_for_status()
                        if nested.content.startswith(b"%PDF"):
                            pdf_url = urljoin(pdf_url, link)
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
