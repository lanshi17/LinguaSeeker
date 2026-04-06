# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportMissingImports=false, reportRedeclaration=false, reportFunctionMemberAccess=false, reportPossiblyUnboundVariable=false, reportReturnType=false

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from loguru import logger

from src.config import settings as cfg
from src.infrastructure.postgres import get_postgres_client, PostgresClient
from src.infrastructure.models import ClinGenEvidenceProfile, ClinVarVariation, VariationCitation
from src.domain.variant.clinvar_client import ClinVarClient, ClinVarVariantSummary
from src.domain.variant.clingen_client import ClinGenEviRepoClient, ClinGenInterpretation


class VariationDataService:
    """Orchestrates ClinVar + ClinGen lookups and persistence."""

    def __init__(
        self,
        citations_ttl_hours: int = 12,
        scorecard_ttl_hours: int = 12,
    ) -> None:
        self._pg: PostgresClient = get_postgres_client()
        self._clinvar = ClinVarClient(api_key=cfg.pubmed_api_key)
        self._clingen = ClinGenEviRepoClient()
        self._citations_ttl = timedelta(hours=citations_ttl_hours)
        self._scorecard_ttl = timedelta(hours=scorecard_ttl_hours)

    # -------------------- Resolution --------------------
    def resolve_variation(self, variant_hgvs: str) -> Optional[ClinVarVariation]:
        normalized = (variant_hgvs or "").strip()
        if not normalized:
            return None

        existing = self._pg.get_clinvar_variation_by_hgvs(normalized)
        if existing:
            self.sync_clinvar_citations(existing.variation_id)
            self.sync_clingen_profiles(existing.variation_id)
            return existing

        variation_id = self._clinvar.search_variation_id(normalized)
        if not variation_id:
            logger.info("ClinVar variation not found for {}", normalized)
            return None

        summary = self._clinvar.fetch_variant_summary(variation_id)
        if not summary:
            logger.info("ClinVar summary empty for variation {}", variation_id)
            return None

        variation = self._persist_summary(summary, primary_hgvs=normalized)
        self.sync_clinvar_citations(variation_id, force=True)
        self.sync_clingen_profiles(variation_id)
        return variation

    # -------------------- Sync routines --------------------
    def sync_clinvar_citations(self, variation_id: int, force: bool = False) -> None:
        record = self._pg.get_clinvar_variation(variation_id)
        if not record:
            return
        now = datetime.now(timezone.utc)
        if (
            not force
            and record.citations_synced_at
            and now - record.citations_synced_at < self._citations_ttl
        ):
            return

        pmids = self._clinvar.fetch_citations(variation_id)
        entries = [{"pmid": pmid, "metadata": {"source": "ClinVar"}} for pmid in pmids]
        self._pg.replace_variation_citations(variation_id, "clinvar", entries)
        self._pg.upsert_clinvar_variation(variation_id, citations_synced_at=now)

    def sync_clingen_profiles(self, variation_id: int, force: bool = False) -> None:
        record = self._pg.get_clinvar_variation(variation_id)
        if not record:
            return
        now = datetime.now(timezone.utc)
        if (
            not force
            and record.scorecards_synced_at
            and now - record.scorecards_synced_at < self._scorecard_ttl
        ):
            return

        profiles = self._clingen.fetch_variant_interpretations(variation_id)
        payloads = [self._interpretation_to_payload(p) for p in profiles]
        if payloads:
            self._pg.replace_clingen_profiles(variation_id, payloads)
        self._pg.upsert_clinvar_variation(variation_id, scorecards_synced_at=now)

    def record_internal_citation(
        self,
        variation_id: int,
        document_id: str,
        evidence_strength: Optional[str] = None,
        pmid: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            self._pg.upsert_internal_variation_citation(
                variation_id=variation_id,
                document_id=document_id,
                evidence_strength=evidence_strength,
                pmid=pmid,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning(
                "Failed to record internal citation for variation {} doc {}: {}",
                variation_id,
                document_id,
                exc,
            )

    # -------------------- Query helpers --------------------
    def build_variation_payload(self, variation_id: int) -> Dict[str, Any]:
        variation = self._pg.get_clinvar_variation(variation_id)
        if not variation:
            return {}
        citations = self._pg.list_variation_citations(variation_id)
        scorecards = self._pg.list_clingen_profiles(variation_id)
        return {
            "variation": self._variation_to_dict(variation),
            "citations": [self._citation_to_dict(c) for c in citations],
            "scorecards": [self._scorecard_to_dict(s) for s in scorecards],
        }

    # -------------------- Internal transforms --------------------
    def _persist_summary(
        self,
        summary: ClinVarVariantSummary,
        primary_hgvs: Optional[str],
    ) -> ClinVarVariation:
        fields: Dict[str, Any] = {
            "preferred_name": summary.preferred_name,
            "gene_symbol": summary.gene_symbol,
            "clinvar_accession": summary.clinvar_accession,
            "review_status": summary.review_status,
            "clinical_significance": summary.clinical_significance,
            "last_evaluated_at": summary.last_evaluated_at,
            "synonyms": summary.synonyms,
            "hgvs_list": summary.hgvs_list,
            "trait_names": summary.trait_names,
            "transcript_id": summary.transcript_id,
            "attributes": summary.attributes,
            "primary_hgvs": primary_hgvs or summary.preferred_name,
        }
        variation = self._pg.upsert_clinvar_variation(summary.variation_id, **fields)
        return variation

    @staticmethod
    def _variation_to_dict(variation: ClinVarVariation) -> Dict[str, Any]:
        return {
            "variation_id": variation.variation_id,
            "preferred_name": variation.preferred_name,
            "primary_hgvs": variation.primary_hgvs,
            "gene_symbol": variation.gene_symbol,
            "clinvar_accession": variation.clinvar_accession,
            "review_status": variation.review_status,
            "clinical_significance": variation.clinical_significance,
            "last_evaluated_at": variation.last_evaluated_at.isoformat()
            if variation.last_evaluated_at
            else None,
            "synonyms": variation.synonyms or [],
            "trait_names": variation.trait_names or [],
            "transcript_id": variation.transcript_id,
        }

    @staticmethod
    def _citation_to_dict(citation: VariationCitation) -> Dict[str, Any]:
        document_payload: Optional[Dict[str, Any]] = None
        if citation.document is not None:
            document_payload = {
                "document_id": str(citation.document.document_id),
                "title": citation.document.title,
                "pmid": citation.document.pmid,
            }
        return {
            "citation_id": citation.citation_id,
            "source": citation.source,
            "pmid": citation.pmid,
            "document": document_payload,
            "evidence_strength": citation.evidence_strength,
            "notes": citation.notes,
            "metadata": citation.citation_metadata or {},
        }

    @staticmethod
    def _scorecard_to_dict(profile: ClinGenEvidenceProfile) -> Dict[str, Any]:
        return {
            "assertion_id": profile.assertion_id,
            "variation_id": profile.variation_id,
            "disease_label": profile.disease_label,
            "disease_mondo": profile.disease_mondo,
            "expert_panel": profile.expert_panel,
            "classification": profile.classification,
            "published_at": profile.published_at.isoformat() if profile.published_at else None,
            "guideline_label": profile.guideline_label,
            "evidence_codes": profile.evidence_codes or [],
            "score_breakdown": profile.score_breakdown or {},
        }

    @staticmethod
    def _interpretation_to_payload(record: ClinGenInterpretation) -> Dict[str, Any]:
        return {
            "assertion_id": record.assertion_id or record.uuid,
            "disease_label": record.disease_label,
            "disease_mondo": record.disease_mondo,
            "expert_panel": record.expert_panel,
            "classification": record.classification,
            "published_at": record.published_at,
            "guideline_label": record.guideline_label,
            "evidence_codes": record.evidence_codes,
            "score_breakdown": record.score_breakdown,
            "raw_payload": record.raw_payload,
        }


_variation_service: Optional[VariationDataService] = None


def get_variation_data_service() -> VariationDataService:
    global _variation_service
    if _variation_service is None:
        _variation_service = VariationDataService()
    return _variation_service
