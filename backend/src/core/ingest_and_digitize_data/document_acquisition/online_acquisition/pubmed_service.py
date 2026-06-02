"""PubMed esearch/esummary/efetch integration (async)."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class OnlineAcquisitionPubMedCandidate:
    pmid: str
    pmcid: str = ""
    doi: str = ""
    title: str = ""
    journal: str = ""
    pub_date: str = ""

    @property
    def pmc_pdf_url(self) -> str:
        """Direct PMC PDF URL if PMCID is available."""
        if self.pmcid:
            return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{self.pmcid}/pdf/"
        return ""


@dataclass
class OnlineAcquisitionPubMedArticle:
    pmid: str
    title: str
    journal: str
    pub_date: str
    abstract: str


class OnlineAcquisitionPubMedService:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("PUBMED_BASE_URL", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils")
        ).rstrip("/")
        self.api_key = api_key or os.getenv("PUBMED_API_KEY", "")

    async def search_candidates(
        self,
        query: str,
        candidate_limit: int = 15,
    ) -> List[OnlineAcquisitionPubMedCandidate]:
        """Search PubMed and return candidate list."""
        term = (query or "").strip()
        if not term:
            return []

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
            summary_resp = await client.get(
                f"{self.base_url}/esummary.fcgi", params=summary_params
            )
            summary_resp.raise_for_status()
            summary_payload = summary_resp.json()

        records = summary_payload.get("result", {})
        candidates: List[OnlineAcquisitionPubMedCandidate] = []
        for pmid in pmids:
            row = records.get(pmid, {})
            if not row:
                continue
            # Extract PMCID and DOI from articleids
            pmcid = ""
            doi = ""
            for aid in row.get("articleids", []) or []:
                idtype = str(aid.get("idtype", "")).lower()
                value = str(aid.get("value", "")).strip()
                if idtype == "pmc" and not pmcid:
                    pmcid = value
                elif idtype == "doi" and not doi:
                    doi = value
            candidates.append(
                OnlineAcquisitionPubMedCandidate(
                    pmid=pmid,
                    pmcid=pmcid,
                    doi=doi,
                    title=str(row.get("title") or "").strip(),
                    journal=str(
                        row.get("fulljournalname") or row.get("source") or ""
                    ).strip(),
                    pub_date=str(row.get("pubdate") or "").strip(),
                )
            )
        return candidates

    async def fetch_article(self, pmid: str) -> Optional[OnlineAcquisitionPubMedArticle]:
        """Fetch full article metadata + abstract by PMID."""
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
            summary_resp = await client.get(
                f"{self.base_url}/esummary.fcgi", params=summary_params
            )
            summary_resp.raise_for_status()
            summary_payload = summary_resp.json()

            fetch_resp = await client.get(
                f"{self.base_url}/efetch.fcgi", params=fetch_params
            )
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
        return OnlineAcquisitionPubMedArticle(
            pmid=normalized_pmid,
            title=str(row.get("title") or "").strip(),
            journal=str(
                row.get("fulljournalname") or row.get("source") or ""
            ).strip(),
            pub_date=str(row.get("pubdate") or "").strip(),
            abstract=abstract_text,
        )


_pubmed_service: Optional[OnlineAcquisitionPubMedService] = None


def get_pubmed_service() -> OnlineAcquisitionPubMedService:
    global _pubmed_service
    if _pubmed_service is None:
        _pubmed_service = OnlineAcquisitionPubMedService()
    return _pubmed_service
