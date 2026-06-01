"""Tests for chat API routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_session(async_client: AsyncClient):
    """POST /api/v1/chat/sessions creates a session."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import ChatSessionResponse

    run_id = uuid4()
    session_id = uuid4()
    mock_response = ChatSessionResponse(
        chat_session_id=session_id,
        processing_run_id=run_id,
        user_id=None,
        created_at="2026-06-01T00:00:00Z",
        message_count=0,
    )

    with patch("src.api.v1.chat.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.create_session = AsyncMock(return_value=mock_response)
        mock_factory.return_value.create_chat_service.return_value = mock_service

        response = await async_client.post(
            "/api/v1/chat/sessions",
            json={"processing_run_id": str(run_id)},
        )
        assert response.status_code == 200
        assert response.json()["chat_session_id"] == str(session_id)


@pytest.mark.asyncio
async def test_append_message(async_client: AsyncClient):
    """POST /api/v1/chat/sessions/{id}/messages appends a message."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import ChatMessageResponse

    session_id = uuid4()
    msg_id = uuid4()
    mock_response = ChatMessageResponse(
        message_id=msg_id,
        chat_session_id=session_id,
        role="user",
        content="What is the gene?",
        evidence_id=None,
        entity_id=None,
        created_at="2026-06-01T00:00:00Z",
    )

    with patch("src.api.v1.chat.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.append_message = AsyncMock(return_value=mock_response)
        mock_service.generate_reply = AsyncMock(return_value=None)
        mock_factory.return_value.create_chat_service.return_value = mock_service

        response = await async_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"role": "user", "content": "What is the gene?"},
        )
        assert response.status_code == 200
        assert response.json()["content"] == "What is the gene?"
