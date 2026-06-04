from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ReviewCreate(BaseModel):
    accommodation_id: int
    rating: int = Field(..., ge=1, le=5)
    body: str = Field(..., min_length=50)


class ReviewResponse(BaseModel):
    id: int
    student_id: int
    accommodation_id: int
    rating: int
    body: str
    status: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class ReviewReplyCreate(BaseModel):
    body: str = Field(..., min_length=10)

class ReviewReplyResponse(BaseModel):
    id: int
    review_id: int
    landlord_id: int
    body: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True