"""Dashboard aggregation service for frontend overview."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    ProcessingRun,
    RunEvidenceItem,
    SourceDocument,
)


@dataclass
class EvidenceByStatus:
    """Count of evidence items by review status."""
    provisional: int = 0
    approved: int = 0
    corrected: int = 0
    rejected: int = 0


@dataclass
class DashboardSummary:
    """Aggregated dashboard metrics."""
    total_documents: int
    total_processing_runs: int
    total_evidence_items: int
    evidence_by_status: EvidenceByStatus
    avg_confidence: float | None
    recent_runs: list[dict[str, Any]]


class DashboardService:
    """Generate aggregated dashboard data for frontend display."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_summary(self) -> DashboardSummary:
        """Fetch all dashboard metrics in parallel queries."""
        # Total documents
        doc_stmt = select(func.count()).select_from(SourceDocument)
        doc_result = await self._session.execute(doc_stmt)
        total_docs = doc_result.scalar() or 0

        # Total processing runs
        run_stmt = select(func.count()).select_from(ProcessingRun)
        run_result = await self._session.execute(run_stmt)
        total_runs = run_result.scalar() or 0

        # Total canonical evidence items
        evidence_stmt = select(func.count()).select_from(CanonicalEvidenceItem)
        evidence_result = await self._session.execute(evidence_stmt)
        total_evidence = evidence_result.scalar() or 0

        # Evidence grouped by review_status
        status_stmt = (
            select(
                CanonicalEvidenceItem.review_status,
                func.count().label("count"),
            )
            .group_by(CanonicalEvidenceItem.review_status)
        )
        status_result = await self._session.execute(status_stmt)
        status_counts = {row[0]: row[1] for row in status_result}
        evidence_by_status = EvidenceByStatus(
            provisional=status_counts.get("provisional", 0),
            approved=status_counts.get("approved", 0),
            corrected=status_counts.get("corrected", 0),
            rejected=status_counts.get("rejected", 0),
        )

        # Average confidence
        avg_stmt = select(func.avg(CanonicalEvidenceItem.current_best_confidence))
        avg_result = await self._session.execute(avg_stmt)
        avg_conf = avg_result.scalar()
        avg_confidence = float(avg_conf) if avg_conf else None

        # Recent 10 processing runs
        recent_stmt = (
            select(ProcessingRun)
            .order_by(ProcessingRun.created_at.desc())
            .limit(10)
        )
        recent_result = await self._session.execute(recent_stmt)
        recent_runs = [
            {
                "processing_run_id": str(run.processing_run_id),
                "source_document_id": str(run.source_document_id),
                "run_status": run.run_status,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            }
            for run in recent_result.scalars().all()
        ]

        return DashboardSummary(
            total_documents=total_docs,
            total_processing_runs=total_runs,
            total_evidence_items=total_evidence,
            evidence_by_status=evidence_by_status,
            avg_confidence=avg_confidence,
            recent_runs=recent_runs,
        )
