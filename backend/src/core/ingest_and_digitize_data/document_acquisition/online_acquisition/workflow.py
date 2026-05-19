"""Top-level literature workflow — orchestrates providers with fallback chains."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from .contracts import (
    OnlineAcquisitionGatewayResult,
    OnlineAcquisitionItem,
    OnlineAcquisitionRequest,
    OnlineAcquisitionResponse,
    OnlineAcquisitionRouteInfo,
    OnlineAcquisitionSourceTraceEntry,
)
from .doi_fallback import doi_fallback_download, probe_doi_landing_page
from .gateway import _normalize_doi, download_from_provider, search_provider
from .literature_type_classifier import LiteratureType, classify_item, filter_by_type
from .normalizers import normalize_items
from .web_providers import call_web_provider

DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
PMCID_PATTERN = re.compile(r"\bPMC\d+\b", re.IGNORECASE)
PMID_PATTERN = re.compile(r"PMID[:\s]*([0-9]{5,9})", re.IGNORECASE)

API_PROVIDER_CHAIN: Dict[str, List[str]] = {
    "doi": ["crossref", "unpaywall", "openalex", "europepmc"],
    "pmid": ["pmc"],
    "pmcid": ["pmc"],
    "default": ["crossref", "unpaywall", "openalex", "europepmc"],
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


def _select_initial_provider(
    request: OnlineAcquisitionRequest,
    identifiers: Dict[str, Optional[str]],
) -> str:
    if request.api_provider:
        return request.api_provider
    if identifiers.get("pmcid") or identifiers.get("pmid"):
        return "pmc"
    if identifiers.get("doi"):
        return "crossref" if request.action == "search" else "unpaywall"
    return "crossref"


def _build_provider_chain(identifiers: Dict[str, Optional[str]]) -> List[str]:
    if identifiers.get("doi"):
        return list(API_PROVIDER_CHAIN["doi"])
    if identifiers.get("pmcid") or identifiers.get("pmid"):
        return list(API_PROVIDER_CHAIN["pmid"])
    return list(API_PROVIDER_CHAIN["default"])


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
    # Auto-detect from DOI domain
    doi = identifiers.get("doi")
    if doi:
        # Chinese journal DOIs
        if doi.startswith("10.3760/") or doi.startswith("10.3969/"):
            return "zh"
    return None


def _aggregate_traces(results: List[OnlineAcquisitionGatewayResult]) -> List[OnlineAcquisitionSourceTraceEntry]:
    """Collect source_trace from multiple provider results."""
    traces: List[OnlineAcquisitionSourceTraceEntry] = []
    for result in results:
        traces.extend(result.source_trace)
    return traces


async def _try_doi_fallback(
    identifiers: Dict[str, Optional[str]],
    request: OnlineAcquisitionRequest,
    warnings: List[str],
) -> Optional[Dict[str, Any]]:
    doi = identifiers.get("doi")
    if not doi or request.action != "download":
        return None
    fallback = await doi_fallback_download(
        doi,
        download_path=request.download_path,
        email=os.getenv("UNPAYWALL_EMAIL"),
    )
    warnings.extend(fallback.get("warnings") or [])
    if fallback.get("success"):
        return fallback
    return None


def _apply_literature_type_filter(
    items: List[OnlineAcquisitionItem],
    literature_types: List[str],
) -> List[OnlineAcquisitionItem]:
    """Tag items with literature_type and filter if types specified."""
    if not literature_types:
        for item in items:
            item.literature_type = classify_item(item)
        return items

    type_set = {LiteratureType(t) for t in literature_types}
    filtered: List[OnlineAcquisitionItem] = []
    for item in items:
        lt = classify_item(item)
        item.literature_type = lt
        if lt in type_set:
            filtered.append(item)
    return filtered


async def _handle_search(
    request: OnlineAcquisitionRequest,
    identifiers: Dict[str, Optional[str]],
    query: str,
    route: OnlineAcquisitionRouteInfo,
    warnings: List[str],
) -> Dict[str, Any]:
    """Handle search action with provider chain fallback."""
    all_results: List[OnlineAcquisitionGatewayResult] = []

    if request.api_provider:
        route.api_provider = request.api_provider
        result = await search_provider(
            provider=request.api_provider,
            query=query,
            identifiers=_build_gateway_identifiers(identifiers),
            limit=request.limit,
            raw=request.raw,
            params=request.api_params,
        )
        all_results.append(result)
        items = normalize_items(result.provider, result.items) if result.success else []
        items = _apply_literature_type_filter(items, request.literature_types)
        warnings.extend(result.warnings)
        route.used = "api"
        route.reason = f"api_provider:{request.api_provider}"
        return OnlineAcquisitionResponse(
            success=bool(items),
            items=items,
            warnings=warnings,
            route=route,
            raw={"source_trace": [t.__dict__ for t in _aggregate_traces(all_results)]} if request.raw else None,
        ).model_dump()

    provider_chain = _build_provider_chain(identifiers)
    initial = _select_initial_provider(request, identifiers)
    if initial not in provider_chain:
        provider_chain = [initial] + provider_chain

    route.api_provider = initial
    for provider in provider_chain:
        result = await search_provider(
            provider=provider,
            query=query,
            identifiers=_build_gateway_identifiers(identifiers),
            limit=request.limit,
            raw=request.raw,
            params=request.api_params,
        )
        all_results.append(result)
        items = normalize_items(result.provider, result.items) if result.success else []
        items = _apply_literature_type_filter(items, request.literature_types)
        warnings.extend(result.warnings)
        if items:
            route.used = "api"
            route.reason = f"api_provider:{provider}"
            return OnlineAcquisitionResponse(
                success=True,
                items=items,
                warnings=warnings,
                route=route,
                raw={"source_trace": [t.__dict__ for t in _aggregate_traces(all_results)]} if request.raw else None,
            ).model_dump()

    # DOI fallback for search — when API providers fail, try DOI landing page
    doi = identifiers.get("doi")
    if doi:
        fallback = await probe_doi_landing_page(doi, email=os.getenv("UNPAYWALL_EMAIL"))
        warnings.extend(fallback.get("warnings") or [])
        if fallback.get("success") and fallback.get("resolved_url"):
            route.fallback_used = True
            route.reason = "doi_fallback:landing_probe"
            item = OnlineAcquisitionItem(
                source="doi_fallback",
                title=None,
                authors=[],
                journal=None,
                year=None,
                doi=doi,
                url=fallback["resolved_url"],
                links=[fallback["resolved_url"]],
            )
            return OnlineAcquisitionResponse(
                success=True,
                items=[item],
                warnings=warnings,
                route=route,
                raw={"source_trace": [t.__dict__ for t in _aggregate_traces(all_results)]} if request.raw else None,
            ).model_dump()

    route.reason = "api_no_items"
    warnings.append("FETCH_NO_RESULT")
    return OnlineAcquisitionResponse(
        success=False,
        items=[],
        warnings=warnings,
        route=route,
        raw={"source_trace": [t.__dict__ for t in _aggregate_traces(all_results)]} if request.raw else None,
    ).model_dump()


async def _handle_download(
    request: OnlineAcquisitionRequest,
    identifiers: Dict[str, Optional[str]],
    query: str,
    route: OnlineAcquisitionRouteInfo,
    warnings: List[str],
) -> Dict[str, Any]:
    """Handle download action with provider chain fallback + DOI fallback + web fallback."""
    all_results: List[OnlineAcquisitionGatewayResult] = []

    if request.api_provider:
        route.api_provider = request.api_provider
        result = await download_from_provider(
            provider=request.api_provider,
            query=query,
            identifiers=_build_gateway_identifiers(identifiers),
            limit=request.limit,
            raw=request.raw,
            download_path=request.download_path,
            selected_index=request.selected_index,
            selected_title=request.selected_title,
            detail_link=request.detail_link,
            params=request.api_params,
        )
        all_results.append(result)
        warnings.extend(result.warnings)
        if result.success and result.downloads:
            route.used = "api"
            route.reason = f"api_provider:{request.api_provider}"
            return OnlineAcquisitionResponse(
                success=True,
                downloads=result.downloads,
                warnings=warnings,
                route=route,
                raw={"source_trace": [t.__dict__ for t in _aggregate_traces(all_results)]} if request.raw else None,
            ).model_dump()

    provider_chain = _build_provider_chain(identifiers)
    initial = _select_initial_provider(request, identifiers)
    if initial not in provider_chain:
        provider_chain = [initial] + provider_chain

    route.api_provider = initial
    for provider in provider_chain:
        result = await download_from_provider(
            provider=provider,
            query=query,
            identifiers=_build_gateway_identifiers(identifiers),
            limit=request.limit,
            raw=request.raw,
            download_path=request.download_path,
            selected_index=request.selected_index,
            selected_title=request.selected_title,
            detail_link=request.detail_link,
            params=request.api_params,
        )
        all_results.append(result)
        warnings.extend(result.warnings)
        if result.success and result.downloads:
            route.used = "api"
            route.reason = f"api_provider:{provider}"
            return OnlineAcquisitionResponse(
                success=True,
                downloads=result.downloads,
                warnings=warnings,
                route=route,
                raw={"source_trace": [t.__dict__ for t in _aggregate_traces(all_results)]} if request.raw else None,
            ).model_dump()

    # DOI fallback
    doi_result = await _try_doi_fallback(identifiers, request, warnings)
    if doi_result:
        route.fallback_used = True
        route.reason = "doi_fallback:landing_probe"
        download_entry: Dict[str, Any] = {}
        if doi_result.get("pdf_url"):
            download_entry["pdf_url"] = doi_result["pdf_url"]
        if doi_result.get("file_path"):
            download_entry["file_path"] = doi_result["file_path"]
        if doi_result.get("resolved_url"):
            download_entry["resolved_url"] = doi_result["resolved_url"]
        return OnlineAcquisitionResponse(
            success=True,
            downloads=[download_entry] if download_entry else [],
            warnings=warnings,
            route=route,
            raw={"source_trace": [t.__dict__ for t in _aggregate_traces(all_results)]} if request.raw else None,
        ).model_dump()

    # Web fallback
    if request.prefer in ("auto", "web"):
        web_provider = request.web_provider or "pubscholar"
        web_result = await call_web_provider(
            provider=web_provider,
            action="download",
            query=query,
            limit=request.limit,
            download_path=request.download_path,
            selected_index=request.selected_index,
            selected_title=request.selected_title,
            detail_link=request.detail_link,
            params=request.web_params,
        )
        all_results.append(web_result)
        warnings.extend(web_result.warnings)
        if web_result.success and web_result.downloads:
            route.used = "web"
            route.web_provider = web_provider
            route.reason = f"web_provider:{web_provider}"
            route.fallback_used = True
            return OnlineAcquisitionResponse(
                success=True,
                downloads=web_result.downloads,
                warnings=warnings,
                route=route,
                raw={"source_trace": [t.__dict__ for t in _aggregate_traces(all_results)]} if request.raw else None,
            ).model_dump()

    route.reason = "api_download_failed"
    warnings.append("FULLTEXT_UNAVAILABLE")
    return OnlineAcquisitionResponse(
        success=False,
        downloads=[],
        warnings=warnings,
        route=route,
        raw={"source_trace": [t.__dict__ for t in _aggregate_traces(all_results)]} if request.raw else None,
    ).model_dump()


async def online_acquisition_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Unified literature workflow — search or download with fallback chains."""
    try:
        request = OnlineAcquisitionRequest.model_validate(payload)
    except Exception as exc:
        route = OnlineAcquisitionRouteInfo(prefer="auto", used="none", reason="invalid_request")
        response = OnlineAcquisitionResponse(
            success=False,
            items=[],
            warnings=[f"invalid_request: {exc}"],
            route=route,
        )
        return response.model_dump()

    if request.prefer == "web" and not request.web_provider:
        return OnlineAcquisitionResponse(
            success=False,
            items=[],
            warnings=["prefer=web requires web_provider to be specified"],
            route=OnlineAcquisitionRouteInfo(prefer="web", used="none", reason="missing_web_provider"),
        ).model_dump()

    query = _build_query(request)
    identifiers = _extract_identifiers([request.query or ""] + request.identifiers)

    # Resolve language-specific download path
    lang = _resolve_language(request, identifiers)
    if lang and request.action == "download":
        request.download_path = f"{request.download_path.rstrip('/')}/{lang}"

    route = OnlineAcquisitionRouteInfo(
        prefer=request.prefer,
        used="none",
        reason=None,
        fallback_used=False,
    )
    warnings: List[str] = []

    if request.action == "search":
        return await _handle_search(request, identifiers, query, route, warnings)
    return await _handle_download(request, identifiers, query, route, warnings)
