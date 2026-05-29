"""Tests for pgvector migration."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
VERSIONS = ROOT / "database" / "migrations" / "versions"


def _load_pgvector_revision():
    for path in sorted(VERSIONS.glob("*_add_terminology_embeddings_pgvector*.py")):
        spec = importlib.util.spec_from_file_location("pgv", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    pytest.fail("pgvector migration not found")


def test_pgvector_chains_from_terminology():
    mod = _load_pgvector_revision()
    assert mod.down_revision == "add_terminology_20260525"


def test_pgvector_creates_extension(monkeypatch):
    sqls = []
    monkeypatch.setattr("alembic.op.execute", lambda s: sqls.append(str(s)))
    monkeypatch.setattr("alembic.op.create_table", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.create_index", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_table", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_index", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_constraint", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.f", lambda name: name)
    mod = _load_pgvector_revision()
    mod.upgrade()
    assert "CREATE EXTENSION IF NOT EXISTS vector" in [s.strip() for s in sqls]


def test_pgvector_creates_embeddings_table(monkeypatch):
    tables = []
    monkeypatch.setattr("alembic.op.execute", lambda s: None)
    monkeypatch.setattr("alembic.op.create_index", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_table", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_index", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_constraint", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.f", lambda name: name)
    monkeypatch.setattr("alembic.op.create_table", lambda name, *a, **kw: tables.append(name))
    mod = _load_pgvector_revision()
    mod.upgrade()
    assert "terminology_embeddings" in tables


def test_pgvector_downgrade_drops(monkeypatch):
    dropped = []
    monkeypatch.setattr("alembic.op.execute", lambda s: None)
    monkeypatch.setattr("alembic.op.create_table", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.create_index", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_index", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_constraint", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_table", lambda name, **kw: dropped.append(name))
    mod = _load_pgvector_revision()
    mod.downgrade()
    assert "terminology_embeddings" in dropped
