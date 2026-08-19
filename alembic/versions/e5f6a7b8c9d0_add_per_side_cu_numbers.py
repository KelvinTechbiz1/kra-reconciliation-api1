"""Add per-side CU numbers to session_reconciliation_results

Only the SAP-side pairing key was persisted, so fallback-paired rows (the only rows
that can be a CU Mismatch) redisplayed that one value on both sides.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = 'session_reconciliation_results'
_COLUMNS = ('sap_cu_number', 'kra_cu_number')


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(_TABLE):
        return

    existing = {c['name'] for c in inspector.get_columns(_TABLE)}
    for column in _COLUMNS:
        if column not in existing:
            op.add_column(_TABLE, sa.Column(column, sa.String(length=100), nullable=True))

    # Backfill both sides from the single stored key. For rows that matched on CU this is
    # exactly right. For fallback-paired rows the KRA value is unrecoverable from what was
    # stored — they keep the old, misleading display until the session is compared again,
    # which is no worse than before.
    op.execute(
        f"UPDATE {_TABLE} SET sap_cu_number = cu_number, kra_cu_number = cu_number "
        "WHERE sap_cu_number IS NULL AND kra_cu_number IS NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(_TABLE):
        return

    existing = {c['name'] for c in inspector.get_columns(_TABLE)}
    for column in _COLUMNS:
        if column in existing:
            op.drop_column(_TABLE, column)
