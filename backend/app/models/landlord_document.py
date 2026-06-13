from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class LandlordDocument(Base):
    __tablename__ = "landlord_documents"

    id = Column(Integer, primary_key=True, index=True)
    landlord_id = Column(Integer, ForeignKey("landlords.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String, nullable=False)  # 'id_copy', 'proof_of_address', 'property_ownership'
    blob_url = Column(String, nullable=False)
    verified = Column(Boolean, default=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    landlord = relationship("Landlord", back_populates="documents")