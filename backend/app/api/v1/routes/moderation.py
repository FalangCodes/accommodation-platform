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
from datetime import datetime, timezone
from app.models.moderation import ModerationQueue, ModerationLog, Appeal
from app.core.dependencies import get_current_moderator
from app.schemas.moderation import AppealOut, AppealResolveBody
from app.services.cache_service import cache_delete_pattern, cache_delete, key_listing

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
    await cache_delete_pattern("search:*")
    await cache_delete(key_listing(listing_id))

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
    result = await db.execute(
        select(Accommodation).where(
            Accommodation.status == "pending",
            Accommodation.ownership_doc_url != None  # ← only show if doc uploaded
        ).order_by(Accommodation.created_at.desc())
    )
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
# ── MODERATION LOG ────────────────────────────────────────────────────────────

@router.get("/log")
async def get_moderation_log(
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ModerationLog).order_by(ModerationLog.created_at.desc())
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "moderator_id": l.moderator_id,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "reason": l.reason,
            "created_at": l.created_at,
        }
        for l in logs
    ]


# ── APPEALS (admin only) ──────────────────────────────────────────────────────

@router.get("/appeals")
async def get_pending_appeals(
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Appeal).where(Appeal.status == "pending").order_by(Appeal.id.asc())
    )
    appeals = result.scalars().all()
    return [
        {
            "id": a.id,
            "appellant_id": a.appellant_id,
            "appellant_role": a.appellant_role,
            "resource_type": a.resource_type,
            "resource_id": a.resource_id,
            "original_action_id": a.original_action_id,
            "reason": a.reason,
            "status": a.status,
            "assigned_admin_id": a.assigned_admin_id,
            "resolved_at": a.resolved_at,
        }
        for a in appeals
    ]


@router.patch("/appeals/{appeal_id}/resolve")
async def resolve_appeal(
    appeal_id: int,
    body: AppealResolveBody,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    if body.decision not in ("upheld", "dismissed"):
        raise HTTPException(status_code=400, detail="Decision must be 'upheld' or 'dismissed'")

    result = await db.execute(select(Appeal).where(Appeal.id == appeal_id))
    appeal = result.scalar_one_or_none()
    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found")
    if appeal.status != "pending":
        raise HTTPException(status_code=400, detail="Appeal already resolved")

    appeal.status = body.decision
    appeal.assigned_admin_id = current_user.id
    appeal.resolved_at = datetime.now(timezone.utc)

    log_entry = ModerationLog(
        moderator_id=current_user.id,
        action=f"appeal_{body.decision}",
        resource_type=appeal.resource_type,
        resource_id=appeal.resource_id,
        reason=body.reason,
    )
    db.add(log_entry)
    await db.commit()

    return {"detail": f"Appeal {body.decision}", "appeal_id": appeal_id}

from app.models.review import Review, ReviewNLPResult

@router.patch("/reviews/{review_id}/release")
async def release_review(
    review_id: int,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Review).where(Review.id == review_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.status != "quarantined":
        raise HTTPException(status_code=400, detail="Review is not quarantined")

    review.status = "released"

    log_entry = ModerationLog(
        moderator_id=current_user.id,
        action="released",
        resource_type="review",
        resource_id=review_id,
    )
    db.add(log_entry)
    await db.commit()

    return {"detail": "Review released and now publicly visible", "review_id": review_id}