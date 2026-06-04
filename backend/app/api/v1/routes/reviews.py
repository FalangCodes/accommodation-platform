from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone
from typing import List

from app.db.base import get_db, AsyncSessionLocal
from app.core.dependencies import get_current_student
from app.models.user import User
from app.models.student import Student
from app.models.accommodation import Accommodation
from app.models.landlord import Landlord
from app.core.dependencies import get_current_landlord
from app.models.review import Review, ReviewReply
from app.schemas.review import ReviewCreate, ReviewResponse, ReviewReplyCreate, ReviewReplyResponse
from app.services.review_service import process_review_nlp

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def submit_review(
    review_in: ReviewCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db)
):
    # 1. Get student profile
    query = select(Student).where(Student.user_id == current_user.id)
    result = await db.execute(query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")

    # 2. Check accommodation exists
    query = select(Accommodation).where(Accommodation.id == review_in.accommodation_id)
    result = await db.execute(query)
    accommodation = result.scalar_one_or_none()

    if not accommodation:
        raise HTTPException(status_code=404, detail="Accommodation not found")

    # 3. Check for existing active review
    query = select(Review).where(
        Review.student_id == student.id,
        Review.accommodation_id == review_in.accommodation_id,
        Review.deleted_at == None
    )
    result = await db.execute(query)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already reviewed this accommodation."
        )

    # 4. Check cooldown from previously deleted review
    query = select(Review).where(
        Review.student_id == student.id,
        Review.accommodation_id == review_in.accommodation_id,
        Review.deleted_at != None,
        Review.cooldown_expires_at > datetime.now(timezone.utc)
    )
    result = await db.execute(query)
    cooldown = result.scalar_one_or_none()

    if cooldown:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You must wait until {cooldown.cooldown_expires_at} before reviewing this accommodation again."
        )

    # 5. Create the review
    new_review = Review(
        student_id=student.id,
        accommodation_id=review_in.accommodation_id,
        rating=review_in.rating,
        body=review_in.body,
        status="pending_analysis"
    )
    db.add(new_review)
    await db.commit()
    await db.refresh(new_review)

    # 6. TODO: Trigger NLP task via Celery (next step)
    background_tasks.add_task(
        process_review_nlp,
        new_review.id,
        new_review.body,
        AsyncSessionLocal()
    )

    return new_review


@router.get("/accommodation/{accommodation_id}", response_model=List[ReviewResponse])
async def get_reviews_for_accommodation(
    accommodation_id: int,
    db: AsyncSession = Depends(get_db)
):
    query = select(Review).where(
        Review.accommodation_id == accommodation_id,
        Review.deleted_at == None
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: int,
    current_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db)
):
    # 1. Get student profile
    query = select(Student).where(Student.user_id == current_user.id)
    result = await db.execute(query)
    student = result.scalar_one_or_none()

    # 2. Find the review
    query = select(Review).where(
        Review.id == review_id,
        Review.student_id == student.id,
        Review.deleted_at == None
    )
    result = await db.execute(query)
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # 3. Soft delete with 14-day cooldown
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    review.deleted_at = now
    review.deleted_by = current_user.id
    review.cooldown_expires_at = now + timedelta(days=14)

    await db.commit()

@router.post("/{review_id}/reply", response_model=ReviewReplyResponse, status_code=status.HTTP_201_CREATED)
async def reply_to_review(
    review_id: int,
    reply_in: ReviewReplyCreate,
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
    # 1. Get landlord profile
    query = select(Landlord).where(Landlord.user_id == current_user.id)
    result = await db.execute(query)
    landlord = result.scalar_one_or_none()

    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord profile not found")

    # 2. Check review exists and is not deleted
    query = select(Review).where(
        Review.id == review_id,
        Review.deleted_at == None
    )
    result = await db.execute(query)
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # 3. Check the review is for one of this landlord's accommodations
    query = select(Accommodation).where(
        Accommodation.id == review.accommodation_id,
        Accommodation.landlord_id == landlord.id
    )
    result = await db.execute(query)
    accommodation = result.scalar_one_or_none()

    if not accommodation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only reply to reviews on your own listings"
        )

    # 4. Check no reply already exists
    query = select(ReviewReply).where(ReviewReply.review_id == review_id)
    result = await db.execute(query)
    existing_reply = result.scalar_one_or_none()

    if existing_reply:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already replied to this review"
        )

    # 5. Create the reply
    new_reply = ReviewReply(
        review_id=review_id,
        landlord_id=landlord.id,
        body=reply_in.body
    )
    db.add(new_reply)
    await db.commit()
    await db.refresh(new_reply)

    return new_reply