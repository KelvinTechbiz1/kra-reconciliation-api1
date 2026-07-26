"""add_import_profiles_and_snapshots

Revision ID: f9b876543210
Revises: c2e0605bf454
Create Date: 2026-07-26 18:47:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9b876543210'
down_revision: Union[str, None] = 'c2e0605bf454'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create import_profiles table
    op.create_table(
        'import_profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('company.id', ondelete='CASCADE'), nullable=True),
        sa.Column('scope', sa.String(length=20), nullable=False, server_default='company'),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('module', sa.String(length=20), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False, server_default='CUSTOM'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_format', sa.String(length=10), nullable=False, server_default='csv'),
        sa.Column('parsing_hints', sa.JSON(), nullable=False),
        sa.Column('column_mapping', sa.JSON(), nullable=False),
        sa.Column('validation_rules', sa.JSON(), nullable=False),
        sa.Column('is_builtin', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'module', 'name', name='uq_company_module_profile_name')
    )
    op.create_index('ix_import_profiles_id', 'import_profiles', ['id'])
    op.create_index('ix_import_profiles_company_id', 'import_profiles', ['company_id'])

    # 2. Add columns to reconciliation_sessions
    op.add_column('reconciliation_sessions', sa.Column('import_profile_id', sa.Integer(), sa.ForeignKey('import_profiles.id', ondelete='SET NULL'), nullable=True))
    op.add_column('reconciliation_sessions', sa.Column('import_profile_name', sa.String(length=100), nullable=True))
    op.add_column('reconciliation_sessions', sa.Column('import_profile_version_used', sa.Integer(), nullable=True))
    op.add_column('reconciliation_sessions', sa.Column('provider', sa.String(length=50), nullable=True))
    op.add_column('reconciliation_sessions', sa.Column('source_format', sa.String(length=10), nullable=True))
    op.add_column('reconciliation_sessions', sa.Column('import_profile_snapshot', sa.JSON(), nullable=True))

    # 3. Add provider column to session_invoices
    op.add_column('session_invoices', sa.Column('provider', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('session_invoices', 'provider')
    op.drop_column('reconciliation_sessions', 'import_profile_snapshot')
    op.drop_column('reconciliation_sessions', 'source_format')
    op.drop_column('reconciliation_sessions', 'provider')
    op.drop_column('reconciliation_sessions', 'import_profile_version_used')
    op.drop_column('reconciliation_sessions', 'import_profile_name')
    op.drop_column('reconciliation_sessions', 'import_profile_id')
    op.drop_table('import_profiles')
