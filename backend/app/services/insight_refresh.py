"""Refresh derived insights after a committed review visibility change."""
import logging
from sqlalchemy import delete
from app.models.insight import AccommodationInsight
from app.services.insight_engine import regenerate_accommodation_insights

logger = logging.getLogger(__name__)


async def refresh_listing_insights(listing_id, db):
    try:
        await regenerate_accommodation_insights(listing_id, db)
    except Exception:
        await db.rollback()
        logger.exception("Insight refresh failed for listing %s; clearing stale insights", listing_id)
        await db.execute(delete(AccommodationInsight).where(
            AccommodationInsight.accommodation_id == listing_id))
        await db.commit()
