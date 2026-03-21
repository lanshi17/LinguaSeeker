from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from src.domain.literature.automated_web.cyberleninka.cyberleninka import (
    cyberleninka_workflow,
)
from src.domain.literature.automated_web.hans_publishers.hans_publishers import (
    hanspub_workflow,
)
from src.domain.literature.automated_web.pubscholar.pubscholar import (
    pubscholar_workflow,
)

WebProvider = Literal["pubscholar", "cyberleninka", "hans_publishers"]
ActionStrategy = Literal["search", "download"]


@dataclass
class WebGatewayRequest:
    provider: WebProvider
    action: ActionStrategy = "search"
    query: Optional[str] = None
    limit: int = 20
    params: Dict[str, Any] = field(default_factory=dict)
    download_path: str = "./downloads"
    selected_index: int = 0
    selected_title: Optional[str] = None
    detail_link: Optional[str] = None


@dataclass
class WebGatewayResult:
    provider: str
    success: bool
    items: List[Dict[str, Any]]
    warnings: List[str]
    downloads: List[Dict[str, Any]] = field(default_factory=list)
    raw: Any = None


def _merge_payload(
    payload: Dict[str, Any], overrides: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    if not overrides:
        return payload
    merged = dict(payload)
    for key, value in overrides.items():
        if key == "search_params" and isinstance(merged.get("search_params"), dict):
            if isinstance(value, dict):
                merged["search_params"] = {**merged["search_params"], **value}
            else:
                merged["search_params"] = value
        else:
            merged[key] = value
    return merged


def _result_from_response(provider: str, response: Dict[str, Any]) -> WebGatewayResult:
    return WebGatewayResult(
        provider=provider,
        success=bool(response.get("success")),
        items=list(response.get("items") or []),
        warnings=list(response.get("warnings") or []),
        downloads=[],
        raw=response,
    )


def _extract_downloads_from_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(response.get("items"), list):
        items = [item for item in response.get("items") or [] if isinstance(item, dict)]
        if items and any(
            any(
                key in item
                for key in ("file_path", "path", "pdf_url", "url", "doc_url", "type")
            )
            for item in items
        ):
            return items

    single = {
        "pdf_url": response.get("pdf_url"),
        "doc_url": response.get("doc_url"),
        "file_path": response.get("file_path"),
    }
    if single["pdf_url"] or single["doc_url"] or single["file_path"]:
        return [single]
    return []


def _download_result_from_response(
    provider: str, response: Dict[str, Any]
) -> WebGatewayResult:
    return WebGatewayResult(
        provider=provider,
        success=bool(response.get("success")),
        items=[],
        warnings=list(response.get("warnings") or []),
        downloads=_extract_downloads_from_response(response),
        raw=response,
    )


def _failure_result(provider: str, error: Exception) -> WebGatewayResult:
    return WebGatewayResult(
        provider=provider,
        success=False,
        items=[],
        warnings=[f"{provider}_error:{error}"],
        downloads=[],
        raw={},
    )


def _build_search_payload(query: Optional[str], limit: int) -> Dict[str, Any]:
    return {
        "action": "search",
        "search_params": {
            "keyword": query or "",
            "filters": {},
            "limit": limit,
        },
    }


def _build_download_payload(
    query: Optional[str],
    limit: int,
    download_path: str,
    selected_index: int,
    selected_title: Optional[str],
    detail_link: Optional[str],
) -> Dict[str, Any]:
    payload = {
        "action": "download",
        "search_params": {
            "keyword": query or "",
            "filters": {},
            "limit": limit,
        },
        "selected_index": selected_index,
        "download_path": download_path,
    }
    if selected_title:
        payload["selected_title"] = selected_title
    if detail_link:
        payload["detail_link"] = detail_link
    return payload


async def call_pubscholar(
    query: Optional[str],
    limit: int,
    action: ActionStrategy = "search",
    download_path: str = "./downloads",
    selected_index: int = 0,
    selected_title: Optional[str] = None,
    detail_link: Optional[str] = None,
    web_params: Optional[Dict[str, Any]] = None,
) -> WebGatewayResult:
    if action == "download":
        payload = _build_download_payload(
            query=query,
            limit=limit,
            download_path=download_path,
            selected_index=selected_index,
            selected_title=selected_title,
            detail_link=detail_link,
        )
    else:
        payload = _build_search_payload(query, limit)
    payload = _merge_payload(payload, web_params)
    try:
        response = await pubscholar_workflow(payload)
        if action == "download":
            return _download_result_from_response("pubscholar", response)
        return _result_from_response("pubscholar", response)
    except Exception as exc:
        return _failure_result("pubscholar", exc)


async def call_hans_publishers(
    query: Optional[str],
    limit: int,
    action: ActionStrategy = "search",
    download_path: str = "./downloads",
    selected_index: int = 0,
    selected_title: Optional[str] = None,
    detail_link: Optional[str] = None,
    web_params: Optional[Dict[str, Any]] = None,
) -> WebGatewayResult:
    if action == "download":
        payload = _build_download_payload(
            query=query,
            limit=limit,
            download_path=download_path,
            selected_index=selected_index,
            selected_title=selected_title,
            detail_link=detail_link,
        )
    else:
        payload = _build_search_payload(query, limit)
    payload = _merge_payload(payload, web_params)
    try:
        response = await hanspub_workflow(payload)
        if action == "download":
            return _download_result_from_response("hans_publishers", response)
        return _result_from_response("hans_publishers", response)
    except Exception as exc:
        return _failure_result("hans_publishers", exc)


async def call_cyberleninka(
    query: Optional[str],
    limit: int,
    action: ActionStrategy = "search",
    download_path: str = "./downloads",
    selected_index: int = 0,
    selected_title: Optional[str] = None,
    detail_link: Optional[str] = None,
    web_params: Optional[Dict[str, Any]] = None,
) -> WebGatewayResult:
    if action == "download":
        payload = _build_download_payload(
            query=query,
            limit=limit,
            download_path=download_path,
            selected_index=selected_index,
            selected_title=selected_title,
            detail_link=detail_link,
        )
    else:
        payload = _build_search_payload(query, limit)
    payload = _merge_payload(payload, web_params)
    try:
        response = await cyberleninka_workflow(payload)
        if action == "download":
            return _download_result_from_response("cyberleninka", response)
        return _result_from_response("cyberleninka", response)
    except Exception as exc:
        return _failure_result("cyberleninka", exc)


async def call_auto_web_gateway(request: WebGatewayRequest) -> WebGatewayResult:
    if request.provider == "pubscholar":
        return await call_pubscholar(
            request.query,
            request.limit,
            request.action,
            request.download_path,
            request.selected_index,
            request.selected_title,
            request.detail_link,
            request.params,
        )
    if request.provider == "hans_publishers":
        return await call_hans_publishers(
            request.query,
            request.limit,
            request.action,
            request.download_path,
            request.selected_index,
            request.selected_title,
            request.detail_link,
            request.params,
        )
    return await call_cyberleninka(
        request.query,
        request.limit,
        request.action,
        request.download_path,
        request.selected_index,
        request.selected_title,
        request.detail_link,
        request.params,
    )
