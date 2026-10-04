from app.services.document_links import ownership_document_link, landlord_document_link
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, text
from datetime import datetime, timezone
from typing import Optional

from app.db.base import get_db
from app.core.dependencies import get_current_admin, get_current_moderator
from app.models.user import User
from app.models.student import Student
from app.models.landlord import Landlord
from app.models.university import University
from app.models.accommodation import Accommodation, AccommodationView, accommodation_universities
from app.models.review import Review, ReviewNLPResult
from app.models.moderation import ModerationLog
from app.core.security import get_password_hash
from app.core.encryption import decrypt_value
from app.services.cache_service import total_listing_views

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Overview Stats ────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_platform_stats(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    # Total students
    result = await db.execute(select(func.count(User.id)).where(User.role == "student"))
    total_students = result.scalar() or 0

    # Total landlords
    result = await db.execute(select(func.count(User.id)).where(User.role == "landlord"))
    total_landlords = result.scalar() or 0

    # Total moderators
    result = await db.execute(select(func.count(User.id)).where(User.role == "moderator"))
    total_moderators = result.scalar() or 0

    # Total accommodations
    result = await db.execute(select(func.count(Accommodation.id)))
    total_accommodations = result.scalar() or 0

    # Approved accommodations
    result = await db.execute(
        select(func.count(Accommodation.id)).where(Accommodation.status == "approved")
    )
    approved_accommodations = result.scalar() or 0

    # Pending accommodations
    result = await db.execute(
        select(func.count(Accommodation.id)).where(Accommodation.status == "pending")
    )
    pending_accommodations = result.scalar() or 0

    # Total reviews
    result = await db.execute(
        select(func.count(Review.id)).where(Review.deleted_at == None)
    )
    total_reviews = result.scalar() or 0

    # Quarantined reviews
    result = await db.execute(
        select(func.count(Review.id)).where(
            Review.status == "quarantined",
            Review.deleted_at == None
        )
    )
    quarantined_reviews = result.scalar() or 0

    # Total views
    result = await db.execute(select(func.count(AccommodationView.id)))
    total_views = result.scalar() or 0

    # Landlord verification breakdown
    result = await db.execute(
        select(Landlord.verification_status, func.count(Landlord.id))
        .group_by(Landlord.verification_status)
    )
    verification_breakdown = {row[0]: row[1] for row in result.all()}

    # Top 5 most viewed accommodations
    result = await db.execute(
        select(
            Accommodation.id,
            Accommodation.title,
            Accommodation.address,
            func.count(AccommodationView.id).label("view_count")
        )
        .join(AccommodationView, AccommodationView.accommodation_id == Accommodation.id)
        .group_by(Accommodation.id, Accommodation.title, Accommodation.address)
        .order_by(func.count(AccommodationView.id).desc())
        .limit(5)
    )
    top_viewed = [
        {"id": r.id, "title": r.title, "address": r.address, "views": r.view_count}
        for r in result.all()
    ]

    # Top 5 highest rated
    result = await db.execute(
        select(
            Accommodation.id,
            Accommodation.title,
            Accommodation.address,
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("review_count")
        )
        .join(Review, Review.accommodation_id == Accommodation.id)
        .where(Review.deleted_at == None, Review.status.in_(["analysed", "released"]))
        .group_by(Accommodation.id, Accommodation.title, Accommodation.address)
        .having(func.count(Review.id) >= 2)
        .order_by(func.avg(Review.rating).desc())
        .limit(5)
    )
    top_rated = [
        {
            "id": r.id,
            "title": r.title,
            "address": r.address,
            "avg_rating": round(float(r.avg_rating), 2),
            "review_count": r.review_count
        }
        for r in result.all()
    ]

    # Recent moderation activity
    result = await db.execute(
        select(ModerationLog).order_by(ModerationLog.created_at.desc()).limit(10)
    )
    recent_activity = [
        {
            "id": log.id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "reason": log.reason,
            "created_at": log.created_at,
        }
        for log in result.scalars().all()
    ]

    return {
        "users": {
            "total_students": total_students,
            "total_landlords": total_landlords,
            "total_moderators": total_moderators,
        },
        "accommodations": {
            "total": total_accommodations,
            "approved": approved_accommodations,
            "pending": pending_accommodations,
        },
        "reviews": {
            "total": total_reviews,
            "quarantined": quarantined_reviews,
        },
        "total_views": total_views,
        "landlord_verification": verification_breakdown,
        "top_viewed": top_viewed,
        "top_rated": top_rated,
        "recent_activity": recent_activity,
    }


# ── Universities Tree ─────────────────────────────────────────────────────────

@router.get("/universities/tree")
async def get_universities_tree(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(University).order_by(University.name))
    universities = result.scalars().all()

    output = []
    for uni in universities:
        # Get accommodations for this university
        acc_result = await db.execute(
            select(Accommodation)
            .join(
                accommodation_universities,
                accommodation_universities.c.accommodation_id == Accommodation.id
            )
            .where(accommodation_universities.c.university_id == uni.id)
            .order_by(Accommodation.created_at.desc())
        )
        accommodations = acc_result.scalars().all()

        acc_list = []
        for acc in accommodations:
            # Get landlord
            landlord_result = await db.execute(
                select(Landlord).where(Landlord.id == acc.landlord_id)
            )
            landlord = landlord_result.scalar_one_or_none()

            db_views = await total_listing_views(db, acc.id)
            today_views = 0
            await db.commit()  # Release the per-listing handoff lock before the next listing.

            # Get review stats
            review_result = await db.execute(
                select(func.count(Review.id), func.avg(Review.rating)).where(
                    Review.accommodation_id == acc.id,
                    Review.deleted_at == None,
                    Review.status.in_(["analysed", "released"])
                )
            )
            review_row = review_result.one()
            review_count = review_row[0] or 0
            avg_rating = round(float(review_row[1]), 2) if review_row[1] else None

            acc_list.append({
                "id": acc.id,
                "title": acc.title,
                "address": acc.address,
                "status": acc.status,
                "created_at": acc.created_at,
                "price_min": acc.price_min,
                "price_max": acc.price_max,
                "gender_policy": acc.gender_policy,
                "funding_type": acc.funding_type,
                "property_type": acc.property_type,
                "website": acc.website,
                "ownership_doc_url": ownership_document_link(acc.id, acc.ownership_doc_url),
                "total_views": db_views + today_views,
                "review_count": review_count,
                "avg_rating": avg_rating,
                "landlord": {
                    "id": landlord.id,
                    "display_name": landlord.display_name,
                    "verification_status": landlord.verification_status,
                } if landlord else None,
            })

        output.append({
            "id": uni.id,
            "name": uni.name,
            "domain": uni.domain,
            "province": uni.province,
            "accommodation_count": len(acc_list),
            "accommodations": acc_list,
        })

    return output


# ── Add University ─────────────────────────────────────────────────────────────

@router.post("/universities", status_code=status.HTTP_201_CREATED)
async def add_university(
    body: dict,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    name = body.get("name", "").strip()
    domain = body.get("domain", "").strip().lower()
    province = body.get("province", "").strip()
    lat = body.get("lat")
    lng = body.get("lng")

    if not all([name, domain, province, lat, lng]):
        raise HTTPException(status_code=400, detail="All fields required")

    result = await db.execute(select(University).where(University.domain == domain))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="University with this domain already exists")

    university = University(
        name=name,
        domain=domain,
        province=province,
        campus_location=f"POINT({lng} {lat})"
    )
    db.add(university)
    await db.commit()
    await db.refresh(university)

    # Invalidate universities cache
    from app.services.cache_service import cache_delete, key_universities
    await cache_delete(key_universities())

    return {"id": university.id, "name": university.name, "domain": university.domain}


# ── User Management ───────────────────────────────────────────────────────────

@router.get("/users/students")
async def get_all_students(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Student, User, University)
        .join(User, User.id == Student.user_id)
        .join(University, University.id == Student.university_id)
        .order_by(User.created_at.desc())
    )
    rows = result.all()

    output = []
    for student, user, university in rows:
        review_result = await db.execute(
            select(func.count(Review.id)).where(
                Review.student_id == student.id,
                Review.deleted_at == None
            )
        )
        review_count = review_result.scalar() or 0

        output.append({
            "id": user.id,
            "student_id": student.id,
            "email": user.email,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "student_number": student.student_number,
            "university": university.name,
            "verification_tier": student.verification_tier,
            "is_active": user.is_active,
            "review_count": review_count,
            "joined": user.created_at,
        })

    return output


@router.get("/users/landlords")
async def get_all_landlords(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Landlord, User).join(User, User.id == Landlord.user_id)
        .order_by(User.created_at.desc())
    )
    rows = result.all()

    output = []
    for landlord, user in rows:
        listing_result = await db.execute(
            select(func.count(Accommodation.id)).where(
                Accommodation.landlord_id == landlord.id
            )
        )
        listing_count = listing_result.scalar() or 0

        id_number = None
        if landlord.id_number_encrypted:
            try:
                id_number = decrypt_value(landlord.id_number_encrypted)
            except Exception:
                id_number = "Decryption failed"

        output.append({
            "id": user.id,
            "landlord_id": landlord.id,
            "email": user.email,
            "display_name": landlord.display_name,
            "contact_phone": landlord.contact_phone,
            "website": landlord.website,
            "verification_status": landlord.verification_status,
            "id_number": id_number,
            "id_copy_url": landlord_document_link(landlord.id, "id-copy", landlord.id_copy_url),
            "proof_of_address_url": landlord_document_link(landlord.id, "proof-of-address", landlord.proof_of_address_url),
            "is_active": user.is_active,
            "listing_count": listing_count,
            "joined": user.created_at,
        })

    return output


@router.get("/users/moderators")
async def get_all_moderators(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.role == "moderator")
        .order_by(User.created_at.desc())
    )
    moderators = result.scalars().all()

    output = []
    for mod in moderators:
        log_result = await db.execute(
            select(func.count(ModerationLog.id)).where(
                ModerationLog.moderator_id == mod.id
            )
        )
        actions_count = log_result.scalar() or 0

        output.append({
            "id": mod.id,
            "email": mod.email,
            "is_active": mod.is_active,
            "actions_count": actions_count,
            "joined": mod.created_at,
        })

    return output


# ── Create Moderator ──────────────────────────────────────────────────────────

@router.post("/moderators", status_code=status.HTTP_201_CREATED)
async def create_moderator(
    body: dict,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "").strip()

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    new_user = User(
        email=email,
        password_hash=get_password_hash(password),
        role="moderator",
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {"id": new_user.id, "email": new_user.email, "role": new_user.role}


# ── Activate / Deactivate User ────────────────────────────────────────────────

@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id).with_for_update())
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot deactivate an admin account")

    if user.is_active:
        user.is_active = False
        user.token_version += 1
    await db.commit()

    return {"detail": f"User {user.email} deactivated", "user_id": user_id}


@router.patch("/users/{user_id}/activate")
async def activate_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id).with_for_update())
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "system":
        raise HTTPException(status_code=400, detail="System accounts cannot be activated")

    if not user.is_active:
        user.is_active = True
        # Also revoke tokens issued before legacy inactive accounts were blocked.
        user.token_version += 1
    await db.commit()

    return {"detail": f"User {user.email} activated", "user_id": user_id}



@router.get("/accommodations/{accommodation_id}/views")
async def get_accommodation_views(
    accommodation_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    return {"total_views": await total_listing_views(db, accommodation_id)}
