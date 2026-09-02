"""Tests for Phase5ServiceFactory."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.agents.phase_5_factory import Phase5ServiceFactory
from src.core.visualize_evidence_with_expert_in_loop.chat_service import ChatService
from src.core.visualize_evidence_with_expert_in_loop.delta_audit_service import (
    DeltaAuditService,
)
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import (
    FeedbackService,
)
from src.core.visualize_evidence_with_expert_in_loop.source_linker import SourceLinker


@pytest.fixture
def factory() -> Phase5ServiceFactory:
    return Phase5ServiceFactory(cfg=MagicMock())


def test_create_feedback_service(factory: Phase5ServiceFactory):
    """create_feedback_service returns a FeedbackService instance."""
    session = MagicMock()
    service = factory.create_feedback_service(session)
    assert isinstance(service, FeedbackService)


def test_create_chat_service(factory: Phase5ServiceFactory):
    """create_chat_service returns a ChatService instance."""
    session = MagicMock()
    service = factory.create_chat_service(session)
    assert isinstance(service, ChatService)


def test_create_source_linker(factory: Phase5ServiceFactory):
    """create_source_linker returns a SourceLinker instance."""
    session = MagicMock()
    linker = factory.create_source_linker(session)
    assert isinstance(linker, SourceLinker)


def test_delta_audit_returns_singleton(factory: Phase5ServiceFactory):
    """delta_audit property returns the same DeltaAuditService instance."""
    audit1 = factory.delta_audit
    audit2 = factory.delta_audit
    assert isinstance(audit1, DeltaAuditService)
    assert audit1 is audit2
