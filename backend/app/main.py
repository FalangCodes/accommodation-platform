from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta, timezone
from sqlalchemy.future import select
from app.api.v1.routes import auth, accommodations, reviews, moderation
from app.api.v1.routes.universities import router as universities_router
from app.api.v1.routes.landlords import router as landlords_router
from app.api.v1.routes.admin import router as admin_router
from app.api.v1.routes.reports import router as reports_router
from app.api.v1.routes.appeals import router as appeals_router
from app.db.base import AsyncSessionLocal
from app.services.cache_service import flush_views_to_db
from app.services.report_service import run_monthly_auto_reports
from app.models.review import Review
from app.core.config import settings
import app.db.models

scheduler = AsyncIOScheduler()

async def scheduled_flush():
    print("Running scheduled view flush...")
    async with AsyncSessionLocal() as db:
        await flush_views_to_db(db)

async def sweep_stuck_reviews():
    """
    Retry NLP analysis for reviews stuck in pending_analysis for more than 5 minutes.

    A 4-second delay is enforced between each review to act as a rate-limit
    governor, keeping us safely under Gemini's 15 RPM free tier limit.
    At 4s per review that's a max of 15 requests/min — exactly at the limit.
    """
    import asyncio
    from app.services.review_service import process_review_nlp
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Review).where(
                Review.status == "pending_analysis",
                Review.created_at < cutoff
            )
        )
        stuck = result.scalars().all()
        if stuck:
            print(f"[Sweep] Found {len(stuck)} stuck review(s) — retrying NLP...")
        for review in stuck:
            await process_review_nlp(review.id, review.body)
            if len(stuck) > 1:
                # Rate-limit governor: gemini-3.6-flash free tier = 5 RPM max
                # 60s / 5 = 12s per request minimum. 13s gives a safe buffer.
                await asyncio.sleep(13)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start scheduler
    scheduler.add_job(
        scheduled_flush,
        "cron",
        hour=0,       # midnight
        minute=0,
        id="flush_views"
    )
    # ── For testing: flush every 1 minute ──
    # scheduler.add_job(scheduled_flush, "interval", minutes=1, id="flush_views")
    scheduler.add_job(
        run_monthly_auto_reports,
        "cron",
        day=1,
        hour=0,
        minute=5,
        id="monthly_reports"
    )
    scheduler.add_job(
        sweep_stuck_reviews,
        "interval",
        minutes=10,
        id="sweep_stuck_reviews"
    )
    scheduler.start()
    print("Scheduler started")
    yield
    scheduler.shutdown()
    print("Scheduler stopped")

app = FastAPI(
    title="Accommodation Platform API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL.rstrip("/"),
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://40.123.252.250:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Auth-Error"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(accommodations.router, prefix="/api/v1")
app.include_router(reviews.router, prefix="/api/v1")
app.include_router(moderation.router, prefix="/api/v1")
app.include_router(universities_router, prefix="/api/v1")
app.include_router(landlords_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(appeals_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
