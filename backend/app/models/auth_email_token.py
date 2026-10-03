from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from app.db.base import Base


class AuthEmailToken(Base):
    __tablename__ = "auth_email_tokens"

    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
