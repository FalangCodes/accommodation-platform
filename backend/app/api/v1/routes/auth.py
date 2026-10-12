from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.core.encryption import encrypt_value
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token, get_password_hash
from app.db.base import get_db
from app.models.user import User
from app.models.student import Student
from app.models.university import University
from app.core.dependencies import get_current_user, ensure_account_access
from app.models.landlord import Landlord
from app.schemas.auth import LoginRequest, RefreshRequest, StudentCreate, LandlordCreate, LandlordVerificationSubmit, UserResponse, tokenResponse, ModeratorCreate
from app.core.config import settings
from app.schemas.auth import AuthEmailRequest, EmailTokenRequest, ResetPasswordRequest
from app.services.auth_email_service import issue_email_token, consume_email_token, now
from app.services.auth_rate_limit import enforce_auth_limit
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/register/student", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_student(student_in: StudentCreate, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_auth_limit(request, "registration", student_in.email)

    query = select(User).where(func.lower(User.email) == student_in.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists.")

    domain = student_in.email.split('@')[1]
    uni_query = select(University.id).where(University.domain == domain)
    uni_result = await db.execute(uni_query)
    university = uni_result.scalar_one_or_none()

    if not university:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"University domain '{domain}' is not currently supported or recognized.")

    new_user = User(
        email=student_in.email,
        password_hash=get_password_hash(student_in.password),
        role="student",
        is_active=True  # Email verification is an independent access requirement.
    )
    db.add(new_user)
    await db.flush()

    new_student = Student(
        user_id=new_user.id,
        university_id=university,
        first_name=student_in.first_name,
        last_name=student_in.last_name,
        student_number=student_in.student_number,
        verification_tier=0
    )
    db.add(new_student)
    try:
        await issue_email_token(db, new_user, "verify_email")
    except Exception:
        await db.rollback()
        logger.error("Registration verification email delivery failed")
        raise HTTPException(status_code=503, detail="We could not send the verification email. Please try registering again shortly.")
    await db.commit()
    await db.refresh(new_user)

    return new_user

@router.post("/login", response_model=tokenResponse)
async def login(credentials: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_auth_limit(request, "login", credentials.email)
    
    # 1. Find the user
    query = select(User).where(func.lower(User.email) == str(credentials.email).lower())
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    # 2. Verify credentials
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    ensure_account_access(user)
    # 3. Issue tokens
    access_token = create_access_token(subject=user.id, token_version=user.token_version)
    refresh_token = create_refresh_token(subject=user.id, token_version=user.token_version)

    return tokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=tokenResponse)
async def refresh(payload: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_auth_limit(request, "refresh")

    # 1. Decode and validate the refresh token
    try:
        token_data = decode_token(payload.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    # 2. Confirm it is actually a refresh token
    if token_data.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )

    # 3. Confirm user still exists and is active
    try:
        user_id = int(token_data["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    ensure_account_access(user, token_data)
    # 4. Issue fresh tokens
    access_token = create_access_token(subject=user.id, token_version=user.token_version)
    new_refresh_token = create_refresh_token(subject=user.id, token_version=user.token_version)

    return tokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token
    )

from app.core.encryption import encrypt_value


@router.post("/resend-verification")
async def resend_verification(payload: AuthEmailRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_auth_limit(request, "email", payload.email)
    result = await db.execute(select(User).where(func.lower(User.email) == payload.email))
    user = result.scalar_one_or_none()
    if user and user.role == "student" and user.email_verified_at is None:
        try:
            await issue_email_token(db, user, "verify_email")
            await db.commit()
        except Exception:
            await db.rollback()
            logger.error("Verification email delivery failed")
    return {"message": "If an unverified student account exists, a verification email will be sent. Please wait at least a minute before requesting another."}


@router.post("/verify-email")
async def verify_email(payload: EmailTokenRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_auth_limit(request, "token")
    user = await consume_email_token(db, payload.token, "verify_email")
    user.email_verified_at = now()
    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()
    if student:
        student.verification_tier = 1
    await db.commit()
    return {"message": "Your email is verified. You can now sign in if your account is active."}


@router.post("/request-password-reset")
async def request_password_reset(payload: AuthEmailRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_auth_limit(request, "email", payload.email)
    result = await db.execute(select(User).where(func.lower(User.email) == payload.email))
    user = result.scalar_one_or_none()
    if user:
        try:
            await issue_email_token(db, user, "reset_password")
            await db.commit()
        except Exception:
            await db.rollback()
            logger.error("Password reset email delivery failed")
    return {"message": "If an account exists, a password reset email will be sent. Please wait at least a minute before requesting another."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_auth_limit(request, "token")
    user = await consume_email_token(db, payload.token, "reset_password")
    user.password_hash = get_password_hash(payload.password)
    user.token_version += 1
    await db.commit()
    return {"message": "Your password has been reset. Sign in with your new password."}

@router.post("/register/landlord", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_landlord(landlord_in: LandlordCreate, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_auth_limit(request, "registration", landlord_in.email)

    query = select(User).where(func.lower(User.email) == landlord_in.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists.")

    new_user = User(
        email=landlord_in.email,
        password_hash=get_password_hash(landlord_in.password),
        role="landlord",
        is_active=True
    )
    db.add(new_user)
    await db.flush()

    new_landlord = Landlord(
        user_id=new_user.id,
        display_name=landlord_in.display_name,
        contact_phone=landlord_in.contact_phone,
        bio=landlord_in.bio,
        website=landlord_in.website,
        id_number_encrypted=encrypt_value(landlord_in.id_number) if landlord_in.id_number else None,
        verification_status="unverified",
        address_line1=landlord_in.address_line1,
        address_line2=landlord_in.address_line2,
        city=landlord_in.city,
        province=landlord_in.province,
        postal_code=landlord_in.postal_code,
    )
    db.add(new_landlord)
    await db.commit()
    await db.refresh(new_user)

    return new_user

@router.post("/register/moderator", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_moderator(moderator_in: ModeratorCreate, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_auth_limit(request, "registration", moderator_in.email)

    # 1. Validate invite key
    if moderator_in.invite_key != settings.MODERATOR_INVITE_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid invite key"
        )

    # 2. Check if user already exists
    query = select(User).where(User.email == moderator_in.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists."
        )

    # 3. Create the moderator user
    new_user = User(
        email=moderator_in.email,
        password_hash=get_password_hash(moderator_in.password),
        role="moderator",
        is_active=True
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user
