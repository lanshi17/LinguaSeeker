"""add source_documents.source_language column

Revision ID: source_language_20260803
Revises: account_scopes_20260709
Create Date: 2026-08-03
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "source_language_20260803"
down_revision: Union[str, None] = "account_scopes_20260709"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable ``source_language`` column to ``source_documents``.

    The column caches the normalized source-language code so the evidence list
    endpoint can read a scalar instead of parsing ``raw_metadata`` /
    ``pipeline_run_states.state_json`` on every request. Backfill is handled
    by ``scripts/backfill_source_language.py``, which reuses the Python
    normalizer to map aliases like ``"english"`` -> ``"en"`` consistently with
    the runtime extraction logic.
    """
    op.add_column(
        "source_documents",
        sa.Column("source_language", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("source_documents", "source_language")
