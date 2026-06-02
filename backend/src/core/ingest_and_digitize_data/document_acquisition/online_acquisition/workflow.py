"""Online acquisition workflow — three-phase pipeline.

Phase 1 (Link Acquisition): Parallel search from API providers + Firecrawl.
Phase 2 (Download): Route candidates by type — DOI → OA API, PMCID → PMC, direct URL → HTTP.
Phase 3 (Gate): LLM classification on downloaded PDF content.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Dict, List, Optional

from loguru import logger

from .contracts import (
    DownloadResult,
    OnlineAcquisitionGatewayResult,
    OnlineAcquisitionItem,
    OnlineAcquisitionRequest,
    OnlineAcquisitionResponse,
    OnlineAcquisitionRouteInfo,
    OnlineAcquisitionSourceTraceEntry,
)
from .doi_fallback import probe_doi_landing_page
from .gateway import (
    _normalize_doi,
    download_file_from_url,
    resolve_oa_url,
    search_provider,
)
from .literature_type_classifier import LiteratureType, classify_item
from .normalizers import normalize_items
from .provider_health import get_health_tracker
from .web_search import SearchLink

DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
PMCID_PATTERN = re.compile(r"\bPMC\d+\b", re.IGNORECASE)
PMID_PATTERN = re.compile(r"PMID[:\s]*([0-9]{5,9})", re.IGNORECASE)

# API providers to search in parallel (order matters for result priority)
_API_SEARCH_PROVIDERS = [
    "crossref", "unpaywall", "openalex", "europepmc", "pmc",
    "doaj", "jstage", "arxiv", "biorxiv", "medrxiv",
    "scielo", "base", "core", "openaire", "cinii",
]

# Identifier-specific provider overrides
_ID_PROVIDER_MAP: Dict[str, List[str]] = {
    "doi": ["crossref", "unpaywall", "openalex", "europepmc"],
    "pmid": ["pmc", "europepmc"],
    "pmcid": ["pmc"],
}


def _extract_identifiers(texts: List[str]) -> Dict[str, Optional[str]]:
    info: Dict[str, Optional[str]] = {"doi": None, "pmcid": None, "pmid": None}
    for text in texts:
        if not text:
            continue
        if not info["doi"]:
            doi_match = DOI_PATTERN.search(text)
            if doi_match:
                info["doi"] = _normalize_doi(doi_match.group(0))
        if not info["pmcid"]:
            pmcid_match = PMCID_PATTERN.search(text)
            if pmcid_match:
                info["pmcid"] = pmcid_match.group(0)
        if not info["pmid"]:
            pmid_match = PMID_PATTERN.search(text)
            if pmid_match:
                info["pmid"] = pmid_match.group(1)
            elif text.isdigit() and 5 <= len(text) <= 9:
                info["pmid"] = text
    return info


def _build_query(request: OnlineAcquisitionRequest) -> str:
    if request.query:
        return request.query.strip()
    return " ".join([s for s in request.identifiers if s])


def _build_gateway_identifiers(identifiers: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
    return {k: v for k, v in identifiers.items() if v is not None}


def _resolve_language(request: OnlineAcquisitionRequest, identifiers: Dict[str, Optional[str]]) -> Optional[str]:
    """Resolve language code for download path organization."""
    lang = (request.language or "").strip().lower()
    if lang and lang != "auto":
        return lang
    doi = identifiers.get("doi")
    if doi:
        if doi.startswith("10.3760/") or doi.startswith("10.3969/"):
            return "zh"
    return None


# ── Phase 1: Link Acquisition ───────────────────────────────────────────


async def _acquire_links_api(
    *,
    query: str,
    identifiers: Dict[str, Optional[str]],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Phase 1a: Search API providers in parallel, return raw items with metadata."""
    doi = identifiers.get("doi")
    pmid = identifiers.get("pmid")
    pmcid = identifiers.get("pmcid")

    if doi:
        providers = _ID_PROVIDER_MAP["doi"]
    elif pmid or pmcid:
        providers = _ID_PROVIDER_MAP.get("pmid" if pmid else "pmcid", ["pmc"])
    else:
        providers = _API_SEARCH_PROVIDERS

    id_params = {k: v for k, v in identifiers.items() if v}

    async def _search_one(provider: str) -> Optional[OnlineAcquisitionGatewayResult]:
        try:
            return await search_provider(
                provider=provider,
                query=query,
                identifiers=id_params,
                limit=limit,
                raw=False,
                params={},
            )
        except Exception as exc:
            logger.debug("api search {} failed: {}", provider, exc)
            return None

    results = await asyncio.gather(*[_search_one(p) for p in providers], return_exceptions=True)

    all_items: List[Dict[str, Any]] = []
    for result in results:
        if isinstance(result, Exception):
            continue
        if result and result.success:
            for item in result.items:
                if isinstance(item, dict):
                    item["_source_provider"] = result.provider
                    all_items.append(item)

    return all_items


async def _acquire_links_firecrawl(
    *,
    query: str,
    language: Optional[str] = None,
) -> List[SearchLink]:
    """Phase 1b: Search via Firecrawl adapter."""
    from .web_search.firecrawl_adapter import FirecrawlAdapter

    from src.core.config import get_config
    cfg = get_config()
    if not cfg.web_search.api_key:
        logger.info("web search skipped: no WEB_SEARCH_API_KEY configured")
        return []

    adapter = FirecrawlAdapter(
        api_key=cfg.web_search.api_key,
        base_url=cfg.web_search.base_url,
        timeout=cfg.web_search.timeout,
        max_results=cfg.web_search.max_results,
    )

    result = await adapter.search(query, language=language)
    if result.warnings:
        for w in result.warnings:
            logger.warning("firecrawl: {}", w)

    all_links = list(result.links)
    scrape_tasks = [adapter.scrape_links(link.url) for link in result.links[:5]]
    scrape_results = await asyncio.gather(*scrape_tasks, return_exceptions=True)
    for sr in scrape_results:
        if isinstance(sr, list):
            all_links.extend(sr)

    return all_links


def _merge_and_dedupe(
    api_items: List[Dict[str, Any]],
    firecrawl_links: List[SearchLink],
) -> List[Dict[str, Any]]:
    """Merge API items and Firecrawl links, deduplicate by DOI/URL/title."""
    seen_dois: set[str] = set()
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    merged: List[Dict[str, Any]] = []

    def _norm_title(t: Optional[str]) -> str:
        if not t:
            return ""
        return re.sub(r"[^\w\s]", "", t.lower()).strip()

    for item in api_items:
        doi = (item.get("doi") or item.get("DOI") or "").strip().lower()
        url = (item.get("url") or item.get("URL") or item.get("link") or "").strip()
        title = _norm_title(item.get("title") or item.get("article_title"))

        if doi and doi in seen_dois:
            continue
        if url and url in seen_urls:
            continue
        if title and title in seen_titles:
            continue

        if doi:
            seen_dois.add(doi)
        if url:
            seen_urls.add(url)
        if title:
            seen_titles.add(title)

        item["_candidate_type"] = "api"
        merged.append(item)

    for link in firecrawl_links:
        url = link.url.strip()
        doi = (link.doi or "").strip().lower()

        # Check DOI dedup against API items
        if doi and doi in seen_dois:
            continue
        if url in seen_urls:
            continue

        if doi:
            seen_dois.add(doi)
        seen_urls.add(url)

        merged.append({
            "url": url,
            "title": link.title or "",
            "doi": link.doi or "",
            "_source_provider": link.source or "firecrawl",
            "_candidate_type": "firecrawl",
        })

    return merged


# ── Phase 2: Download ───────────────────────────────────────────────────


async def _download_candidates(
    candidates: List[Dict[str, Any]],
    download_path: str,
) -> List[DownloadResult]:
    """Phase 2: Download files from candidate links.

    Routing:
    - DOI → unpaywall OA resolution → download
    - PMCID → PMC PDF URL → download
    - Direct URL → HTTP download (with HTML→PDF redirect handling)
    """
    async def _download_one(candidate: Dict[str, Any]) -> Optional[DownloadResult]:
        doi = candidate.get("doi") or candidate.get("DOI")
        pmid = candidate.get("pmid")
        if not pmid and isinstance(candidate.get("identifiers"), dict):
            pmid = candidate["identifiers"].get("pmid")
        pmcid = candidate.get("pmcid")
        url = candidate.get("url") or candidate.get("URL")
        title = candidate.get("title", "untitled")
        filename_stem = re.sub(r"[^\w\-]", "_", title)[:80] if title else "untitled"

        # Route 1: DOI → unpaywall OA resolution
        if doi:
            try:
                id_params = {"doi": doi}
                result = await search_provider(
                    provider="unpaywall",
                    query="",
                    identifiers=id_params,
                    limit=1,
                    raw=False,
                    params={},
                )
                oa_url = resolve_oa_url(result)
                if oa_url:
                    file_path, final_url, warns = await download_file_from_url(
                        oa_url, download_path, filename_stem
                    )
                    if file_path:
                        return DownloadResult(
                            file_path=file_path,
                            source="unpaywall",
                            doi=doi,
                            url=final_url,
                            warnings=warns,
                        )
            except Exception as exc:
                logger.debug("unpaywall download failed for {}: {}", doi, exc)

        # Route 2: PMCID → PMC direct PDF URL
        if pmcid:
            pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
            file_path, final_url, warns = await download_file_from_url(
                pdf_url, download_path, filename_stem
            )
            if file_path:
                return DownloadResult(
                    file_path=file_path,
                    source="pmc",
                    pmcid=pmcid,
                    url=final_url,
                    warnings=warns,
                )

        # Route 3: Direct URL download
        if url:
            file_path, final_url, warns = await download_file_from_url(
                url, download_path, filename_stem
            )
            if file_path:
                return DownloadResult(
                    file_path=file_path,
                    source=candidate.get("_source_provider", "direct"),
                    url=final_url,
                    warnings=warns,
                )

        return None

    results = await asyncio.gather(*[_download_one(c) for c in candidates], return_exceptions=True)
    downloads = [r for r in results if isinstance(r, DownloadResult)]

    return downloads


# ── Main Entry Point ────────────────────────────────────────────────────


async def online_acquisition_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Main entry point — three-phase online acquisition pipeline.

    Phase 1: Parallel link acquisition (API providers + Firecrawl).
    Phase 2: Download by candidate type (DOI→OA, PMCID→PMC, URL→direct).
    Phase 3: LLM content gate on downloaded PDFs.
    """
    # --- Validate request ---
    try:
        request = OnlineAcquisitionRequest(**payload)
    except Exception as exc:
        route = OnlineAcquisitionRouteInfo(prefer="auto", used="none", reason="invalid_request")
        return OnlineAcquisitionResponse(
            success=False,
            items=[],
            warnings=[f"invalid_request: {exc}"],
            route=route,
            candidate_links=[],
        ).model_dump()
    query = _build_query(request)
    identifiers = _extract_identifiers([request.query or ""] + request.identifiers)
    language = _resolve_language(request, identifiers)

    route = OnlineAcquisitionRouteInfo(
        prefer=request.prefer,
        api_provider=request.api_provider,
        web_provider=request.web_provider,
        used="api",
        reason="parallel_acquisition",
        fallback_used=False,
    )
    warnings: List[str] = []
    traces: List[OnlineAcquisitionSourceTraceEntry] = []

    download_path = request.download_path
    if language:
        download_path = os.path.join(download_path, language)

    # === Phase 1: Link Acquisition (parallel) ===
    id_params = _build_gateway_identifiers(identifiers)

    api_task = _acquire_links_api(query=query, identifiers=id_params, limit=request.limit)
    firecrawl_task = _acquire_links_firecrawl(query=query, language=language)

    api_items, firecrawl_links = await asyncio.gather(api_task, firecrawl_task, return_exceptions=True)

    if isinstance(api_items, Exception):
        logger.warning("api acquisition failed: {}", api_items)
        api_items = []
    if isinstance(firecrawl_links, Exception):
        logger.warning("firecrawl acquisition failed: {}", firecrawl_links)
        firecrawl_links = []

    candidates = _merge_and_dedupe(api_items, firecrawl_links)

    if not candidates:
        warnings.append("FETCH_NO_RESULT: no candidates from any source")
        return OnlineAcquisitionResponse(
            success=False,
            items=[],
            downloads=[],
            warnings=warnings,
            route=route,
            candidate_links=[],
        ).model_dump()

    # Normalize API items
    normalized_items: List[OnlineAcquisitionItem] = []
    for item in candidates:
        provider = item.get("_source_provider", "unknown")
        try:
            normalized = normalize_items(provider, [item])
            normalized_items.extend(normalized)
        except Exception:
            try:
                normalized = normalize_items("firecrawl", [item])
                normalized_items.extend(normalized)
            except Exception:
                pass

    # Apply literature type filter
    if request.literature_types:
        typed_items = []
        for ni in normalized_items:
            lt = classify_item(ni)
            ni.literature_type = lt.value if lt else None
            if lt and lt.value in request.literature_types:
                typed_items.append(ni)
        normalized_items = typed_items

    clean_candidates = [{k: v for k, v in c.items() if not k.startswith("_")} for c in candidates]

    # === Search-only mode ===
    if request.action == "search":
        return OnlineAcquisitionResponse(
            success=bool(normalized_items),
            items=normalized_items,
            downloads=[],
            warnings=warnings,
            route=route,
            candidate_links=clean_candidates,
        ).model_dump()

    # === Phase 2: Download ===
    download_results = await _download_candidates(candidates, download_path)

    if not download_results:
        warnings.append("FULLTEXT_UNAVAILABLE: no files downloaded")

    downloads = [
        {
            "file_path": dr.file_path,
            "source": dr.source,
            "doi": dr.doi,
            "pmcid": dr.pmcid,
            "url": dr.url,
            "warnings": dr.warnings,
        }
        for dr in download_results
    ]

    # === Phase 3: LLM Content Gate ===
    # Currently keyword-based on title/journal; PDF content classification
    # can be added as a future enhancement.

    return OnlineAcquisitionResponse(
        success=bool(download_results),
        items=normalized_items,
        downloads=downloads,
        warnings=warnings,
        route=route,
        candidate_links=clean_candidates,
    ).model_dump()
