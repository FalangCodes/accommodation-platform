"""Add single-use email tokens and authentication token versions.

Existing accounts are not activated or marked verified by this migration.
"""
from alembic import op
import sqlalchemy as sa

revision = "b2d5e8f1a4c7"
down_revision = "a1c4f7e9b2d3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "auth_email_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_auth_email_tokens_user_id", "auth_email_tokens", ["user_id"])


def downgrade():
    op.drop_index("ix_auth_email_tokens_user_id", table_name="auth_email_tokens")
    op.drop_table("auth_email_tokens")
    op.drop_column("users", "token_version")
