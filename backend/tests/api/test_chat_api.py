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
async def test_create_standalone_session_api(async_client: AsyncClient):
    """POST /api/v1/chat/sessions accepts an empty body for standalone chat."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import ChatSessionResponse

    session_id = uuid4()
    mock_response = ChatSessionResponse(
        chat_session_id=session_id,
        processing_run_id=None,
        user_id=None,
        created_at="2026-06-11T00:00:00Z",
        message_count=0,
    )

    with patch("src.api.v1.chat.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.create_session = AsyncMock(return_value=mock_response)
        mock_factory.return_value.create_chat_service.return_value = mock_service

        response = await async_client.post("/api/v1/chat/sessions", json={})

    assert response.status_code == 200
    assert response.json()["chat_session_id"] == str(session_id)
    assert response.json()["processing_run_id"] is None
    mock_service.create_session.assert_awaited_once_with(
        processing_run_id=None,
        user_id=None,
    )


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


@pytest.mark.asyncio
async def test_append_message_does_not_generate_reply_by_default(
    async_client: AsyncClient,
):
    """Message append is persist-only unless auto_reply is explicitly requested."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import ChatMessageResponse

    session_id = uuid4()
    msg_id = uuid4()
    mock_response = ChatMessageResponse(
        message_id=msg_id,
        chat_session_id=session_id,
        role="user",
        content="What is BRCA1?",
        evidence_id=None,
        entity_id=None,
        created_at="2026-06-11T00:00:00Z",
    )

    with patch("src.api.v1.chat.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.append_message = AsyncMock(return_value=mock_response)
        mock_service.generate_reply = AsyncMock(return_value="BRCA1 answer")
        mock_factory.return_value.create_chat_service.return_value = mock_service

        response = await async_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"role": "user", "content": "What is BRCA1?"},
        )

    assert response.status_code == 200
    mock_service.generate_reply.assert_not_called()


@pytest.mark.asyncio
async def test_append_message_can_generate_reply_when_requested(
    async_client: AsyncClient,
):
    """Legacy non-streaming callers can opt into generated assistant replies."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import ChatMessageResponse

    session_id = uuid4()
    user_msg_id = uuid4()
    assistant_msg_id = uuid4()
    user_response = ChatMessageResponse(
        message_id=user_msg_id,
        chat_session_id=session_id,
        role="user",
        content="What is BRCA1?",
        evidence_id=None,
        entity_id=None,
        created_at="2026-06-11T00:00:00Z",
    )
    assistant_response = ChatMessageResponse(
        message_id=assistant_msg_id,
        chat_session_id=session_id,
        role="assistant",
        content="BRCA1 answer",
        evidence_id=None,
        entity_id=None,
        created_at="2026-06-11T00:00:01Z",
    )

    with patch("src.api.v1.chat.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.append_message = AsyncMock(side_effect=[user_response, assistant_response])
        mock_service.generate_reply = AsyncMock(return_value="BRCA1 answer")
        mock_factory.return_value.create_chat_service.return_value = mock_service

        response = await async_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "role": "user",
                "content": "What is BRCA1?",
                "auto_reply": True,
            },
        )

    assert response.status_code == 200
    mock_service.generate_reply.assert_awaited_once()
    assert mock_service.append_message.await_count == 2
