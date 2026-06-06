from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.base import get_session
from app.models.university import University
from app.schemas.university import UniversityOut
from pydantic import BaseModel

router = APIRouter(prefix="/universities", tags=["universities"])



@router.get("/", response_model=list[UniversityOut])
async def list_universities(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(University).order_by(University.name))
    return result.scalars().all()