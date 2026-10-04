"""Appeals apply to the current penalty, never to an older or positive action."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import secrets
from app.core.security import get_password_hash

from app.models.moderation import ModerationLog
from app.models.user import User

SYSTEM_EMAIL = "automated-moderation@accomfind.invalid"
PENALTIES = {
    "review": {"remove_review", "quarantined"},
    "listing": {"reject_listing", "suspend_listing", "remove_listing"},
    "landlord": {"landlord_verification_rejected"},
}


def log_resource_type(resource_type):
    return "accommodation" if resource_type == "listing" else resource_type


def penalty_applies(resource_type, resource, action):
    if resource_type == "review":
        return (resource.deleted_at is not None and resource.deleted_by is not None
                if action == "remove_review"
                else resource.deleted_at is None and resource.status == "quarantined")
    if resource_type == "listing":
        return resource.status == {"reject_listing": "rejected", "suspend_listing": "suspended",
                                   "remove_listing": "removed"}.get(action)
    return resource.verification_status == "rejected"


async def latest_action(db, resource_type, resource_id):
    result = await db.execute(select(ModerationLog).where(
        ModerationLog.resource_type == log_resource_type(resource_type),
        ModerationLog.resource_id == resource_id,
        # Closing an older appeal does not supersede a newer resource decision.
        ModerationLog.action != "appeal_dismissed",
    ).order_by(ModerationLog.id.desc()).limit(1))
    return result.scalar_one_or_none()


async def validate_current_penalty(db, resource_type, resource, action):
    if action.action not in PENALTIES[resource_type]:
        raise HTTPException(status_code=422, detail="This action is not an appealable penalty.")
    latest = await latest_action(db, resource_type, resource.id)
    if not latest or latest.id != action.id or not penalty_applies(resource_type, resource, action.action):
        raise HTTPException(status_code=409, detail="This penalty is no longer current. Refresh before appealing or restoring it.")


async def system_actor(db):
    """Create a disabled audit identity, with no usable password or privileges."""
    actor = (await db.execute(select(User).where(User.email == SYSTEM_EMAIL))).scalar_one_or_none()
    if actor is None:
        try:
            async with db.begin_nested():
                actor = User(email=SYSTEM_EMAIL, password_hash=get_password_hash(secrets.token_urlsafe(48)),
                             role="system", is_active=False)
                db.add(actor)
                await db.flush()
        except IntegrityError:
            actor = (await db.execute(select(User).where(User.email == SYSTEM_EMAIL))).scalar_one()
    if actor.role != "system" or actor.is_active:
        raise RuntimeError("The reserved moderation identity must be inactive and have the system role")
    return actor


async def record_quarantine(db, review, reason="Automatic review analysis flagged this review for moderation."):
    actor = await system_actor(db)
    db.add(ModerationLog(moderator_id=actor.id, action="quarantined", resource_type="review",
                         resource_id=review.id, reason=reason))


async def ensure_quarantine_action(db, review):
    """Make pre-existing automatic quarantines appealable without inventing a human action."""
    action = await latest_action(db, "review", review.id)
    if action is None and review.deleted_at is None and review.status == "quarantined":
        await record_quarantine(db, review, "Existing automatic quarantine recorded when an appeal was requested.")
        await db.flush()
        action = await latest_action(db, "review", review.id)
    return action
