from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .models import UnifiedLiteratureItem

DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
ISSN_PATTERN = re.compile(r"\b\d{4}-\d{3}[\dX]\b", re.IGNORECASE)


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value).strip() or None


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    output = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _first(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            text = _clean_text(item)
            if text:
                return text
        return None
    return _clean_text(value)


def _normalize_authors(value: Any) -> List[str]:
    if value is None:
        return []
    authors: List[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                name = _clean_text(item.get("name"))
                if not name:
                    given = _clean_text(item.get("given") or item.get("first"))
                    family = _clean_text(item.get("family") or item.get("last"))
                    if given and family:
                        name = f"{given} {family}".strip()
                    else:
                        name = given or family
                if name:
                    authors.append(name)
            else:
                text = _clean_text(item)
                if text:
                    authors.append(text)
        return _dedupe(authors)
    if isinstance(value, str):
        if ";" in value:
            parts = [p.strip() for p in value.split(";") if p.strip()]
        elif " and " in value:
            parts = [p.strip() for p in value.split(" and ") if p.strip()]
        else:
            parts = [value.strip()]
        return _dedupe([p for p in parts if p])
    return []


def _extract_year(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        match = re.search(r"(19|20)\d{2}", value)
        return match.group(0) if match else _clean_text(value)
    if isinstance(value, dict):
        for key in ("date-parts", "date_parts", "dateparts"):
            parts = value.get(key)
            if parts and isinstance(parts, list):
                try:
                    year = parts[0][0]
                    if year:
                        return str(year)
                except (IndexError, TypeError):
                    continue
        for key in ("year", "published_year", "pubyear"):
            if key in value:
                return _extract_year(value.get(key))
    if isinstance(value, (list, tuple)):
        for item in value:
            year = _extract_year(item)
            if year:
                return year
    return None


def _extract_links(values: Sequence[Any]) -> List[str]:
    links: List[str] = []
    for value in values:
        if not value:
            continue
        if isinstance(value, str):
            links.append(value.strip())
            continue
        if isinstance(value, dict):
            for key in ("url", "URL", "link", "landing_page_url", "doi_url", "url_for_pdf"):
                if value.get(key):
                    links.append(str(value.get(key)).strip())
    return _dedupe([l for l in links if l])


def normalize_crossref_item(item: Dict[str, Any]) -> UnifiedLiteratureItem:
    title = _first(item.get("title"))
    authors = _normalize_authors(item.get("author") or item.get("authors"))
    journal = _first(item.get("container-title"))
    doi = _clean_text(item.get("DOI") or item.get("doi"))
    url = _clean_text(item.get("URL") or item.get("url"))
    year = _extract_year(
        item.get("issued")
        or item.get("published")
        or item.get("created")
        or item.get("published-online")
        or item.get("published-print")
    )
    language = _clean_text(item.get("language"))
    publisher = _clean_text(item.get("publisher"))
    issn = _dedupe([_clean_text(v) for v in _as_list(item.get("ISSN")) if _clean_text(v)])
    keywords = _dedupe([_clean_text(v) for v in _as_list(item.get("subject")) if _clean_text(v)])
    links = _extract_links([url, item.get("URL"), item.get("url")])
    return UnifiedLiteratureItem(
        source="crossref",
        title=title,
        authors=authors,
        journal=journal,
        year=year,
        doi=doi,
        url=url,
        links=links,
        language=language,
        publisher=publisher,
        issn=issn,
        identifiers={"issn": issn} if issn else {},
        keywords=keywords,
    )


def normalize_unpaywall_item(item: Dict[str, Any]) -> UnifiedLiteratureItem:
    title = _clean_text(item.get("title") or item.get("publication_title"))
    doi = _clean_text(item.get("doi") or item.get("DOI"))
    journal = _clean_text(item.get("journal_name") or item.get("journal"))
    publisher = _clean_text(item.get("publisher"))
    year = _extract_year(item.get("year") or item.get("published_date"))
    authors = _normalize_authors(item.get("authors") or item.get("author"))
    best_oa = item.get("best_oa_location") or {}
    url = _clean_text(
        item.get("url")
        or best_oa.get("url")
        or best_oa.get("landing_page_url")
        or item.get("doi_url")
    )
    links = _extract_links(
        [
            url,
            item.get("url"),
            item.get("doi_url"),
            best_oa.get("url"),
            best_oa.get("url_for_pdf"),
        ]
    )
    return UnifiedLiteratureItem(
        source="unpaywall",
        title=title,
        authors=authors,
        journal=journal,
        year=year,
        doi=doi,
        url=url,
        links=links,
        language=_clean_text(item.get("language")),
        publisher=publisher,
        identifiers={"is_oa": item.get("is_oa")} if "is_oa" in item else {},
        keywords=_dedupe([_clean_text(v) for v in _as_list(item.get("keywords")) if _clean_text(v)]),
    )


def _collect_strings(value: Any, limit: int = 5000) -> List[str]:
    collected: List[str] = []
    queue: List[Any] = [value]
    while queue and len(collected) < limit:
        current = queue.pop(0)
        if isinstance(current, dict):
            queue.extend(current.values())
        elif isinstance(current, list):
            queue.extend(current)
        elif isinstance(current, tuple):
            queue.extend(list(current))
        else:
            text = _clean_text(current)
            if text:
                collected.append(text)
    return collected


def _find_first_match(pattern: re.Pattern[str], values: Iterable[str]) -> Optional[str]:
    for value in values:
        match = pattern.search(value)
        if match:
            return match.group(0)
    return None


def normalize_pmc_item(item: Dict[str, Any]) -> UnifiedLiteratureItem:
    strings = _collect_strings(item)
    title = _first(item.get("title")) or _find_first_match(re.compile(r"<title>(.+?)</title>"), strings)
    doi = _find_first_match(DOI_PATTERN, strings)
    pmcid = _find_first_match(re.compile(r"\bPMC\d+\b", re.IGNORECASE), strings)
    journal = _first(item.get("journal_title")) or _first(item.get("journal"))
    year = _extract_year(item.get("year") or item.get("pubyear"))
    issn_matches = []
    for s in strings:
        issn_matches.extend(ISSN_PATTERN.findall(s))
    issn = _dedupe([m.upper() for m in issn_matches])
    links = _extract_links([item.get("link"), item.get("url")])
    identifiers: Dict[str, Any] = {}
    if pmcid:
        identifiers["pmcid"] = pmcid
    return UnifiedLiteratureItem(
        source="pmc",
        title=_clean_text(title) if isinstance(title, str) else _clean_text(title),
        authors=_normalize_authors(item.get("authors")),
        journal=_clean_text(journal),
        year=year,
        doi=_clean_text(doi),
        url=_first(links) if links else None,
        links=links,
        language=_clean_text(item.get("language")),
        issn=issn,
        identifiers=identifiers,
        keywords=_dedupe([_clean_text(v) for v in _as_list(item.get("keywords")) if _clean_text(v)]),
    )


def normalize_jstage_item(item: Dict[str, Any]) -> UnifiedLiteratureItem:
    title = _clean_text(item.get("article_title_en") or item.get("article_title_ja"))
    journal = _clean_text(item.get("material_title_en") or item.get("material_title_ja"))
    doi = _clean_text(item.get("doi"))
    url = _clean_text(item.get("link"))
    issn = _dedupe(
        [
            _clean_text(item.get("issn")),
            _clean_text(item.get("eissn")),
        ]
    )
    return UnifiedLiteratureItem(
        source="jstage",
        title=title,
        authors=[],
        journal=journal,
        year=_extract_year(item.get("pubyear")),
        doi=doi,
        url=url,
        links=_extract_links([url]),
        language="ja" if item.get("article_title_ja") else None,
        issn=issn,
        identifiers={"issn": issn} if issn else {},
        keywords=[],
    )


def normalize_doaj_item(item: Dict[str, Any]) -> UnifiedLiteratureItem:
    title = _clean_text(item.get("title"))
    journal = _clean_text(item.get("journal_title"))
    doi = _clean_text(item.get("doi"))
    url = _clean_text(_first(item.get("links")))
    issn = _dedupe([_clean_text(v) for v in _as_list(item.get("issns")) if _clean_text(v)])
    links = _extract_links([url] + _as_list(item.get("links")))
    return UnifiedLiteratureItem(
        source="doaj",
        title=title,
        authors=[],
        journal=journal,
        year=_extract_year(item.get("year")),
        doi=doi,
        url=url,
        links=links,
        language=None,
        publisher=_clean_text(item.get("publisher")),
        issn=issn,
        identifiers={"issn": issn} if issn else {},
        keywords=_dedupe([_clean_text(v) for v in _as_list(item.get("keywords")) if _clean_text(v)]),
    )


def normalize_pubscholar_item(item: Dict[str, Any]) -> UnifiedLiteratureItem:
    title = _clean_text(item.get("title"))
    authors = _normalize_authors(item.get("authors"))
    journal = _clean_text(item.get("journal"))
    url = _clean_text(item.get("source_link"))
    links = _extract_links([url])
    return UnifiedLiteratureItem(
        source="pubscholar",
        title=title,
        authors=authors,
        journal=journal,
        year=_extract_year(item.get("year")),
        doi=_clean_text(item.get("doi")),
        url=url,
        links=links,
        language=_clean_text(item.get("language")),
        issn=[],
        identifiers={"paper_type": item.get("paper_type")},
        keywords=_dedupe([_clean_text(v) for v in _as_list(item.get("subjects")) if _clean_text(v)]),
    )


def normalize_hans_item(item: Dict[str, Any]) -> UnifiedLiteratureItem:
    title = _clean_text(item.get("title"))
    authors = _normalize_authors(item.get("authors"))
    journal = _clean_text(item.get("journal"))
    url = _clean_text(item.get("detail_link"))
    return UnifiedLiteratureItem(
        source="hans_publishers",
        title=title,
        authors=authors,
        journal=journal,
        year=_extract_year(item.get("year")),
        doi=_clean_text(item.get("doi")),
        url=url,
        links=_extract_links([url]),
        language="zh" if title and re.search(r"[\u4e00-\u9fff]", title) else None,
        keywords=_dedupe([_clean_text(item.get("subject"))]) if item.get("subject") else [],
    )


def normalize_cyberleninka_item(item: Dict[str, Any]) -> UnifiedLiteratureItem:
    title = _clean_text(item.get("title"))
    authors = _normalize_authors(item.get("authors"))
    journal = _clean_text(item.get("journal"))
    url = _clean_text(item.get("detail_link"))
    return UnifiedLiteratureItem(
        source="cyberleninka",
        title=title,
        authors=authors,
        journal=journal,
        year=_extract_year(item.get("year")),
        doi=_clean_text(item.get("doi")),
        url=url,
        links=_extract_links([url]),
        language="ru" if title and re.search(r"[\u0400-\u04FF]", title) else None,
        keywords=_dedupe([_clean_text(item.get("subject"))]) if item.get("subject") else [],
    )


NORMALIZER_MAP = {
    "crossref": normalize_crossref_item,
    "unpaywall": normalize_unpaywall_item,
    "pmc": normalize_pmc_item,
    "jstage": normalize_jstage_item,
    "doaj": normalize_doaj_item,
    "pubscholar": normalize_pubscholar_item,
    "hans_publishers": normalize_hans_item,
    "cyberleninka": normalize_cyberleninka_item,
}


def normalize_items(provider: str, items: List[Dict[str, Any]]) -> List[UnifiedLiteratureItem]:
    normalizer = NORMALIZER_MAP.get(provider)
    if not normalizer:
        return []
    output: List[UnifiedLiteratureItem] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        output.append(normalizer(item))
    return output
