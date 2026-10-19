"""Add ca_certificate to company_sap_connections

SAP Business One Service Layer ships with a self-signed certificate, which the system CA
store rejects. Each connection can now pin the certificate its server presents so TLS stays
verified instead of being switched off.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = 'company_sap_connections'
_COLUMN = 'ca_certificate'


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(_TABLE):
        return

    if _COLUMN not in {c['name'] for c in inspector.get_columns(_TABLE)}:
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(_TABLE):
        return

    if _COLUMN in {c['name'] for c in inspector.get_columns(_TABLE)}:
        op.drop_column(_TABLE, _COLUMN)
