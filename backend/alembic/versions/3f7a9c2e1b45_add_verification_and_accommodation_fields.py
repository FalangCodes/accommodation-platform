"""add verification and accommodation fields

Revision ID: 3f7a9c2e1b45
Revises: 9a856dfe8c39
Create Date: 2026-06-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '3f7a9c2e1b45'
down_revision = '9a856dfe8c39'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Students ──────────────────────────────────────────────────────────────
    op.add_column('students', sa.Column('first_name', sa.String(), nullable=True))
    op.add_column('students', sa.Column('last_name', sa.String(), nullable=True))
    op.add_column('students', sa.Column('student_number', sa.String(), nullable=True))

    # ── Landlords ─────────────────────────────────────────────────────────────
    op.add_column('landlords', sa.Column('website', sa.String(), nullable=True))
    op.add_column('landlords', sa.Column('id_number_encrypted', sa.String(), nullable=True))
    op.add_column('landlords', sa.Column('id_number_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('landlords', sa.Column('verification_status', sa.String(), nullable=False, server_default='unverified'))
    op.add_column('landlords', sa.Column('rejection_reason', sa.String(), nullable=True))

    # ── Landlord Documents ────────────────────────────────────────────────────
    op.create_table(
        'landlord_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('landlord_id', sa.Integer(), sa.ForeignKey('landlords.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_type', sa.String(), nullable=False),
        sa.Column('blob_url', sa.String(), nullable=False),
        sa.Column('verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_landlord_documents_landlord_id', 'landlord_documents', ['landlord_id'])

    # ── Accommodations ────────────────────────────────────────────────────────
    op.add_column('accommodations', sa.Column('gender_policy', sa.String(), nullable=True))
    op.add_column('accommodations', sa.Column('funding_type', sa.String(), nullable=True))
    op.add_column('accommodations', sa.Column('property_type', sa.String(), nullable=True))
    op.add_column('accommodations', sa.Column('website', sa.String(), nullable=True))
    op.add_column('accommodations', sa.Column('amenities', JSONB(), nullable=True))


def downgrade() -> None:
    # Accommodations
    op.drop_column('accommodations', 'amenities')
    op.drop_column('accommodations', 'website')
    op.drop_column('accommodations', 'property_type')
    op.drop_column('accommodations', 'funding_type')
    op.drop_column('accommodations', 'gender_policy')

    # Landlord documents
    op.drop_index('ix_landlord_documents_landlord_id', table_name='landlord_documents')
    op.drop_table('landlord_documents')

    # Landlords
    op.drop_column('landlords', 'rejection_reason')
    op.drop_column('landlords', 'verification_status')
    op.drop_column('landlords', 'id_number_verified')
    op.drop_column('landlords', 'id_number_encrypted')
    op.drop_column('landlords', 'website')

    # Students
    op.drop_column('students', 'student_number')
    op.drop_column('students', 'last_name')
    op.drop_column('students', 'first_name')