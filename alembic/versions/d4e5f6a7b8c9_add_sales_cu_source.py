"""Add sales_cu_source to company_settings

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-30 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    if inspector.has_table('company_settings'):
        cols = [c['name'] for c in inspector.get_columns('company_settings')]
        if 'sales_cu_source' not in cols:
            op.add_column(
                'company_settings',
                sa.Column(
                    'sales_cu_source',
                    sa.String(length=50),
                    nullable=False,
                    server_default='U_CUINV',
                    comment='SAP field holding the CU number on Sales Invoices',
                ),
            )

    if inspector.has_table('system_settings'):
        cols = [c['name'] for c in inspector.get_columns('system_settings')]
        if 'sales_cu_source' not in cols:
            op.add_column(
                'system_settings',
                sa.Column(
                    'sales_cu_source',
                    sa.String(length=50),
                    nullable=False,
                    server_default='U_CUINV',
                    comment='SAP field holding the CU number on Sales Invoices',
                ),
            )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    if inspector.has_table('company_settings'):
        cols = [c['name'] for c in inspector.get_columns('company_settings')]
        if 'sales_cu_source' in cols:
            op.drop_column('company_settings', 'sales_cu_source')

    if inspector.has_table('system_settings'):
        cols = [c['name'] for c in inspector.get_columns('system_settings')]
        if 'sales_cu_source' in cols:
            op.drop_column('system_settings', 'sales_cu_source')
