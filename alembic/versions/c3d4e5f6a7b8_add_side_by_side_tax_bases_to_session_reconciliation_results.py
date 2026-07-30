"""add_side_by_side_tax_bases_to_session_reconciliation_results

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-07-30 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('session_reconciliation_results')]
    
    new_cols = [
        'sap_base_16', 'sap_base_8', 'sap_base_0', 'sap_base_exempt',
        'kra_base_16', 'kra_base_8', 'kra_base_0', 'kra_base_exempt'
    ]
    for col_name in new_cols:
        if col_name not in cols:
            op.add_column('session_reconciliation_results', sa.Column(col_name, sa.Numeric(18, 2), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('session_reconciliation_results')]
    
    new_cols = [
        'sap_base_16', 'sap_base_8', 'sap_base_0', 'sap_base_exempt',
        'kra_base_16', 'kra_base_8', 'kra_base_0', 'kra_base_exempt'
    ]
    for col_name in new_cols:
        if col_name in cols:
            op.drop_column('session_reconciliation_results', col_name)
