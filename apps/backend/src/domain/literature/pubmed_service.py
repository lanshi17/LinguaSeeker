from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import httpx

from src.config import settings


@dataclass(frozen=True)
class PubMedCandidate:
    pmid: str
    title: str
    journal: str
    pub_date: str


@dataclass(frozen=True)
class PubMedArticle:
    pmid: str
    title: str
    journal: str
    pub_date: str
    abstract: str
    doi: Optional[str] = None


class PubMedService:
    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 20.0,
    ) -> None:
        self._base_url = (base_url or settings.pubmed_base_url).rstrip("/")
        self._api_key = api_key or settings.pubmed_api_key
        self._timeout = timeout

    async def search_candidates(
        self,
        query: str,
        country: str = "不限",
        candidate_limit: int = 15,
    ) -> List[PubMedCandidate]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            raise ValueError("query is required")

        limit = max(1, min(int(candidate_limit or 15), 15))
        term = normalized_query
        normalized_country = str(country or "").strip()
        if normalized_country and normalized_country not in {"不限", "all", "auto"}:
            term = f"({normalized_query}) AND ({normalized_country}[Affiliation])"

        search_resp = await self._request_json(
            "/esearch.fcgi",
            params={
                "db": "pubmed",
                "retmode": "json",
                "retmax": limit,
                "sort": "relevance",
                "term": term,
            },
        )
        id_list = (
            (search_resp.get("esearchresult") or {}).get("idlist")
            if isinstance(search_resp, dict)
            else None
        ) or []
        pmids = [str(pmid).strip() for pmid in id_list if str(pmid).strip()]
        if not pmids:
            return []

        summary_resp = await self._request_json(
            "/esummary.fcgi",
            params={
                "db": "pubmed",
                "retmode": "json",
                "id": ",".join(pmids),
            },
        )
        result = (
            (summary_resp or {}).get("result") if isinstance(summary_resp, dict) else {}
        )
        rows: List[PubMedCandidate] = []
        for pmid in pmids:
            item = result.get(pmid) if isinstance(result, dict) else None
            if not isinstance(item, dict):
                continue
            rows.append(
                PubMedCandidate(
                    pmid=pmid,
                    title=str(item.get("title") or f"PMID:{pmid}"),
                    journal=str(
                        item.get("fulljournalname") or item.get("source") or ""
                    ),
                    pub_date=str(item.get("pubdate") or ""),
                )
            )
        return rows

    async def fetch_article_metadata_abstract(
        self, pmid: str
    ) -> Optional[PubMedArticle]:
        normalized_pmid = str(pmid or "").strip()
        if not normalized_pmid:
            raise ValueError("pmid is required")

        summary_resp = await self._request_json(
            "/esummary.fcgi",
            params={
                "db": "pubmed",
                "retmode": "json",
                "id": normalized_pmid,
            },
        )
        result = (
            (summary_resp or {}).get("result") if isinstance(summary_resp, dict) else {}
        )
        item = result.get(normalized_pmid) if isinstance(result, dict) else None
        if not isinstance(item, dict):
            return None

        title = str(item.get("title") or f"PMID:{normalized_pmid}")
        journal = str(item.get("fulljournalname") or item.get("source") or "")
        pub_date = str(item.get("pubdate") or "")

        xml_text = await self._request_text(
            "/efetch.fcgi",
            params={
                "db": "pubmed",
                "retmode": "xml",
                "id": normalized_pmid,
            },
        )
        abstract, doi = self._parse_abstract_and_doi(xml_text)
        return PubMedArticle(
            pmid=normalized_pmid,
            title=title,
            journal=journal,
            pub_date=pub_date,
            abstract=abstract,
            doi=doi,
        )

    async def _request_json(
        self,
        path: str,
        *,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = dict(params)
        if self._api_key:
            merged["api_key"] = self._api_key
        async with httpx.AsyncClient(
            timeout=self._timeout, follow_redirects=True
        ) as client:
            response = await client.get(f"{self._base_url}{path}", params=merged)
            response.raise_for_status()
            payload = response.json()
        return payload if isinstance(payload, dict) else {}

    async def _request_text(
        self,
        path: str,
        *,
        params: Dict[str, Any],
    ) -> str:
        merged = dict(params)
        if self._api_key:
            merged["api_key"] = self._api_key
        async with httpx.AsyncClient(
            timeout=self._timeout, follow_redirects=True
        ) as client:
            response = await client.get(f"{self._base_url}{path}", params=merged)
            response.raise_for_status()
            return response.text

    @staticmethod
    def _parse_abstract_and_doi(xml_text: str) -> tuple[str, Optional[str]]:
        abstract_parts: List[str] = []
        doi: Optional[str] = None
        if not xml_text:
            return "", None
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return "", None

        for node in root.findall(".//AbstractText"):
            content = "".join(node.itertext()).strip()
            if content:
                label = node.attrib.get("Label")
                if label:
                    abstract_parts.append(f"{label}: {content}")
                else:
                    abstract_parts.append(content)
        for article_id in root.findall(".//ArticleId"):
            id_type = str(article_id.attrib.get("IdType") or "").lower()
            if id_type == "doi":
                value = "".join(article_id.itertext()).strip()
                if value:
                    doi = value
                    break

        return "\n\n".join(abstract_parts), doi


_pubmed_service: Optional[PubMedService] = None


def get_pubmed_service() -> PubMedService:
    global _pubmed_service
    if _pubmed_service is None:
        _pubmed_service = PubMedService()
    return _pubmed_service
