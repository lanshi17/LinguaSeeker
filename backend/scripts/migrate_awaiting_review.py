"""One-time migration: transition awaiting_review runs to completed.

Run once after the orchestrator change (RUNNING → COMPLETED instead of
RUNNING → AWAITING_REVIEW). Existing awaiting_review runs are finalized
to completed with a completed_at timestamp.

Usage:
    cd backend
    uv run python scripts/migrate_awaiting_review.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select, text, func
from src.dao.postgresql.connection import build_async_engine
from src.dao.postgresql.models import PipelineRunState


async def main() -> None:
    engine = build_async_engine()

    jsonb_status = PipelineRunState.state_json["pipeline_status"].astext

    async with engine.begin() as conn:
        count_result = await conn.execute(
            select(func.count())
            .select_from(PipelineRunState)
            .where(jsonb_status == "awaiting_review")
        )
        total = count_result.scalar() or 0

        if total == 0:
            print("No awaiting_review runs found. Nothing to migrate.")
            return

        print(f"Found {total} awaiting_review run(s). Updating to completed...")

        result = await conn.execute(text("""
            UPDATE pipeline_run_states
            SET pipeline_status = 'completed',
                state_json = jsonb_set(
                    jsonb_set(state_json, '{pipeline_status}', '"completed"'),
                    '{completed_at}',
                    to_jsonb(now()::text)
                ),
                updated_at = now()
            WHERE state_json->>'pipeline_status' = 'awaiting_review'
        """))

        print(f"Updated {result.rowcount} run(s) to completed.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
