from fastapi import FastAPI
from app.api.v1.routes import auth, accommodations, reviews, moderation
import app.db.models

app = FastAPI(
    title="Accommodation Platform API",
    version="1.0.0"
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(accommodations.router, prefix="/api/v1")
app.include_router(reviews.router, prefix="/api/v1")
app.include_router(moderation.router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok"}