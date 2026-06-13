from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)

    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    student_number = Column(String, nullable=True)

    # Kept for future Tier 2 verification
    student_number_hash = Column(String, nullable=True)
    verification_tier = Column(Integer, default=1)

    # Relationships
    user = relationship("User", backref="student_profile")
    university = relationship("University")
    reviews = relationship("Review", back_populates="student")