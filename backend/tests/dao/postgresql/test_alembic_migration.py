"""Tests for Alembic async migration environment."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import sqlalchemy as sa

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
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
    """env.py references Base from src.dao.postgresql.models and resolves to correct metadata."""
    backend_str = str(BACKEND_DIR)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)

    source = ENV_PY.read_text()
    assert "from src.dao.postgresql.models import Base" in source, (
        "env.py must import Base from src.dao.postgresql.models"
    )
    assert "target_metadata = Base.metadata" in source, (
        "env.py must wire target_metadata to Base.metadata"
    )

    # Verify the metadata contains the expected tables.
    from src.dao.postgresql.models import Base  # noqa: E402

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


def test_head_revision_points_to_variant_internal_id_index() -> None:
    """The Alembic head is the document annotations migration."""
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
    assert head.revision == "doc_ann_20260623"
    assert head.down_revision == "content_blocks_20260623"


def test_pipeline_run_leases_migration_chain() -> None:
    """The pipeline run leases migration chains after allow_standalone_chat_sessions."""
    backend_str = str(BACKEND_DIR)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    script = ScriptDirectory.from_config(config)

    lease_revision = script.get_revision("pipeline_run_leases_20260611")
    assert lease_revision is not None
    assert lease_revision.down_revision == "2026_06_11_allow_standalone_chat_sessions"


def test_schema_hardening_migration_chain() -> None:
    """The schema hardening migrations form a correct linear chain."""
    backend_str = str(BACKEND_DIR)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    script = ScriptDirectory.from_config(config)

    rm_fk = script.get_revision("rm_canonical_fk_20260608")
    unmappable = script.get_revision("reviewed_unmappable_20260608")
    pipeline_status = script.get_revision("extract_pipeline_status_20260608")

    assert rm_fk is not None
    assert rm_fk.down_revision == "lit_profiles_20260608"

    assert unmappable is not None
    assert unmappable.down_revision == "rm_canonical_fk_20260608"

    assert pipeline_status is not None
    assert pipeline_status.down_revision == "reviewed_unmappable_20260608"


def test_terminology_relationships_migration_defines_unique_identity_constraint(monkeypatch) -> None:
    """Terminology relationships must have a 4-column identity uniqueness guarantee."""
    module = _load_terminology_revision_module()
    captured: list[object] = []

    def fake_create_table(name: str, *items, **_kwargs) -> None:
        if name == "terminology_relationships":
            captured.extend(items)

    monkeypatch.setattr(module.op, "create_table", fake_create_table)
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.op, "f", lambda name: name)

    module.upgrade()

    unique_constraints = [
        item for item in captured
        if isinstance(item, sa.UniqueConstraint)
    ]
    assert any(
        tuple(constraint.columns.keys() or getattr(constraint, "_pending_colargs", ())) == (
            "subject_entry_id",
            "object_entry_id",
            "relationship_type",
            "source_db",
        )
        for constraint in unique_constraints
    )


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
    from src.dao.postgresql.models import Base
    from src.dao.postgresql.search_index_repo import frontend_search_index

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


def test_terminology_migration_relationship_identity_unique(monkeypatch) -> None:
    """Terminology migration creates the relationship identity unique constraint."""
    module = _load_terminology_revision_module()
    captured: list[object] = []

    def fake_create_table(name: str, *items, **_kwargs) -> None:
        if name == "terminology_relationships":
            captured.extend(items)

    monkeypatch.setattr(module.op, "create_table", fake_create_table)
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.op, "f", lambda name: name)
    module.upgrade()

    unique_constraints = [
        item for item in captured if isinstance(item, sa.UniqueConstraint)
    ]
    assert any(
        constraint.name == "uq_terminology_relationships_identity"
        for constraint in unique_constraints
    )


def _load_variant_internal_id_revision_module():
    """Load the variant internal-id index migration revision as a Python module."""
    import importlib.util

    revision_paths = list(VERSIONS_DIR.glob("*add_variant_internal_id_index.py"))
    assert len(revision_paths) == 1
    revision_path = revision_paths[0]
    spec = importlib.util.spec_from_file_location("add_variant_internal_id_index", revision_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_variant_internal_id_migration_chain() -> None:
    """The variant internal-id index migration chains after critical_indexes_20260621."""
    module = _load_variant_internal_id_revision_module()
    assert module.down_revision == "critical_indexes_20260621"


def test_variant_internal_id_migration_creates_unique_index(monkeypatch) -> None:
    """The migration creates a partial unique index on internal variant external_ids."""
    module = _load_variant_internal_id_revision_module()
    created: list[tuple] = []

    def fake_create_index(index_name, table_name, columns, **kwargs):
        created.append((index_name, table_name, list(columns), kwargs))

    monkeypatch.setattr(module.op, "create_index", fake_create_index)
    monkeypatch.setattr(module.op, "execute", lambda *a, **k: None)

    module.upgrade()

    assert any(
        name == "uq_normalized_entities_variant_internal_id"
        and table == "normalized_entities"
        and cols == ["external_id"]
        and kwargs.get("unique") is True
        and str(kwargs.get("postgresql_where"))
        == "external_id LIKE 'internal:variant:%'"
        for name, table, cols, kwargs in created
    )


def test_variant_internal_id_migration_downgrade_drops_index(monkeypatch) -> None:
    """The migration downgrade drops the internal variant-id unique index."""
    module = _load_variant_internal_id_revision_module()
    dropped: list[tuple] = []

    def fake_drop_index(index_name, *args, **kwargs):
        dropped.append((index_name, kwargs))

    monkeypatch.setattr(module.op, "drop_index", fake_drop_index)
    monkeypatch.setattr(module.op, "execute", lambda *a, **k: None)

    module.downgrade()

    assert any(
        name == "uq_normalized_entities_variant_internal_id"
        and kwargs.get("table_name") == "normalized_entities"
        for name, kwargs in dropped
    )

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
        await conn.execute(text("DROP SCHEMA IF EXISTS lingua_seeker CASCADE"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS lingua_seeker"))

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
        return set(inspector.get_table_names(schema="lingua_seeker"))

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
        "terminology_entries",
        "terminology_aliases",
        "terminology_relationships",
        "terminology_embeddings",
        "users",
    }
    assert expected <= tables, f"Missing tables: {expected - tables}"

    await engine.dispose()


@pytest.mark.skip(reason="Requires a running PostgreSQL instance")
@pytest.mark.asyncio
async def test_nulls_not_distinct_constraint_prevents_duplicate_scalar_assertions() -> None:
    """NULLS NOT DISTINCT on terminology_relationships treats NULL object_entry_id as equal.

    Two INSERTs with the same (subject_entry_id, NULL, relationship_type, source_db)
    must trigger ON CONFLICT DO UPDATE rather than inserting a second row.
    """
    import uuid

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.core.config import Settings

    cfg = Settings()
    engine = create_async_engine(cfg.postgresql_dsn)

    try:
        async with engine.begin() as conn:
            schema = cfg.postgresql.schema_
            await conn.execute(text(f"SET search_path TO {schema},public"))

            # Insert a subject entry for the relationship.
            subject_id = uuid.uuid4()
            await conn.execute(
                text("""
                    INSERT INTO terminology_entries
                        (entry_id, entity_type, source_db, external_id,
                         display_name, normalized_name, version)
                    VALUES
                        (:id, 'gene', 'test', 'HGNC:1234', 'BRCA1', 'brca1', 'v1')
                """),
                {"id": subject_id},
            )

            # First insert: scalar assertion (NULL object_entry_id).
            rel_id_1 = uuid.uuid4()
            await conn.execute(
                text("""
                    INSERT INTO terminology_relationships
                        (relationship_id, subject_entry_id, object_entry_id,
                         relationship_type, source_db, evidence_level, raw_payload)
                    VALUES
                        (:rid, :sid, NULL, 'assertion', 'test', 'strong', '{}'::jsonb)
                """),
                {"rid": rel_id_1, "sid": subject_id},
            )

            # Second insert: same scalar assertion → must conflict and update.
            rel_id_2 = uuid.uuid4()
            result = await conn.execute(
                text("""
                    INSERT INTO terminology_relationships
                        (relationship_id, subject_entry_id, object_entry_id,
                         relationship_type, source_db, evidence_level, raw_payload)
                    VALUES
                        (:rid, :sid, NULL, 'assertion', 'test', 'moderate', '{}'::jsonb)
                    ON CONFLICT (subject_entry_id, object_entry_id,
                                 relationship_type, source_db)
                    DO UPDATE SET evidence_level = EXCLUDED.evidence_level
                    RETURNING relationship_id, evidence_level
                """),
                {"rid": rel_id_2, "sid": subject_id},
            )
            row = result.mappings().first()
            assert row is not None, "ON CONFLICT DO UPDATE should return the conflicting row"
            # The UPDATE should have set evidence_level to 'moderate'.
            assert row["evidence_level"] == "moderate"
            # The returned ID should be the original, not the new one.
            assert row["relationship_id"] == rel_id_1

            # Verify only one row exists.
            count_result = await conn.execute(
                text("""
                    SELECT count(*) AS cnt
                    FROM terminology_relationships
                    WHERE subject_entry_id = :sid
                      AND relationship_type = 'assertion'
                      AND source_db = 'test'
                """),
                {"sid": subject_id},
            )
            assert count_result.scalar() == 1, "NULLS NOT DISTINCT must prevent duplicate scalar rows"

            # Cleanup.
            await conn.execute(text("DELETE FROM terminology_relationships WHERE source_db = 'test'"))
            await conn.execute(text("DELETE FROM terminology_entries WHERE source_db = 'test'"))
    finally:
        await engine.dispose()
