from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

import httpx

from src.config import settings as cfg


_COUNTRY_MAP: Dict[str, str] = {
    "不限": "ALL",
    "all": "ALL",
    "us": "US",
    "uk": "UK",
    "ca": "CA",
    "au": "AU",
    "nz": "NZ",
    "ie": "IE",
    "sg": "SG",
    "in": "IN",
    "za": "ZA",
    "ng": "NG",
    "cn": "CN",
    "my": "MY",
    "hk": "HK",
    "mo": "MO",
    "tw": "TW",
}


@dataclass
class PubMedCandidate:
    pmid: str
    title: str
    journal: str
    pub_date: str


@dataclass
class PubMedArticle:
    pmid: str
    title: str
    journal: str
    pub_date: str
    abstract: str


class PubMedService:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.base_url = (base_url or cfg.pubmed_base_url).rstrip("/")
        self.api_key = api_key or cfg.pubmed_api_key

    @staticmethod
    def normalize_country(country: str) -> str:
        normalized = (country or "不限").strip().lower()
        if normalized in _COUNTRY_MAP:
            return _COUNTRY_MAP[normalized]
        upper = (country or "").strip().upper()
        if upper in _COUNTRY_MAP.values():
            return upper
        raise ValueError("Fetch no result: unsupported country mapping")

    async def search_candidates(
        self,
        query: str,
        country: str,
        candidate_limit: int = 15,
    ) -> List[PubMedCandidate]:
        country_code = self.normalize_country(country)
        term = (query or "").strip()
        if not term:
            return []

        if country_code != "ALL":
            term = f"({term}) AND ({country_code}[ad])"

        params: Dict[str, Any] = {
            "db": "pubmed",
            "term": term,
            "retmax": max(1, min(candidate_limit, 15)),
            "retmode": "json",
            "sort": "pub date",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        async with httpx.AsyncClient(timeout=15.0) as client:
            esearch_resp = await client.get(f"{self.base_url}/esearch.fcgi", params=params)
            esearch_resp.raise_for_status()
            esearch_payload = esearch_resp.json()

            pmids: List[str] = (
                esearch_payload.get("esearchresult", {}).get("idlist", []) or []
            )
            if not pmids:
                return []

            summary_params: Dict[str, Any] = {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "json",
            }
            if self.api_key:
                summary_params["api_key"] = self.api_key
            summary_resp = await client.get(f"{self.base_url}/esummary.fcgi", params=summary_params)
            summary_resp.raise_for_status()
            summary_payload = summary_resp.json()

        records = summary_payload.get("result", {})
        candidates: List[PubMedCandidate] = []
        for pmid in pmids:
            row = records.get(pmid, {})
            if not row:
                continue
            candidates.append(
                PubMedCandidate(
                    pmid=pmid,
                    title=str(row.get("title") or "").strip(),
                    journal=str(row.get("fulljournalname") or row.get("source") or "").strip(),
                    pub_date=str(row.get("pubdate") or "").strip(),
                )
            )
        return candidates

    async def fetch_article_metadata_abstract(self, pmid: str) -> Optional[PubMedArticle]:
        normalized_pmid = str(pmid or "").strip()
        if not normalized_pmid:
            return None

        summary_params: Dict[str, Any] = {
            "db": "pubmed",
            "id": normalized_pmid,
            "retmode": "json",
        }
        if self.api_key:
            summary_params["api_key"] = self.api_key

        fetch_params: Dict[str, Any] = {
            "db": "pubmed",
            "id": normalized_pmid,
            "retmode": "xml",
        }
        if self.api_key:
            fetch_params["api_key"] = self.api_key

        async with httpx.AsyncClient(timeout=15.0) as client:
            summary_resp = await client.get(f"{self.base_url}/esummary.fcgi", params=summary_params)
            summary_resp.raise_for_status()
            summary_payload = summary_resp.json()

            fetch_resp = await client.get(f"{self.base_url}/efetch.fcgi", params=fetch_params)
            fetch_resp.raise_for_status()
            fetch_xml = fetch_resp.text

        row = summary_payload.get("result", {}).get(normalized_pmid, {})
        if not row:
            return None

        abstract_fragments: List[str] = []
        try:
            root = ET.fromstring(fetch_xml)
            for node in root.findall(".//Abstract/AbstractText"):
                text = "".join(node.itertext()).strip()
                if text:
                    abstract_fragments.append(text)
        except ET.ParseError:
            abstract_fragments = []

        abstract_text = "\n\n".join(abstract_fragments).strip()
        return PubMedArticle(
            pmid=normalized_pmid,
            title=str(row.get("title") or "").strip(),
            journal=str(row.get("fulljournalname") or row.get("source") or "").strip(),
            pub_date=str(row.get("pubdate") or "").strip(),
            abstract=abstract_text,
        )


_pubmed_service: Optional[PubMedService] = None


def get_pubmed_service() -> PubMedService:
    global _pubmed_service
    if _pubmed_service is None:
        _pubmed_service = PubMedService()
    return _pubmed_service
