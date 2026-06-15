from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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

    result = await session.execute(select(University).order_by(University.name))
    universities = result.scalars().all()
    data = [{"id": u.id, "name": u.name, "domain": u.domain, "province": u.province} for u in universities]

    await cache_set(key_universities(), data, TTL_UNIVERSITIES)
    return data