"""add insight engine tables

Revision ID: a1c4f7e9b2d3
Revises: 9b5c3d4e2f17
Create Date: 2026-07-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'a1c4f7e9b2d3'
down_revision = '9b5c3d4e2f17'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add aspect_details to review_nlp_results
    op.add_column(
        'review_nlp_results',
        sa.Column('aspect_details', JSONB(), nullable=True)
    )

    # Create accommodation_insights table
    op.create_table(
        'accommodation_insights',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('accommodation_id', sa.Integer(),
                  sa.ForeignKey('accommodations.id', ondelete='CASCADE'),
                  nullable=False, unique=True),
        sa.Column('insights', JSONB(), nullable=False),
        sa.Column('recommendations', JSONB(), nullable=False),
        sa.Column('review_count', sa.Integer(), default=0),
        sa.Column('generated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_accommodation_insights_accommodation_id',
        'accommodation_insights',
        ['accommodation_id'],
        unique=True
    )


def downgrade() -> None:
    op.drop_index('ix_accommodation_insights_accommodation_id',
                  table_name='accommodation_insights')
    op.drop_table('accommodation_insights')
    op.drop_column('review_nlp_results', 'aspect_details')