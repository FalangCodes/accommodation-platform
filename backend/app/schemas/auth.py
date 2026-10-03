from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional

class StudentCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=64)
    first_name: str = Field(..., min_length=2, max_length=50)
    last_name: str = Field(..., min_length=2, max_length=50)
    student_number: str = Field(..., min_length=5, max_length=20)

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must fit within 72 UTF-8 bytes")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.lower()
        if not v.endswith(".ac.za"):
            raise ValueError('Student registration requires a valid .ac.za institutional email address')
        return v.lower()

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.replace("-", "").replace(" ", "").isalpha():
            raise ValueError("Name must contain only letters")
        return v.strip().capitalize()


class LandlordCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=64)
    display_name: str = Field(..., min_length=2, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=20)
    website: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = Field(None, max_length=500)
    id_number: str = Field(..., max_length=13)
    address_line1: str = Field(..., min_length=5, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    city: str = Field(..., min_length=2, max_length=100)
    province: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., min_length=4, max_length=10)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must fit within 72 UTF-8 bytes")
        return value

    @field_validator("id_number")
    @classmethod
    def validate_id_number(cls, v: str) -> str:
        digits = v.replace(" ", "")
        if not digits.isdigit() or len(digits) != 13:
            raise ValueError("South African ID number must be exactly 13 digits")
        return digits


class LandlordVerificationSubmit(BaseModel):
    """Landlord submits ID number + uploads docs separately via file endpoint."""
    id_number: str = Field(..., max_length=13)

    @field_validator("id_number")
    @classmethod
    def validate_id_number(cls, v: str) -> str:
        digits = v.replace(" ", "")
        if not digits.isdigit() or len(digits) != 13:
            raise ValueError("South African ID number must be exactly 13 digits")
        return digits


class LandlordOut(BaseModel):
    id: int
    display_name: str
    contact_phone: Optional[str] = None
    bio: Optional[str] = None
    website: Optional[str] = None
    verification_status: str
    id_number_verified: bool

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class tokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ModeratorCreate(BaseModel):
    email: str
    password: str
    invite_key: str


class AuthEmailRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return value.lower()


class EmailTokenRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=200)


class ResetPasswordRequest(EmailTokenRequest):
    password: str = Field(..., min_length=8, max_length=64)

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must fit within 72 UTF-8 bytes")
        return value
