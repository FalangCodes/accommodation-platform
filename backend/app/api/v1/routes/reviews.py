from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
from typing import List

from app.db.base import get_db, AsyncSessionLocal
from app.core.dependencies import get_current_student, get_current_moderator, get_optional_user
from app.models.user import User
from app.models.student import Student
from app.models.accommodation import Accommodation
from app.models.landlord import Landlord
from app.core.dependencies import get_current_landlord
from app.models.review import Review, ReviewReply, ReviewNLPResult
from app.schemas.review import ReviewCreate, ReviewResponse, ReviewReplyCreate, ReviewReplyResponse
from app.services.review_service import process_review_nlp
from app.services.cache_service import cache_delete, cache_delete_pattern, key_listing, key_reviews, key_analytics, cache_get, cache_set, TTL_REVIEWS

from app.services.guest_access import reviews_response
from app.services.resource_access import visible_accommodation
from app.services.review_policy import review_eligibility, is_active_review_conflict

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def submit_review(
    review_in: ReviewCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db)
):
    # 1. Get student profile
    query = select(Student).where(Student.user_id == current_user.id).with_for_update()
    result = await db.execute(query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")

    await visible_accommodation(db, review_in.accommodation_id, current_user)
    eligibility = await review_eligibility(db, student.id, review_in.accommodation_id)
    if not eligibility["can_review"]:
        raise HTTPException(status_code=409, detail=eligibility)

    # 5. Create the review
    new_review = Review(
        student_id=student.id,
        accommodation_id=review_in.accommodation_id,
        rating=review_in.rating,
        body=review_in.body,
        status="pending_analysis"
    )
    db.add(new_review)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        if is_active_review_conflict(error):
            raise HTTPException(status_code=409, detail={"code": "active_review", "message": "You already have a review for this listing."})
        raise
    await cache_delete(
    key_listing(review_in.accommodation_id),
    key_reviews(review_in.accommodation_id),
    key_analytics(review_in.accommodation_id),
    )
    await cache_delete_pattern("search:*")
    await db.refresh(new_review)

    # 6. Trigger NLP task in background
    background_tasks.add_task(
        process_review_nlp,
        new_review.id,
        new_review.body,
    )

    return new_review

@router.get("/eligibility/{accommodation_id}")
async def get_review_eligibility(
    accommodation_id: int,
    current_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    await visible_accommodation(db, accommodation_id, current_user)
    result = await db.execute(select(Student).where(Student.user_id == current_user.id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return await review_eligibility(db, student.id, accommodation_id)


@router.get("/my")
async def get_my_reviews(
    current_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db)
):
    query = select(Student).where(Student.user_id == current_user.id)
    result = await db.execute(query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")

    from sqlalchemy import or_

    result = await db.execute(
        select(Review).where(
            Review.student_id == student.id,
            or_(
                Review.deleted_at == None,
                Review.deleted_by != current_user.id
            )
        ).order_by(Review.created_at.desc())
    )
    reviews = result.scalars().all()

    if not reviews:
        return []

    accommodation_ids = [r.accommodation_id for r in reviews]
    acc_result = await db.execute(
        select(Accommodation).where(Accommodation.id.in_(accommodation_ids))
    )
    acc_map = {a.id: a for a in acc_result.scalars().all()}

    return [
        {
            "id": r.id,
            "accommodation_id": r.accommodation_id,
            "accommodation_title": acc_map[r.accommodation_id].title if r.accommodation_id in acc_map else "Unknown listing",
            "rating": r.rating,
            "body": r.body,
            "status": "quarantined" if r.deleted_at is not None else r.status,
            "created_at": r.created_at,
        }
        for r in reviews
    ]

@router.get("/flagged")
async def get_flagged_reviews(
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Return all reviews currently in quarantine."""
    result = await db.execute(
        select(Review, ReviewNLPResult)
        .join(ReviewNLPResult, ReviewNLPResult.review_id == Review.id)
        .where(
            Review.status == "quarantined",
            Review.deleted_at == None
        )
        .order_by(Review.created_at.desc())
    )
    rows = result.all()

    return [
        {
            "id": review.id,
            "accommodation_id": review.accommodation_id,
            "student_id": review.student_id,
            "rating": review.rating,
            "body": review.body,
            "created_at": review.created_at,
            "nlp": {
                "sentiment": nlp.sentiment,
                "spam_flag": nlp.spam_flag,
            }
        }
        for review, nlp in rows
    ]


@router.get("/accommodation/{accommodation_id}")
async def get_reviews_for_accommodation(
    accommodation_id: int,
    current_user: User = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    await visible_accommodation(db, accommodation_id, current_user)
    cache_key = key_reviews(accommodation_id)
    cached = await cache_get(cache_key)
    if cached is not None:
        return reviews_response(cached, current_user is not None)
    result = await db.execute(
        select(Review).where(
            Review.accommodation_id == accommodation_id,
            Review.deleted_at == None,
            Review.status.in_(["analysed", "released"])
        ).order_by(Review.created_at.desc(), Review.id.desc())
    )
    reviews = result.scalars().all()

    if not reviews:
        return reviews_response([], current_user is not None)

    review_ids = [r.id for r in reviews]
    student_ids = [r.student_id for r in reviews]

    nlp_result = await db.execute(
        select(ReviewNLPResult).where(ReviewNLPResult.review_id.in_(review_ids))
    )
    nlp_map = {n.review_id: n for n in nlp_result.scalars().all()}

    reply_result = await db.execute(
        select(ReviewReply).where(ReviewReply.review_id.in_(review_ids))
    )
    reply_map = {r.review_id: r for r in reply_result.scalars().all()}

    from app.models.student import Student
    student_result = await db.execute(
        select(Student).where(Student.id.in_(student_ids))
    )
    student_name_map = {}
    for student in student_result.scalars().all():
        if student.first_name and student.last_name:
            display = f"{student.first_name} {student.last_name[0].upper()}."
        else:
            display = "Student"
        student_name_map[student.id] = display

    output = []
    for review in reviews:
        nlp = nlp_map.get(review.id)
        reply = reply_map.get(review.id)
        output.append({
            "id": review.id,
            "student_id": review.student_id,
            "student_name": student_name_map.get(review.student_id, "Student"),
            "accommodation_id": review.accommodation_id,
            "rating": review.rating,
            "body": review.body,
            "status": review.status,
            "created_at": review.created_at,
            "nlp": {
                "sentiment": nlp.sentiment,
                "sentiment_score": nlp.sentiment_score,
                "aspects": nlp.aspects,
            } if nlp else None,
            "reply": {
                "id": reply.id,
                "review_id": reply.review_id,
                "landlord_id": reply.landlord_id,
                "body": reply.body,
                "created_at": reply.created_at,
            } if reply else None,
        })

    await cache_set(cache_key, output, TTL_REVIEWS)
    return reviews_response(output, current_user is not None)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: int,
    current_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db)
):
    # 1. Get student profile
    query = select(Student).where(Student.user_id == current_user.id).with_for_update()
    result = await db.execute(query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")

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
    await cache_delete(
    key_listing(review.accommodation_id),
    key_reviews(review.accommodation_id),
    key_analytics(review.accommodation_id),
)

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
    ).with_for_update()
    result = await db.execute(query)
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.status not in ("analysed", "released"):
        raise HTTPException(status_code=409, detail="Only published reviews can receive a reply")

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
    await cache_delete(key_reviews(review.accommodation_id))

    return new_reply
