"""Add source_filename to session_invoices

KRA uploads append, and nothing recorded which rows came from which CSV, so one mistaken
upload could only be undone by abandoning the session. Tagging each row with its file
makes a single upload removable.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = 'session_invoices'
_COLUMN = 'source_filename'
_INDEX = 'ix_session_invoices_session_source_file'


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(_TABLE):
        return

    # No backfill. Rows stored before this column existed have no recoverable filename;
    # they stay NULL and are simply not removable per-file. Sessions expire after 30
    # minutes of inactivity, so the untagged population drains on its own.
    if _COLUMN not in {c['name'] for c in inspector.get_columns(_TABLE)}:
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(length=255), nullable=True))

    if _INDEX not in {i['name'] for i in inspector.get_indexes(_TABLE)}:
        op.create_index(_INDEX, _TABLE, ['session_id', 'source', _COLUMN])


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(_TABLE):
        return

    if _INDEX in {i['name'] for i in inspector.get_indexes(_TABLE)}:
        op.drop_index(_INDEX, table_name=_TABLE)

    if _COLUMN in {c['name'] for c in inspector.get_columns(_TABLE)}:
        op.drop_column(_TABLE, _COLUMN)
