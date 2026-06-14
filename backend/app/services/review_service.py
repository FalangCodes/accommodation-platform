from app.db.base import AsyncSessionLocal
from app.models.review import Review, ReviewNLPResult
from app.services.nlp_service import analyse_review
from sqlalchemy.future import select


async def process_review_nlp(review_id: int, review_text: str, db=None):
    """Background task: call NLP service and store results."""
    result = await analyse_review(review_id, review_text)

    if not result:
        print(f"NLP service returned no result for review {review_id}")
        return

    async with AsyncSessionLocal() as session:
        try:
            # Fetch the review
            review_result = await session.execute(
                select(Review).where(Review.id == review_id)
            )
            review = review_result.scalar_one_or_none()
            if not review:
                print(f"Review {review_id} not found")
                return

            # Save NLP result
            nlp_record = ReviewNLPResult(
                review_id=review_id,
                sentiment=result["sentiment"],
                sentiment_score=result["sentiment_score"],
                aspects=result["aspects"],
                spam_flag=result["is_toxic"],
            )
            session.add(nlp_record)

            # Set status based on toxicity
            if result["is_toxic"]:
                review.status = "quarantined"
                print(f"Review {review_id} quarantined — toxic content detected")
            else:
                review.status = "analysed"
                print(f"Review {review_id} analysed — sentiment: {result['sentiment']}")

            await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"Failed to save NLP results for review {review_id}: {e}")