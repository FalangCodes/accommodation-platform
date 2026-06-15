from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base

class Landlord(Base):
    __tablename__ = "landlords"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    contact_phone = Column(String, nullable=True)
    bio = Column(String, nullable=True)
    website = Column(String, nullable=True)
    address_line1 = Column(String, nullable=True)
    address_line2 = Column(String, nullable=True)
    city = Column(String, nullable=True)
    province = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)

    # Verification documents
    id_copy_url = Column(String, nullable=True)
    proof_of_address_url = Column(String, nullable=True)

    # Verification
    id_number_encrypted = Column(String, nullable=True)
    id_number_verified = Column(Boolean, default=False)
    verification_status = Column(String, default="unverified")  # unverified, pending, verified, rejected
    rejection_reason = Column(String, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref="landlord_profile")
    accommodations = relationship("Accommodation", back_populates="landlord")