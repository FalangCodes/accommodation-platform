import os
import asyncio
import requests
from celery import Celery
from sqlalchemy.future import select

# Import your database and models
from app.db.base import AsyncSessionLocal
from app.models.review import Review, ReviewNLPResult

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")

# Initialize Celery
celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

async def save_nlp_result_to_db(review_id: int, analysis: dict):
    """Asynchronously saves the NLP analysis back to the database."""
    async with AsyncSessionLocal() as db:
        query = select(Review).where(Review.id == review_id)
        result = await db.execute(query)
        review = result.scalar_one_or_none()
        
        if review:
            # 1. Update the original review status
            review.status = "analyzed"
            
            # 2. Create the NLP Result record
            nlp_record = ReviewNLPResult(
                review_id=review_id,
                sentiment_label=analysis["sentiment"],
                sentiment_score=analysis["sentiment_score"],
                is_toxic=analysis["is_toxic"],
                toxicity_score=analysis["toxicity_score"],
                extracted_aspects=analysis["aspects"]
            )
            db.add(nlp_record)
            await db.commit()
            print(f"✅ Successfully saved NLP results for Review #{review_id}")

@celery_app.task(name="analyze_review_task", bind=True, max_retries=3)
def analyze_review_task(self, review_id: int, review_text: str):
    """The synchronous Celery task that calls the NLP microservice."""
    # This URL uses Docker's internal DNS to hit the NLP container
    nlp_url = "http://nlp:8001/analyze" 
    
    try:
        # Call the HuggingFace microservice
        response = requests.post(nlp_url, json={"text": review_text}, timeout=20)
        response.raise_for_status()
        analysis = response.json()
        
        # Safely run our async database function
        asyncio.run(save_nlp_result_to_db(review_id, analysis))
        
        return analysis
        
    except requests.exceptions.RequestException as exc:
        print(f"⚠️ NLP Service unavailable. Retrying review {review_id}...")
        # Auto-retry if the NLP container is busy or rebooting
        raise self.retry(exc=exc, countdown=10)