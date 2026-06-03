from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token, get_password_hash
from app.schemas.auth import LoginRequest, RefreshRequest, StudentCreate, UserResponse, tokenResponse
from app.db.base import get_db
from app.models.user import User
from app.models.student import Student
from app.models.university import University

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register/student", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_student(student_in: StudentCreate, db: AsyncSession = Depends(get_db)):
    
    # 1. Check if user already exists
    query = select(User).where(User.email == student_in.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists."
        )

    # 2. Extract domain and find the matching University
    domain = student_in.email.split('@')[1]
    uni_query = select(University).where(University.domain == domain)
    uni_result = await db.execute(uni_query)
    university = uni_result.scalar_one_or_none()
    
    if not university:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"University domain '{domain}' is not currently supported or recognized."
        )

    # 3. Create the base User record
    new_user = User(
        email=student_in.email,
        password_hash=get_password_hash(student_in.password),
        role="student",
        is_active=False # They must verify email before this becomes True (Section 8.1)
    )
    db.add(new_user)
    await db.flush() # Flushes to DB so new_user gets an ID assigned

    # 4. Create the linked Student profile
    new_student = Student(
        user_id=new_user.id,
        university_id=university.id,
        verification_tier=1
    )
    db.add(new_student)
    await db.commit()
    await db.refresh(new_user)

    return new_user

@router.post("/login", response_model=tokenResponse)
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    
    # 1. Find the user
    query = select(User).where(User.email == credentials.email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    # 2. Verify credentials
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # 3. Issue tokens
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return tokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=tokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):

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
    query = select(User).where(User.id == int(token_data["sub"]))
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # 4. Issue fresh tokens
    access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)

    return tokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token
    )