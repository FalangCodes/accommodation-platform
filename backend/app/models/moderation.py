from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from app.db.base import Base

class ModerationLog(Base):
    __tablename__ = "moderation_log"

    id = Column(Integer, primary_key=True, index=True)
    moderator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False) # e.g., 'approved', 'rejected', 'removed'
    
    resource_type = Column(String, nullable=False)
    resource_id = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Appeal(Base):
    __tablename__ = "appeals"

    id = Column(Integer, primary_key=True, index=True)
    appellant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    appellant_role = Column(String, nullable=False) # 'landlord' or 'student'
    
    resource_type = Column(String, nullable=False)
    resource_id = Column(Integer, nullable=False)
    original_action_id = Column(Integer, ForeignKey("moderation_log.id"), nullable=False)
    
    reason = Column(Text, nullable=False)
    status = Column(String, default="pending", index=True) # pending, upheld, dismissed
    
    assigned_admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)