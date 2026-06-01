"""add_fk_chat_message_evidence_entity

Revision ID: 547f7e3f71e3
Revises: 4ce26825046c
Create Date: 2026-06-01 10:46:30.691420+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '547f7e3f71e3'
down_revision: Union[str, None] = '4ce26825046c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Clean orphaned references before adding FK constraints
    op.execute("""
        DELETE FROM chat_messages
        WHERE evidence_id IS NOT NULL
          AND evidence_id NOT IN (SELECT canonical_evidence_id FROM canonical_evidence_items)
    """)
    op.execute("""
        DELETE FROM chat_messages
        WHERE entity_id IS NOT NULL
          AND entity_id NOT IN (SELECT entity_id FROM normalized_entities)
    """)

    # Add FK constraints
    op.create_foreign_key(
        'fk_chat_messages_evidence_id',
        'chat_messages',
        'canonical_evidence_items',
        ['evidence_id'],
        ['canonical_evidence_id'],
    )
    op.create_foreign_key(
        'fk_chat_messages_entity_id',
        'chat_messages',
        'normalized_entities',
        ['entity_id'],
        ['entity_id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_chat_messages_entity_id', 'chat_messages', type_='foreignkey')
    op.drop_constraint('fk_chat_messages_evidence_id', 'chat_messages', type_='foreignkey')
