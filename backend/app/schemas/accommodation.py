from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


VALID_GENDER_POLICIES = {"male", "female", "mixed"}
VALID_FUNDING_TYPES = {"self_funded", "bursary", "both"}
VALID_PROPERTY_TYPES = {"bachelor", "single_room", "shared_room", "flat", "house", "mixed"}
VALID_AMENITIES = {
    "wifi", "parking", "laundry", "furnished", "security",
    "generator", "solar", "cctv", "study_room", "kitchen", "garden"
}


class AccommodationCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20)
    address: str = Field(..., min_length=5)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    price_min: float = Field(..., gt=0)
    price_max: float = Field(..., gt=0)

    # New fields
    gender_policy: Optional[str] = None
    funding_type: Optional[str] = None
    property_type: Optional[str] = None
    website: Optional[str] = Field(None, max_length=255)
    amenities: Optional[List[str]] = None

    @field_validator("gender_policy")
    @classmethod
    def validate_gender_policy(cls, v):
        if v is not None and v not in VALID_GENDER_POLICIES:
            raise ValueError(f"gender_policy must be one of {VALID_GENDER_POLICIES}")
        return v

    @field_validator("funding_type")
    @classmethod
    def validate_funding_type(cls, v):
        if v is not None and v not in VALID_FUNDING_TYPES:
            raise ValueError(f"funding_type must be one of {VALID_FUNDING_TYPES}")
        return v

    @field_validator("property_type")
    @classmethod
    def validate_property_type(cls, v):
        if v is not None and v not in VALID_PROPERTY_TYPES:
            raise ValueError(f"property_type must be one of {VALID_PROPERTY_TYPES}")
        return v

    @field_validator("amenities")
    @classmethod
    def validate_amenities(cls, v):
        if v is not None:
            invalid = set(v) - VALID_AMENITIES
            if invalid:
                raise ValueError(f"Invalid amenities: {invalid}")
        return v


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
    gender_policy: Optional[str] = None
    funding_type: Optional[str] = None
    property_type: Optional[str] = None
    website: Optional[str] = None
    amenities: Optional[List[str]] = None

    model_config = {"from_attributes": True}