"""add_invoice_type_to_session_reconciliation_results

Revision ID: a1b2c3d4e5f6
Revises: f9b876543210
Create Date: 2026-07-30 14:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f9b876543210'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('session_reconciliation_results')]
    if 'invoice_type' not in cols:
        op.add_column(
            'session_reconciliation_results',
            sa.Column('invoice_type', sa.String(length=50), nullable=True, server_default='Single Tax')
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('session_reconciliation_results')]
    if 'invoice_type' in cols:
        op.drop_column('session_reconciliation_results', 'invoice_type')
