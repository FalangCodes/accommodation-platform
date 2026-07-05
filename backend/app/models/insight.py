from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class AccommodationInsight(Base):
    __tablename__ = "accommodation_insights"

    id = Column(Integer, primary_key=True, index=True)
    accommodation_id = Column(
        Integer,
        ForeignKey("accommodations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    insights = Column(JSONB, nullable=False)
    recommendations = Column(JSONB, nullable=False)
    review_count = Column(Integer, default=0)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())