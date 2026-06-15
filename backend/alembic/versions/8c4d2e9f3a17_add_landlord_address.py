"""add landlord address fields

Revision ID: 8c4d2e9f3a17
Revises: 7d3e8f1a2b56
Create Date: 2026-06-11

"""
from alembic import op
import sqlalchemy as sa

revision = '8c4d2e9f3a17'
down_revision = '7d3e8f1a2b56'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('landlords', sa.Column('address_line1', sa.String(), nullable=True))
    op.add_column('landlords', sa.Column('address_line2', sa.String(), nullable=True))
    op.add_column('landlords', sa.Column('city', sa.String(), nullable=True))
    op.add_column('landlords', sa.Column('province', sa.String(), nullable=True))
    op.add_column('landlords', sa.Column('postal_code', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('landlords', 'postal_code')
    op.drop_column('landlords', 'province')
    op.drop_column('landlords', 'city')
    op.drop_column('landlords', 'address_line2')
    op.drop_column('landlords', 'address_line1')