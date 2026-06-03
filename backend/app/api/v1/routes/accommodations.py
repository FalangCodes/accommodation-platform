from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.db.base import get_db
from app.core.dependencies import get_current_landlord
from app.models.user import User
from app.models.landlord import Landlord
from app.models.accommodation import Accommodation
from app.schemas.accommodation import AccommodationCreate, AccommodationResponse

router = APIRouter(prefix="/accommodations", tags=["Accommodations"])


@router.post("", response_model=AccommodationResponse, status_code=status.HTTP_201_CREATED)
async def create_accommodation(
    accommodation_in: AccommodationCreate,
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
    # Get landlord profile
    query = select(Landlord).where(Landlord.user_id == current_user.id)
    result = await db.execute(query)
    landlord = result.scalar_one_or_none()

    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord profile not found")

    new_accommodation = Accommodation(
        landlord_id=landlord.id,
        title=accommodation_in.title,
        description=accommodation_in.description,
        address=accommodation_in.address,
        location=f"POINT({accommodation_in.longitude} {accommodation_in.latitude})",
        price_min=accommodation_in.price_min,
        price_max=accommodation_in.price_max,
        status="pending"
    )
    db.add(new_accommodation)
    await db.commit()
    await db.refresh(new_accommodation)

    return new_accommodation


@router.get("", response_model=List[AccommodationResponse])
async def list_accommodations(db: AsyncSession = Depends(get_db)):
    query = select(Accommodation).where(Accommodation.status == "approved")
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{accommodation_id}", response_model=AccommodationResponse)
async def get_accommodation(accommodation_id: int, db: AsyncSession = Depends(get_db)):
    query = select(Accommodation).where(Accommodation.id == accommodation_id)
    result = await db.execute(query)
    accommodation = result.scalar_one_or_none()

    if not accommodation:
        raise HTTPException(status_code=404, detail="Accommodation not found")

    return accommodation