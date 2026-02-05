"""Align publication_date column and parsing task FK/enum."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20250205_adjust_documents_and_tasks"
down_revision = "20240204_add_task_type_enum"
branch_labels = None
depends_on = None


def _ensure_publication_date(bind) -> None:
    inspector = inspect(bind)
    columns = inspector.get_columns("documents")
    publication_column = next(
        (col for col in columns if col["name"] == "publication_date"), None
    )

    if publication_column is None:
        op.add_column(
            "documents",
            sa.Column("publication_date", sa.DateTime(timezone=True), nullable=True),
        )
        return

    # If the column exists but is not timezone-aware, upgrade the type
    col_type = publication_column["type"]
    is_timezone_aware = getattr(col_type, "timezone", False)
    if not is_timezone_aware:
        op.alter_column(
            "documents",
            "publication_date",
            existing_type=sa.Date(),
            type_=sa.DateTime(timezone=True),
            postgresql_using="publication_date::timestamp with time zone",
        )


def _ensure_tasktype_enum_has_data_extraction() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_enum e ON t.oid = e.enumtypid
                WHERE t.typname = 'tasktype'
                  AND e.enumlabel = 'data_extraction'
            ) THEN
                ALTER TYPE tasktype ADD VALUE 'data_extraction';
            END IF;
        END $$;
        """
    )


def _rebuild_document_fk(bind) -> None:
    inspector = inspect(bind)
    fks = inspector.get_foreign_keys("parsing_tasks")
    for fk in fks:
        if fk["constrained_columns"] == ["document_id"]:
            op.drop_constraint(fk["name"], "parsing_tasks", type_="foreignkey")
            break

    op.alter_column(
        "parsing_tasks",
        "document_id",
        existing_type=postgresql.UUID(),
        nullable=True,
    )

    op.create_foreign_key(
        "parsing_tasks_document_id_fkey",
        "parsing_tasks",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="SET NULL",
        deferrable=True,
        initially="IMMEDIATE",
    )


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_publication_date(bind)
    _ensure_tasktype_enum_has_data_extraction()
    _rebuild_document_fk(bind)


def downgrade() -> None:
    # Rebuild FK without deferrable/on delete options and make document_id NOT NULL again
    op.drop_constraint("parsing_tasks_document_id_fkey", "parsing_tasks", type_="foreignkey")
    op.alter_column(
        "parsing_tasks",
        "document_id",
        existing_type=postgresql.UUID(),
        nullable=False,
    )
    op.create_foreign_key(
        "parsing_tasks_document_id_fkey",
        "parsing_tasks",
        "documents",
        ["document_id"],
        ["id"],
    )

    # Removing enum values in PostgreSQL requires recreating the type.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_enum e ON t.oid = e.enumtypid
                WHERE t.typname = 'tasktype'
                  AND e.enumlabel = 'data_extraction'
            ) THEN
                ALTER TYPE tasktype RENAME TO tasktype_with_data_extraction;
                CREATE TYPE tasktype AS ENUM ('pdf_parse', 'identifier_resolve');
                ALTER TABLE parsing_tasks
                    ALTER COLUMN task_type TYPE tasktype
                    USING task_type::text::tasktype;
                DROP TYPE tasktype_with_data_extraction;
            END IF;
        END $$;
        """
    )

    # Revert publication_date to DATE for completeness
    op.alter_column(
        "documents",
        "publication_date",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.Date(),
        postgresql_using="publication_date::date",
    )
