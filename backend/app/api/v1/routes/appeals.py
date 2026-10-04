from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from datetime import datetime, timezone

from app.db.base import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.student import Student
from app.models.landlord import Landlord
from app.models.accommodation import Accommodation
from app.models.review import Review
from app.models.moderation import Appeal, ModerationLog
from app.schemas.moderation import AppealCreate, AppealOut
from app.services.appeal_policy import validate_current_penalty, ensure_quarantine_action

router = APIRouter(prefix="/appeals", tags=["Appeals"])


# ── Submit an appeal ──────────────────────────────────────────────────────────

@router.post("", response_model=AppealOut, status_code=status.HTTP_201_CREATED)
async def submit_appeal(
    body: AppealCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a moderation appeal. Accessible to students and landlords only.
    Moderators and admins cannot submit appeals.
    """
    if current_user.role not in ("student", "landlord"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students and landlords can submit appeals.",
        )

    if len(body.reason.strip()) < 20:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Appeal reason must be at least 20 characters.",
        )

    if body.resource_type not in ("review", "listing", "landlord"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="resource_type must be one of: review, listing, landlord.",
        )

    # Ownership must be established before looking up actions or duplicates.
    if body.resource_type == "review":
        if current_user.role != "student":
            raise HTTPException(status_code=403, detail="Only the review author can appeal this review.")
        result = await db.execute(select(Student).where(Student.user_id == current_user.id).with_for_update())
        student = result.scalar_one_or_none()
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")
        result = await db.execute(select(Review).where(
            Review.id == body.resource_id, Review.student_id == student.id,
        ).with_for_update())
    else:
        if current_user.role != "landlord":
            raise HTTPException(status_code=403, detail="Only the owning landlord can appeal this item.")
        result = await db.execute(select(Landlord).where(Landlord.user_id == current_user.id).with_for_update())
        landlord = result.scalar_one_or_none()
        if not landlord:
            raise HTTPException(status_code=404, detail="Landlord profile not found")
        if body.resource_type == "listing":
            result = await db.execute(select(Accommodation).where(
                Accommodation.id == body.resource_id, Accommodation.landlord_id == landlord.id,
            ).with_for_update())
        else:
            result = await db.execute(select(Landlord).where(
                Landlord.id == body.resource_id, Landlord.user_id == current_user.id,
            ))
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="Appealable item not found")

    lookup_type = "accommodation" if body.resource_type == "listing" else body.resource_type

    if body.resource_type == "review":
        await ensure_quarantine_action(db, resource)

    # Resolve the moderation log entry — use provided ID or look up the latest one
    if body.original_action_id is not None:
        log_result = await db.execute(
            select(ModerationLog).where(ModerationLog.id == body.original_action_id)
        )
        log_entry = log_result.scalar_one_or_none()
        if not log_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The referenced moderation action was not found.",
            )
        if log_entry.resource_type != lookup_type or log_entry.resource_id != body.resource_id:
            raise HTTPException(status_code=422, detail="The moderation action does not match this item.")
        resolved_action_id = log_entry.id
    else:
        # Auto-resolve: find the most recent log entry for this resource
        # Note: ModerationLog saves listings under 'accommodation'
        lookup_type = "accommodation" if body.resource_type == "listing" else body.resource_type
        
        log_result = await db.execute(
            select(ModerationLog)
            .where(
                ModerationLog.resource_type == lookup_type,
                ModerationLog.resource_id == body.resource_id,
            )
            .order_by(ModerationLog.id.desc())
            .limit(1)
        )
        log_entry = log_result.scalar_one_or_none()
        if not log_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No moderation action found for this item. There is nothing to appeal.",
            )
        resolved_action_id = log_entry.id


    await validate_current_penalty(db, body.resource_type, resource, log_entry)

    # Serialize on the owner profile so concurrent requests cannot create duplicates.
    existing = await db.execute(
        select(Appeal).where(
            Appeal.appellant_id == current_user.id,
            Appeal.resource_type == body.resource_type,
            Appeal.resource_id == body.resource_id,
            or_(Appeal.status == "pending", Appeal.original_action_id == resolved_action_id),
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An appeal is already pending for this item, or this action has already been appealed.",
        )

    appeal = Appeal(
        appellant_id=current_user.id,
        appellant_role=current_user.role,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        original_action_id=resolved_action_id,
        reason=body.reason.strip(),
        status="pending",
    )
    db.add(appeal)
    await db.commit()
    await db.refresh(appeal)
    return appeal


# ── Get current user's own appeals ───────────────────────────────────────────

@router.get("/my", response_model=list[AppealOut])
async def get_my_appeals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all appeals submitted by the currently authenticated user."""
    result = await db.execute(
        select(Appeal)
        .where(Appeal.appellant_id == current_user.id)
        .order_by(Appeal.id.desc())
    )
    return result.scalars().all()
