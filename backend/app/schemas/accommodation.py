from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AccommodationCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20)
    address: str = Field(..., min_length=5)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    price_min: float = Field(..., gt=0)
    price_max: float = Field(..., gt=0)


class AccommodationResponse(BaseModel):
    id: int
    landlord_id: int
    title: str
    description: str
    address: str
    price_min: float
    price_max: float
    status: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True