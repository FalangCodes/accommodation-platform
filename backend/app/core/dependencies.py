from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.base import get_db
from app.core.security import decode_token
from app.models.user import User

bearer_scheme = HTTPBearer()


def ensure_account_access(user: User, payload: dict | None = None) -> None:
    if user.role == "system":
        raise HTTPException(status_code=403, detail="System accounts cannot sign in.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Your account is inactive. Contact the administrator.", headers={"X-Auth-Error": "account_inactive"})
    if user.role == "student" and user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Verify your institutional email before signing in.", headers={"X-Auth-Error": "email_unverified"})
    if payload is not None and payload.get("ver", 0) != user.token_version:
        raise HTTPException(status_code=401, detail="Your session has expired. Sign in again.", headers={"X-Auth-Error": "session_revoked"})

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:

    token = credentials.credentials

    try:
        payload = decode_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists"
        )

    ensure_account_access(user, payload)
    return user


optional_bearer_scheme = HTTPBearer(auto_error=False)

async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(optional_bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> User | None:
    if not credentials:
        return None
        
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        query = select(User).where(User.id == int(payload["sub"]))
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        if user:
            ensure_account_access(user, payload)
        return user
    except Exception:
        return None


async def get_current_student(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students only"
        )
    return current_user


async def get_current_landlord(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "landlord":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Landlords only"
        )
    return current_user


async def get_current_moderator(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderators only"
        )
    return current_user

async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins only"
        )
    return current_user
