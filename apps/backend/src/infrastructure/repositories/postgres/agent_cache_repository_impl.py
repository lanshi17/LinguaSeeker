"""PostgreSQL implementation of Agent Cache Repository.

Provides caching for agent inputs/outputs to improve performance
and ensure deterministic results with SHA256 input hash keys.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.infrastructure.database.postgres_models import (
    AgentCacheEntry as AgentCacheModel,
)


class AgentCacheRepositoryImpl:
    """PostgreSQL implementation of agent cache repository."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    async def get(self, input_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached agent result by input hash.

        Args:
            input_hash: SHA256 hash of agent input

        Returns:
            Cached result dictionary or None if not found/expired
        """
        # Check if entry exists and is not expired
        stmt = select(AgentCacheModel).where(
            and_(
                AgentCacheModel.input_hash == input_hash,
                AgentCacheModel.expires_at > datetime.utcnow()
            )
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            return {
                "output": model.output,
                "confidence_score": model.confidence_score,
                "latency_ms": model.latency_ms,
                "created_at": model.created_at,
                "expires_at": model.expires_at,
                "model_version": model.model_version,
                "agent_type": model.agent_type,
            }
        return None

    async def set(
        self,
        input_hash: str,
        output: Dict[str, Any],
        confidence_score: Optional[float],
        latency_ms: int,
        model_version: str,
        agent_type: str,
        ttl_hours: int = 24
    ) -> bool:
        """
        Store agent result in cache.

        Args:
            input_hash: SHA256 hash of agent input
            output: Agent output/result
            confidence_score: Confidence score if applicable
            latency_ms: Execution time in milliseconds
            model_version: LLM model version identifier
            agent_type: Type of agent (LAYOUT, TRANSLATION, etc.)
            ttl_hours: Time-to-live in hours (default 24)

        Returns:
            True if stored successfully
        """
        try:
            # Convert output to JSON string if it's a dict
            import json
            output_str = json.dumps(output) if isinstance(output, dict) else str(output)

            expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

            cache_entry = AgentCacheModel(
                input_hash=input_hash,
                output=output_str,
                confidence_score=confidence_score,
                latency_ms=latency_ms,
                model_version=model_version,
                agent_type=agent_type,
                expires_at=expires_at,
            )

            self.session.add(cache_entry)
            await self.session.commit()
            return True

        except IntegrityError:
            # Entry already exists, update it instead
            await self.session.rollback()
            stmt = select(AgentCacheModel).where(AgentCacheModel.input_hash == input_hash)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.output = output_str
                existing.confidence_score = confidence_score
                existing.latency_ms = latency_ms
                existing.model_version = model_version
                existing.agent_type = agent_type
                existing.expires_at = expires_at
                existing.updated_at = datetime.utcnow()

                await self.session.commit()
                return True

            return False

    async def delete(self, input_hash: str) -> bool:
        """
        Delete cache entry by input hash.

        Args:
            input_hash: SHA256 hash of agent input

        Returns:
            True if deleted, False if not found
        """
        stmt = select(AgentCacheModel).where(AgentCacheModel.input_hash == input_hash)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            await self.session.delete(model)
            await self.session.commit()
            return True
        return False

    async def delete_expired(self) -> int:
        """
        Delete all expired cache entries.

        Returns:
            Number of entries deleted
        """
        stmt = select(AgentCacheModel).where(
            AgentCacheModel.expires_at <= datetime.utcnow()
        )
        result = await self.session.execute(stmt)
        expired_entries = result.scalars().all()

        count = len(expired_entries)
        for entry in expired_entries:
            await self.session.delete(entry)

        await self.session.commit()
        return count

    async def clear_all(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries deleted
        """
        stmt = select(AgentCacheModel)
        result = await self.session.execute(stmt)
        all_entries = result.scalars().all()

        count = len(all_entries)
        for entry in all_entries:
            await self.session.delete(entry)

        await self.session.commit()
        return count

    async def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats (total, expired, valid)
        """
        total = await self.session.execute(
            select(func.count()).select_from(AgentCacheModel)
        )
        total_count = total.scalar()

        valid = await self.session.execute(
            select(func.count()).select_from(AgentCacheModel).where(
                AgentCacheModel.expires_at > datetime.utcnow()
            )
        )
        valid_count = valid.scalar()

        return {
            "total_entries": total_count,
            "valid_entries": valid_count,
            "expired_entries": total_count - valid_count,
        }

    async def exists(self, input_hash: str) -> bool:
        """
        Check if cache entry exists and is not expired.

        Args:
            input_hash: SHA256 hash of agent input

        Returns:
            True if valid entry exists
        """
        stmt = select(func.count()).select_from(AgentCacheModel).where(
            and_(
                AgentCacheModel.input_hash == input_hash,
                AgentCacheModel.expires_at > datetime.utcnow()
            )
        )
        result = await self.session.execute(stmt)
        count = result.scalar()
        return count > 0