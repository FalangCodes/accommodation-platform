from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import Optional

from app.db.base import get_db
from app.core.dependencies import get_current_moderator
from app.models.user import User
from app.models.accommodation import Accommodation
from app.models.review import Review
from app.models.moderation import ModerationLog

router = APIRouter(prefix="/moderation", tags=["Moderation"])


class ModerationDecision(BaseModel):
    reason: Optional[str] = None


# ── LISTING MODERATION ────────────────────────────────────────────────────────

@router.patch("/listings/{accommodation_id}/approve", status_code=status.HTTP_200_OK)
async def approve_listing(
    accommodation_id: int,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    query = select(Accommodation).where(Accommodation.id == accommodation_id)
    result = await db.execute(query)
    accommodation = result.scalar_one_or_none()

    if not accommodation:
        raise HTTPException(status_code=404, detail="Accommodation not found")

    if accommodation.status == "approved":
        raise HTTPException(status_code=409, detail="Listing is already approved")

    accommodation.status = "approved"

    log = ModerationLog(
        moderator_id=current_user.id,
        action="approve_listing",
        resource_type="accommodation",
        resource_id=accommodation_id
    )
    db.add(log)
    await db.commit()

    return {"message": f"Listing {accommodation_id} approved successfully"}


@router.patch("/listings/{accommodation_id}/reject", status_code=status.HTTP_200_OK)
async def reject_listing(
    accommodation_id: int,
    decision: ModerationDecision,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    query = select(Accommodation).where(Accommodation.id == accommodation_id)
    result = await db.execute(query)
    accommodation = result.scalar_one_or_none()

    if not accommodation:
        raise HTTPException(status_code=404, detail="Accommodation not found")

    accommodation.status = "rejected"

    log = ModerationLog(
        moderator_id=current_user.id,
        action="reject_listing",
        resource_type="accommodation",
        resource_id=accommodation_id,
        reason=decision.reason
    )
    db.add(log)
    await db.commit()

    return {"message": f"Listing {accommodation_id} rejected", "reason": decision.reason}


# ── REVIEW MODERATION ─────────────────────────────────────────────────────────

@router.delete("/reviews/{review_id}", status_code=status.HTTP_200_OK)
async def remove_review(
    review_id: int,
    decision: ModerationDecision,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    query = select(Review).where(
        Review.id == review_id,
        Review.deleted_at == None
    )
    result = await db.execute(query)
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    from datetime import datetime, timezone
    review.deleted_at = datetime.now(timezone.utc)
    review.deleted_by = current_user.id

    log = ModerationLog(
        moderator_id=current_user.id,
        action="remove_review",
        resource_type="review",
        resource_id=review_id,
        reason=decision.reason
    )
    db.add(log)
    await db.commit()

    return {"message": f"Review {review_id} removed", "reason": decision.reason}


# ── PENDING LISTINGS QUEUE ────────────────────────────────────────────────────

@router.get("/listings/pending")
async def get_pending_listings(
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    query = select(Accommodation).where(Accommodation.status == "pending")
    result = await db.execute(query)
    listings = result.scalars().all()

    return [
        {
            "id": l.id,
            "title": l.title,
            "address": l.address,
            "price_min": l.price_min,
            "price_max": l.price_max,
            "created_at": l.created_at
        }
        for l in listings
    ]