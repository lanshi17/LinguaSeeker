from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger


@dataclass
class ClinGenInterpretation:
    variation_id: int
    uuid: str
    assertion_id: str
    disease_label: Optional[str]
    disease_mondo: Optional[str]
    expert_panel: Optional[str]
    classification: Optional[str]
    published_at: Optional[date]
    guideline_label: Optional[str]
    evidence_codes: List[Dict[str, Any]]
    score_breakdown: Dict[str, Any]
    raw_payload: Dict[str, Any]


class ClinGenEviRepoError(RuntimeError):
    pass


class ClinGenEviRepoClient:
    """Thin HTTP client for ClinGen Evidence Repository."""

    _BASE_URL = "https://erepo.genome.network/evrepo/api"

    def __init__(self, timeout: float = 10.0, client: Optional[httpx.Client] = None) -> None:
        self._timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def fetch_variant_interpretations(self, variation_id: int) -> List[ClinGenInterpretation]:
        params = {
            "variationId": variation_id,
            "matchMode": "exact",
            "matchLimit": 50,
        }
        try:
            resp = self._client.get(f"{self._BASE_URL}/classifications", params=params)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # pragma: no cover - network failure
            logger.warning("ClinGen query failed for variation {}: {}", variation_id, exc)
            return []

        interpretations = payload.get("variantInterpretations") or []
        parsed: List[ClinGenInterpretation] = []
        for record in interpretations:
            parsed.append(self._parse_interpretation(record))
        return parsed

    @staticmethod
    def _parse_interpretation(record: Dict[str, Any]) -> ClinGenInterpretation:
        variation_id = int(record.get("variationId") or 0)
        guideline = (record.get("guidelines") or [None])[0] or {}
        agents = guideline.get("agents") or []
        expert_panel = None
        evidence_codes: List[Dict[str, Any]] = []
        for agent in agents:
            if not expert_panel:
                expert_panel = agent.get("affiliation") or agent.get("label")
            for code in agent.get("evidenceCodes") or []:
                evidence_codes.append(
                    {
                        "code": code.get("label"),
                        "status": code.get("status"),
                        "uri": code.get("@id"),
                        "agent": agent.get("label") or agent.get("affiliation"),
                    }
                )
        score_breakdown = {
            code.get("label"): code.get("status") for code in guideline.get("evidenceCodes", []) or []
        }
        published_at = ClinGenEviRepoClient._parse_date(record.get("publishedDate"))
        return ClinGenInterpretation(
            variation_id=variation_id,
            uuid=record.get("uuid") or record.get("@id") or "",
            assertion_id=record.get("@id") or record.get("uuid") or "",
            disease_label=(record.get("condition") or {}).get("label"),
            disease_mondo=(record.get("condition") or {}).get("@id"),
            expert_panel=expert_panel,
            classification=(guideline.get("outcome") or {}).get("label"),
            published_at=published_at,
            guideline_label=guideline.get("label"),
            evidence_codes=evidence_codes,
            score_breakdown=score_breakdown,
            raw_payload=record,
        )

    @staticmethod
    def _parse_date(raw: Optional[str]) -> Optional[date]:
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None
