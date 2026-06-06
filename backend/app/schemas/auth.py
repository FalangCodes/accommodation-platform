from pydantic import BaseModel, EmailStr, Field, field_validator

class StudentCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=64)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not v.endswith(".ac.za"):
            raise ValueError('Student registration requires a valid .ac.za institutional email address')
        return v.lower()
    
class LandlordCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=64)
    display_name: str = Field(..., min_length=2, max_length=100)
    contact_phone: str = Field(None, max_length=20)
    
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str

    class Config:
        from_attributes = True

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
    invite_key: str  # must match env var MODERATOR_INVITE_KEY