from app.db.base import AsyncSessionLocal
from app.models.review import Review, ReviewNLPResult
from app.services.nlp_service import analyse_review
from app.services.insight_engine import extract_aspect_details, regenerate_accommodation_insights
from sqlalchemy.future import select


async def process_review_nlp(review_id: int, review_text: str, db=None):
    """Background task: call NLP service, extract aspect details, regenerate insights."""
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

            # Extract aspect-level details using insight engine
            aspect_details = await extract_aspect_details(
                aspects=result.get("aspects", {}),
                sentences=result.get("sentences", []),
                overall_sentiment=result.get("sentiment", "neutral")
            )

            # Save enriched NLP result
            nlp_record = ReviewNLPResult(
                review_id=review_id,
                sentiment=result["sentiment"],
                sentiment_score=result["sentiment_score"],
                aspects=result["aspects"],
                aspect_details=aspect_details,  # ← new
                spam_flag=result["is_toxic"],
            )
            session.add(nlp_record)

            # Set review status
            if result["is_toxic"]:
                review.status = "quarantined"
            else:
                review.status = "analysed"

            await session.commit()
            print(f"NLP complete for review {review_id}")

            # Regenerate accommodation insights
            await regenerate_accommodation_insights(review.accommodation_id, session)

        except Exception as e:
            await session.rollback()
            print(f"Failed to process review {review_id}: {e}")