import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Student Accommodation Discovery System"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/accommodation_db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379")
    NLP_SERVICE_URL: str = os.getenv("NLP_SERVICE_URL", "http://nlp:8001")
    DEFAULT_SEARCH_RADIUS_KM: int = 5
    MODERATOR_INVITE_KEY: str = "change-me-in-env"
    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_STORAGE_CONTAINER_NAME: str = "listing-images"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()