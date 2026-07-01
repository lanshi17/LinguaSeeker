"""Literature profile repository — aggregation and persistence of evidence groups.

Builds and maintains the ``literature_profiles`` table, which stores a
per-document aggregated view of ``canonical_evidence_items`` grouped into
``evidence_groups`` JSONB.
"""

from __future__ import annotations

import json
import uuid
from collections import OrderedDict
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select

from src.dao.postgresql.contracts import LiteratureProfileRow, LiteratureProfileSearchItem
from src.utils.parsing import parse_gene_from_group_id, parse_variant_from_group_id
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    LiteratureProfile,
    SourceDocument,
    SourceDocumentIdentifier,
)

# ── Summary field sets (first-match-wins per category) ───────────────────────

_GENE_FIELDS = ("A.gene_symbol", "A.gene_aliases")
_VARIANT_FIELDS = ("A.variant_hgvs", "A.variant_hgvs_p", "A.variant_hgvs_c", "A.variant_rs_id")
_DISEASE_FIELDS = ("B.disease_diagnosis", "B.clinical_diagnosis", "B.hpo_terms")
_CLASSIFICATION_FIELDS = ("J.authority_classification", "J.clinvar_assertion")

# Worst-case ordering: highest index = worst.
_REVIEW_SEVERITY: dict[str, int] = {
    "provisional": 0,
    "approved": 1,
    "corrected": 2,
    "rejected": 3,
}


def _coerce_str(val: Any) -> str:
    """Normalize a payload value to string for consistent JSONB storage."""
    if val is None:
        return ""
    if isinstance(val, (list, dict)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def _coerce_json_number(val: Any) -> float | int | str | None:
    """Normalize numeric values for JSONB storage."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (float, int)):
        return val
    return str(val)


# ── Repository ───────────────────────────────────────────────────────────────


class LiteratureProfileRepository:
    """Manages the ``literature_profiles`` read model.

    Builds ``evidence_groups`` JSONB from ``canonical_evidence_items`` and
    exposes search/retrieval over the aggregated profiles.
    """

    def __init__(self, session: Any) -> None:
        """Wrap an async SQLAlchemy session.

        The session parameter is typed as ``Any`` so mock-friendly test
        sessions can be passed alongside real ``AsyncSession`` instances.
        """
        self._session = session

    # ── Pure aggregation ──────────────────────────────────────────────────

    def _build_evidence_groups(self, canonical_rows: list) -> list[dict]:
        """Group canonical ORM rows into the evidence_groups structure.

        Args:
            canonical_rows: List of CanonicalEvidenceItem ORM objects.

        Returns:
            List of group dicts with ``group_id``, ``summary``, ``avg_confidence``,
            ``field_count``, ``review_status``, and ``fields``.
        """
        groups: OrderedDict[str, dict] = OrderedDict()

        for row in canonical_rows:
            payload = row.active_payload or {}
            group_id = payload.get("group_id", "")
            if not group_id:
                continue

            if group_id not in groups:
                groups[group_id] = {
                    "group_id": group_id,
                    "summary": {
                        "gene": None,
                        "variant": None,
                        "disease": None,
                        "classification": None,
                    },
                    "confidences": [],
                    "review_status": "provisional",
                    "fields": [],
                }

            grp = groups[group_id]

            conf = row.current_best_confidence
            if conf is not None:
                grp["confidences"].append(float(conf))

            row_status = row.review_status
            if _REVIEW_SEVERITY.get(row_status, 0) > _REVIEW_SEVERITY.get(grp["review_status"], 0):
                grp["review_status"] = row_status

            grp["fields"].append(
                {
                    "canonical_evidence_id": str(row.canonical_evidence_id),
                    "field_id": payload.get("field_id", row.field_id),
                    "field_name": payload.get("field_name", ""),
                    "category": payload.get("category", ""),
                    "value": _coerce_str(payload.get("value")),
                    "confidence": _coerce_json_number(
                        payload.get("confidence", row.current_best_confidence),
                    ),
                    "status": payload.get("status", ""),
                    "track": payload.get("track", ""),
                }
            )

            field_id = row.field_id
            summary = grp["summary"]

            if summary["gene"] is None and field_id in _GENE_FIELDS:
                val = _coerce_str(payload.get("value"))
                if val:
                    summary["gene"] = val

            if summary["variant"] is None and field_id in _VARIANT_FIELDS:
                val = _coerce_str(payload.get("value"))
                if val:
                    summary["variant"] = val

            if summary["disease"] is None and field_id in _DISEASE_FIELDS:
                val = _coerce_str(payload.get("value"))
                if val:
                    summary["disease"] = val

            if summary["classification"] is None and field_id in _CLASSIFICATION_FIELDS:
                val = _coerce_str(payload.get("value"))
                if val:
                    summary["classification"] = val

        for grp in groups.values():
            if not grp["summary"]["gene"]:
                grp["summary"]["gene"] = parse_gene_from_group_id(grp["group_id"])
            if not grp["summary"]["variant"]:
                grp["summary"]["variant"] = parse_variant_from_group_id(grp["group_id"])

        result: list[dict] = []
        for grp in groups.values():
            confs = grp["confidences"]
            result.append(
                {
                    "group_id": grp["group_id"],
                    "summary": grp["summary"],
                    "avg_confidence": round(sum(confs) / len(confs), 4) if confs else 0.0,
                    "field_count": len(grp["fields"]),
                    "review_status": grp["review_status"],
                    "fields": grp["fields"],
                }
            )

        return result

    # ── Refresh ───────────────────────────────────────────────────────────

    async def refresh_for_document(self, source_document_id: uuid.UUID) -> None:
        """Rebuild the literature profile for one document.

        Steps:
            1. Load SourceDocumentIdentifier rows (pmid, doi).
            2. Load SourceDocument row (raw_metadata).
            3. Load all CanonicalEvidenceItem rows.
            4. Aggregate into evidence_groups.
            5. Compute statistics.
            6. Upsert via ON CONFLICT DO UPDATE.
            7. Commit.
        """
        # 1. Identifiers (pmid, doi).
        id_result = await self._session.execute(
            select(
                SourceDocumentIdentifier.identifier_type,
                SourceDocumentIdentifier.identifier_value,
            ).where(
                SourceDocumentIdentifier.source_document_id == source_document_id,
            )
        )
        id_rows = id_result.all()
        pmid: str | None = None
        doi: str | None = None
        for id_type, id_value in id_rows:
            if id_type == "pmid":
                pmid = id_value
            elif id_type == "doi":
                doi = id_value

        # 2. Source document metadata.
        sd_result = await self._session.execute(
            select(SourceDocument).where(
                SourceDocument.source_document_id == source_document_id,
            )
        )
        source_doc = sd_result.scalar_one_or_none()
        raw_meta: dict = {}
        if source_doc is not None:
            raw_meta = source_doc.raw_metadata or {}

        title = raw_meta.get("title")
        authors = raw_meta.get("authors", [])
        journal = raw_meta.get("journal")
        publication_year = raw_meta.get("publication_year")
        latest_run_id = source_doc.latest_processing_run_id if source_doc is not None else None

        # 3. Canonical evidence items (ORM objects).
        cei_result = await self._session.execute(
            select(CanonicalEvidenceItem)
            .where(CanonicalEvidenceItem.source_document_id == source_document_id)
            .order_by(
                CanonicalEvidenceItem.active_payload["group_id"],
                CanonicalEvidenceItem.field_id,
            )
        )
        canonical_rows = list(cei_result.scalars().all())

        # 4. Aggregate (pass ORM objects directly).
        evidence_groups = self._build_evidence_groups(canonical_rows)

        # 5. Statistics.
        total_fields = len(canonical_rows)
        found_count = sum(1 for r in canonical_rows if (r.active_payload or {}).get("status") == "found")
        not_found_count = total_fields - found_count

        conf_values = [
            float(r.current_best_confidence) for r in canonical_rows if r.current_best_confidence is not None
        ]
        overall_confidence = round(sum(conf_values) / len(conf_values), 4) if conf_values else None

        review_status = "provisional"
        for r in canonical_rows:
            rs = r.review_status
            if _REVIEW_SEVERITY.get(rs, 0) > _REVIEW_SEVERITY.get(review_status, 0):
                review_status = rs

        # 6. Upsert.
        stmt = pg_insert(LiteratureProfile).values(
            literature_profile_id=uuid.uuid4(),
            source_document_id=source_document_id,
            pmid=pmid,
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            publication_year=publication_year,
            evidence_groups=evidence_groups,
            review_status=review_status,
            overall_confidence=overall_confidence,
            total_evidence_fields=total_fields,
            found_count=found_count,
            not_found_count=not_found_count,
            latest_processing_run_id=latest_run_id,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[LiteratureProfile.source_document_id],
            set_={
                "pmid": stmt.excluded.pmid,
                "doi": stmt.excluded.doi,
                "title": stmt.excluded.title,
                "authors": stmt.excluded.authors,
                "journal": stmt.excluded.journal,
                "publication_year": stmt.excluded.publication_year,
                "evidence_groups": stmt.excluded.evidence_groups,
                "review_status": stmt.excluded.review_status,
                "overall_confidence": stmt.excluded.overall_confidence,
                "total_evidence_fields": stmt.excluded.total_evidence_fields,
                "found_count": stmt.excluded.found_count,
                "not_found_count": stmt.excluded.not_found_count,
                "latest_processing_run_id": stmt.excluded.latest_processing_run_id,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

    # ── Queries ───────────────────────────────────────────────────────────

    async def get_by_document(self, source_document_id: uuid.UUID) -> LiteratureProfileRow | None:
        """Return the literature profile as a typed contract, or None if not found."""
        result = await self._session.execute(
            select(LiteratureProfile).where(
                LiteratureProfile.source_document_id == source_document_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None

        return LiteratureProfileRow(
            literature_profile_id=str(row.literature_profile_id),
            source_document_id=str(row.source_document_id),
            pmid=row.pmid,
            doi=row.doi,
            title=row.title,
            authors=row.authors,
            journal=row.journal,
            publication_year=row.publication_year,
            evidence_groups=row.evidence_groups,
            review_status=row.review_status,
            review_notes=row.review_notes,
            overall_confidence=float(row.overall_confidence) if row.overall_confidence is not None else None,
            total_evidence_fields=row.total_evidence_fields,
            found_count=row.found_count,
            not_found_count=row.not_found_count,
            created_at=row.created_at.isoformat() if row.created_at else None,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        )

    async def search(
        self,
        *,
        gene: str | None = None,
        variant: str | None = None,
        disease: str | None = None,
        pmid: str | None = None,
        doi: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[LiteratureProfileSearchItem], int]:
        """Search literature profiles with optional filters.

        All filter conditions are OR-combined. Returns ``(items, total_count)``.
        """
        conditions: list = []

        if pmid:
            conditions.append(LiteratureProfile.pmid == pmid)

        if doi:
            conditions.append(LiteratureProfile.doi.ilike(f"%{doi}%"))

        if gene:
            conditions.append(LiteratureProfile.evidence_groups.contains([{"summary": {"gene": gene}}]))

        if variant:
            conditions.append(LiteratureProfile.evidence_groups.contains([{"summary": {"variant": variant}}]))

        if disease:
            conditions.append(LiteratureProfile.evidence_groups.contains([{"summary": {"disease": disease}}]))

        base_stmt = select(LiteratureProfile)
        if conditions:
            base_stmt = base_stmt.where(or_(*conditions))

        # Count query.
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        count_result = await self._session.execute(count_stmt)
        total_count = count_result.scalar_one()

        # Data query with pagination.
        offset = (page - 1) * page_size
        data_stmt = base_stmt.order_by(LiteratureProfile.updated_at.desc()).offset(offset).limit(page_size)
        data_result = await self._session.execute(data_stmt)
        rows = data_result.scalars().all()

        items: list[LiteratureProfileSearchItem] = []
        for row in rows:
            eg = row.evidence_groups or []
            merged: dict[str, str | None] = {
                "gene": None,
                "variant": None,
                "disease": None,
                "classification": None,
            }
            for group in eg:
                s = group.get("summary", {})
                for key in merged:
                    if merged[key] is None and s.get(key):
                        merged[key] = s[key]

            items.append(
                LiteratureProfileSearchItem(
                    literature_profile_id=str(row.literature_profile_id),
                    source_document_id=str(row.source_document_id),
                    pmid=row.pmid,
                    doi=row.doi,
                    title=row.title,
                    journal=row.journal,
                    publication_year=row.publication_year,
                    review_status=row.review_status,
                    overall_confidence=(float(row.overall_confidence) if row.overall_confidence is not None else None),
                    total_evidence_fields=row.total_evidence_fields,
                    found_count=row.found_count,
                    evidence_group_count=len(eg),
                    gene=merged["gene"],
                    variant=merged["variant"],
                    disease=merged["disease"],
                    classification=merged["classification"],
                    created_at=row.created_at.isoformat() if row.created_at else None,
                )
            )

        return items, total_count
