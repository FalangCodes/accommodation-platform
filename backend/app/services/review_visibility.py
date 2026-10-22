"""One publication rule for reviews and their derived public metrics."""
from sqlalchemy import and_, or_, exists, select
from app.models.review import Review, ReviewNLPResult


def published_review_condition():
    flagged = exists(select(1).select_from(ReviewNLPResult).where(
        ReviewNLPResult.review_id == Review.id,
        ReviewNLPResult.spam_flag.is_(True),
    )).correlate(Review)
    return and_(Review.deleted_at.is_(None), or_(
        Review.status == "released",
        and_(Review.status == "analysed", ~flagged),
    ))


# Static alias used by the discovery queries; never interpolate user input here.
PUBLISHED_REVIEW_SQL = """r.deleted_at IS NULL AND (
    r.status = 'released' OR (r.status = 'analysed' AND NOT EXISTS (
        SELECT 1 FROM review_nlp_results moderation_flags
        WHERE moderation_flags.review_id = r.id AND moderation_flags.spam_flag IS TRUE
    ))
)"""
