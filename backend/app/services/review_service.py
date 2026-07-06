from app.db.base import AsyncSessionLocal
from app.models.review import Review, ReviewNLPResult
from app.services.nlp_service import analyse_review
from sqlalchemy.future import select
import asyncio


async def process_review_nlp(review_id: int, review_text: str, db=None):
    """Background task: call NLP service and store results. Insight regeneration fires separately."""
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

            accommodation_id = review.accommodation_id

            # Save NLP result WITHOUT aspect_details for now
            nlp_record = ReviewNLPResult(
                review_id=review_id,
                sentiment=result["sentiment"],
                sentiment_score=result["sentiment_score"],
                aspects=result["aspects"],
                aspect_details=None,  # filled by insight task separately
                spam_flag=result["is_toxic"],
            )
            session.add(nlp_record)

            # Set review status immediately
            if result["is_toxic"]:
                review.status = "quarantined"
            else:
                review.status = "analysed"

            await session.commit()
            print(f"NLP complete for review {review_id} — now visible publicly")

            # Fire insight regeneration as completely separate task
            # Does NOT block review visibility
            asyncio.create_task(
                run_insight_pipeline(review_id, accommodation_id, result)
            )

        except Exception as e:
            await session.rollback()
            print(f"Failed to save NLP results for review {review_id}: {e}")


async def run_insight_pipeline(review_id: int, accommodation_id: int, nlp_result: dict):
    """Separate task: extract aspect details and regenerate accommodation insights."""
    from app.services.insight_engine import extract_aspect_details, regenerate_accommodation_insights
    from app.models.review import ReviewNLPResult
    from sqlalchemy import update

    print(f"Starting insight pipeline for review {review_id}...")

    try:
        # Extract aspect details
        aspect_details = await extract_aspect_details(
            aspects=nlp_result.get("aspects", {}),
            sentences=nlp_result.get("sentences", []),
            overall_sentiment=nlp_result.get("sentiment", "neutral")
        )

        # Save aspect details
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(ReviewNLPResult)
                .where(ReviewNLPResult.review_id == review_id)
                .values(aspect_details=aspect_details)
            )
            await session.commit()
            print(f"Aspect details saved for review {review_id}")

            # Regenerate accommodation insights
            await regenerate_accommodation_insights(accommodation_id, session)
            print(f"Insights regenerated for accommodation {accommodation_id}")

    except Exception as e:
        print(f"Insight pipeline failed for review {review_id}: {e}")