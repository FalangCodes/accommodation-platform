from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, UniqueConstraint, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.base import Base

class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    accommodation_id = Column(Integer, ForeignKey("accommodations.id"), nullable=False)
    
    rating = Column(Integer, nullable=False) # 1-5
    body = Column(Text, nullable=False)
    
    # pending_analysis, analysed, flagged
    status = Column(String, default="pending_analysis", index=True) 

    # Soft delete fields
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    cooldown_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Enforce one review per student per accommodation
    __table_args__ = (
        UniqueConstraint('student_id', 'accommodation_id', name='uix_student_accommodation_review'),
    )

    # Relationships
    student = relationship("Student", back_populates="reviews")
    accommodation = relationship("Accommodation", back_populates="reviews")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ReviewNLPResult(Base):
    __tablename__ = "review_nlp_results"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    sentiment = Column(String, nullable=False) # positive/neutral/negative
    sentiment_score = Column(Float, nullable=False)
    aspects = Column(JSONB, nullable=False)
    spam_flag = Column(Boolean, default=False)
    
    analysed_at = Column(DateTime(timezone=True), server_default=func.now())

class ReviewReply(Base):
    __tablename__ = "review_replies"

    id = Column(Integer, primary_key=True, index=True)
    
    # [KK2] Unique constraint strictly on review_id to enforce one reply per review total
    review_id = Column(Integer, ForeignKey("reviews.id", ondelete="CASCADE"), unique=True, nullable=False)
    landlord_id = Column(Integer, ForeignKey("landlords.id"), nullable=False)
    
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())