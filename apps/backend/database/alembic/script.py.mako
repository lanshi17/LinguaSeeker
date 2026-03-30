<%text>
"""Empty message

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
</%text>
from __future__ import annotations

from typing import Final

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: Final[str] = ${repr(up_revision)}
down_revision: Final[str] = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
	pass


def downgrade() -> None:
	pass
