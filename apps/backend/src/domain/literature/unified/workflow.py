from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from src.domain.literature.gateway.api_gateway import (
    ApiGatewayRequest,
    ApiGatewayResult,
    call_api_gateway,
)
from src.domain.literature.gateway.web_gateway import (
    WebGatewayRequest,
    WebGatewayResult,
    call_auto_web_gateway,
)
from src.domain.literature.unified.models import (
    ApiProvider,
    UnifiedLiteratureRequest,
    UnifiedLiteratureResponse,
    UnifiedRouteInfo,
    WebProvider,
)
from src.domain.literature.unified.normalizers import normalize_items

DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
PMCID_PATTERN = re.compile(r"\bPMC\d+\b", re.IGNORECASE)
PMID_PATTERN = re.compile(r"PMID[:\s]*([0-9]{5,9})", re.IGNORECASE)
ISSN_PATTERN = re.compile(r"\b\d{4}-\d{3}[\dX]\b", re.IGNORECASE)


class IdentifierInfo(Dict[str, Optional[str]]):
    pass


def _detect_language(text: str) -> str:
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[\u0400-\u04FF]", text):
        return "ru"
    return "en"


def _extract_url(text: str) -> Optional[str]:
    candidate = text.strip()
    if not candidate:
        return None
    if candidate.startswith("http://") or candidate.startswith("https://"):
        return candidate
    if re.match(r"^[\w.-]+\.[a-z]{2,}(/.*)?$", candidate, re.IGNORECASE):
        return f"https://{candidate}"
    return None


def _extract_identifiers(texts: List[str]) -> IdentifierInfo:
    info: IdentifierInfo = {
        "doi": None,
        "pmcid": None,
        "pmid": None,
        "issn": None,
        "url": None,
        "domain": None,
    }
    for text in texts:
        if not text:
            continue
        if not info["doi"]:
            doi_match = DOI_PATTERN.search(text)
            if doi_match:
                info["doi"] = doi_match.group(0)
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
        if not info["issn"]:
            issn_match = ISSN_PATTERN.search(text)
            if issn_match:
                info["issn"] = issn_match.group(0)
        if not info["url"]:
            url = _extract_url(text)
            if url:
                info["url"] = url
                parsed = urlparse(url)
                info["domain"] = parsed.netloc.lower() if parsed.netloc else None
    return info


def _select_api_provider(
    request: UnifiedLiteratureRequest, identifiers: IdentifierInfo, language: str
) -> ApiProvider:
    if request.api_provider:
        return request.api_provider
    if request.action == "download":
        if identifiers.get("doi"):
            return "unpaywall"
        if identifiers.get("pmcid") or identifiers.get("pmid"):
            return "pmc"
        return "pmc"
    if identifiers.get("doi"):
        return "unpaywall"
    if identifiers.get("pmcid") or identifiers.get("pmid"):
        return "pmc"
    if language == "ja":
        return "jstage"
    if identifiers.get("issn"):
        return "crossref"
    return "crossref"


def _select_web_provider(
    request: UnifiedLiteratureRequest, identifiers: IdentifierInfo, language: str
) -> Optional[WebProvider]:
    if request.web_provider:
        return request.web_provider
    domain = identifiers.get("domain") or ""
    if "cyberleninka.ru" in domain:
        return "cyberleninka"
    if "pubscholar.cn" in domain:
        return "pubscholar"
    if "hanspub.org" in domain:
        return "hans_publishers"
    if language == "zh":
        return "pubscholar"
    if language == "ru":
        return "cyberleninka"
    return None


def _build_query(request: UnifiedLiteratureRequest) -> str:
    if request.query:
        return request.query.strip()
    return " ".join([s for s in request.identifiers if s])


def _api_response_to_raw(result: ApiGatewayResult) -> Dict[str, Any]:
    return {
        "success": result.success,
        "items": result.items,
        "downloads": result.downloads,
        "warnings": result.warnings,
        "raw": result.raw,
        "meta": result.meta,
    }


def _web_response_to_raw(result: WebGatewayResult) -> Dict[str, Any]:
    return result.raw or {
        "success": result.success,
        "items": result.items,
        "downloads": result.downloads,
        "warnings": result.warnings,
    }


async def _execute_api(
    provider: ApiProvider,
    request: UnifiedLiteratureRequest,
    identifiers: IdentifierInfo,
    query: str,
) -> ApiGatewayResult:
    gateway_request = ApiGatewayRequest(
        provider=provider,
        action=request.action,
        query=query,
        identifiers=identifiers,
        limit=request.limit,
        raw=request.raw,
        params=request.api_params,
        download_path=request.download_path,
        selected_index=request.selected_index,
        selected_title=request.selected_title,
        detail_link=request.detail_link,
    )
    return await call_api_gateway(gateway_request)


async def _execute_web(
    provider: WebProvider,
    request: UnifiedLiteratureRequest,
    query: str,
) -> WebGatewayResult:
    gateway_request = WebGatewayRequest(
        provider=provider,
        action=request.action,
        query=query,
        limit=request.limit,
        params=request.web_params,
        download_path=request.download_path,
        selected_index=request.selected_index,
        selected_title=request.selected_title,
        detail_link=request.detail_link,
    )
    return await call_auto_web_gateway(gateway_request)


def _build_api_response(
    request: UnifiedLiteratureRequest,
    route: UnifiedRouteInfo,
    warnings: List[str],
    raw_payload: Dict[str, Any],
    api_result: ApiGatewayResult,
    api_items: List[Dict[str, Any]],
) -> UnifiedLiteratureResponse:
    if request.action == "download":
        return UnifiedLiteratureResponse(
            success=api_result.success,
            items=[],
            downloads=api_result.downloads,
            warnings=warnings,
            route=route,
            raw=raw_payload if raw_payload else None,
        )
    return UnifiedLiteratureResponse(
        success=api_result.success,
        items=api_items,
        warnings=warnings,
        route=route,
        raw=raw_payload if raw_payload else None,
    )


def _build_web_response(
    request: UnifiedLiteratureRequest,
    route: UnifiedRouteInfo,
    warnings: List[str],
    raw_payload: Dict[str, Any],
    web_result: WebGatewayResult,
    web_items: List[Dict[str, Any]],
) -> UnifiedLiteratureResponse:
    if request.action == "download":
        return UnifiedLiteratureResponse(
            success=web_result.success,
            items=[],
            downloads=web_result.downloads,
            warnings=warnings,
            route=route,
            raw=raw_payload if raw_payload else None,
        )
    return UnifiedLiteratureResponse(
        success=web_result.success,
        items=web_items,
        warnings=warnings,
        route=route,
        raw=raw_payload if raw_payload else None,
    )


async def literature_unified_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Unified literature metadata workflow (API-first with optional web fallback)."""
    try:
        request = UnifiedLiteratureRequest.model_validate(payload)
    except Exception as exc:
        route = UnifiedRouteInfo(prefer="auto", used="none", reason="invalid_request")
        response = UnifiedLiteratureResponse(
            success=False,
            items=[],
            warnings=[f"invalid_request: {exc}"],
            route=route,
        )
        return response.model_dump()

    query = _build_query(request)
    identifiers = _extract_identifiers([request.query or ""] + request.identifiers)
    language = request.language
    if not language or language == "auto":
        language = _detect_language(query)

    api_provider = _select_api_provider(request, identifiers, language)
    web_provider = _select_web_provider(request, identifiers, language)

    route = UnifiedRouteInfo(
        prefer=request.prefer,
        api_provider=api_provider,
        web_provider=web_provider,
        used="none",
        reason=None,
        fallback_used=False,
    )
    warnings: List[str] = []
    raw_payload: Dict[str, Any] = {}

    if request.prefer == "web":
        if not web_provider:
            warnings.append("web_provider_unavailable")
            route.used = "none"
            route.reason = "no_web_provider"
            response = UnifiedLiteratureResponse(
                success=False,
                items=[],
                warnings=warnings,
                route=route,
                raw=None,
            )
            return response.model_dump()

        web_result = await _execute_web(web_provider, request, query)
        route.used = "web"
        route.reason = f"web_provider:{web_provider}"
        warnings.extend(web_result.warnings)
        if request.raw:
            raw_payload["web"] = _web_response_to_raw(web_result)
        web_items = (
            normalize_items(web_result.provider, web_result.items)
            if request.action == "search"
            else []
        )
        response = _build_web_response(
            request, route, warnings, raw_payload, web_result, web_items
        )
        return response.model_dump()

    api_result = await _execute_api(api_provider, request, identifiers, query)
    api_items = (
        normalize_items(api_result.provider, api_result.items)
        if request.action == "search"
        else []
    )
    warnings.extend(api_result.warnings)
    if request.raw:
        raw_payload["api"] = _api_response_to_raw(api_result)

    if (
        request.action == "search"
        and api_provider == "unpaywall"
        and (not api_result.success or not api_items)
    ):
        fallback_crossref = await call_api_gateway(
            ApiGatewayRequest(
                provider="crossref",
                action="search",
                query=query,
                identifiers=identifiers,
                limit=request.limit,
                raw=request.raw,
                params=request.api_params,
            )
        )
        fallback_items = normalize_items("crossref", fallback_crossref.items)
        if fallback_items:
            api_result = fallback_crossref
            api_items = fallback_items
            warnings.extend(fallback_crossref.warnings)
            if request.raw:
                raw_payload["api_fallback"] = _api_response_to_raw(fallback_crossref)
            route.api_provider = "crossref"

    api_has_result = (
        bool(api_result.downloads) if request.action == "download" else bool(api_items)
    )
    if request.prefer == "api" or api_has_result:
        route.used = "api"
        route.reason = f"api_provider:{route.api_provider}"
        response = _build_api_response(
            request, route, warnings, raw_payload, api_result, api_items
        )
        return response.model_dump()

    if request.prefer == "auto" and web_provider:
        web_result = await _execute_web(web_provider, request, query)
        route.used = "web"
        route.reason = f"fallback_web:{web_provider}"
        route.fallback_used = True
        warnings.extend(web_result.warnings)
        if request.raw:
            raw_payload["web"] = _web_response_to_raw(web_result)
        web_items = (
            normalize_items(web_result.provider, web_result.items)
            if request.action == "search"
            else []
        )
        response = _build_web_response(
            request, route, warnings, raw_payload, web_result, web_items
        )
        return response.model_dump()

    route.used = "api"
    route.reason = (
        "api_download_failed" if request.action == "download" else "api_no_items"
    )
    response = _build_api_response(
        request,
        route,
        warnings
        or (["download_failed"] if request.action == "download" else ["no_results"]),
        raw_payload,
        api_result,
        api_items,
    )
    return response.model_dump()
