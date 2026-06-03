from fastapi import FastAPI
from app.api.v1.routes import auth

app = FastAPI(
    title="Accommodation Platform API",
    version="1.0.0"
)

app.include_router(auth.router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok"}