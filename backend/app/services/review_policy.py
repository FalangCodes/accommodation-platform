from datetime import datetime, timezone
from sqlalchemy import select, func
from app.models.review import Review

ACTIVE_REVIEW_INDEX = "uix_student_accommodation_review"


def now():
    return datetime.now(timezone.utc)


async def review_eligibility(db, student_id, accommodation_id):
    result = await db.execute(select(Review).where(
        Review.student_id == student_id, Review.accommodation_id == accommodation_id,
        Review.deleted_at.is_(None),
    ).limit(1))
    active = result.scalar_one_or_none()
    if active:
        return {"can_review": False, "code": "active_review", "active_review_id": active.id,
                "message": "You already have a review for this listing, including any review awaiting analysis or moderation.",
                "available_at": None}
    result = await db.execute(select(func.max(Review.cooldown_expires_at)).where(
        Review.student_id == student_id, Review.accommodation_id == accommodation_id,
        Review.deleted_at.is_not(None),
    ))
    deadline = result.scalar_one_or_none()
    if deadline and deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if deadline and deadline > now():
        return {"can_review": False, "code": "cooldown", "active_review_id": None,
                "message": "Your 14-day cooldown has not ended yet.", "available_at": deadline.isoformat()}
    return {"can_review": True, "code": "eligible", "active_review_id": None,
            "message": "Share your experience", "available_at": None}


def is_active_review_conflict(error):
    original = error.orig
    names = [getattr(original, "constraint_name", None),
             getattr(getattr(original, "__cause__", None), "constraint_name", None),
             getattr(getattr(original, "diag", None), "constraint_name", None)]
    return ACTIVE_REVIEW_INDEX in names
