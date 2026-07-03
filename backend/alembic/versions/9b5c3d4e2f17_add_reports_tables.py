"""add monthly reports tables

Revision ID: 9b5c3d4e2f17
Revises: 8c4d2e9f3a17
Create Date: 2026-06-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '9b5c3d4e2f17'
down_revision = '8c4d2e9f3a17'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'monthly_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_type', sa.String(), nullable=False),
        sa.Column('period_year', sa.Integer(), nullable=False),
        sa.Column('period_month', sa.Integer(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('generated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='generating'),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('entity_type', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_monthly_reports_period', 'monthly_reports', ['period_year', 'period_month'])
    op.create_index('ix_monthly_reports_type', 'monthly_reports', ['report_type'])

    op.create_table(
        'report_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_id', sa.Integer(), sa.ForeignKey('monthly_reports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('metric_key', sa.String(), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=True),
        sa.Column('metric_label', sa.String(), nullable=False),
        sa.Column('metric_category', sa.String(), nullable=False),
        sa.Column('breakdown', JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_report_metrics_report_id', 'report_metrics', ['report_id'])


def downgrade() -> None:
    op.drop_index('ix_report_metrics_report_id', table_name='report_metrics')
    op.drop_table('report_metrics')
    op.drop_index('ix_monthly_reports_type', table_name='monthly_reports')
    op.drop_index('ix_monthly_reports_period', table_name='monthly_reports')
    op.drop_table('monthly_reports')