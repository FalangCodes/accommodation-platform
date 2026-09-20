"""
Review NLP processing service.

Orchestrates the full pipeline for a submitted review:
  1. Calls Gemini Flash via nlp_service.analyse_review()
  2. Maps the richer Gemini output into the DB (including true per-aspect sentiment)
  3. Triggers accommodation insight regeneration
"""

from app.db.base import AsyncSessionLocal
from app.models.review import Review, ReviewNLPResult
from app.services.nlp_service import analyse_review
from app.services.insight_engine import extract_aspect_details, regenerate_accommodation_insights
from sqlalchemy.future import select
from sqlalchemy import select as sa_select
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)


async def process_review_nlp(review_id: int, review_text: str, db=None):
    """
    Full NLP processing pipeline for a single review.

    - Calls Gemini Flash for sentiment, aspect detection, and spam check
    - Stores results in review_nlp_results
    - Updates review.status to 'analysed' or 'quarantined'
    - Regenerates accommodation-level insight aggregations
    """
    result = await analyse_review(review_id, review_text)

    if not result:
        logger.warning(f"[ReviewService] NLP returned no result for review {review_id} — will retry on next sweep")
        return

    async with AsyncSessionLocal() as session:
        try:
            # ── Guard: skip if NLP result already exists (prevents UniqueViolationError on retries) ──
            existing = await session.execute(
                sa_select(ReviewNLPResult).where(ReviewNLPResult.review_id == review_id)
            )
            existing_record = existing.scalar_one_or_none()

            review_result = await session.execute(
                sa_select(Review).where(Review.id == review_id)
            )
            review = review_result.scalar_one_or_none()
            if not review:
                logger.warning(f"[ReviewService] Review {review_id} not found in DB")
                return

            # ── Determine aspect details ──────────────────────────────────────────
            # Prefer the new Gemini per-aspect sentiments (fixes the inheritance bug).
            # Fall back to the old keyword-extraction method if not available.
            gemini_aspect_sentiments = result.get("aspect_sentiments", {})

            if gemini_aspect_sentiments:
                # Build aspect_details directly from Gemini's independent per-aspect scores
                aspect_details = {
                    aspect: {
                        "aspect_sentiment": data["sentiment"],
                        # Gemini rationale becomes a single-item strength or concern list
                        "strengths":  [data["rationale"]] if data["sentiment"] == "positive" else [],
                        "concerns":   [data["rationale"]] if data["sentiment"] == "negative"  else [],
                    }
                    for aspect, data in gemini_aspect_sentiments.items()
                }
            else:
                # Legacy fallback — keyword-based extraction (used if Gemini call somehow omits aspect_sentiments)
                aspect_details = extract_aspect_details(
                    aspects=result.get("aspects", {}),
                    review_body=review_text,
                    overall_sentiment=result.get("sentiment", "neutral"),
                    sentiment_score=result.get("sentiment_score", 0.5),
                )

            # ── Upsert NLP result (handles retried reviews gracefully) ────────────
            if existing_record:
                # Update existing record instead of inserting (fixes the sweep UniqueViolationError bug)
                existing_record.sentiment       = result["sentiment"]
                existing_record.sentiment_score = result["sentiment_score"]
                existing_record.aspects         = result["aspects"]
                existing_record.aspect_details  = aspect_details
                existing_record.spam_flag       = result["is_toxic"]
                logger.info(f"[ReviewService] Updated existing NLP record for review {review_id}")
            else:
                nlp_record = ReviewNLPResult(
                    review_id       = review_id,
                    sentiment       = result["sentiment"],
                    sentiment_score = result["sentiment_score"],
                    aspects         = result["aspects"],
                    aspect_details  = aspect_details,
                    spam_flag       = result["is_toxic"],
                )
                session.add(nlp_record)

            # ── Update review status ───────────────────────────────────────────────
            if result["is_toxic"]:
                review.status = "quarantined"
                logger.info(f"[ReviewService] Review {review_id} quarantined (spam/toxic)")
            else:
                review.status = "analysed"

            await session.commit()
            logger.info(f"[ReviewService] NLP complete for review {review_id} — status={review.status}")

            # ── Regenerate accommodation-level insights ────────────────────────────
            await regenerate_accommodation_insights(review.accommodation_id, session)

        except Exception as e:
            await session.rollback()
            logger.error(f"[ReviewService] Failed to process review {review_id}: {e}", exc_info=True)