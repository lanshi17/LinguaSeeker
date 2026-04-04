from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

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
    UnifiedLiteratureItem,
    UnifiedLiteratureRequest,
    UnifiedLiteratureResponse,
    UnifiedRouteInfo,
    WebProvider,
)
from src.domain.literature.unified.normalizers import normalize_items

DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
PMCID_PATTERN = re.compile(r"\bPMC\d+\b", re.IGNORECASE)
PMID_PATTERN = re.compile(r"PMID[:\s]*([0-9]{5,9})", re.IGNORECASE)


class IdentifierInfo(Dict[str, Optional[str]]):
    pass


DEFAULT_PROVIDER_RETRIES = {
    "search": 2,
    "download": 2,
}


def _extract_identifiers(texts: List[str]) -> IdentifierInfo:
    info: IdentifierInfo = IdentifierInfo(
        doi=None,
        pmcid=None,
        pmid=None,
    )

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
    return info


def _select_api_provider(
    request: UnifiedLiteratureRequest, identifiers: IdentifierInfo
) -> ApiProvider:
    if request.api_provider:
        return request.api_provider

    if identifiers.get("pmcid") or identifiers.get("pmid"):
        return "pmc"

    if identifiers.get("doi"):
        if request.action == "download":
            return "unpaywall"
        return "crossref"

    if request.prefer == "api":
        return "crossref"

    return "pmc"


def _infer_web_provider(query: str) -> WebProvider | None:
    lowered = str(query or "").strip().lower()
    if "cyberleninka.ru" in lowered:
        return "cyberleninka"
    if "hanspub.org" in lowered:
        return "hans_publishers"
    if "pubscholar.cn" in lowered:
        return "pubscholar"
    return None


def _select_web_provider(
    request: UnifiedLiteratureRequest, query: str
) -> WebProvider:
    if request.web_provider:
        return request.web_provider

    inferred = _infer_web_provider(query)
    if inferred is not None:
        return inferred

    return "pubscholar"


def _should_use_web(request: UnifiedLiteratureRequest, query: str) -> bool:
    if request.web_provider is not None:
        return True
    if request.api_provider is not None:
        return False
    if request.prefer == "web":
        return True
    return request.prefer == "auto" and _infer_web_provider(query) is not None


def _build_query(request: UnifiedLiteratureRequest) -> str:
    if request.query:
        return request.query.strip()
    return " ".join([s for s in request.identifiers if s])


def _api_response_to_raw(result: ApiGatewayResult) -> Dict[str, Any]:
    meta = dict(result.meta or {})
    return {
        "success": result.success,
        "items": result.items,
        "downloads": result.downloads,
        "warnings": result.warnings,
        "raw": result.raw,
        "meta": meta,
        "source_trace": meta.get("source_trace", []),
        "attempts": meta.get("attempts"),
    }


def _web_response_to_raw(result: WebGatewayResult, source_trace: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "success": result.success,
        "items": result.items,
        "downloads": result.downloads,
        "warnings": result.warnings,
        "raw": result.raw,
        "source_trace": source_trace,
        "attempts": len(source_trace),
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

    attempts = DEFAULT_PROVIDER_RETRIES[request.action]
    source_trace: List[Dict[str, Any]] = []
    last_exception: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            result = await call_api_gateway(gateway_request)
        except Exception as exc:
            last_exception = exc
            source_trace.append(
                {
                    "provider": provider,
                    "attempt": attempt,
                    "success": False,
                    "items_count": 0,
                    "downloads_count": 0,
                    "warnings": [],
                    "error": str(exc),
                }
            )
            if attempt == attempts:
                raise
            continue

        source_trace.append(
            {
                "provider": provider,
                "attempt": attempt,
                "success": result.success,
                "items_count": len(result.items),
                "downloads_count": len(result.downloads),
                "warnings": result.warnings,
                "error": None,
            }
        )
        result.meta = dict(result.meta or {})
        result.meta["source_trace"] = source_trace
        result.meta["attempts"] = attempt

        has_result = (
            bool(result.downloads)
            if request.action == "download"
            else bool(result.items)
        )
        if result.success and has_result:
            return result
        if attempt == attempts:
            return result

    if last_exception is not None:
        raise last_exception
    raise RuntimeError("provider execution failed without result")


async def _execute_web(
    provider: WebProvider,
    request: UnifiedLiteratureRequest,
    query: str,
) -> tuple[WebGatewayResult, List[Dict[str, Any]]]:
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

    attempts = DEFAULT_PROVIDER_RETRIES[request.action]
    source_trace: List[Dict[str, Any]] = []
    last_exception: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            result = await call_auto_web_gateway(gateway_request)
        except Exception as exc:
            last_exception = exc
            source_trace.append(
                {
                    "provider": provider,
                    "attempt": attempt,
                    "success": False,
                    "items_count": 0,
                    "downloads_count": 0,
                    "warnings": [],
                    "error": str(exc),
                }
            )
            if attempt == attempts:
                raise
            continue

        source_trace.append(
            {
                "provider": provider,
                "attempt": attempt,
                "success": result.success,
                "items_count": len(result.items),
                "downloads_count": len(result.downloads),
                "warnings": result.warnings,
                "error": None,
            }
        )

        has_result = (
            bool(result.downloads)
            if request.action == "download"
            else bool(result.items)
        )
        if result.success and has_result:
            return result, source_trace
        if attempt == attempts:
            return result, source_trace

    if last_exception is not None:
        raise last_exception
    raise RuntimeError("web provider execution failed without result")


def _build_api_response(
    *,
    success: bool,
    request: UnifiedLiteratureRequest,
    route: UnifiedRouteInfo,
    warnings: List[str],
    raw_payload: Dict[str, Any],
    api_result: ApiGatewayResult,
    api_items: List[UnifiedLiteratureItem],
) -> UnifiedLiteratureResponse:
    if request.action == "download":
        return UnifiedLiteratureResponse(
            success=success,
            items=[],
            downloads=api_result.downloads,
            warnings=warnings,
            route=route,
            raw=raw_payload if raw_payload else None,
        )
    return UnifiedLiteratureResponse(
        success=success,
        items=api_items,
        warnings=warnings,
        route=route,
        raw=raw_payload if raw_payload else None,
    )


def _build_web_response(
    *,
    success: bool,
    request: UnifiedLiteratureRequest,
    route: UnifiedRouteInfo,
    warnings: List[str],
    raw_payload: Dict[str, Any],
    web_result: WebGatewayResult,
    web_items: List[UnifiedLiteratureItem],
) -> UnifiedLiteratureResponse:
    if request.action == "download":
        return UnifiedLiteratureResponse(
            success=success,
            items=[],
            downloads=web_result.downloads,
            warnings=warnings,
            route=route,
            raw=raw_payload if raw_payload else None,
        )
    return UnifiedLiteratureResponse(
        success=success,
        items=web_items,
        warnings=warnings,
        route=route,
        raw=raw_payload if raw_payload else None,
    )


async def literature_unified_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Unified literature metadata workflow for API and web providers."""
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
    use_web = _should_use_web(request, query)
    warnings: List[str] = []
    raw_payload: Dict[str, Any] = {}

    if use_web:
        web_provider = _select_web_provider(request, query)
        route = UnifiedRouteInfo(
            prefer=request.prefer,
            api_provider=request.api_provider,
            web_provider=web_provider,
            used="none",
            reason=None,
            fallback_used=False,
        )
        web_result, source_trace = await _execute_web(web_provider, request, query)
        web_items = (
            normalize_items(web_result.provider, web_result.items)
            if request.action == "search"
            else []
        )
        warnings.extend(web_result.warnings)
        if request.raw:
            raw_payload["web"] = _web_response_to_raw(web_result, source_trace)

        web_has_result = (
            bool(web_result.downloads)
            if request.action == "download"
            else bool(web_items)
        )

        route.used = "web"
        if web_has_result:
            route.reason = f"web_provider:{route.web_provider}"
        else:
            route.reason = (
                "web_download_failed" if request.action == "download" else "web_no_items"
            )
            warnings.append(
                "FULLTEXT_UNAVAILABLE"
                if request.action == "download"
                else "FETCH_NO_RESULT"
            )

        response = _build_web_response(
            success=bool(web_result.success and web_has_result),
            request=request,
            route=route,
            warnings=warnings,
            raw_payload=raw_payload,
            web_result=web_result,
            web_items=web_items,
        )
        return response.model_dump()

    api_provider = _select_api_provider(request, identifiers)
    route = UnifiedRouteInfo(
        prefer=request.prefer,
        api_provider=api_provider,
        web_provider=request.web_provider,
        used="none",
        reason=None,
        fallback_used=False,
    )
    api_result = await _execute_api(api_provider, request, identifiers, query)
    api_items = (
        normalize_items(api_result.provider, api_result.items)
        if request.action == "search"
        else []
    )
    warnings.extend(api_result.warnings)
    if request.raw:
        raw_payload["api"] = _api_response_to_raw(api_result)

    api_has_result = (
        bool(api_result.downloads) if request.action == "download" else bool(api_items)
    )

    route.used = "api"
    if api_has_result:
        route.reason = f"api_provider:{route.api_provider}"
    else:
        route.reason = (
            "api_download_failed" if request.action == "download" else "api_no_items"
        )
        warnings.append(
            "FULLTEXT_UNAVAILABLE"
            if request.action == "download"
            else "FETCH_NO_RESULT"
        )

    response = _build_api_response(
        success=bool(api_result.success and api_has_result),
        request=request,
        route=route,
        warnings=warnings,
        raw_payload=raw_payload,
        api_result=api_result,
        api_items=api_items,
    )
    return response.model_dump()
