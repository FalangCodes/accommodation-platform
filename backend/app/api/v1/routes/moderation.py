from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional

from app.db.base import get_db
from app.core.dependencies import get_current_moderator
from app.models.user import User
from app.models.accommodation import Accommodation
from app.models.review import Review
from app.models.moderation import ModerationLog
from app.models.landlord import Landlord
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
    await cache_delete(key_listing(accommodation_id))

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
            Accommodation.ownership_doc_url != None
        ).order_by(Accommodation.created_at.desc())
    )
    listings = result.scalars().all()

    output = []
    for l in listings:
        # Fetch landlord
        landlord_result = await db.execute(
            select(Landlord).where(Landlord.id == l.landlord_id)
        )
        landlord = landlord_result.scalar_one_or_none()

        # Decrypt ID number
        id_number = None
        if landlord and landlord.id_number_encrypted:
            try:
                from app.core.encryption import decrypt_value
                id_number = decrypt_value(landlord.id_number_encrypted)
            except Exception:
                id_number = "Decryption failed"

        output.append({
            "id": l.id,
            "title": l.title,
            "address": l.address,
            "price_min": l.price_min,
            "price_max": l.price_max,
            "created_at": l.created_at,
            "ownership_doc_url": l.ownership_doc_url,
            "landlord": {
                "display_name": landlord.display_name if landlord else None,
                "contact_phone": landlord.contact_phone if landlord else None,
                "id_number": id_number,
                "verification_status": landlord.verification_status if landlord else None,
            } if landlord else None,
        })

    return output
# ── MODERATION LOG ────────────────────────────────────────────────────────────

@router.get("/log")
async def get_moderation_log(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    from app.models.student import Student
    from app.models.accommodation import Accommodation
    from app.models.landlord import Landlord

    page = max(1, page)
    page_size = min(max(1, page_size), 50)
    offset = (page - 1) * page_size

    # Total count
    count_result = await db.execute(select(func.count(ModerationLog.id)))
    total = count_result.scalar() or 0

    # Paginated logs
    result = await db.execute(
        select(ModerationLog)
        .order_by(ModerationLog.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    logs = result.scalars().all()

    output = []
    for log in logs:
        # Moderator name
        mod_result = await db.execute(select(User).where(User.id == log.moderator_id))
        moderator = mod_result.scalar_one_or_none()

        resource_detail = {}

        if log.resource_type == "accommodation":
            acc_result = await db.execute(
                select(Accommodation).where(Accommodation.id == log.resource_id)
            )
            acc = acc_result.scalar_one_or_none()
            if acc:
                landlord_result = await db.execute(
                    select(Landlord).where(Landlord.id == acc.landlord_id)
                )
                landlord = landlord_result.scalar_one_or_none()
                resource_detail = {
                    "title": acc.title,
                    "address": acc.address,
                    "landlord_name": landlord.display_name if landlord else None,
                    "landlord_phone": landlord.contact_phone if landlord else None,
                }

        elif log.resource_type == "review":
            review_result = await db.execute(
                select(Review).where(Review.id == log.resource_id)
            )
            review = review_result.scalar_one_or_none()
            if review:
                student_result = await db.execute(
                    select(Student).where(Student.id == review.student_id)
                )
                student = student_result.scalar_one_or_none()
                student_user = None
                if student:
                    su_result = await db.execute(
                        select(User).where(User.id == student.user_id)
                    )
                    student_user = su_result.scalar_one_or_none()
                resource_detail = {
                    "body": review.body,
                    "rating": review.rating,
                    "status": review.status,
                    "student_name": f"{student.first_name} {student.last_name}".strip() if student and student.first_name else (student_user.email if student_user else None),
                }

        elif log.resource_type == "landlord":
            landlord_result = await db.execute(
                select(Landlord).where(Landlord.id == log.resource_id)
            )
            landlord = landlord_result.scalar_one_or_none()
            if landlord:
                resource_detail = {
                    "display_name": landlord.display_name,
                    "verification_status": landlord.verification_status,
                }

        output.append({
            "id": log.id,
            "moderator_email": moderator.email if moderator else f"User #{log.moderator_id}",
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "reason": log.reason,
            "created_at": log.created_at,
            "resource_detail": resource_detail,
        })

    return {
        "items": output,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


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

    # Automatically restore the resource if upheld
    if body.decision == "upheld":
        if appeal.resource_type == "review":
            res = await db.execute(select(Review).where(Review.id == appeal.resource_id))
            review = res.scalar_one_or_none()
            if review:
                review.deleted_at = None
                review.deleted_by = None
                review.status = "released"
                await cache_delete_pattern(f"reviews:{review.accommodation_id}")
        elif appeal.resource_type == "listing":
            res = await db.execute(select(Accommodation).where(Accommodation.id == appeal.resource_id))
            acc = res.scalar_one_or_none()
            if acc:
                acc.status = "approved"
                await cache_delete(key_listing(acc.id))
                await cache_delete_pattern("search:*")

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