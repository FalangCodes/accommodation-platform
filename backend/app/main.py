from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.routes import auth, accommodations, reviews, moderation, universities
import app.db.models

app = FastAPI(
    title="Accommodation Platform API",
    version="1.0.0"
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
app.include_router(universities.router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok"}