import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.models import University

async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        spu = University(
            name="Sol Plaatje University",
            domain="spu.ac.za",
            province="Northern Cape",
            campus_location="POINT(24.7435 -28.7282)"
        )
        session.add(spu)
        await session.commit()
        print("SPU seeded successfully")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed())