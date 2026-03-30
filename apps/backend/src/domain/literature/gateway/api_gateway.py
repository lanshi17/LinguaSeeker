from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast
from urllib.parse import urljoin

if TYPE_CHECKING:
    from src.domain.literature.gateway.registry import ProviderAdapterRegistry

import httpx

from src.domain.literature.api.crossref.workflow import crossref_http_workflow
from src.domain.literature.api.doaj.workflow import doaj_http_workflow
from src.domain.literature.api.jstage.workflow import jstage_http_workflow
from src.domain.literature.api.pmc.workflow import pmc_http_workflow
from src.domain.literature.api.unpaywall.workflow import unpaywall_workflow
from src.domain.literature.gateway.contracts import ApiGatewayRequest, ApiGatewayResult


def _merge_payload(
    payload: Dict[str, Any], overrides: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    if not overrides:
        return payload
    merged = dict(payload)
    for key, value in overrides.items():
        if (
            key in {"params", "search_params"}
            and isinstance(merged.get(key), dict)
            and isinstance(value, dict)
        ):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def _result_from_response(provider: str, response: Dict[str, Any]) -> ApiGatewayResult:
    return ApiGatewayResult(
        provider=provider,
        success=bool(response.get("success")),
        items=list(response.get("items") or []),
        downloads=[],
        warnings=list(response.get("warnings") or []),
        raw=response.get("raw"),
        meta=response.get("meta"),
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
) -> ApiGatewayResult:
    downloads = _extract_downloads_from_response(response)
    return ApiGatewayResult(
        provider=provider,
        success=bool(response.get("success")),
        items=[],
        downloads=downloads,
        warnings=list(response.get("warnings") or []),
        raw=response.get("raw"),
        meta=response.get("meta"),
    )


def _failure_result(provider: str, error: Exception) -> ApiGatewayResult:
    return ApiGatewayResult(
        provider=provider,
        success=False,
        items=[],
        downloads=[],
        warnings=[f"{provider}_error:{error}"],
    )


def _crossref_filter_from_identifiers(
    identifiers: Dict[str, Optional[str]],
) -> Optional[str]:
    doi = identifiers.get("doi")
    issn = identifiers.get("issn")
    if doi:
        return f"doi:{doi}"
    if issn:
        return f"issn:{issn}"
    return None


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", str(name or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned or "paper")[:120]


def _choose_item(
    items: List[Dict[str, Any]],
    selected_index: int,
    selected_title: Optional[str],
    title_keys: List[str],
) -> Optional[Dict[str, Any]]:
    def _read_key(item: Dict[str, Any], key: str) -> str:
        if "." not in key:
            return str(item.get(key) or "").strip()
        current: Any = item
        for part in key.split("."):
            if not isinstance(current, dict):
                return ""
            current = current.get(part)
        return str(current or "").strip()

    if selected_title:
        wanted = str(selected_title).strip().lower()
        for item in items:
            for key in title_keys:
                title = _read_key(item, key).lower()
                if title and wanted in title:
                    return item
    if 0 <= selected_index < len(items):
        return items[selected_index]
    return None


def _extract_pdf_links_from_html(html_text: str, base_url: str) -> List[str]:
    if not html_text:
        return []
    links: List[str] = []
    seen = set()
    for match in re.findall(
        r"href=[\"']([^\"']+)[\"']", html_text, flags=re.IGNORECASE
    ):
        href = str(match or "").strip()
        if not href:
            continue
        resolved = urljoin(base_url, href)
        lowered = resolved.lower()
        if ".pdf" not in lowered and "/_pdf" not in lowered and "pdf" not in lowered:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        links.append(resolved)
    return links


def _jstage_pdf_candidates(detail_link: str) -> List[str]:
    link = str(detail_link or "").strip()
    if not link:
        return []
    candidates = [link]
    if "/_article" in link:
        candidates.append(link.replace("/_article", "/_pdf", 1))
    if "/_article/" in link:
        candidates.append(link.replace("/_article/", "/_pdf/", 1))
    seen = set()
    ordered: List[str] = []
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


async def _download_pdf_from_candidates(
    candidates: List[str],
    download_path: str,
    filename_stem: str,
) -> Tuple[Optional[str], Optional[str], List[str]]:
    warnings: List[str] = []
    queue = [str(url).strip() for url in candidates if str(url).strip()]
    visited = set()
    target = Path(download_path) / f"{_sanitize_filename(filename_stem)}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        while queue:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                response = await client.get(url)
                response.raise_for_status()
            except Exception as exc:
                warnings.append(f"download_failed:{url}:{exc}")
                continue

            content = response.content or b""
            content_type = str(response.headers.get("content-type") or "").lower()
            final_url = str(response.url)

            if content.startswith(b"%PDF"):
                target.write_bytes(content)
                return str(target), final_url, warnings

            if "html" in content_type or b"<html" in content[:2048].lower():
                extra = _extract_pdf_links_from_html(
                    response.text or "",
                    final_url or url,
                )
                for link in extra:
                    if link not in visited:
                        queue.append(link)
                continue

            warnings.append(f"non_pdf_content_type:{content_type or 'unknown'}")

    return None, None, warnings


async def call_crossref(
    query: Optional[str],
    limit: int,
    raw: bool,
    filter_expr: Optional[str] = None,
    api_params: Optional[Dict[str, Any]] = None,
) -> ApiGatewayResult:
    params: Dict[str, Any] = {
        "resource": "works",
        "rows": min(limit, 100),
        "limit": limit,
    }
    if query:
        params["query"] = query
    if filter_expr:
        params["filter"] = filter_expr
    payload = {"action": "search", "params": params, "raw": raw}
    payload = _merge_payload(payload, api_params)
    try:
        response = await crossref_http_workflow(payload)
        return _result_from_response("crossref", response)
    except Exception as exc:
        return _failure_result("crossref", exc)


async def call_unpaywall(
    query: Optional[str],
    doi: Optional[str],
    limit: int,
    raw: bool,
    api_params: Optional[Dict[str, Any]] = None,
) -> ApiGatewayResult:
    if doi:
        payload = {"action": "doi", "doi": doi, "raw": raw}
    else:
        payload = {
            "action": "query",
            "search_params": {"keyword": [query] if query else [], "limit": limit},
            "raw": raw,
        }
    payload = _merge_payload(payload, api_params)
    try:
        response = await unpaywall_workflow(payload)
        return _result_from_response("unpaywall", response)
    except Exception as exc:
        return _failure_result("unpaywall", exc)


async def call_unpaywall_download(
    query: Optional[str],
    doi: Optional[str],
    limit: int,
    raw: bool,
    download_path: str,
    selected_index: int,
    api_params: Optional[Dict[str, Any]] = None,
) -> ApiGatewayResult:
    if doi:
        payload: Dict[str, Any] = {
            "action": "download",
            "doi": doi,
            "download_path": download_path,
            "selected_index": selected_index,
            "raw": raw,
        }
    else:
        payload = {
            "action": "download",
            "search_params": {
                "keyword": [query] if query else [],
                "limit": limit,
            },
            "download_path": download_path,
            "selected_index": selected_index,
            "raw": raw,
        }

    payload = _merge_payload(payload, api_params)
    try:
        response = await unpaywall_workflow(payload)
        return _download_result_from_response("unpaywall", response)
    except Exception as exc:
        return _failure_result("unpaywall", exc)


async def call_pmc_metadata(
    pmcids: List[str],
    raw: bool,
    api_params: Optional[Dict[str, Any]] = None,
) -> ApiGatewayResult:
    items: List[Dict[str, Any]] = []
    warnings: List[str] = []
    raw_payloads: List[Any] = []

    async def fetch_one(pmcid: str) -> Dict[str, Any]:
        payload = {"action": "metadata", "params": {"pmcid": pmcid}, "raw": raw}
        payload = _merge_payload(payload, api_params)
        return await pmc_http_workflow(payload)

    tasks = [fetch_one(pmcid) for pmcid in pmcids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for res in results:
        if isinstance(res, Exception):
            warnings.append(f"pmc_metadata_error:{res}")
            continue
        response_payload = cast(dict[str, Any], res)
        items.extend(response_payload.get("items") or [])
        warnings.extend(response_payload.get("warnings") or [])
        if raw:
            raw_payloads.append(response_payload)

    return ApiGatewayResult(
        provider="pmc",
        success=bool(items),
        items=items,
        warnings=warnings,
        raw=raw_payloads if raw else None,
    )


async def call_pmc_search(
    term: str,
    limit: int,
    raw: bool,
    api_params: Optional[Dict[str, Any]] = None,
) -> ApiGatewayResult:
    payload = {
        "action": "search",
        "params": {
            "term": term,
            "retmax": min(limit, 50),
            "limit": limit,
        },
        "raw": raw,
    }
    payload = _merge_payload(payload, api_params)
    try:
        response = await pmc_http_workflow(payload)
        return _result_from_response("pmc", response)
    except Exception as exc:
        return _failure_result("pmc", exc)


async def call_pmc_for_pmid(
    pmid: str,
    limit: int,
    raw: bool,
    api_params: Optional[Dict[str, Any]] = None,
) -> ApiGatewayResult:
    search_term = f"{pmid}[pmid]"
    search_result = await call_pmc_search(search_term, limit, raw, api_params)
    pmcids = [
        pmcid
        for item in search_result.items
        if isinstance((pmcid := item.get("pmcid")), str)
    ]
    if not pmcids:
        return search_result
    metadata_result = await call_pmc_metadata(pmcids[:limit], raw, api_params)
    metadata_result.warnings = search_result.warnings + metadata_result.warnings
    return metadata_result


async def call_pmc_download(
    query: Optional[str],
    identifiers: Dict[str, Optional[str]],
    limit: int,
    raw: bool,
    download_path: str,
    api_params: Optional[Dict[str, Any]] = None,
) -> ApiGatewayResult:
    warnings: List[str] = []
    pmcids: List[str] = []

    pmcid = identifiers.get("pmcid")
    pmid = identifiers.get("pmid")
    if pmcid:
        pmcids = [pmcid]
    elif pmid:
        search_result = await call_pmc_search(f"{pmid}[pmid]", limit, False, api_params)
        warnings.extend(search_result.warnings)
        pmcids = [
            found_pmcid
            for item in search_result.items
            if isinstance((found_pmcid := item.get("pmcid")), str)
        ]
    else:
        search_result = await call_pmc_search(query or "", limit, False, api_params)
        warnings.extend(search_result.warnings)
        pmcids = [
            found_pmcid
            for item in search_result.items
            if isinstance((found_pmcid := item.get("pmcid")), str)
        ]

    if not pmcids:
        return ApiGatewayResult(
            provider="pmc",
            success=False,
            items=[],
            downloads=[],
            warnings=warnings or ["pmc_download_no_pmcid"],
        )

    payload = {
        "action": "download",
        "params": {
            "pmcids": pmcids[:limit],
            "file_types": ["pdf"],
            "out_dir": download_path,
        },
        "raw": raw,
    }
    payload = _merge_payload(payload, api_params)
    try:
        response = await pmc_http_workflow(payload)
        result = _download_result_from_response("pmc", response)
        result.warnings = warnings + result.warnings
        return result
    except Exception as exc:
        return _failure_result("pmc", exc)


async def call_jstage(
    query: Optional[str],
    limit: int,
    raw: bool,
    api_params: Optional[Dict[str, Any]] = None,
) -> ApiGatewayResult:
    payload = {
        "action": "articles",
        "params": {
            "keyword": query,
            "count": min(limit, 100),
            "limit": limit,
        },
        "raw": raw,
    }
    payload = _merge_payload(payload, api_params)
    try:
        response = await jstage_http_workflow(payload)
        return _result_from_response("jstage", response)
    except Exception as exc:
        return _failure_result("jstage", exc)


async def call_jstage_download(
    query: Optional[str],
    limit: int,
    raw: bool,
    download_path: str,
    selected_index: int,
    selected_title: Optional[str],
    detail_link: Optional[str],
    api_params: Optional[Dict[str, Any]] = None,
) -> ApiGatewayResult:
    warnings: List[str] = []
    item_title = selected_title or "jstage-paper"
    candidates: List[str] = []

    if detail_link:
        candidates.extend(_jstage_pdf_candidates(detail_link))

    if not candidates:
        search_payload = {
            "action": "articles",
            "params": {
                "keyword": query,
                "count": min(limit, 100),
                "limit": limit,
            },
            "raw": raw,
        }
        search_payload = _merge_payload(search_payload, api_params)
        try:
            search_response = await jstage_http_workflow(search_payload)
        except Exception as exc:
            return _failure_result("jstage", exc)

        warnings.extend(list(search_response.get("warnings") or []))
        items = [
            item
            for item in (search_response.get("items") or [])
            if isinstance(item, dict)
        ]
        if not items:
            return ApiGatewayResult(
                provider="jstage",
                success=False,
                items=[],
                downloads=[],
                warnings=warnings or ["no_search_results"],
                raw=search_response.get("raw") if raw else None,
                meta=search_response.get("meta"),
            )

        chosen = _choose_item(
            items,
            selected_index=selected_index,
            selected_title=selected_title,
            title_keys=["article_title_ja", "article_title_en"],
        )
        if not chosen:
            return ApiGatewayResult(
                provider="jstage",
                success=False,
                items=[],
                downloads=[],
                warnings=warnings + ["invalid_selected_index"],
                raw=search_response.get("raw") if raw else None,
                meta=search_response.get("meta"),
            )

        item_title = (
            str(chosen.get("article_title_ja") or "").strip()
            or str(chosen.get("article_title_en") or "").strip()
            or item_title
        )
        link = str(chosen.get("link") or "").strip()
        if link:
            candidates.extend(_jstage_pdf_candidates(link))

    file_path, pdf_url, extra_warnings = await _download_pdf_from_candidates(
        candidates=candidates,
        download_path=download_path,
        filename_stem=item_title,
    )
    warnings.extend(extra_warnings)
    if not file_path:
        return ApiGatewayResult(
            provider="jstage",
            success=False,
            items=[],
            downloads=[],
            warnings=warnings or ["pdf_not_found"],
        )

    return ApiGatewayResult(
        provider="jstage",
        success=True,
        items=[],
        downloads=[
            {
                "pdf_url": pdf_url,
                "file_path": file_path,
            }
        ],
        warnings=warnings,
    )


async def call_doaj(
    query: Optional[str],
    limit: int,
    raw: bool,
    api_params: Optional[Dict[str, Any]] = None,
) -> ApiGatewayResult:
    payload = {
        "action": "search",
        "search_params": {
            "resource": "articles",
            "search_query": query or "",
            "page": 1,
            "page_size": min(limit, 100),
            "limit": limit,
        },
        "raw": raw,
    }
    payload = _merge_payload(payload, api_params)
    try:
        response = await doaj_http_workflow(payload)
        return _result_from_response("doaj", response)
    except Exception as exc:
        return _failure_result("doaj", exc)


def _extract_doaj_article_links(item: Dict[str, Any]) -> List[str]:
    bibjson = item.get("bibjson") or {}
    links = bibjson.get("link") or []
    prioritized: List[str] = []
    fallback: List[str] = []
    for link in links:
        if not isinstance(link, dict):
            continue
        url = str(link.get("url") or "").strip()
        if not url:
            continue
        content_type = str(link.get("content_type") or "").lower()
        link_type = str(link.get("type") or "").lower()
        if "pdf" in content_type:
            prioritized.append(url)
            continue
        if link_type in {"fulltext", "full_text"}:
            prioritized.append(url)
            continue
        fallback.append(url)

    doi = ""
    for identifier in bibjson.get("identifier") or []:
        if not isinstance(identifier, dict):
            continue
        id_type = str(identifier.get("type") or "").lower()
        if id_type == "doi":
            doi = str(identifier.get("id") or "").strip()
            break
    if doi:
        fallback.append(f"https://doi.org/{doi}")

    ordered: List[str] = []
    seen = set()
    for candidate in prioritized + fallback:
        if candidate and candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


async def call_doaj_download(
    query: Optional[str],
    limit: int,
    raw: bool,
    download_path: str,
    selected_index: int,
    selected_title: Optional[str],
    detail_link: Optional[str],
    api_params: Optional[Dict[str, Any]] = None,
) -> ApiGatewayResult:
    warnings: List[str] = []
    if detail_link:
        file_path, pdf_url, extra_warnings = await _download_pdf_from_candidates(
            candidates=[detail_link],
            download_path=download_path,
            filename_stem=selected_title or "doaj-paper",
        )
        warnings.extend(extra_warnings)
        if file_path:
            return ApiGatewayResult(
                provider="doaj",
                success=True,
                items=[],
                downloads=[{"pdf_url": pdf_url, "file_path": file_path}],
                warnings=warnings,
            )

    payload = {
        "action": "search",
        "search_params": {
            "resource": "articles",
            "search_query": query or "",
            "page": 1,
            "page_size": min(max(limit, 10), 100),
            "limit": max(limit, 10),
        },
        "raw": True,
    }
    payload = _merge_payload(payload, api_params)
    try:
        response = await doaj_http_workflow(payload)
    except Exception as exc:
        return _failure_result("doaj", exc)

    warnings.extend(list(response.get("warnings") or []))
    items = [item for item in (response.get("items") or []) if isinstance(item, dict)]
    if not items:
        return ApiGatewayResult(
            provider="doaj",
            success=False,
            items=[],
            downloads=[],
            warnings=warnings or ["no_search_results"],
            raw=response if raw else None,
            meta=response.get("meta"),
        )

    chosen = _choose_item(
        items,
        selected_index=selected_index,
        selected_title=selected_title,
        title_keys=["title", "bibjson.title"],
    )
    if not chosen:
        return ApiGatewayResult(
            provider="doaj",
            success=False,
            items=[],
            downloads=[],
            warnings=warnings + ["invalid_selected_index"],
            raw=response if raw else None,
            meta=response.get("meta"),
        )

    bibjson = chosen.get("bibjson") or {}
    item_title = str(bibjson.get("title") or selected_title or "doaj-paper")
    candidates = _extract_doaj_article_links(chosen)
    file_path, pdf_url, extra_warnings = await _download_pdf_from_candidates(
        candidates=candidates,
        download_path=download_path,
        filename_stem=item_title,
    )
    warnings.extend(extra_warnings)
    if not file_path:
        return ApiGatewayResult(
            provider="doaj",
            success=False,
            items=[],
            downloads=[],
            warnings=warnings or ["pdf_not_found"],
            raw=response if raw else None,
            meta=response.get("meta"),
        )

    return ApiGatewayResult(
        provider="doaj",
        success=True,
        items=[],
        downloads=[{"pdf_url": pdf_url, "file_path": file_path}],
        warnings=warnings,
        raw=response if raw else None,
        meta=response.get("meta"),
    )


def get_api_provider_registry() -> "ProviderAdapterRegistry":
    from src.domain.literature.gateway.adapters.crossref_adapter import CrossrefAdapter
    from src.domain.literature.gateway.adapters.doaj_adapter import DoajAdapter
    from src.domain.literature.gateway.adapters.jstage_adapter import JStageAdapter
    from src.domain.literature.gateway.adapters.pmc_adapter import PMCAdapter
    from src.domain.literature.gateway.adapters.unpaywall_adapter import (
        UnpaywallAdapter,
    )
    from src.domain.literature.gateway.registry import ProviderAdapterRegistry

    return ProviderAdapterRegistry(
        [
            PMCAdapter(
                metadata_call=call_pmc_metadata,
                search_call=call_pmc_search,
                pmid_call=call_pmc_for_pmid,
            ),
            JStageAdapter(
                search_call=call_jstage,
                download_call=call_jstage_download,
            ),
            DoajAdapter(
                search_call=call_doaj,
                download_call=call_doaj_download,
            ),
            UnpaywallAdapter(
                search_call=call_unpaywall,
                download_call=call_unpaywall_download,
            ),
            CrossrefAdapter(
                search_call=call_crossref,
            ),
        ]
    )


async def call_api_gateway(request: ApiGatewayRequest) -> ApiGatewayResult:
    provider = request.provider
    identifiers = request.identifiers or {}
    api_params = request.params or {}

    if request.action == "download":
        if provider == "unpaywall":
            registry = get_api_provider_registry()
            if registry.supports(provider):
                return await registry.get(provider).execute(request)
            return await call_unpaywall_download(
                request.query,
                identifiers.get("doi"),
                request.limit,
                request.raw,
                request.download_path,
                request.selected_index,
                api_params,
            )

        if provider == "pmc":
            return await call_pmc_download(
                request.query,
                identifiers,
                request.limit,
                request.raw,
                request.download_path,
                api_params,
            )
        if provider == "jstage":
            registry = get_api_provider_registry()
            if registry.supports(provider):
                return await registry.get(provider).execute(request)
            return await call_jstage_download(
                request.query,
                request.limit,
                request.raw,
                request.download_path,
                request.selected_index,
                request.selected_title,
                request.detail_link,
                api_params,
            )

        if provider == "doaj":
            registry = get_api_provider_registry()
            if registry.supports(provider):
                return await registry.get(provider).execute(request)
            return await call_doaj_download(
                request.query,
                request.limit,
                request.raw,
                request.download_path,
                request.selected_index,
                request.selected_title,
                request.detail_link,
                api_params,
            )
        return ApiGatewayResult(
            provider=provider,
            success=False,
            items=[],
            downloads=[],
            warnings=[f"{provider}_download_unsupported"],
        )

    if provider == "unpaywall":
        registry = get_api_provider_registry()
        if registry.supports(provider):
            return await registry.get(provider).execute(request)
        return await call_unpaywall(
            request.query,
            identifiers.get("doi"),
            request.limit,
            request.raw,
            api_params,
        )

    if provider == "pmc":
        registry = get_api_provider_registry()
        if registry.supports(provider):
            return await registry.get(provider).execute(request)
        pmcid = identifiers.get("pmcid")
        pmid = identifiers.get("pmid")
        if pmcid:
            return await call_pmc_metadata([pmcid], request.raw, api_params)
        if pmid:
            return await call_pmc_for_pmid(pmid, request.limit, request.raw, api_params)

        search_result = await call_pmc_search(
            request.query or "",
            request.limit,
            request.raw,
            api_params,
        )
        pmcids = [
            found_pmcid
            for item in search_result.items
            if isinstance((found_pmcid := item.get("pmcid")), str)
        ]
        if not pmcids:
            return search_result
        metadata_result = await call_pmc_metadata(
            pmcids[: request.limit],
            request.raw,
            api_params,
        )
        metadata_result.warnings = search_result.warnings + metadata_result.warnings
        return metadata_result

    if provider == "jstage":
        registry = get_api_provider_registry()
        if registry.supports(provider):
            return await registry.get(provider).execute(request)
        return await call_jstage(
            request.query,
            request.limit,
            request.raw,
            api_params,
        )

    if provider == "doaj":
        registry = get_api_provider_registry()
        if registry.supports(provider):
            return await registry.get(provider).execute(request)
        return await call_doaj(
            request.query,
            request.limit,
            request.raw,
            api_params,
        )

    if provider == "crossref":
        registry = get_api_provider_registry()
        if registry.supports(provider):
            return await registry.get(provider).execute(request)
        return await call_crossref(
            request.query,
            request.limit,
            request.raw,
            _crossref_filter_from_identifiers(identifiers),
            api_params,
        )

    return ApiGatewayResult(
        provider=provider,
        success=False,
        items=[],
        downloads=[],
        warnings=[f"{provider}_unsupported"],
    )
