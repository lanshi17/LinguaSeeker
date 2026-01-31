"""PostgreSQL implementation of Audit Log Repository.

Manages immutable audit trail for agent decisions.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.postgres_models import (
    AuditLogEntry as AuditLogModel,
    AgentType,
)


class AuditLogRepositoryImpl:
    """PostgreSQL implementation of audit log repository.

    Audit logs are immutable - no updates or deletes allowed.
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    async def create(
        self,
        task_id: UUID,
        agent_type: str,
        state_from: str,
        state_to: str,
        confidence_score: Optional[float],
        latency_ms: int,
        input_prompt: str,
        output_reasoning: str,
        failure_reason: Optional[str],
        model_version: str,
        token_count: Optional[int],
    ) -> AuditLogModel:
        """Create immutable audit log entry.

        Args:
            task_id: Task UUID
            agent_type: Agent type (LAYOUT, TRANSLATION, etc.)
            state_from: Previous state
            state_to: New state
            confidence_score: Confidence score if applicable
            latency_ms: Agent execution time
            input_prompt: Full prompt sent to agent
            output_reasoning: Agent's response
            failure_reason: Error details if failed
            model_version: LLM model identifier
            token_count: Tokens consumed

        Returns:
            Created audit log entry
        """
        log_entry = AuditLogModel(
            task_id=task_id,
            agent_type=AgentType(agent_type),
            state_from=state_from,
            state_to=state_to,
            confidence_score=confidence_score,
            latency_ms=latency_ms,
            input_prompt=input_prompt,
            output_reasoning=output_reasoning,
            failure_reason=failure_reason,
            model_version=model_version,
            token_count=token_count,
        )

        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        return log_entry

    async def find_by_task_id(
        self, task_id: UUID, limit: int = 100
    ) -> List[AuditLogModel]:
        """Find all audit logs for a task.

        Args:
            task_id: Task UUID
            limit: Maximum logs to return

        Returns:
            List of audit log entries ordered by creation time
        """
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.task_id == task_id)
            .order_by(AuditLogModel.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_agent_type(
        self,
        agent_type: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLogModel]:
        """Find audit logs by agent type.

        Args:
            agent_type: Agent type to filter by
            limit: Maximum logs to return
            offset: Number to skip

        Returns:
            List of audit log entries
        """
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.agent_type == AgentType(agent_type))
            .order_by(AuditLogModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_failures(
        self,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditLogModel]:
        """Find failed agent executions.

        Args:
            since: Only return failures after this timestamp
            limit: Maximum logs to return

        Returns:
            List of failed audit entries
        """
        stmt = select(AuditLogModel).where(
            AuditLogModel.failure_reason.isnot(None)
        )

        if since:
            stmt = stmt.where(AuditLogModel.created_at >= since)

        stmt = stmt.order_by(AuditLogModel.created_at.desc()).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_agent_stats(
        self, agent_type: str, since: Optional[datetime] = None
    ) -> dict:
        """Get statistics for an agent type.

        Args:
            agent_type: Agent type to analyze
            since: Calculate stats from this timestamp

        Returns:
            Dictionary with stats (avg_latency, total_calls, failure_rate, etc.)
        """
        stmt = select(
            func.count(AuditLogModel.id).label("total_calls"),
            func.avg(AuditLogModel.latency_ms).label("avg_latency"),
            func.min(AuditLogModel.latency_ms).label("min_latency"),
            func.max(AuditLogModel.latency_ms).label("max_latency"),
            func.avg(AuditLogModel.confidence_score).label("avg_confidence"),
            func.sum(
                func.case((AuditLogModel.failure_reason.isnot(None), 1), else_=0)
            ).label("failure_count"),
        ).where(AuditLogModel.agent_type == AgentType(agent_type))

        if since:
            stmt = stmt.where(AuditLogModel.created_at >= since)

        result = await self.session.execute(stmt)
        row = result.one()

        total = row.total_calls or 0
        failures = row.failure_count or 0

        return {
            "agent_type": agent_type,
            "total_calls": total,
            "avg_latency_ms": float(row.avg_latency) if row.avg_latency else 0,
            "min_latency_ms": row.min_latency or 0,
            "max_latency_ms": row.max_latency or 0,
            "avg_confidence": float(row.avg_confidence) if row.avg_confidence else 0,
            "failure_count": failures,
            "failure_rate": (failures / total * 100) if total > 0 else 0,
        }

    async def cleanup_old_logs(self, retention_days: int = 90) -> int:
        """Delete audit logs older than retention period.

        Args:
            retention_days: Days to retain logs

        Returns:
            Number of logs deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        stmt = select(AuditLogModel).where(AuditLogModel.created_at < cutoff_date)
        result = await self.session.execute(stmt)
        old_logs = result.scalars().all()

        count = len(old_logs)
        for log in old_logs:
            await self.session.delete(log)

        await self.session.commit()
        return count

    async def count_by_task(self, task_id: UUID) -> int:
        """Count audit logs for a task."""
        stmt = (
            select(func.count())
            .select_from(AuditLogModel)
            .where(AuditLogModel.task_id == task_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar()
