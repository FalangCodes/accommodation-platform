from sqlalchemy import text, func
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.db.base import get_db
from app.core.dependencies import get_current_landlord
from app.models.user import User
from app.models.landlord import Landlord
from app.models.accommodation import Accommodation, AccommodationView
from app.models.university import University
from app.models.review import Review, ReviewNLPResult
from app.schemas.accommodation import AccommodationCreate, AccommodationResponse

router = APIRouter(prefix="/accommodations", tags=["Accommodations"])


@router.post("", response_model=AccommodationResponse, status_code=status.HTTP_201_CREATED)
async def create_accommodation(
    accommodation_in: AccommodationCreate,
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
    # Get landlord profile
    query = select(Landlord).where(Landlord.user_id == current_user.id)
    result = await db.execute(query)
    landlord = result.scalar_one_or_none()

    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord profile not found")

    new_accommodation = Accommodation(
        landlord_id=landlord.id,
        title=accommodation_in.title,
        description=accommodation_in.description,
        address=accommodation_in.address,
        location=f"POINT({accommodation_in.longitude} {accommodation_in.latitude})",
        price_min=accommodation_in.price_min,
        price_max=accommodation_in.price_max,
        status="pending"
    )
    db.add(new_accommodation)
    await db.commit()
    await db.refresh(new_accommodation)

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
    page: int = 1,
    page_size: int = 15,
    db: AsyncSession = Depends(get_db)
):
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
                COUNT(r.id) AS review_count
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
                COUNT(r.id) AS review_count
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

    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@router.get("/{accommodation_id}/analytics")
async def get_analytics(
    accommodation_id: int,
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
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
    total_views = result.scalar() or 0

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

    return {
        "accommodation_id": accommodation_id,
        "total_views": total_views,
        "total_reviews": total_reviews,
        "average_rating": average_rating,
        "sentiment_distribution": sentiment_distribution,
        "top_aspects": top_aspects
    }


@router.get("/{accommodation_id}", response_model=AccommodationResponse)
async def get_accommodation(accommodation_id: int, db: AsyncSession = Depends(get_db)):
    query = select(Accommodation).where(Accommodation.id == accommodation_id)
    result = await db.execute(query)
    accommodation = result.scalar_one_or_none()

    if not accommodation:
        raise HTTPException(status_code=404, detail="Accommodation not found")

    return accommodation

