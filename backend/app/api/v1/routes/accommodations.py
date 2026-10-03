from sqlalchemy import text, func
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import hashlib
from app.db.base import get_db
from app.core.dependencies import get_current_landlord, get_optional_user, get_current_user
from app.models.user import User
from app.models.landlord import Landlord
from app.models.accommodation import Accommodation, AccommodationView, AccommodationImage
from app.models.university import University
from app.models.insight import AccommodationInsight
from app.models.review import Review, ReviewNLPResult
from app.schemas.accommodation import AccommodationCreate, AccommodationResponse
from app.services.storage_service import upload_image, delete_image
from app.services.cache_service import (
    cache_get, cache_set, cache_delete, cache_delete_pattern, get_today_views,
    key_search, key_listing, key_reviews, key_analytics, increment_view,
    key_platform_stats, key_featured, key_activity,
    TTL_SEARCH, TTL_LISTING, TTL_REVIEWS, TTL_ANALYTICS, TTL_FEATURED, TTL_ACTIVITY
)

from app.services.guest_access import GUEST_SEARCH_PAGE_SIZE, search_response
from app.services.resource_access import owned_accommodation, visible_accommodation
from app.services.document_links import ownership_document_link, listing_document_response
from app.api.v1.routes.documents import store_document_upload

router = APIRouter(prefix="/accommodations", tags=["Accommodations"])


@router.post("", response_model=AccommodationResponse, status_code=status.HTTP_201_CREATED)
async def create_accommodation(
    accommodation_in: AccommodationCreate,
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
    query = select(Landlord).where(Landlord.user_id == current_user.id)
    result = await db.execute(query)
    landlord = result.scalar_one_or_none()

    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord profile not found")

    # ── Block unverified landlords ──
    if landlord.verification_status != "verified":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account must be verified before you can list properties. Please complete your verification in the dashboard."
        )

    new_accommodation = Accommodation(
    landlord_id=landlord.id,
    title=accommodation_in.title,
    description=accommodation_in.description,
    address=accommodation_in.address,
    location=f"POINT({accommodation_in.longitude} {accommodation_in.latitude})",
    price_min=accommodation_in.price_min,
    price_max=accommodation_in.price_max,
    gender_policy=accommodation_in.gender_policy,
    funding_type=accommodation_in.funding_type,
    property_type=accommodation_in.property_type,
    website=accommodation_in.website,
    amenities=accommodation_in.amenities,
    status="incomplete"
)
    db.add(new_accommodation)
    await db.commit()
    await db.refresh(new_accommodation)

    # Auto-link to nearest university
    nearest_uni = await db.execute(
        text("""
            SELECT id FROM universities
            ORDER BY ST_Distance(
                campus_location,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
            ) ASC
            LIMIT 1
        """),
        {"lng": accommodation_in.longitude, "lat": accommodation_in.latitude}
    )
    uni_row = nearest_uni.fetchone()
    if uni_row:
        await db.execute(
            text("""
                INSERT INTO accommodation_universities (accommodation_id, university_id)
                VALUES (:acc_id, :uni_id)
                ON CONFLICT DO NOTHING
            """),
            {"acc_id": new_accommodation.id, "uni_id": uni_row[0]}
        )
        await db.commit()

    return new_accommodation


@router.get("", response_model=List[AccommodationResponse])
async def list_accommodations(db: AsyncSession = Depends(get_db)):
    query = select(Accommodation).where(Accommodation.status == "approved")
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/search")
async def search_accommodations(
    university_id: int = None,
    radius_km: int = 5,
    price_min: float = None,
    price_max: float = None,
    min_rating: float = None,
    gender_policy: str = None,
    funding_type: str = None,
    q: str = None,
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    page = max(1, page)
    if page > 1 and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view page 2 and beyond."
        )

    page_size = min(max(1, page_size), 50) if current_user else GUEST_SEARCH_PAGE_SIZE
    cache_key = key_search(
        university_id, radius_km, price_min, price_max, min_rating,
        page=page, gender_policy=gender_policy, funding_type=funding_type, q=q,
    ) + f":size:{page_size}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return search_response(cached, current_user is not None)
    offset = (page - 1) * page_size
    params: dict = {}

    if university_id:
        query = select(University).where(University.id == university_id)
        result = await db.execute(query)
        university = result.scalar_one_or_none()
        if not university:
            raise HTTPException(status_code=404, detail="University not found")

        base_sql = """
            SELECT
                a.id, a.landlord_id, a.title, a.description, a.address,
                a.price_min, a.price_max, a.status, a.created_at,
                ROUND((ST_Distance(a.location, u.campus_location) / 1000)::numeric, 2) AS distance_km,
                ST_Y(a.location::geometry) AS lat,
                ST_X(a.location::geometry) AS lng,
                COALESCE(AVG(r.rating), NULL)::float AS average_rating,
                COUNT(r.id) AS review_count,
                (SELECT blob_url FROM accommodation_images
                WHERE accommodation_id = a.id
                ORDER BY display_order ASC LIMIT 1) AS cover_image
            FROM accommodations a
            JOIN universities u ON u.id = :university_id
            LEFT JOIN reviews r ON r.accommodation_id = a.id AND r.deleted_at IS NULL
            WHERE a.status = 'approved'
            AND ST_DWithin(a.location, u.campus_location, :radius_meters)
        """
        group_by = """
            GROUP BY a.id, a.landlord_id, a.title, a.description,
                     a.address, a.price_min, a.price_max, a.status, a.created_at,
                     a.location, u.campus_location
        """
        order_by = "ORDER BY ST_Distance(a.location, u.campus_location), a.id"
        params["university_id"] = university_id
        params["radius_meters"] = radius_km * 1000
    else:
        base_sql = """
            SELECT
                a.id, a.landlord_id, a.title, a.description, a.address,
                a.price_min, a.price_max, a.status, a.created_at,
                NULL AS distance_km,
                ST_Y(a.location::geometry) AS lat,
                ST_X(a.location::geometry) AS lng,
                COALESCE(AVG(r.rating), NULL)::float AS average_rating,
                COUNT(r.id) AS review_count,
                (SELECT blob_url FROM accommodation_images
                WHERE accommodation_id = a.id
                ORDER BY display_order ASC LIMIT 1) AS cover_image
            FROM accommodations a
            LEFT JOIN reviews r ON r.accommodation_id = a.id AND r.deleted_at IS NULL
            WHERE a.status = 'approved'
        """
        group_by = """
            GROUP BY a.id, a.landlord_id, a.title, a.description,
                     a.address, a.price_min, a.price_max, a.status, a.created_at,
                     a.location
        """
        order_by = "ORDER BY a.created_at DESC, a.id DESC"

    # Optional filters
    filter_clauses = []
    if price_min is not None:
        filter_clauses.append("a.price_max >= :price_min")
        params["price_min"] = price_min
    if price_max is not None:
        filter_clauses.append("a.price_min <= :price_max")
        params["price_max"] = price_max
    if gender_policy is not None:
        filter_clauses.append("(a.gender_policy = :gender_policy OR a.gender_policy = 'mixed')")
        params["gender_policy"] = gender_policy
    if funding_type is not None:
        filter_clauses.append("(a.funding_type = :funding_type OR a.funding_type = 'both')")
        params["funding_type"] = funding_type
    if q is not None and q.strip():
        filter_clauses.append("a.title ILIKE :q")
        params["q"] = f"%{q.strip()}%"
    where_extra = (" AND " + " AND ".join(filter_clauses)) if filter_clauses else ""

    having_clause = ""
    if min_rating is not None:
        having_clause = "HAVING COALESCE(AVG(r.rating), 0) >= :min_rating"
        params["min_rating"] = min_rating

    # Count
    count_sql = text(f"""
        SELECT COUNT(*) FROM (
            {base_sql}
            {where_extra}
            {group_by}
            {having_clause}
        ) AS subq
    """)
    count_result = await db.execute(count_sql, params)
    total = count_result.scalar() or 0

    # Paginated results
    main_sql = text(f"""
        {base_sql}
        {where_extra}
        {group_by}
        {having_clause}
        {order_by}
        LIMIT :limit OFFSET :offset
    """)
    params["limit"] = page_size
    params["offset"] = offset

    result = await db.execute(main_sql, params)
    rows = result.mappings().all()
    result_data = {
        "items": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

    await cache_set(cache_key, result_data, TTL_SEARCH)
    return search_response(result_data, current_user is not None)

@router.get("/my")

async def get_my_accommodations(
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
    query = select(Landlord).where(Landlord.user_id == current_user.id)
    result = await db.execute(query)
    landlord = result.scalar_one_or_none()

    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord profile not found")

    result = await db.execute(
        select(Accommodation)
        .where(Accommodation.landlord_id == landlord.id)
        .order_by(Accommodation.created_at.desc())
    )
    accommodations = result.scalars().all()

    if not accommodations:
        return []

    # Enrich with review stats
    output = []
    for acc in accommodations:
        reviews_result = await db.execute(
            select(Review).where(
                Review.accommodation_id == acc.id,
                Review.deleted_at == None
            )
        )
        reviews = reviews_result.scalars().all()
        total_reviews = len(reviews)
        average_rating = round(
            sum(r.rating for r in reviews) / total_reviews, 2
        ) if total_reviews > 0 else None

        output.append({
            "id": acc.id,
            "title": acc.title,
            "address": acc.address,
            "price_min": acc.price_min,
            "price_max": acc.price_max,
            "status": acc.status,
            "created_at": acc.created_at,
            "total_reviews": total_reviews,
            "average_rating": average_rating,
            "ownership_doc_url": ownership_document_link(acc.id, acc.ownership_doc_url),
        })

    return output


# ─── Public: Platform Stats ───────────────────────────────────────────────────
# NOTE: These static-path routes MUST be declared before any /{accommodation_id}
# parameterized routes, otherwise FastAPI tries to cast "platform-stats" / "featured"
# as integers and returns 422.

@router.get("/platform-stats")
async def get_platform_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    Returns aggregate platform stats for the landing page.
    Cached for 24 hours. No auth required.
    """
    cached = await cache_get(key_platform_stats())
    if cached:
        return cached

    # Total approved listings
    listings_result = await db.execute(
        select(func.count()).where(
            Accommodation.status == "approved"
        ).select_from(Accommodation)
    )
    total_listings = listings_result.scalar() or 0

    # Total non-deleted reviews
    reviews_result = await db.execute(
        select(func.count()).where(
            Review.deleted_at == None
        ).select_from(Review)
    )
    total_reviews = reviews_result.scalar() or 0

    # Total verified students
    from app.models.student import Student
    students_result = await db.execute(
        select(func.count()).select_from(Student)
    )
    total_students = students_result.scalar() or 0

    payload = {
        "listings": total_listings,
        "reviews": total_reviews,
        "students": total_students,
    }

    await cache_set(key_platform_stats(), payload, TTL_FEATURED)
    return payload


# ─── Public: Featured Listings ────────────────────────────────────────────────

@router.get("/featured")
async def get_featured_listings(
    db: AsyncSession = Depends(get_db)
):
    """
    Returns top 3 approved listings ranked by avg rating then total views.
    Cached for 24 hours. No auth required.
    """
    cached = await cache_get(key_featured())
    if cached:
        return cached

    result = await db.execute(
        text("""
            SELECT
                a.id,
                a.title,
                a.address,
                a.price_min,
                a.price_max,
                COALESCE(AVG(r.rating), 0)::float AS avg_rating,
                COUNT(DISTINCT r.id) AS review_count,
                COUNT(DISTINCT av.id) AS view_count,
                (
                    SELECT ai2.blob_url
                    FROM accommodation_images ai2
                    WHERE ai2.accommodation_id = a.id
                    ORDER BY ai2.display_order ASC
                    LIMIT 1
                ) AS first_image_url
            FROM accommodations a
            LEFT JOIN reviews r
                ON r.accommodation_id = a.id AND r.deleted_at IS NULL
            LEFT JOIN accommodation_views av
                ON av.accommodation_id = a.id
            WHERE a.status = 'approved'
            GROUP BY a.id
            ORDER BY avg_rating DESC, view_count DESC
            LIMIT 3
        """)
    )
    rows = result.mappings().all()

    payload = [
        {
            "id": row["id"],
            "title": row["title"],
            "address": row["address"],
            "price_min": float(row["price_min"]),
            "price_max": float(row["price_max"]),
            "avg_rating": round(float(row["avg_rating"]), 1),
            "review_count": int(row["review_count"]),
            "view_count": int(row["view_count"]),
            "first_image_url": row["first_image_url"],
        }
        for row in rows
    ]

    await cache_set(key_featured(), payload, TTL_FEATURED)
    return payload


# ─── Public: Activity Feed ────────────────────────────────────────────────────

@router.get("/activity")
async def get_activity_feed(
    db: AsyncSession = Depends(get_db)
):
    """
    Returns a shuffled mix of real reviews and approved listings for the
    landing page social proof toast. No timestamps exposed. Cached 1 hour.
    No auth required.
    """
    cached = await cache_get(key_activity())
    if cached:
        return cached

    import random

    # Pull a random sample of analysed, non-deleted reviews with listing title
    reviews_result = await db.execute(
        text("""
            SELECT r.rating, a.title AS accommodation_title
            FROM reviews r
            JOIN accommodations a ON a.id = r.accommodation_id
            WHERE r.deleted_at IS NULL
              AND r.status != 'pending_analysis'
              AND a.status = 'approved'
            ORDER BY RANDOM()
            LIMIT 8
        """)
    )

    # Pull a random sample of approved listings
    listings_result = await db.execute(
        text("""
            SELECT title
            FROM accommodations
            WHERE status = 'approved'
            ORDER BY RANDOM()
            LIMIT 4
        """)
    )

    items = []
    for row in reviews_result.mappings():
        items.append({
            "type": "review",
            "rating": int(row["rating"]),
            "title": row["accommodation_title"],
        })
    for row in listings_result.mappings():
        items.append({
            "type": "listing",
            "title": row["title"],
        })

    random.shuffle(items)

    await cache_set(key_activity(), items, TTL_ACTIVITY)
    return items


# ─── Parameterized routes below — keep all /{accommodation_id} routes AFTER this line ───

@router.get("/{accommodation_id}/analytics")
async def get_analytics(
    accommodation_id: int,
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
    await owned_accommodation(db, accommodation_id, current_user)
    cache_key = key_analytics(accommodation_id)
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    # 2. Total views
    query = select(func.count(AccommodationView.id)).where(
    AccommodationView.accommodation_id == accommodation_id
    )
    result = await db.execute(query)
    db_views = result.scalar() or 0
    today_views = await get_today_views(accommodation_id)
    total_views = db_views + today_views

    # 3. Reviews stats
    query = select(Review).where(
        Review.accommodation_id == accommodation_id,
        Review.deleted_at == None
    )
    result = await db.execute(query)
    reviews = result.scalars().all()

    total_reviews = len(reviews)
    average_rating = round(
        sum(r.rating for r in reviews) / total_reviews, 2
    ) if total_reviews > 0 else 0.0

    # 4. Sentiment distribution
    review_ids = [r.id for r in reviews]
    sentiment_distribution = {"positive": 0, "neutral": 0, "negative": 0}

    if review_ids:
        query = select(ReviewNLPResult).where(
            ReviewNLPResult.review_id.in_(review_ids)
        )
        result = await db.execute(query)
        nlp_results = result.scalars().all()

        for nlp in nlp_results:
            label = nlp.sentiment.lower()
            if label in sentiment_distribution:
                sentiment_distribution[label] += 1

        # 5. Average aspect scores
        all_aspects = {}
        aspect_counts = {}

        for nlp in nlp_results:
            if nlp.aspects:
                for aspect, score in nlp.aspects.items():
                    if aspect not in all_aspects:
                        all_aspects[aspect] = 0.0
                        aspect_counts[aspect] = 0
                    all_aspects[aspect] += score
                    aspect_counts[aspect] += 1

        top_aspects = {
            aspect: round(all_aspects[aspect] / aspect_counts[aspect], 4)
            for aspect in all_aspects
        }
        top_aspects = dict(sorted(
            top_aspects.items(),
            key=lambda x: x[1],
            reverse=True
        ))
    else:
        top_aspects = {}

    result_data = {
        "accommodation_id": accommodation_id,
        "total_views": total_views,
        "total_reviews": total_reviews,
        "average_rating": average_rating,
        "sentiment_distribution": sentiment_distribution,
        "top_aspects": top_aspects
    }

    await cache_set(cache_key, result_data, TTL_ANALYTICS)
    return result_data

@router.post("/{accommodation_id}/view", status_code=status.HTTP_204_NO_CONTENT)
async def record_view(
    accommodation_id: int,
    request: Request,
    current_user: User = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    """Record a listing view — increments Redis counter, flushed to DB at midnight."""
    await visible_accommodation(db, accommodation_id, current_user)

    # Increment Redis counter
    await increment_view(accommodation_id)

@router.get("/{accommodation_id}")
async def get_accommodation(
    accommodation_id: int,
    current_user: User = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    accommodation = await visible_accommodation(db, accommodation_id, current_user)
    cache_key = key_listing(accommodation_id)
    cached = await cache_get(cache_key)
    if cached is not None:
        return await listing_document_response(db, {**cached, "status": accommodation.status}, accommodation, current_user)

    # 2. Coordinates from PostGIS
    coords_result = await db.execute(
        text("SELECT ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng FROM accommodations WHERE id = :id"),
        {"id": accommodation_id}
    )
    coords = coords_result.mappings().one_or_none()

    # 3. Images
    images_result = await db.execute(
        select(AccommodationImage)
        .where(AccommodationImage.accommodation_id == accommodation_id)
        .order_by(AccommodationImage.display_order)
    )
    images = images_result.scalars().all()

    # 4. Landlord display name
    from app.models.landlord import Landlord
    landlord_result = await db.execute(
        select(Landlord).where(Landlord.id == accommodation.landlord_id)
    )
    landlord = landlord_result.scalar_one_or_none()

    # 5. Reviews stats + NLP summary
    reviews_result = await db.execute(
        select(Review).where(
            Review.accommodation_id == accommodation_id,
            Review.deleted_at == None
        )
    )
    reviews = reviews_result.scalars().all()
    total_reviews = len(reviews)
    average_rating = round(
        sum(r.rating for r in reviews) / total_reviews, 2
    ) if total_reviews > 0 else None

    # 6. NLP sentiment distribution
    sentiment_distribution = {"positive": 0, "neutral": 0, "negative": 0}
    top_aspects = {}

    if reviews:
        review_ids = [r.id for r in reviews]
        nlp_result = await db.execute(
            select(ReviewNLPResult).where(ReviewNLPResult.review_id.in_(review_ids))
        )
        nlp_results = nlp_result.scalars().all()

        aspect_totals: dict = {}
        aspect_counts: dict = {}

        for nlp in nlp_results:
            label = (nlp.sentiment or "").lower()
            if label in sentiment_distribution:
                sentiment_distribution[label] += 1
            if nlp.aspects:
                for aspect, score in nlp.aspects.items():
                    aspect_totals[aspect] = aspect_totals.get(aspect, 0.0) + score
                    aspect_counts[aspect] = aspect_counts.get(aspect, 0) + 1

        top_aspects = {
            k: round(aspect_totals[k] / aspect_counts[k], 4)
            for k in aspect_totals
        }
        top_aspects = dict(sorted(top_aspects.items(), key=lambda x: x[1], reverse=True))

    # Dominant sentiment
    dominant_sentiment = max(sentiment_distribution, key=sentiment_distribution.get) \
        if total_reviews > 0 else None

    result_data = {
        "id": accommodation.id,
        "landlord_id": accommodation.landlord_id,
        "landlord_name": landlord.display_name if landlord else None,
        "title": accommodation.title,
        "description": accommodation.description,
        "address": accommodation.address,
        "price_min": accommodation.price_min,
        "price_max": accommodation.price_max,
        "status": accommodation.status,
        "created_at": accommodation.created_at,
        "lat": coords["lat"] if coords else None,
        "lng": coords["lng"] if coords else None,
        "gender_policy": accommodation.gender_policy,
        "funding_type": accommodation.funding_type,
        "property_type": accommodation.property_type,
        "website": accommodation.website,
        "amenities": accommodation.amenities,
        "images": [{"id": img.id, "url": img.blob_url, "order": img.display_order} for img in images],
        "total_reviews": total_reviews,
        "average_rating": average_rating,
        "dominant_sentiment": dominant_sentiment,
        "sentiment_distribution": sentiment_distribution,
        "top_aspects": top_aspects,
    }

    await cache_set(cache_key, result_data, TTL_LISTING)
    return await listing_document_response(db, result_data, accommodation, current_user)

@router.post("/{accommodation_id}/images")
async def upload_accommodation_image(
    accommodation_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
    # 1. Verify landlord owns this listing
    result = await db.execute(select(Landlord).where(Landlord.user_id == current_user.id))
    landlord = result.scalar_one_or_none()
    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord profile not found")

    result = await db.execute(
        select(Accommodation).where(
            Accommodation.id == accommodation_id,
            Accommodation.landlord_id == landlord.id
        )
    )
    accommodation = result.scalar_one_or_none()
    if not accommodation:
        raise HTTPException(status_code=403, detail="Listing not found or does not belong to you")

    # 2. Check image count limit
    result = await db.execute(
        select(func.count(AccommodationImage.id)).where(
            AccommodationImage.accommodation_id == accommodation_id
        )
    )
    count = result.scalar() or 0
    if count >= 8:
        raise HTTPException(status_code=400, detail="Maximum of 8 images per listing reached")

    # 3. Validate file type
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG and WebP images are allowed")

    # 4. Upload to Azure
    file_bytes = await file.read()
    if len(file_bytes) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(status_code=400, detail="Image must be under 5MB")

    blob_url = await upload_image(file_bytes, file.filename, file.content_type)

    # 5. Save to DB
    result = await db.execute(
        select(func.max(AccommodationImage.display_order)).where(
            AccommodationImage.accommodation_id == accommodation_id
        )
    )
    max_order = result.scalar() or 0

    image = AccommodationImage(
        accommodation_id=accommodation_id,
        blob_url=blob_url,
        display_order=max_order + 1
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)

    return {"id": image.id, "url": blob_url, "order": image.display_order}


@router.delete("/{accommodation_id}/images/{image_id}")
async def delete_accommodation_image(
    accommodation_id: int,
    image_id: int,
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
    await owned_accommodation(db, accommodation_id, current_user)

    result = await db.execute(
        select(AccommodationImage).where(
            AccommodationImage.id == image_id,
            AccommodationImage.accommodation_id == accommodation_id
        )
    )
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    await delete_image(image.blob_url)
    await db.delete(image)
    await db.commit()
    await cache_delete(key_listing(accommodation_id))
    await cache_delete_pattern("search:*")
    await cache_delete(key_featured())

    return {"detail": "Image deleted"}

@router.post("/{accommodation_id}/documents/ownership", status_code=status.HTTP_200_OK)
async def upload_ownership_document(
    accommodation_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
    # Verify landlord owns this listing
    result = await db.execute(select(Landlord).where(Landlord.user_id == current_user.id))
    landlord = result.scalar_one_or_none()
    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord profile not found")

    result = await db.execute(
        select(Accommodation).where(
            Accommodation.id == accommodation_id,
            Accommodation.landlord_id == landlord.id
        )
    )
    accommodation = result.scalar_one_or_none()
    if not accommodation:
        raise HTTPException(status_code=403, detail="Listing not found or does not belong to you")

    accommodation.ownership_doc_url = await store_document_upload(file)
    accommodation.status = "pending"

    await db.commit()
    await cache_delete(key_listing(accommodation_id))
    await cache_delete_pattern("search:*")
    await cache_delete(key_featured())

    return {"detail": "Ownership document uploaded", "url": ownership_document_link(accommodation.id, accommodation.ownership_doc_url)}

@router.get("/{accommodation_id}/insights")
async def get_accommodation_insights(
    accommodation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Detailed insights require an active, verified authenticated account."""
    await visible_accommodation(db, accommodation_id, current_user)
    result = await db.execute(
        select(AccommodationInsight).where(
            AccommodationInsight.accommodation_id == accommodation_id
        )
    )
    insight = result.scalar_one_or_none()

    if not insight:
        return {"insights": {}, "recommendations": [], "review_count": 0}

    return {
        "insights": insight.insights,
        "recommendations": insight.recommendations,
        "review_count": insight.review_count,
        "generated_at": insight.generated_at,
    }