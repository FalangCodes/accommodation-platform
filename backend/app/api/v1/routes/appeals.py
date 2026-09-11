from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone

from app.db.base import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.student import Student
from app.models.landlord import Landlord
from app.models.moderation import Appeal, ModerationLog
from app.schemas.moderation import AppealCreate, AppealOut

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
        resolved_action_id = log_entry.id
    else:
        # Auto-resolve: find the most recent log entry for this resource
        log_result = await db.execute(
            select(ModerationLog)
            .where(
                ModerationLog.resource_type == body.resource_type,
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


    # Check no duplicate appeal already exists for this resource + appellant
    existing = await db.execute(
        select(Appeal).where(
            Appeal.appellant_id == current_user.id,
            Appeal.resource_type == body.resource_type,
            Appeal.resource_id == body.resource_id,
            Appeal.status == "pending",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a pending appeal for this item.",
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
