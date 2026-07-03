from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.api.v1.routes import auth, accommodations, reviews, moderation
from app.api.v1.routes.universities import router as universities_router
from app.api.v1.routes.landlords import router as landlords_router
from app.api.v1.routes.admin import router as admin_router
from app.api.v1.routes.reports import router as reports_router
from app.db.base import AsyncSessionLocal
from app.services.cache_service import flush_views_to_db
from app.services.report_service import run_monthly_auto_reports
import app.db.models

scheduler = AsyncIOScheduler()

async def scheduled_flush():
    print("Running scheduled view flush...")
    async with AsyncSessionLocal() as db:
        await flush_views_to_db(db)

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
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://40.123.252.250:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(accommodations.router, prefix="/api/v1")
app.include_router(reviews.router, prefix="/api/v1")
app.include_router(moderation.router, prefix="/api/v1")
app.include_router(universities_router, prefix="/api/v1")
app.include_router(landlords_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok"}