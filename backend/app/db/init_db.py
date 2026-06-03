import asyncio
import sys
import os

# Fix import paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from app.db.base import engine, Base

# We MUST import all models here so SQLAlchemy knows what to build
from app.models.user import User
from app.models.student import Student
from app.models.landlord import Landlord
from app.models.university import University
from app.models.accommodation import Accommodation, AccommodationView, AccommodationImage
from app.models.review import Review, ReviewNLPResult, ReviewReply
from app.models.moderation import ModerationLog, ModerationQueue, Appeal

async def force_build_database():
    async with engine.begin() as conn:
        # 1. Guarantee PostGIS is active for your geographic columns
        print("Enabling PostGIS extension...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        
        # 2. Wipe the slate completely clean
        print("Dropping old schema (if any)...")
        await conn.run_sync(Base.metadata.drop_all)
        
        # 3. Force-build every single table
        print("Building all tables directly from models...")
        await conn.run_sync(Base.metadata.create_all)
        
    print("Database foundation successfully built! 🏗️")

if __name__ == "__main__":
    asyncio.run(force_build_database())