from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import httpx
from loguru import logger


@dataclass
class ClinVarVariantSummary:
    """Structured subset of ClinVar summary fields used by the backend."""

    variation_id: int
    preferred_name: Optional[str]
    gene_symbol: Optional[str]
    clinvar_accession: Optional[str]
    review_status: Optional[str]
    clinical_significance: Optional[str]
    last_evaluated_at: Optional[datetime]
    synonyms: List[str]
    hgvs_list: List[str]
    trait_names: List[str]
    transcript_id: Optional[str]
    attributes: Dict[str, Any]


class ClinVarApiError(RuntimeError):
    pass


class ClinVarClient:
    """Lightweight wrapper around NCBI ClinVar E-utilities APIs."""

    _BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def search_variation_id(self, term: str) -> Optional[int]:
        params = {
            "db": "clinvar",
            "retmode": "json",
            "term": term,
            "retmax": 1,
        }
        self._apply_api_key(params)
        try:
            resp = self._client.get(f"{self._BASE_URL}/esearch.fcgi", params=params)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # pragma: no cover - network failure
            logger.warning("ClinVar search failed for term {}: {}", term, exc)
            return None
        id_list = payload.get("esearchresult", {}).get("idlist") or []
        if not id_list:
            return None
        try:
            return int(id_list[0])
        except (ValueError, TypeError):
            return None

    def fetch_variant_summary(self, variation_id: int) -> Optional[ClinVarVariantSummary]:
        params = {
            "db": "clinvar",
            "retmode": "json",
            "id": variation_id,
        }
        self._apply_api_key(params)
        try:
            resp = self._client.get(f"{self._BASE_URL}/esummary.fcgi", params=params)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # pragma: no cover - network failure
            logger.warning("ClinVar summary failed for variation {}: {}", variation_id, exc)
            return None

        record = (payload.get("result") or {}).get(str(variation_id))
        if not record:
            return None

        germline = record.get("germline_classification") or {}
        trait_names = [
            trait.get("trait_name")
            for trait in germline.get("trait_set") or []
            if trait.get("trait_name")
        ]
        variation_set = record.get("variation_set") or []
        hgvs_list: List[str] = []
        synonyms: List[str] = []
        transcript_id: Optional[str] = None
        for measure in variation_set:
            variation_name = measure.get("variation_name")
            if variation_name:
                hgvs_list.append(variation_name)
            aliases = measure.get("aliases") or []
            for alias in aliases:
                if alias:
                    synonyms.append(alias)
            transcripts = measure.get("transcripts") or []
            if transcripts and not transcript_id:
                transcript_id = transcripts[0].get("transcript_id")

        genes = record.get("genes") or []
        gene_symbol = genes[0].get("symbol") if genes else None
        preferred_name = record.get("title")
        summary = ClinVarVariantSummary(
            variation_id=variation_id,
            preferred_name=preferred_name,
            gene_symbol=gene_symbol,
            clinvar_accession=record.get("accession"),
            review_status=germline.get("review_status"),
            clinical_significance=germline.get("description"),
            last_evaluated_at=self._parse_date(germline.get("last_evaluated")),
            synonyms=synonyms,
            hgvs_list=hgvs_list,
            trait_names=[t for t in trait_names if t],
            transcript_id=transcript_id,
            attributes={
                "supporting_submissions": record.get("supporting_submissions"),
                "germline_classification": germline,
                "variation_set": variation_set,
            },
        )
        return summary

    def fetch_citations(self, variation_id: int) -> List[str]:
        accession = self._to_accession(variation_id)
        params = {
            "db": "clinvar",
            "id": accession,
            "retmode": "xml",
            "rettype": "vcv",
        }
        self._apply_api_key(params)
        try:
            resp = self._client.get(f"{self._BASE_URL}/efetch.fcgi", params=params)
            resp.raise_for_status()
            xml_text = resp.text
        except Exception as exc:  # pragma: no cover - network failure
            logger.warning("ClinVar citations fetch failed for {}: {}", variation_id, exc)
            return []

        pmids: List[str] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:  # pragma: no cover - bad XML
            logger.warning("ClinVar citation XML parse error for {}: {}", variation_id, exc)
            return []

        for node in root.findall(".//Citation/ID[@Source=PubMed]"):
            if node.text:
                pmid = node.text.strip()
                if pmid:
                    pmids.append(pmid)
        # Deduplicate while preserving order
        seen = set()
        unique_pmids = []
        for pmid in pmids:
            if pmid not in seen:
                seen.add(pmid)
                unique_pmids.append(pmid)
        return unique_pmids

    def _apply_api_key(self, params: Dict[str, Any]) -> None:
        if self._api_key:
            params["api_key"] = self._api_key

    @staticmethod
    def _to_accession(variation_id: int) -> str:
        return f"VCV{variation_id:09d}"

    @staticmethod
    def _parse_date(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        cleaned = raw.strip()
        for pattern in ("%Y/%m/%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(cleaned, pattern)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None
