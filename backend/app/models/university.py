from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from geoalchemy2 import Geography
from app.db.base import Base

class University(Base):
    __tablename__ = "universities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    domain = Column(String, nullable=False, unique=True) # e.g., 'spu.ac.za'
    province = Column(String, nullable=False)
    
    # PostGIS Geography type for accurate distance calculations
    campus_location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())