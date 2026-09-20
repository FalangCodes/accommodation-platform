from pydantic import BaseModel, Field
from typing import Optional

class UniversityOut(BaseModel):
    id: int
    name: str
    domain: str
    province: str
    lat: Optional[float] = None
    lng: Optional[float] = None

    model_config = {"from_attributes": True}