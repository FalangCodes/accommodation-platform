"""restructure documents — embed in landlord and accommodation

Revision ID: 7d3e8f1a2b56
Revises: 3f7a9c2e1b45
Create Date: 2026-06-11

"""
from alembic import op
import sqlalchemy as sa

revision = '7d3e8f1a2b56'
down_revision = '3f7a9c2e1b45'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add document URLs to landlords
    op.add_column('landlords', sa.Column('id_copy_url', sa.String(), nullable=True))
    op.add_column('landlords', sa.Column('proof_of_address_url', sa.String(), nullable=True))

    # Add ownership doc to accommodations
    op.add_column('accommodations', sa.Column('ownership_doc_url', sa.String(), nullable=True))

    # Drop landlord_documents table
    op.drop_index('ix_landlord_documents_landlord_id', table_name='landlord_documents')
    op.drop_table('landlord_documents')


def downgrade() -> None:
    # Recreate landlord_documents
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

    # Remove added columns
    op.drop_column('accommodations', 'ownership_doc_url')
    op.drop_column('landlords', 'proof_of_address_url')
    op.drop_column('landlords', 'id_copy_url')