from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.review import Review, ReviewNLPResult
from app.services.nlp_service import analyse_review


async def process_review_nlp(review_id: int, review_text: str, db: AsyncSession):
    """Background task: call NLP service and store results."""
    result = await analyse_review(review_id, review_text)

    if not result:
        return

    async with db:
        nlp_result = ReviewNLPResult(
            review_id=review_id,
            sentiment=result["sentiment"],
            sentiment_score=result["sentiment_score"],
            aspects=result["aspects"],
            spam_flag=result["is_toxic"]
        )
        db.add(nlp_result)
        await db.commit()
        print(f"NLP results saved for review {review_id}")