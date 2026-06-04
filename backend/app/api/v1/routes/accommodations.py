from sqlalchemy import text
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.db.base import get_db
from app.core.dependencies import get_current_landlord
from app.models.user import User
from app.models.landlord import Landlord
from app.models.accommodation import Accommodation
from app.models.university import University
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

@router.get("/search", response_model=List[AccommodationResponse])
async def search_accommodations(
    university_id: int,
    radius_km: int = 5,
    price_min: float = None,
    price_max: float = None,
    min_rating: float = None,
    db: AsyncSession = Depends(get_db)
):
    # 1. Get university campus coordinates
    query = select(University).where(University.id == university_id)
    result = await db.execute(query)
    university = result.scalar_one_or_none()

    if not university:
        raise HTTPException(status_code=404, detail="University not found")

    # 2. Build PostGIS radius search query
    sql = text("""
        SELECT a.id, a.landlord_id, a.title, a.description, a.address,
               a.price_min, a.price_max, a.status, a.created_at,
               ST_Distance(a.location, u.campus_location) / 1000 AS distance_km
        FROM accommodations a
        JOIN universities u ON u.id = :university_id
        WHERE a.status = 'approved'
        AND ST_DWithin(a.location, u.campus_location, :radius_meters)
        ORDER BY ST_Distance(a.location, u.campus_location)
    """)

    params = {
        "university_id": university_id,
        "radius_meters": radius_km * 1000
    }

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    # 3. Apply optional filters
    accommodations = []
    for row in rows:
        if price_min and row["price_min"] < price_min:
            continue
        if price_max and row["price_max"] > price_max:
            continue
        accommodations.append(dict(row))

    return accommodations