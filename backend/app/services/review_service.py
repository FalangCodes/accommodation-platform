from sqlalchemy.ext.asyncio import AsyncSession
from app.models.review import Review, ReviewNLPResult
from app.services.nlp_service import analyse_review
from app.db.base import AsyncSessionLocal


async def process_review_nlp(review_id: int, review_text: str, db: AsyncSession = None):
    """Background task: call NLP service and store results."""
    result = await analyse_review(review_id, review_text)

    if not result:
        print(f"NLP service returned no result for review {review_id}")
        return

    # Always create a fresh session — the request session is closed by this point
    async with AsyncSessionLocal() as session:
        try:
            nlp_record = ReviewNLPResult(
                review_id=review_id,
                sentiment=result["sentiment"],
                sentiment_score=result["sentiment_score"],
                aspects=result["aspects"],
                spam_flag=result["is_toxic"],
            )
            session.add(nlp_record)

            # Mark review as analysed
            from sqlalchemy.future import select
            review_result = await session.execute(
                select(Review).where(Review.id == review_id)
            )
            review = review_result.scalar_one_or_none()
            if review:
                review.status = "analysed"

            await session.commit()
            print(f"NLP results saved for review {review_id} — sentiment: {result['sentiment']}")
        except Exception as e:
            await session.rollback()
            print(f"Failed to save NLP results for review {review_id}: {e}")