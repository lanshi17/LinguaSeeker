"""Tests for ChatMessage foreign key constraints."""
from __future__ import annotations

from src.dao.postgresql.models import ChatMessage


def test_chat_message_evidence_id_has_foreign_key():
    """ChatMessage.evidence_id should reference canonical_evidence_items."""
    cols = ChatMessage.__table__.columns
    evidence_col = cols["evidence_id"]
    fk_tables = {fk.column.table.name for fk in evidence_col.foreign_keys}
    assert "canonical_evidence_items" in fk_tables


def test_chat_message_entity_id_has_foreign_key():
    """ChatMessage.entity_id should reference normalized_entities."""
    cols = ChatMessage.__table__.columns
    entity_col = cols["entity_id"]
    fk_tables = {fk.column.table.name for fk in entity_col.foreign_keys}
    assert "normalized_entities" in fk_tables
