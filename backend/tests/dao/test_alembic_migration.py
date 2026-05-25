"""Tests for Alembic async migration environment."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import sqlalchemy as sa

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
ALEMBIC_INI = REPO_ROOT / "database" / "alembic.ini"
MIGRATIONS_DIR = REPO_ROOT / "database" / "migrations"
ENV_PY = MIGRATIONS_DIR / "env.py"
SCRIPT_MAKO = MIGRATIONS_DIR / "script.py.mako"
VERSIONS_DIR = MIGRATIONS_DIR / "versions"


def _load_initial_revision_module():
    """Load the initial migration revision as a Python module."""
    import importlib.util

    revision_paths = list(VERSIONS_DIR.glob("*_init_mvp_schema.py"))
    assert len(revision_paths) == 1
    revision_path = revision_paths[0]
    spec = importlib.util.spec_from_file_location("init_mvp_schema", revision_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_terminology_revision_module():
    """Load the terminology migration revision as a Python module."""
    import importlib.util

    revision_paths = list(VERSIONS_DIR.glob("*add_terminology_reference_tables.py"))
    assert len(revision_paths) == 1
    revision_path = revision_paths[0]
    spec = importlib.util.spec_from_file_location("add_terminology_reference_tables", revision_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_embedding_revision_module():
    """Load the terminology embedding migration revision as a Python module."""
    import importlib.util

    revision_paths = list(VERSIONS_DIR.glob("*add_terminology_embeddings_pgvector.py"))
    assert len(revision_paths) == 1
    revision_path = revision_paths[0]
    spec = importlib.util.spec_from_file_location("add_terminology_embeddings_pgvector", revision_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _captured_created_table(table_name: str, monkeypatch) -> list[object]:
    """Capture columns and constraints passed to op.create_table for a table."""
    module = _load_initial_revision_module()
    captured: list[object] = []

    def fake_create_table(name: str, *items, **_kwargs) -> None:
        if name == table_name:
            captured.extend(items)

    monkeypatch.setattr(module.op, "create_table", fake_create_table)
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.op, "create_foreign_key", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.op, "f", lambda name: name)
    module.upgrade()
    assert captured
    return captured


# ── Structural existence ──────────────────────────────────────────────────


def test_alembic_ini_exists() -> None:
    """Alembic configuration file exists at the expected path."""
    assert ALEMBIC_INI.exists(), f"Missing {ALEMBIC_INI}"


def test_env_py_exists() -> None:
    """Migration environment module exists."""
    assert ENV_PY.exists(), f"Missing {ENV_PY}"


def test_script_py_mako_exists() -> None:
    """Migration script template exists."""
    assert SCRIPT_MAKO.exists(), f"Missing {SCRIPT_MAKO}"


def test_versions_directory_exists() -> None:
    """Migration versions directory exists."""
    assert VERSIONS_DIR.is_dir(), f"Missing {VERSIONS_DIR}"


# ── env.py importability and metadata wiring ──────────────────────────────


def test_env_py_imports_models_metadata() -> None:
    """env.py references Base from src.dao.models and resolves to correct metadata."""
    backend_str = str(BACKEND_DIR)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)

    source = ENV_PY.read_text()
    assert "from src.dao.models import Base" in source, (
        "env.py must import Base from src.dao.models"
    )
    assert "target_metadata = Base.metadata" in source, (
        "env.py must wire target_metadata to Base.metadata"
    )

    # Verify the metadata contains the expected tables.
    from src.dao.models import Base  # noqa: E402

    metadata = Base.metadata
    assert "source_documents" in metadata.tables, "source_documents must be in metadata"
    assert "run_evidence_items" in metadata.tables, "run_evidence_items must be in metadata"
    assert "canonical_evidence_items" in metadata.tables, (
        "canonical_evidence_items must be in metadata"
    )


def test_env_py_uses_async_migration() -> None:
    """env.py uses asyncio.run for online async migrations."""
    source = ENV_PY.read_text()

    assert "run_migrations_online" in source, "env.py must define run_migrations_online"
    assert "run_migrations_offline" in source, "env.py must define run_migrations_offline"
    assert "target_metadata" in source, "env.py must reference target_metadata"
    assert "asyncio.run" in source, "env.py must use asyncio.run for async migrations"
    assert "run_sync" in source, "env.py must use connection.run_sync for migrations"
    assert "create_async_engine" in source, (
        "env.py must use create_async_engine for online mode"
    )


# ── Revision chain ────────────────────────────────────────────────────────


def test_revision_chain_has_initial_revision() -> None:
    """Versions directory contains at least one migration revision script."""
    backend_str = str(BACKEND_DIR)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    script = ScriptDirectory.from_config(config)

    revisions = list(script.walk_revisions())
    assert len(revisions) >= 1, "At least one migration revision must exist"


def test_head_revision_points_to_terminology_schema() -> None:
    """The terminology revision extends the initial MVP schema."""
    backend_str = str(BACKEND_DIR)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    script = ScriptDirectory.from_config(config)

    revisions = list(script.walk_revisions())
    base = revisions[-1]

    terminology = script.get_revision("add_terminology_20260525")
    assert terminology is not None
    assert terminology.down_revision == "4a82b5793055"
    assert base.revision == "4a82b5793055"
    assert base.down_revision is None


def test_head_revision_points_to_pgvector_embeddings() -> None:
    """The Alembic head includes pgvector terminology embeddings."""
    backend_str = str(BACKEND_DIR)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    script = ScriptDirectory.from_config(config)

    head = script.get_revision("head")

    assert head is not None
    assert head.revision == "add_terminology_embeddings_20260525"
    assert head.down_revision == "add_terminology_20260525"


def test_embedding_migration_creates_pgvector_extension(monkeypatch) -> None:
    """The embedding migration enables pgvector before creating vector columns."""
    module = _load_embedding_revision_module()
    statements: list[str] = []

    monkeypatch.setattr(module.op, "execute", lambda statement: statements.append(str(statement)))
    monkeypatch.setattr(module.op, "create_table", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.op, "f", lambda name: name)

    module.upgrade()

    assert "CREATE EXTENSION IF NOT EXISTS vector" in statements


def test_initial_migration_canonical_evidence_matches_orm_columns(monkeypatch) -> None:
    """Initial migration creates all canonical evidence columns required by the ORM."""
    items = _captured_created_table("canonical_evidence_items", monkeypatch)
    columns = {item.name: item for item in items if isinstance(item, sa.Column)}

    assert "current_best_status" in columns
    assert "conflict_flag" in columns
    assert columns["review_status"].server_default is not None


def test_search_index_table_is_not_in_alembic_target_metadata() -> None:
    """The manual search-index projection must not pollute Base metadata autogenerate."""
    from src.dao.models import Base
    from src.dao.search_index_repo import frontend_search_index

    assert frontend_search_index.metadata is not Base.metadata
    assert "frontend_search_index" not in Base.metadata.tables


def test_terminology_migration_relationship_object_nullable(monkeypatch) -> None:
    """Terminology migration keeps object_entry_id nullable for scalar assertions."""
    module = _load_terminology_revision_module()
    captured: list[object] = []

    def fake_create_table(name: str, *items, **_kwargs) -> None:
        if name == "terminology_relationships":
            captured.extend(items)

    monkeypatch.setattr(module.op, "create_table", fake_create_table)
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.op, "f", lambda name: name)
    module.upgrade()

    columns = {item.name: item for item in captured if isinstance(item, sa.Column)}
    assert columns["object_entry_id"].nullable is True


# ── Database-dependent tests (skip when PostgreSQL is unavailable) ─────────


@pytest.mark.skip(reason="Requires a running PostgreSQL instance")
@pytest.mark.asyncio
async def test_upgrade_head_creates_tables() -> None:
    """Running upgrade head against a test database creates the MVP tables."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect, text
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.core.config import Settings

    settings = Settings()
    test_dsn = settings.postgresql_dsn
    engine = create_async_engine(test_dsn)

    # Drop all tables first for a clean test
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS acmg_app CASCADE"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS acmg_app"))

    # Run migration
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", test_dsn)

    def upgrade():
        command.upgrade(config, "head")

    await engine.run_sync(lambda _: upgrade())

    # Verify tables
    def get_tables(conn):
        inspector = inspect(conn)
        return set(inspector.get_table_names(schema="acmg_app"))

    async with engine.connect() as conn:
        tables = await conn.run_sync(get_tables)

    expected = {
        "source_documents",
        "source_document_identifiers",
        "processing_runs",
        "normalized_entities",
        "entity_merge_events",
        "run_evidence_items",
        "evidence_entity_bindings",
        "canonical_evidence_items",
        "users",
    }
    assert expected <= tables, f"Missing tables: {expected - tables}"

    await engine.dispose()
