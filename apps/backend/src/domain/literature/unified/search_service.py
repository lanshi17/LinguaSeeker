from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Optional, Sequence, TypedDict

from src.domain.literature.unified.workflow import literature_unified_workflow


class ProviderPlanItem(TypedDict):
    route: str
    provider: str


LANG_PROVIDER_MATRIX: dict[str, list[ProviderPlanItem]] = {
    "zh": [
        {"route": "web", "provider": "pubscholar"},
        {"route": "web", "provider": "hans_publishers"},
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
        {"route": "api", "provider": "pmc"},
    ],
    "ja": [
        {"route": "api", "provider": "jstage"},
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
        {"route": "api", "provider": "pmc"},
    ],
    "ko": [
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
        {"route": "api", "provider": "pmc"},
    ],
    "ru": [
        {"route": "web", "provider": "cyberleninka"},
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
    ],
    "de": [
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
        {"route": "api", "provider": "pmc"},
    ],
    "en": [
        {"route": "api", "provider": "pmc"},
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
    ],
    "auto": [
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
        {"route": "api", "provider": "pmc"},
    ],
}

_TITLE_NORMALIZER = re.compile(r"[^\w\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]+", re.UNICODE)


def build_provider_plan(
    *, language: str = "auto", provider_hints: Optional[Sequence[str]] = None
) -> list[ProviderPlanItem]:
    normalized_language = (language or "auto").strip().lower() or "auto"
    plan = list(LANG_PROVIDER_MATRIX.get(normalized_language, LANG_PROVIDER_MATRIX["auto"]))
    hints = [str(item).strip().lower() for item in (provider_hints or []) if str(item).strip()]
    if not hints:
        return plan

    hinted = [item for item in plan if item["provider"] in hints]
    remaining = [item for item in plan if item["provider"] not in hints]
    return hinted + remaining


def _normalize_title(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    normalized = _TITLE_NORMALIZER.sub("", str(title).casefold())
    return normalized or None


def _clean_identifier(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text.casefold() or None


def _candidate_keys(candidate: Dict[str, Any]) -> list[tuple[str, str]]:
    identifiers = candidate.get("identifiers") or {}
    keys: list[tuple[str, str]] = []

    doi = _clean_identifier(candidate.get("doi") or identifiers.get("doi"))
    if doi:
        keys.append(("doi", doi))

    url = _clean_identifier(
        candidate.get("url")
        or candidate.get("detail_link")
        or identifiers.get("url")
        or identifiers.get("detail_link")
    )
    if url:
        keys.append(("url", url))

    normalized_title = _normalize_title(candidate.get("title"))
    if normalized_title:
        keys.append(("title", normalized_title))

    return keys


def dedupe_candidates(candidates: Sequence[Dict[str, Any]]) -> list[Dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[Dict[str, Any]] = []

    for candidate in candidates:
        keys = _candidate_keys(candidate)
        if keys and any(key in seen for key in keys):
            continue
        deduped.append(candidate)
        for key in keys:
            seen.add(key)

    return deduped


def _build_candidate_id(candidate: Dict[str, Any]) -> str:
    identity = {
        "provider": candidate.get("provider"),
        "route": candidate.get("route"),
        "doi": candidate.get("doi"),
        "url": candidate.get("url"),
        "title": candidate.get("title"),
    }
    digest = hashlib.sha1(
        json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"cand-{digest[:12]}"


def _normalize_candidate(item: Dict[str, Any], plan_item: ProviderPlanItem) -> Dict[str, Any]:
    identifiers = dict(item.get("identifiers") or {})
    doi = item.get("doi") or identifiers.get("doi")
    url = item.get("url") or identifiers.get("url")
    links = item.get("links") if isinstance(item.get("links"), list) else []
    detail_link = item.get("url") or (links[0] if links else None)

    normalized = {
        "candidate_id": "",
        "provider": plan_item["provider"],
        "route": plan_item["route"],
        "title": str(item.get("title") or "").strip(),
        "journal": item.get("journal"),
        "year": item.get("year"),
        "language": item.get("language"),
        "doi": doi,
        "url": url,
        "identifiers": identifiers,
        "detail_link": detail_link,
    }
    if doi and not normalized["identifiers"].get("doi"):
        normalized["identifiers"]["doi"] = doi
    if url and not normalized["identifiers"].get("url"):
        normalized["identifiers"]["url"] = url
    normalized["candidate_id"] = _build_candidate_id(normalized)
    return normalized


def rank_candidates(
    candidates: Sequence[Dict[str, Any]],
    *,
    expected_title: Optional[str] = None,
    preferred_provider: Optional[str] = None,
) -> list[Dict[str, Any]]:
    normalized_expected_title = _normalize_title(expected_title)
    normalized_provider = str(preferred_provider or "").strip().lower() or None

    def _score(candidate: Dict[str, Any]) -> tuple[int, int, int]:
        normalized_title = _normalize_title(candidate.get("title"))
        exact_title = int(bool(normalized_expected_title and normalized_title == normalized_expected_title))
        provider_match = int(bool(normalized_provider and str(candidate.get("provider") or "").strip().lower() == normalized_provider))
        has_doi = int(bool(_clean_identifier(candidate.get("doi") or (candidate.get("identifiers") or {}).get("doi"))))
        return (exact_title, provider_match, has_doi)

    return sorted(candidates, key=_score, reverse=True)


async def search_multilingual_candidates(
    *,
    target: str,
    disease: str,
    language: str = "auto",
    candidate_limit: int = 15,
    country: str = "不限",
    provider_hints: Optional[Sequence[str]] = None,
) -> list[Dict[str, Any]]:
    query = f"{target} {disease} case report".strip()
    if not query:
        return []

    plan = build_provider_plan(language=language, provider_hints=provider_hints)
    collected: list[Dict[str, Any]] = []
    preferred_provider = plan[0]["provider"] if plan else None

    for plan_item in plan:
        payload: Dict[str, Any] = {
            "action": "search",
            "query": query,
            "prefer": plan_item["route"],
            "limit": candidate_limit,
            "language": language,
            "raw": False,
        }
        if plan_item["route"] == "api":
            payload["api_provider"] = plan_item["provider"]
            if country and country != "不限":
                payload["api_params"] = {"country": country}
        else:
            payload["web_provider"] = plan_item["provider"]
            if country and country != "不限":
                payload["web_params"] = {"country": country}

        result = await literature_unified_workflow(payload)
        for item in result.get("items", []) or []:
            if not item.get("title"):
                continue
            collected.append(_normalize_candidate(item, plan_item))

        collected = dedupe_candidates(collected)
        collected = rank_candidates(
            collected,
            expected_title=target,
            preferred_provider=preferred_provider,
        )
        if len(collected) >= candidate_limit:
            return collected[:candidate_limit]

    return rank_candidates(
        collected,
        expected_title=target,
        preferred_provider=preferred_provider,
    )[:candidate_limit]
