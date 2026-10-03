"""Check current resource access before returning any cached data."""
from fastapi import HTTPException
from sqlalchemy import select

from app.models.accommodation import Accommodation
from app.models.landlord import Landlord


async def owned_accommodation(db, accommodation_id, user):
    result = await db.execute(select(Landlord).where(Landlord.user_id == user.id))
    landlord = result.scalar_one_or_none()
    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord profile not found")
    result = await db.execute(select(Accommodation).where(
        Accommodation.id == accommodation_id,
        Accommodation.landlord_id == landlord.id,
    ))
    accommodation = result.scalar_one_or_none()
    if not accommodation:
        raise HTTPException(status_code=403, detail="Listing not found or does not belong to you")
    return accommodation


async def visible_accommodation(db, accommodation_id, user):
    result = await db.execute(select(Accommodation).where(Accommodation.id == accommodation_id))
    accommodation = result.scalar_one_or_none()
    if not accommodation:
        raise HTTPException(status_code=404, detail="Accommodation not found")
    if accommodation.status == "approved":
        return accommodation
    if user and user.role in ("moderator", "admin"):
        return accommodation
    if user and user.role == "landlord":
        result = await db.execute(select(Landlord).where(
            Landlord.user_id == user.id,
            Landlord.id == accommodation.landlord_id,
        ))
        if result.scalar_one_or_none():
            return accommodation
    raise HTTPException(status_code=404, detail="Accommodation not found")
