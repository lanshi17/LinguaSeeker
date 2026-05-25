# Phase 3 Entity Standardization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the Phase 3 MVP that imports local biomedical terminology resources, standardizes Phase 2 evidence entities, and persists standardized evidence bindings into the existing PostgreSQL evidence schema.

**Architecture:** Keep Phase 3 as an orchestrated vertical slice under `backend/src/core/standardize_entities_and_align_knowledge/`. A `DualResultAdapter` converts current Phase 2 dual-track extraction output into typed standardization input; deterministic matchers use unified terminology reference tables; a repository writes normalized entities, run evidence, bindings, and current-best canonical evidence. Migrations create reference tables, while import scripts stream local terminology files into those tables.

**Tech Stack:** Python 3.12, Pydantic, SQLAlchemy 2.0 async ORM, Alembic, PostgreSQL JSONB, loguru, pytest, uv, Ruff

---

**Status:** completed
**Created:** 2026-05-25
**Completed:** 2026-05-25
**PR:** pending

## Prerequisites

- Read `docs/plans/2026-05-25-phase-3-standardization-design.md`.
- Use @test-driven-development for each implementation task.
- Use @systematic-debugging for any unexpected test failure.
- Use @verification-before-completion before claiming completion.
- Use @module-guide after the module is implemented and tests pass.
- Use @doc-organize after docs are updated.
- Do not commit unrelated dirty worktree changes.

## Confirmed Decisions

- MVP input is `DualEvidenceExtractionResult`; `FusedResultAdapter` is a future extension.
- The caller passes `source_document_id` and `processing_run_id`.
- Reference data uses `terminology_entries`, `terminology_aliases`, and `terminology_relationships`.
- Entries are only `gene`, `disease`, `phenotype`, and `variant`.
- ClinGen MONDO disease IDs create source-limited disease entries.
- ClinVar imports from `variant_summary.txt`, excludes 0-star/evidence-free rows, and imports 1-star and above rows.
- Matchers are deterministic: exact and synonym only, no edit-distance fuzzy, no vectors, no Agent disambiguation.
- `normalized_entities.standardization_status` includes `ambiguous`.
- Binding roles are fixed: gene=`subject`, variant=`target`, disease/phenotype=`context`.
- `entity_scope_hash` is chain-level.
- `run_evidence_items` stores FOUND and non-FOUND items.
- `canonical_evidence_items` stores FOUND plus review-relevant problem statuses; ordinary NOT_FOUND remains run-level only.
- Canonical priority is `FOUND > SOURCE_INVALID > OCR_GAP > TABLE_UNGROUNDED > NOT_FOUND`, then confidence.

---

### Task 1: Add Terminology ORM Models

**Files:**
- Modify: `backend/src/dao/models.py`
- Modify: `backend/tests/dao/test_models.py`

**Step 1: Write the failing tests**

Append tests that assert the ORM metadata contains the terminology tables and key constraints:

```python
def test_terminology_reference_tables_exist() -> None:
    metadata = Base.metadata
    assert "terminology_entries" in metadata.tables
    assert "terminology_aliases" in metadata.tables
    assert "terminology_relationships" in metadata.tables


def test_terminology_entries_unique_source_external_id() -> None:
    table = _table("terminology_entries")
    assert ("source_db", "external_id") in _unique_constraint_columns(table)


def test_terminology_aliases_lookup_index_exists() -> None:
    table = _table("terminology_aliases")
    index = _index_by_name(table, "ix_terminology_aliases_lookup")
    assert tuple(expression.name for expression in index.expressions) == (
        "entity_type",
        "normalized_alias",
    )


def test_terminology_relationship_object_is_nullable() -> None:
    table = _table("terminology_relationships")
    assert table.c.object_entry_id.nullable is True
```

If `_index_by_name` is missing in `test_models.py`, add:

```python
def _index_by_name(table, name: str):
    for index in table.indexes:
        if index.name == name:
            return index
    raise AssertionError(f"Missing index {name}")
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/dao/test_models.py -v
```

Expected: FAIL because the terminology models do not exist.

**Step 3: Implement the minimal ORM models**

Add to `backend/src/dao/models.py`:

```python
class TerminologyEntry(Base, TimestampMixin):
    """Unified reference entity imported from terminology databases."""

    __tablename__ = "terminology_entries"
    __table_args__ = (
        UniqueConstraint("source_db", "external_id", name="uq_terminology_entries_source_external_id"),
        Index("ix_terminology_entries_entity_type_normalized_name", "entity_type", "normalized_name"),
        Index("ix_terminology_entries_source_db", "source_db"),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_db: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[str] = mapped_column(String(128), nullable=False)


class TerminologyAlias(Base, TimestampMixin):
    """Indexed lookup alias for terminology matching."""

    __tablename__ = "terminology_aliases"
    __table_args__ = (
        UniqueConstraint("entry_id", "normalized_alias", "alias_type", name="uq_terminology_aliases_entry_alias_type"),
        Index("ix_terminology_aliases_lookup", "entity_type", "normalized_alias"),
        Index("ix_terminology_aliases_entry_id", "entry_id"),
    )

    alias_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminology_entries.entry_id"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    alias_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_alias: Mapped[str] = mapped_column(Text, nullable=False)
    alias_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_db: Mapped[str] = mapped_column(String(64), nullable=False)


class TerminologyRelationship(Base, TimestampMixin):
    """Structured relationship between terminology entries or scalar assertions."""

    __tablename__ = "terminology_relationships"
    __table_args__ = (
        Index("ix_terminology_relationships_subject_type", "subject_entry_id", "relationship_type"),
        Index("ix_terminology_relationships_object_type", "object_entry_id", "relationship_type"),
    )

    relationship_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminology_entries.entry_id"),
        nullable=False,
    )
    object_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminology_entries.entry_id"),
        nullable=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(96), nullable=False)
    source_db: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_level: Mapped[str | None] = mapped_column(String(96), nullable=True)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/dao/test_models.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/dao/models.py backend/tests/dao/test_models.py
git commit -m "feat(standardization): add terminology reference models"
```

---

### Task 2: Add Alembic Migration for Terminology Tables

**Files:**
- Create: `database/migrations/versions/2026-05-25_add_terminology_reference_tables.py`
- Modify: `backend/tests/dao/test_alembic_migration.py`

**Step 1: Write the failing migration tests**

Add tests that load the new revision and capture terminology table columns:

```python
def _load_terminology_revision_module():
    import importlib.util

    revision_paths = list(VERSIONS_DIR.glob("*add_terminology_reference_tables.py"))
    assert len(revision_paths) == 1
    spec = importlib.util.spec_from_file_location("add_terminology_reference_tables", revision_paths[0])
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_terminology_migration_relationship_object_nullable(monkeypatch) -> None:
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
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/dao/test_alembic_migration.py::test_terminology_migration_relationship_object_nullable -v
```

Expected: FAIL because the revision file does not exist.

**Step 3: Create the migration**

Create a revision with:

```python
"""add terminology reference tables

Revision ID: add_terminology_20260525
Revises: 4a82b5793055
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "add_terminology_20260525"
down_revision: Union[str, None] = "4a82b5793055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "terminology_entries",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("source_db", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("aliases", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("entry_id", name=op.f("pk_terminology_entries")),
        sa.UniqueConstraint("source_db", "external_id", name=op.f("uq_terminology_entries_source_external_id")),
    )
    op.create_index(
        "ix_terminology_entries_entity_type_normalized_name",
        "terminology_entries",
        ["entity_type", "normalized_name"],
    )
    op.create_index("ix_terminology_entries_source_db", "terminology_entries", ["source_db"])

    op.create_table(
        "terminology_aliases",
        sa.Column("alias_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("alias_text", sa.Text(), nullable=False),
        sa.Column("normalized_alias", sa.Text(), nullable=False),
        sa.Column("alias_type", sa.String(64), nullable=False),
        sa.Column("source_db", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("alias_id", name=op.f("pk_terminology_aliases")),
        sa.ForeignKeyConstraint(["entry_id"], ["terminology_entries.entry_id"], name=op.f("fk_terminology_aliases_entry_id")),
        sa.UniqueConstraint("entry_id", "normalized_alias", "alias_type", name=op.f("uq_terminology_aliases_entry_alias_type")),
    )
    op.create_index("ix_terminology_aliases_lookup", "terminology_aliases", ["entity_type", "normalized_alias"])
    op.create_index("ix_terminology_aliases_entry_id", "terminology_aliases", ["entry_id"])

    op.create_table(
        "terminology_relationships",
        sa.Column("relationship_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("relationship_type", sa.String(96), nullable=False),
        sa.Column("source_db", sa.String(64), nullable=False),
        sa.Column("evidence_level", sa.String(96), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("relationship_id", name=op.f("pk_terminology_relationships")),
        sa.ForeignKeyConstraint(["subject_entry_id"], ["terminology_entries.entry_id"], name=op.f("fk_terminology_relationships_subject_entry_id")),
        sa.ForeignKeyConstraint(["object_entry_id"], ["terminology_entries.entry_id"], name=op.f("fk_terminology_relationships_object_entry_id")),
    )
    op.create_index("ix_terminology_relationships_subject_type", "terminology_relationships", ["subject_entry_id", "relationship_type"])
    op.create_index("ix_terminology_relationships_object_type", "terminology_relationships", ["object_entry_id", "relationship_type"])


def downgrade() -> None:
    op.drop_index("ix_terminology_relationships_object_type", table_name="terminology_relationships")
    op.drop_index("ix_terminology_relationships_subject_type", table_name="terminology_relationships")
    op.drop_table("terminology_relationships")
    op.drop_index("ix_terminology_aliases_entry_id", table_name="terminology_aliases")
    op.drop_index("ix_terminology_aliases_lookup", table_name="terminology_aliases")
    op.drop_table("terminology_aliases")
    op.drop_index("ix_terminology_entries_source_db", table_name="terminology_entries")
    op.drop_index("ix_terminology_entries_entity_type_normalized_name", table_name="terminology_entries")
    op.drop_table("terminology_entries")
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/dao/test_alembic_migration.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add database/migrations/versions/2026-05-25_add_terminology_reference_tables.py backend/tests/dao/test_alembic_migration.py
git commit -m "feat(standardization): add terminology reference migration"
```

---

### Task 3: Add Phase 3 Contracts and Normalizers

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/__init__.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/contracts.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/normalizers.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/__init__.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_contracts.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_normalizers.py`

**Step 1: Write the failing contract tests**

Create `test_contracts.py`:

```python
from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityType,
    MatchStatus,
    StandardizationCandidate,
)


def test_candidate_contract_requires_typed_entity_and_role() -> None:
    candidate = StandardizationCandidate(
        candidate_id="chain-1:gene",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )

    assert candidate.entity_type == EntityType.GENE
    assert candidate.role == BindingRole.SUBJECT
    assert candidate.raw_text == "BRCA1"


def test_match_status_includes_ambiguous() -> None:
    assert MatchStatus.AMBIGUOUS.value == "ambiguous"
```

Create `test_normalizers.py`:

```python
from src.core.standardize_entities_and_align_knowledge.normalizers import (
    make_entity_scope_hash,
    normalize_lookup_text,
)


def test_lookup_normalization_is_stable() -> None:
    assert normalize_lookup_text("  Charcot-Marie Tooth  ") == "charcot-marie tooth"


def test_entity_scope_hash_is_order_independent() -> None:
    left = make_entity_scope_hash([
        ("target", "ClinVarVariation:123"),
        ("subject", "HGNC:1100"),
    ])
    right = make_entity_scope_hash([
        ("subject", "HGNC:1100"),
        ("target", "ClinVarVariation:123"),
    ])

    assert left == right
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_contracts.py tests/core/standardize_entities_and_align_knowledge/test_normalizers.py -v
```

Expected: FAIL because the package does not exist.

**Step 3: Implement the contracts and normalizers**

Add to `contracts.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EntityType(str, Enum):
    GENE = "gene"
    DISEASE = "disease"
    PHENOTYPE = "phenotype"
    VARIANT = "variant"


class BindingRole(str, Enum):
    SUBJECT = "subject"
    TARGET = "target"
    CONTEXT = "context"
    MENTION = "mention"


class MatchStatus(str, Enum):
    STANDARDIZED = "standardized"
    UNMAPPED = "unmapped"
    AMBIGUOUS = "ambiguous"


class CanonicalStatusRank(str, Enum):
    FOUND = "found"
    SOURCE_INVALID = "source_invalid"
    OCR_GAP = "ocr_gap"
    TABLE_UNGROUNDED = "table_ungrounded"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class StandardizationCandidate:
    candidate_id: str
    entity_type: EntityType
    role: BindingRole
    raw_text: str
    chain_id: str
    track: str
    field_id: str = ""
    context: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TerminologyCandidate:
    entry_id: str
    entity_type: EntityType
    source_db: str
    external_id: str
    display_name: str
    normalized_alias: str
    alias_type: str
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EntityMatch:
    candidate: StandardizationCandidate
    status: MatchStatus
    external_id: str | None
    display_name: str
    terminology_candidates: tuple[TerminologyCandidate, ...] = ()
    rationale: str = ""


@dataclass(frozen=True)
class StandardizationInput:
    document_id: str
    source_document_id: str
    processing_run_id: str
    candidates: tuple[StandardizationCandidate, ...]
    evidence_items: tuple[Any, ...]
    track_payloads: dict[str, Any] = field(default_factory=dict)
```

Add to `normalizers.py`:

```python
from __future__ import annotations

import hashlib
import re
import unicodedata

_SPACE_RE = re.compile(r"\s+")


def normalize_lookup_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = _SPACE_RE.sub(" ", text.strip())
    return text.casefold()


def normalize_gene_symbol(value: str) -> str:
    return normalize_lookup_text(value).upper()


def normalize_variant_text(value: str) -> str:
    return _SPACE_RE.sub("", unicodedata.normalize("NFKC", value or "").strip())


def make_entity_scope_hash(bindings: list[tuple[str, str]]) -> str:
    stable = "|".join(f"{role}:{identity}" for role, identity in sorted(bindings))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_contracts.py tests/core/standardize_entities_and_align_knowledge/test_normalizers.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge backend/tests/core/standardize_entities_and_align_knowledge
git commit -m "feat(standardization): add typed phase three contracts"
```

---

### Task 4: Implement Terminology Import Parsers

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/importers.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_importers.py`

**Step 1: Write the failing parser tests**

Create small in-memory fixture tests:

```python
from pathlib import Path

from src.core.standardize_entities_and_align_knowledge.importers import (
    is_importable_clinvar_review_status,
    parse_hgnc_rows,
)


def test_parse_hgnc_rows_builds_gene_entry_and_aliases(tmp_path: Path) -> None:
    path = tmp_path / "hgnc_complete_set.txt"
    path.write_text(
        "HGNC ID\tApproved symbol\tApproved name\tAlias symbols\tPrevious symbols\n"
        "1100\tBRCA1\tBRCA1 DNA repair associated\tRNF53, BRCC1\tFANCS\n",
        encoding="utf-8",
    )

    batch = parse_hgnc_rows(path, version="hgnc_test")

    assert batch.entries[0].external_id == "HGNC:1100"
    assert batch.entries[0].display_name == "BRCA1"
    assert {alias.alias_text for alias in batch.aliases} >= {"BRCA1", "RNF53", "BRCC1", "FANCS"}


def test_clinvar_review_status_filters_zero_star() -> None:
    assert is_importable_clinvar_review_status("criteria provided, single submitter")
    assert is_importable_clinvar_review_status("criteria provided, conflicting classifications")
    assert not is_importable_clinvar_review_status("no assertion criteria provided")
    assert not is_importable_clinvar_review_status("no classification provided")
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_importers.py -v
```

Expected: FAIL because `importers.py` does not exist.

**Step 3: Implement minimal parser contracts and HGNC/ClinVar review filtering**

Add parser dataclasses:

```python
@dataclass(frozen=True)
class ImportEntry:
    entity_type: EntityType
    source_db: str
    external_id: str
    display_name: str
    normalized_name: str
    aliases: tuple[str, ...]
    raw_payload: dict[str, object]
    version: str


@dataclass(frozen=True)
class ImportAlias:
    external_id: str
    entity_type: EntityType
    source_db: str
    alias_text: str
    normalized_alias: str
    alias_type: str


@dataclass(frozen=True)
class ImportRelationship:
    subject_external_id: str
    object_external_id: str | None
    relationship_type: str
    source_db: str
    evidence_level: str | None
    raw_payload: dict[str, object]


@dataclass(frozen=True)
class ImportBatch:
    entries: tuple[ImportEntry, ...] = ()
    aliases: tuple[ImportAlias, ...] = ()
    relationships: tuple[ImportRelationship, ...] = ()
```

Implement:

```python
ZERO_STAR_REVIEW_STATUSES = {
    "",
    "-",
    "no assertion criteria provided",
    "no classification provided",
    "no classification for the single variant",
    "no classifications from unflagged records",
}


def is_importable_clinvar_review_status(review_status: str) -> bool:
    return normalize_lookup_text(review_status) not in ZERO_STAR_REVIEW_STATUSES
```

Implement `parse_hgnc_rows()` with `csv.DictReader(delimiter="\t")`, split aliases on comma, and emit primary/alias/previous symbol aliases.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_importers.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/importers.py backend/tests/core/standardize_entities_and_align_knowledge/test_importers.py
git commit -m "feat(standardization): parse terminology import rows"
```

---

### Task 5: Complete Terminology Import Coverage and CLI

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/importers.py`
- Create: `scripts/import_terminology.py`
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/test_importers.py`

**Step 1: Write failing tests for OMIM, HPO, ClinGen, and ClinVar**

Add fixture tests that verify:

- OMIM disease rows create `OMIM:<id>` disease entries.
- HPO rows create `HP:<id>` phenotype entries.
- ClinGen MONDO rows create `MONDO:<id>` source-limited disease entries and `gene_associated_with_disease` relationships.
- ClinVar rows create `ClinVarVariation:<VariationID>` variant entries, `rs<RS#>` aliases, and `variant_has_clinical_significance` relationships with `object_external_id is None`.

Example ClinVar assertion:

```python
def test_parse_clinvar_rows_keeps_significance_as_scalar_relationship(tmp_path: Path) -> None:
    path = tmp_path / "variant_summary.txt"
    path.write_text(
        "#AlleleID\tType\tName\tGeneID\tGeneSymbol\tHGNC_ID\tClinicalSignificance\tClinSigSimple\tLastEvaluated\tRS# (dbSNP)\t"
        "nsv/esv (dbVar)\tRCVaccession\tPhenotypeIDS\tPhenotypeList\tOrigin\tOriginSimple\tAssembly\tChromosomeAccession\t"
        "Chromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\tCytogenetic\tReviewStatus\tNumberSubmitters\tGuidelines\t"
        "TestedInGTR\tOtherIDs\tSubmitterCategories\tVariationID\n"
        "1\tsingle nucleotide variant\tNM_000059.4(BRCA2):c.5946del\t675\tBRCA2\tHGNC:1101\tPathogenic\t1\t2024-01-01\t80359550\t"
        "-\tRCV0001\tOMIM:612555\tBreast cancer\tgermline\tgermline\tGRCh38\tNC_000013.11\t13\t1\t1\tA\t-\t-\t"
        "criteria provided, single submitter\t1\t-\tN\t-\t-\t12345\n",
        encoding="utf-8",
    )

    batch = parse_clinvar_rows(path, version="clinvar_test")

    assert batch.entries[0].external_id == "ClinVarVariation:12345"
    assert any(alias.alias_text == "rs80359550" for alias in batch.aliases)
    relationship = batch.relationships[0]
    assert relationship.relationship_type == "variant_has_clinical_significance"
    assert relationship.object_external_id is None
    assert relationship.raw_payload["clinical_significance"] == "Pathogenic"
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_importers.py -v
```

Expected: FAIL for missing parser functions.

**Step 3: Implement the remaining parsers and CLI**

Implement streaming parser functions:

- `parse_omim_rows(root: Path, version: str) -> ImportBatch`
- `parse_hpo_rows(root: Path, version: str) -> ImportBatch`
- `parse_clingen_rows(root: Path, version: str) -> ImportBatch`
- `parse_clinvar_rows(path: Path, version: str) -> ImportBatch`

Create `scripts/import_terminology.py`:

```python
"""Import local terminology database files into PostgreSQL reference tables."""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from src.core.config import get_config
from src.core.standardize_entities_and_align_knowledge.api import import_terminology


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminology-root", default="database/terminology_database")
    parser.add_argument("--version", required=True)
    parser.add_argument("--sources", nargs="+", default=["hgnc", "omim", "hpo", "clingen", "clinvar"])
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    await import_terminology(
        cfg=get_config(),
        terminology_root=Path(args.terminology_root),
        version=args.version,
        sources=args.sources,
    )


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_importers.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/importers.py scripts/import_terminology.py backend/tests/core/standardize_entities_and_align_knowledge/test_importers.py
git commit -m "feat(standardization): import local terminology sources"
```

---

### Task 6: Implement Terminology and Evidence Repository

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/repositories.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_repositories.py`

**Step 1: Write failing repository tests with a fake async session**

Test that repository methods execute expected table inserts/selects without requiring PostgreSQL:

```python
class FakeSession:
    def __init__(self) -> None:
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeResult()

    async def flush(self) -> None:
        return None


class FakeResult:
    def mappings(self):
        return self

    def all(self):
        return []


async def test_find_alias_candidates_filters_by_type_and_alias() -> None:
    repo = StandardizationRepository(FakeSession())

    await repo.find_alias_candidates(EntityType.GENE, "BRCA1")

    statement = repo.session.statements[0]
    assert "terminology_aliases" in str(statement)
    assert "normalized_alias" in str(statement)
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_repositories.py -v
```

Expected: FAIL because `repositories.py` does not exist.

**Step 3: Implement repository skeleton**

Add methods:

- `find_alias_candidates(entity_type: EntityType, raw_text: str) -> tuple[TerminologyCandidate, ...]`
- `upsert_terminology_batch(batch: ImportBatch) -> None`
- `upsert_normalized_entity(match: EntityMatch) -> str`
- `insert_run_evidence_items(input_data: StandardizationInput, matches: tuple[EntityMatch, ...]) -> tuple[str, ...]`
- `insert_entity_bindings(...) -> None`
- `upsert_canonical_evidence(...) -> None`

Use SQLAlchemy statements against `TerminologyEntry`, `TerminologyAlias`, `TerminologyRelationship`, `NormalizedEntity`, `RunEvidenceItem`, `EvidenceEntityBinding`, and `CanonicalEvidenceItem`.

Repository methods returning flexible SQL row payloads may use `# noqa: dict-return` only with a short reason.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_repositories.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/repositories.py backend/tests/core/standardize_entities_and_align_knowledge/test_repositories.py
git commit -m "feat(standardization): add persistence repository"
```

---

### Task 7: Implement Deterministic Matchers

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/matchers.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_matchers.py`

**Step 1: Write failing matcher tests**

Use a fake repository:

```python
class FakeRepository:
    def __init__(self, candidates):
        self.candidates = tuple(candidates)

    async def find_alias_candidates(self, entity_type, raw_text):
        return self.candidates


async def test_unique_gene_alias_match_standardizes() -> None:
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )
    terminology = TerminologyCandidate(
        entry_id="entry-1",
        entity_type=EntityType.GENE,
        source_db="HGNC",
        external_id="HGNC:1100",
        display_name="BRCA1",
        normalized_alias="BRCA1",
        alias_type="primary",
    )

    matcher = TerminologyMatcher(FakeRepository([terminology]))
    match = await matcher.match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "HGNC:1100"


async def test_multiple_candidates_are_ambiguous() -> None:
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.DISEASE,
        role=BindingRole.CONTEXT,
        raw_text="mitochondrial disease",
        chain_id="chain-1",
        track="original",
    )
    choices = [
        TerminologyCandidate("e1", EntityType.DISEASE, "OMIM", "OMIM:1", "Disease A", "mitochondrial disease", "name"),
        TerminologyCandidate("e2", EntityType.DISEASE, "OMIM", "OMIM:2", "Disease B", "mitochondrial disease", "name"),
    ]

    match = await TerminologyMatcher(FakeRepository(choices)).match(candidate)

    assert match.status == MatchStatus.AMBIGUOUS
    assert match.external_id is None
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_matchers.py -v
```

Expected: FAIL because `matchers.py` does not exist.

**Step 3: Implement matcher rules**

Implement:

```python
class TerminologyMatcher:
    def __init__(self, repository: StandardizationRepository):
        self._repository = repository

    async def match(self, candidate: StandardizationCandidate) -> EntityMatch:
        choices = await self._repository.find_alias_candidates(candidate.entity_type, candidate.raw_text)
        choices = self._rank(candidate, choices)
        if len(choices) == 1:
            selected = choices[0]
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.STANDARDIZED,
                external_id=selected.external_id,
                display_name=selected.display_name,
                terminology_candidates=(selected,),
                rationale=f"unique {selected.source_db} {selected.alias_type} match",
            )
        if len(choices) > 1:
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.AMBIGUOUS,
                external_id=None,
                display_name=candidate.raw_text,
                terminology_candidates=tuple(choices),
                rationale="multiple deterministic terminology candidates",
            )
        return EntityMatch(
            candidate=candidate,
            status=MatchStatus.UNMAPPED,
            external_id=None,
            display_name=candidate.raw_text,
            rationale="no deterministic terminology candidate",
        )
```

Ranking rules:

- gene: keep HGNC only.
- disease: OMIM choices first; HPO/MONDO fallback only when no OMIM candidate exists.
- phenotype: keep HPO only.
- variant: keep ClinVar only.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_matchers.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/matchers.py backend/tests/core/standardize_entities_and_align_knowledge/test_matchers.py
git commit -m "feat(standardization): match entities deterministically"
```

---

### Task 8: Implement Dual Result Adapter

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/adapters.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_adapters.py`

**Step 1: Write failing adapter tests**

Create a minimal `DualEvidenceExtractionResult` and verify candidates:

```python
def test_dual_result_adapter_extracts_chain_candidates() -> None:
    result = DualEvidenceExtractionResult(
        document_id="doc-1",
        original_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-1",
            track=Track.ORIGINAL,
            evidence_chains=[
                EvidenceChain(
                    chain_id="gene=BRCA1|variant=c.5946del",
                    gene_text="BRCA1",
                    disease_text="Breast cancer",
                    variant_text="c.5946del",
                )
            ],
        ),
        translated_result=EvidenceExtractionResult(
            status=EvidenceExtractionStatus.COMPLETED,
            document_id="doc-1",
            track=Track.TRANSLATED,
        ),
    )

    adapter = DualResultAdapter()
    output = adapter.to_standardization_input(
        result,
        source_document_id="source-1",
        processing_run_id="run-1",
    )

    assert [candidate.entity_type for candidate in output.candidates] == [
        EntityType.GENE,
        EntityType.DISEASE,
        EntityType.VARIANT,
    ]
```

Add a second test for phenotype extraction from `B.hpo_terms` and `B.clinical_phenotypes`.

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_adapters.py -v
```

Expected: FAIL because `adapters.py` does not exist.

**Step 3: Implement `DualResultAdapter`**

Implement:

- Iterate original then translated results.
- Prefer EvidenceChain for gene/disease/variant candidates.
- Extract phenotype candidates from phenotype-bearing field IDs.
- Deduplicate by `(entity_type, raw_text, chain_id)` after normalization.
- Preserve raw original/translated track payloads in `StandardizationInput.track_payloads`.

Use fixed role mapping:

```python
ROLE_BY_ENTITY_TYPE = {
    EntityType.GENE: BindingRole.SUBJECT,
    EntityType.VARIANT: BindingRole.TARGET,
    EntityType.DISEASE: BindingRole.CONTEXT,
    EntityType.PHENOTYPE: BindingRole.CONTEXT,
}
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_adapters.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/adapters.py backend/tests/core/standardize_entities_and_align_knowledge/test_adapters.py
git commit -m "feat(standardization): adapt dual extraction results"
```

---

### Task 9: Implement Standardization Service

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/core.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_core.py`

**Step 1: Write failing service tests**

Use fake matcher and repository:

```python
class FakeMatcher:
    async def match(self, candidate):
        return EntityMatch(
            candidate=candidate,
            status=MatchStatus.STANDARDIZED,
            external_id="HGNC:1100",
            display_name="BRCA1",
            rationale="test",
        )


class FakeRepository:
    def __init__(self) -> None:
        self.normalized = []
        self.run_items = []
        self.bindings = []
        self.canonical = []

    async def upsert_normalized_entity(self, match):
        self.normalized.append(match)
        return "entity-1"

    async def persist_run_evidence(self, input_data, matches):
        self.run_items.append((input_data, matches))
        return ("run-item-1",)

    async def persist_bindings(self, input_data, matches, entity_ids):
        self.bindings.append((input_data, matches, entity_ids))

    async def upsert_canonical_evidence(self, input_data, matches, entity_ids):
        self.canonical.append((input_data, matches, entity_ids))


async def test_standardization_service_matches_and_persists_candidates() -> None:
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )
    input_data = StandardizationInput(
        document_id="doc-1",
        source_document_id="source-1",
        processing_run_id="run-1",
        candidates=(candidate,),
        evidence_items=(),
    )
    repo = FakeRepository()

    result = await StandardizationService(FakeMatcher(), repo).run(input_data)

    assert result.match_count == 1
    assert repo.normalized[0].external_id == "HGNC:1100"
    assert repo.bindings
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_core.py -v
```

Expected: FAIL because `core.py` does not exist.

**Step 3: Implement service and result contract**

Add `StandardizationResult` to `contracts.py`:

```python
@dataclass(frozen=True)
class StandardizationResult:
    document_id: str
    match_count: int
    standardized_count: int
    ambiguous_count: int
    unmapped_count: int
    normalized_entity_ids: tuple[str, ...]
```

Implement `StandardizationService.run()`:

```python
class StandardizationService:
    def __init__(self, matcher: TerminologyMatcher, repository: StandardizationRepository):
        self._matcher = matcher
        self._repository = repository

    async def run(self, input_data: StandardizationInput) -> StandardizationResult:
        matches = tuple([await self._matcher.match(candidate) for candidate in input_data.candidates])
        entity_ids = tuple([await self._repository.upsert_normalized_entity(match) for match in matches])
        await self._repository.persist_run_evidence(input_data, matches)
        await self._repository.persist_bindings(input_data, matches, entity_ids)
        await self._repository.upsert_canonical_evidence(input_data, matches, entity_ids)
        return StandardizationResult(
            document_id=input_data.document_id,
            match_count=len(matches),
            standardized_count=sum(match.status == MatchStatus.STANDARDIZED for match in matches),
            ambiguous_count=sum(match.status == MatchStatus.AMBIGUOUS for match in matches),
            unmapped_count=sum(match.status == MatchStatus.UNMAPPED for match in matches),
            normalized_entity_ids=entity_ids,
        )
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_core.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/core.py backend/src/core/standardize_entities_and_align_knowledge/contracts.py backend/tests/core/standardize_entities_and_align_knowledge/test_core.py
git commit -m "feat(standardization): orchestrate entity matching"
```

---

### Task 10: Add Public API Facade

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/api.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_api.py`

**Step 1: Write failing facade tests**

```python
def test_api_exposes_standardization_service_class() -> None:
    from src.core.standardize_entities_and_align_knowledge.api import EntityStandardizationService

    assert EntityStandardizationService is not None
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_api.py -v
```

Expected: FAIL because `api.py` does not exist.

**Step 3: Implement facade**

Implement `EntityStandardizationService`:

```python
class EntityStandardizationService:
    def __init__(self, cfg: Any, session: Any):
        self._cfg = cfg
        self._session = session

    async def run_dual_result(
        self,
        result: DualEvidenceExtractionResult,
        *,
        source_document_id: str,
        processing_run_id: str,
    ) -> StandardizationResult:
        repository = StandardizationRepository(self._session)
        matcher = TerminologyMatcher(repository)
        adapter = DualResultAdapter()
        input_data = adapter.to_standardization_input(
            result,
            source_document_id=source_document_id,
            processing_run_id=processing_run_id,
        )
        return await StandardizationService(matcher, repository).run(input_data)
```

Implement `import_terminology()` for `scripts/import_terminology.py` to call importer parsers and repository upserts.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_api.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/api.py backend/tests/core/standardize_entities_and_align_knowledge/test_api.py
git commit -m "feat(standardization): expose phase three facade"
```

---

### Task 11: Add Integration Test for Dual Result Standardization

**Files:**
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_integration.py`

**Step 1: Write failing integration test**

Use fake repository-backed terminology candidates and run:

```python
async def test_dual_result_standardization_pipeline_standardizes_gene_variant_disease() -> None:
    result = build_minimal_dual_result(
        gene="BRCA1",
        disease="Breast cancer",
        variant="rs80359550",
        phenotype="Breast carcinoma",
    )

    service = build_service_with_fake_repository()
    output = await service.run_dual_result(
        result,
        source_document_id="source-1",
        processing_run_id="run-1",
    )

    assert output.standardized_count >= 3
    assert output.ambiguous_count == 0
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_integration.py -v
```

Expected: FAIL until all facade wiring is complete.

**Step 3: Fix wiring only**

Fix imports, constructor wiring, missing typed fields, and fake repository test helpers. Do not broaden feature scope.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_integration.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/tests/core/standardize_entities_and_align_knowledge/test_integration.py backend/src/core/standardize_entities_and_align_knowledge
git commit -m "test(standardization): cover dual result pipeline"
```

---

### Task 12: Verify Type Safety, Ruff, and Targeted Tests

**Files:**
- Modify only files needed to fix verification failures.

**Step 1: Run targeted tests**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge tests/dao/test_models.py tests/dao/test_alembic_migration.py -v
```

Expected: PASS.

**Step 2: Run Ruff**

Run:

```bash
cd backend
uv run ruff check src/core/standardize_entities_and_align_knowledge src/dao tests/core/standardize_entities_and_align_knowledge tests/dao
```

Expected: PASS.

**Step 3: Fix only Phase 3 regressions**

If tests or Ruff fail, use @systematic-debugging:

- Read the failing assertion.
- Reproduce with the narrowest command.
- Fix only the relevant file.
- Re-run the failing command.

**Step 4: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge backend/tests/core/standardize_entities_and_align_knowledge backend/src/dao backend/tests/dao database/migrations scripts/import_terminology.py
git commit -m "fix(standardization): satisfy phase three verification"
```

Skip this commit if there are no changes after verification.

---

### Task 13: Add Module Guide and Update Project Progress

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/README.md`
- Modify: `docs/README.md`
- Modify: `progress.txt`

**Step 1: Generate the module guide**

Use @module-guide for:

```text
backend/src/core/standardize_entities_and_align_knowledge/
```

The guide must cover:

- public facade usage
- contracts
- import flow
- matcher rules
- repository write boundaries
- unsupported next-iteration features

**Step 2: Update progress**

Append:

```text
[2026-05-25] Phase 3 entity standardization MVP implemented with terminology reference tables, deterministic matching, and evidence persistence [completed]
```

**Step 3: Organize docs**

Use @doc-organize to keep `docs/README.md` current.

**Step 4: Run final verification**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge tests/dao/test_models.py tests/dao/test_alembic_migration.py -v
uv run ruff check src/core/standardize_entities_and_align_knowledge src/dao tests/core/standardize_entities_and_align_knowledge tests/dao
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/README.md docs/README.md progress.txt
git commit -m "docs(standardization): document phase three module"
```

---

## Execution Notes

- Keep `database/terminology_database/` untracked unless the project explicitly decides to version local terminology files.
- Do not import the 28G dbSNP file in this plan.
- Do not add model configuration for embedding or arbitration in this plan.
- Do not mutate existing Phase 2 extraction contracts unless a failing Phase 3 adapter test proves a contract gap.
- Do not use bare `dict` return annotations in backend code. Use dataclasses, Pydantic models, or `TypedDict`; add `# noqa: dict-return` only for intentionally unstructured SQL projection rows.
