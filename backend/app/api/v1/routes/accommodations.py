from sqlalchemy import text, func
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import hashlib
from app.db.base import get_db
from app.core.dependencies import get_current_landlord, get_optional_user
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
    TTL_SEARCH, TTL_LISTING, TTL_REVIEWS, TTL_ANALYTICS
)

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

    cache_key = key_search(university_id, radius_km, price_min, price_max, min_rating, gender_policy, funding_type, page, q=q)
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    page = max(1, page)
    page_size = min(max(1, page_size), 50)
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
        order_by = "ORDER BY ST_Distance(a.location, u.campus_location)"
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
        order_by = "ORDER BY a.created_at DESC"

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
    return result_data

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
            "ownership_doc_url": acc.ownership_doc_url,
        })

    return output

@router.get("/{accommodation_id}/analytics")
async def get_analytics(
    accommodation_id: int,
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
    cache_key = key_analytics(accommodation_id)
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    # 1. Verify landlord owns this listing
    query = select(Landlord).where(Landlord.user_id == current_user.id)
    result = await db.execute(query)
    landlord = result.scalar_one_or_none()

    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord profile not found")

    query = select(Accommodation).where(
        Accommodation.id == accommodation_id,
        Accommodation.landlord_id == landlord.id
    )
    result = await db.execute(query)
    accommodation = result.scalar_one_or_none()

    if not accommodation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Listing not found or does not belong to you"
        )

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
    db: AsyncSession = Depends(get_db)
):
    """Record a listing view — increments Redis counter, flushed to DB at midnight."""
    # Verify accommodation exists
    result = await db.execute(
        select(Accommodation).where(Accommodation.id == accommodation_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Accommodation not found")

    # Increment Redis counter
    await increment_view(accommodation_id)

@router.get("/{accommodation_id}")
async def get_accommodation(accommodation_id: int, db: AsyncSession = Depends(get_db)):
    cache_key = key_listing(accommodation_id)
    cached = await cache_get(cache_key)
    if cached:
        return cached
    # 1. Base accommodation
    result = await db.execute(
        select(Accommodation).where(Accommodation.id == accommodation_id)
    )
    accommodation = result.scalar_one_or_none()
    if not accommodation:
        raise HTTPException(status_code=404, detail="Accommodation not found")

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
        "ownership_doc_url": accommodation.ownership_doc_url,
        "images": [{"id": img.id, "url": img.blob_url, "order": img.display_order} for img in images],
        "total_reviews": total_reviews,
        "average_rating": average_rating,
        "dominant_sentiment": dominant_sentiment,
        "sentiment_distribution": sentiment_distribution,
        "top_aspects": top_aspects,
    }

    await cache_set(cache_key, result_data, TTL_LISTING)
    return result_data

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
    result = await db.execute(select(Landlord).where(Landlord.user_id == current_user.id))
    landlord = result.scalar_one_or_none()
    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord profile not found")

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

    # Validate file
    allowed = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, WebP and PDF files are allowed")

    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File must be under 10MB")

    blob_url = await upload_image(file_bytes, f"ownership_{accommodation_id}", file.content_type)
    accommodation.ownership_doc_url = blob_url
    accommodation.status = "pending"

    # Invalidate cache
    await cache_delete(key_listing(accommodation_id))
    await db.commit()

    return {"detail": "Ownership document uploaded", "url": blob_url}

@router.get("/{accommodation_id}/insights")
async def get_accommodation_insights(
    accommodation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Public endpoint — returns student-filtered insights + landlord full view based on auth."""
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