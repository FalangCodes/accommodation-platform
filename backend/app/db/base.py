from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

async def get_db():
    """FastAPI dependency to get database session"""
    async with AsyncSessionLocal() as session:
        yield session

# Import all models here so SQLAlchemy can resolve all relationships
from app.models.user import User
from app.models.student import Student
from app.models.landlord import Landlord
from app.models.university import University
from app.models.accommodation import Accommodation, AccommodationView, AccommodationImage
from app.models.review import Review, ReviewNLPResult, ReviewReply
from app.models.moderation import ModerationLog, ModerationQueue, Appeal