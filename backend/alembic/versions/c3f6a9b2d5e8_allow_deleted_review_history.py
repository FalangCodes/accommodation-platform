"""Retain review history while enforcing one non-deleted review per pair."""
from alembic import op
import sqlalchemy as sa

revision = "c3f6a9b2d5e8"
down_revision = "b2d5e8f1a4c7"
branch_labels = None
depends_on = None
NAME = "uix_student_accommodation_review"


def upgrade():
    op.drop_constraint(NAME, "reviews", type_="unique")
    op.create_index(NAME, "reviews", ["student_id", "accommodation_id"], unique=True,
                    postgresql_where=sa.text("deleted_at IS NULL"))


def downgrade():
    if op.get_bind().execute(sa.text(
        "SELECT 1 FROM reviews GROUP BY student_id, accommodation_id HAVING COUNT(*) > 1 LIMIT 1"
    )).first():
        raise RuntimeError("Cannot restore the lifetime constraint while historical review rows exist; no data was deleted.")
    op.drop_index(NAME, table_name="reviews")
    op.create_unique_constraint(NAME, "reviews", ["student_id", "accommodation_id"])
