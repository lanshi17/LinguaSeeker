"""Dashboard aggregation API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    DashboardSummaryResponse,
    EvidenceByStatusResponse,
    ProcessingRunSummary,
)
from src.core.visualize_evidence_with_expert_in_loop.dashboard_service import (
    DashboardService,
)

router = APIRouter()


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    session: AsyncSession = Depends(get_db_session),
) -> DashboardSummaryResponse:
    """Get aggregated dashboard metrics for the frontend overview.

    Returns:
        - Total counts (documents, runs, evidence items)
        - Evidence grouped by review status
        - Average confidence score
        - Recent 10 processing runs
    """
    service = DashboardService(session)
    summary = await service.get_summary()

    return DashboardSummaryResponse(
        total_documents=summary.total_documents,
        total_processing_runs=summary.total_processing_runs,
        total_evidence_items=summary.total_evidence_items,
        evidence_by_status=EvidenceByStatusResponse(
            provisional=summary.evidence_by_status.provisional,
            approved=summary.evidence_by_status.approved,
            corrected=summary.evidence_by_status.corrected,
            rejected=summary.evidence_by_status.rejected,
        ),
        avg_confidence=summary.avg_confidence,
        recent_runs=[
            ProcessingRunSummary(
                processing_run_id=run["processing_run_id"],
                source_document_id=run["source_document_id"],
                run_status=run["run_status"],
                created_at=run["created_at"],
                completed_at=run["completed_at"],
            )
            for run in summary.recent_runs
        ],
    )
