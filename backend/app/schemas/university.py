from pydantic import BaseModel, Field
from typing import Optional

class UniversityOut(BaseModel):
    id: int
    name: str
    domain: str
    province: str

    model_config = {"from_attributes": True}