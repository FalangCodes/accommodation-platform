from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, Table, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography
from db.base import Base

class Accommodation(Base):
    __tablename__ = "accommodations"

    id = Column(Integer, primary_key=True, index=True)
    landlord_id = Column(Integer, ForeignKey("landlords.id"), nullable=False)
    
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    address = Column(String, nullable=False)
    
    # PostGIS point
    location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    
    price_min = Column(Float, nullable=False)
    price_max = Column(Float, nullable=False)
    
    # pending, approved, rejected, removed
    status = Column(String, default="pending", index=True) 

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    landlord = relationship("Landlord", back_populates="accommodations")
    reviews = relationship("Review", back_populates="accommodation")

# Many-to-Many Association Table for Accommodations <-> Universities
accommodation_universities = Table(
    "accommodation_universities",
    Base.metadata,
    Column("accommodation_id", Integer, ForeignKey("accommodations.id", ondelete="CASCADE"), primary_key=True),
    Column("university_id", Integer, ForeignKey("universities.id", ondelete="CASCADE"), primary_key=True)
)

class AccommodationImage(Base):
    __tablename__ = "accommodation_images"

    id = Column(Integer, primary_key=True, index=True)
    accommodation_id = Column(Integer, ForeignKey("accommodations.id", ondelete="CASCADE"), nullable=False)
    blob_url = Column(String, nullable=False)
    display_order = Column(Integer, default=0)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

class AccommodationView(Base):
    __tablename__ = "accommodation_views"

    id = Column(Integer, primary_key=True, index=True)
    accommodation_id = Column(Integer, ForeignKey("accommodations.id", ondelete="CASCADE"), nullable=False)
    
    # [KK1] Hash generated via HMAC in the application layer before insertion
    viewer_ip_hash = Column(String, nullable=False, index=True) 
    viewed_at = Column(DateTime(timezone=True), server_default=func.now())