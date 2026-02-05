"""Add task type enum and ensure parsing_tasks schema matches models."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "20240204_add_task_type_enum"
down_revision = None
branch_labels = None
depends_on = None


task_status_enum = sa.Enum(
    "PENDING",
    "PROCESSING",
    "COMPLETED",
    "FAILED",
    "RETRY",
    name="taskstatus",
)

task_stage_enum = sa.Enum(
    "INGESTION",
    "DECOMPOSITION",
    "LAYOUT",
    "TRANSLATION",
    "EVIDENCE",
    "ARBITRATION",
    "COMPLETED",
    name="taskstage",
)

task_type_enum = sa.Enum(
    "pdf_parse",
    "identifier_resolve",
    name="tasktype",
)


def upgrade() -> None:
    bind = op.get_bind()

    # Ensure the enum types exist before they are referenced by columns.
    task_status_enum.create(bind, checkfirst=True)
    task_stage_enum.create(bind, checkfirst=True)
    task_type_enum.create(bind, checkfirst=True)

    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("parsing_tasks")}

    if "task_type" not in columns:
        op.add_column(
            "parsing_tasks",
            sa.Column(
                "task_type",
                task_type_enum,
                nullable=False,
                server_default="pdf_parse",
            ),
        )
        op.execute("ALTER TABLE parsing_tasks ALTER COLUMN task_type DROP DEFAULT")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("parsing_tasks")}

    if "task_type" in columns:
        op.drop_column("parsing_tasks", "task_type")

    # Drop enums last to avoid dependency issues.
    task_type_enum.drop(bind, checkfirst=True)
    task_stage_enum.drop(bind, checkfirst=True)
    task_status_enum.drop(bind, checkfirst=True)
