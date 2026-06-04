import httpx
from app.core.config import settings


async def analyse_review(review_id: int, text: str) -> dict:
    """Call the NLP microservice and return the analysis results."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.NLP_SERVICE_URL}/analyze",
                json={"review_id": review_id, "text": text}
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"NLP analysis failed for review {review_id}: {e}")
        return None