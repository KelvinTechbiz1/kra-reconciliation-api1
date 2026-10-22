"""Add configurable purchase invoice fields to company_settings

Some companies record the real VAT code and VAT-exclusive amount of a purchase invoice in
UDFs (e.g. U_Taxable, U_ExcVat) because the standard fields are booked as zero-rated with
the VAT-inclusive amount. These settings name the SAP fields to compare instead.
NULL field names keep the standard TaxPercentagePerRow/VatGroup and LineTotal fields.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-22 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = 'company_settings'
_COLUMNS = [
    sa.Column('purchase_vat_field', sa.String(length=50), nullable=True),
    sa.Column('purchase_vat_field_level', sa.String(length=10), nullable=False, server_default='line'),
    sa.Column('purchase_amount_field', sa.String(length=50), nullable=True),
    sa.Column('purchase_amount_field_level', sa.String(length=10), nullable=False, server_default='line'),
]


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(_TABLE):
        return

    existing = {c['name'] for c in inspector.get_columns(_TABLE)}
    for column in _COLUMNS:
        if column.name not in existing:
            op.add_column(_TABLE, column)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(_TABLE):
        return

    existing = {c['name'] for c in inspector.get_columns(_TABLE)}
    for column in reversed(_COLUMNS):
        if column.name in existing:
            op.drop_column(_TABLE, column.name)
