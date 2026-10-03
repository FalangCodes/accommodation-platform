from datetime import datetime, timedelta
from typing import Any, Union
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings


# Enforcing bycrypt with a work factor of 12 for password hashing
pwd_context = CryptContext(
    schemes=["bcrypt"], 
    deprecated="auto", 
    bcrypt__rounds=12
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # "Verify if provided password matches the hashed password"
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    # "Hash the password using bcrypt"
    return pwd_context.hash(password)

def create_access_token(subject: Union[str, Any], token_version: int = 0) -> str:
    # "Create a JWT access token with an expiration time"
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject), "type": "access", "ver": token_version}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(subject: Union[str, Any], token_version: int = 0) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh", "ver": token_version}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.JWTError:
        raise ValueError("Invalid token")
