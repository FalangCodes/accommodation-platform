from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.db.base import get_db
from app.models.university import University
from app.schemas.university import UniversityOut
from app.services.cache_service import cache_get, cache_set, key_universities, TTL_UNIVERSITIES
from pydantic import BaseModel

router = APIRouter(prefix="/universities", tags=["Universities"])


@router.get("/", response_model=list[UniversityOut])
async def list_universities(session: AsyncSession = Depends(get_db)):
    cached = await cache_get(key_universities())
    if cached:
        return cached

    result = await session.execute(
        text("""
            SELECT
                id, name, domain, province,
                ST_Y(campus_location::geometry) AS lat,
                ST_X(campus_location::geometry) AS lng
            FROM universities
            ORDER BY name
        """)
    )
    rows = result.mappings().all()
    data = [
        {
            "id": row["id"],
            "name": row["name"],
            "domain": row["domain"],
            "province": row["province"],
            "lat": float(row["lat"]) if row["lat"] is not None else None,
            "lng": float(row["lng"]) if row["lng"] is not None else None,
        }
        for row in rows
    ]

    await cache_set(key_universities(), data, TTL_UNIVERSITIES)
    return data