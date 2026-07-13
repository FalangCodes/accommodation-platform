from app.db.base import AsyncSessionLocal
from app.models.review import Review, ReviewNLPResult
from app.services.nlp_service import analyse_review
from app.services.insight_engine import extract_aspect_details, regenerate_accommodation_insights
from sqlalchemy.future import select


async def process_review_nlp(review_id: int, review_text: str, db=None):
    result = await analyse_review(review_id, review_text)

    if not result:
        print(f"NLP service returned no result for review {review_id}")
        return

    async with AsyncSessionLocal() as session:
        try:
            review_result = await session.execute(
                select(Review).where(Review.id == review_id)
            )
            review = review_result.scalar_one_or_none()
            if not review:
                return

            # Extract aspect details — pure Python, no HTTP calls
            aspect_details = extract_aspect_details(
                aspects=result.get("aspects", {}),
                review_body=review_text,
                overall_sentiment=result.get("sentiment", "neutral"),
                sentiment_score=result.get("sentiment_score", 0.5),
            )

            nlp_record = ReviewNLPResult(
                review_id=review_id,
                sentiment=result["sentiment"],
                sentiment_score=result["sentiment_score"],
                aspects=result["aspects"],
                aspect_details=aspect_details,
                spam_flag=result["is_toxic"],
            )
            session.add(nlp_record)

            if result["is_toxic"]:
                review.status = "quarantined"
            else:
                review.status = "analysed"

            await session.commit()
            print(f"NLP complete for review {review_id}")

            # Regenerate insights — fast now, no HTTP calls
            await regenerate_accommodation_insights(review.accommodation_id, session)

        except Exception as e:
            await session.rollback()
            print(f"Failed to process review {review_id}: {e}")