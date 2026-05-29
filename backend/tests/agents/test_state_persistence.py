"""Tests for PipelineRunState ORM model."""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.dao.models import PipelineRunState


@pytest.mark.asyncio
async def test_pipeline_run_state_insert(db_session: AsyncSession):
    """PipelineRunState can be inserted."""
    run_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    state = PipelineRunState(
        processing_run_id=run_id,
        source_document_id=doc_id,
        state_json={
            "phase_1_status": {"status": "completed"},
            "phase_2_status": {"status": "running"},
        },
    )
    db_session.add(state)
    await db_session.commit()

    loaded = await db_session.get(PipelineRunState, run_id)
    assert loaded is not None
    assert loaded.source_document_id == doc_id
    assert loaded.state_json["phase_1_status"]["status"] == "completed"


@pytest.mark.asyncio
async def test_pipeline_run_state_update(db_session: AsyncSession):
    """PipelineRunState can be updated in place."""
    run_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    state = PipelineRunState(
        processing_run_id=run_id,
        source_document_id=doc_id,
        state_json={"phase_1_status": {"status": "pending"}},
    )
    db_session.add(state)
    await db_session.commit()

    loaded = await db_session.get(PipelineRunState, run_id)
    loaded.state_json = {
        "phase_1_status": {"status": "completed"},
        "phase_2_status": {"status": "running"},
    }
    await db_session.commit()

    reloaded = await db_session.get(PipelineRunState, run_id)
    assert reloaded.state_json["phase_2_status"]["status"] == "running"
