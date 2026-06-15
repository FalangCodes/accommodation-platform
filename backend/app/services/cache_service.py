import json
import hashlib
from typing import Any, Optional
import redis.asyncio as aioredis
from app.core.config import settings

# ─── Client ───────────────────────────────────────────────────────────────────

_redis_client: Optional[aioredis.Redis] = None

async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    return _redis_client

# ─── TTLs (seconds) ───────────────────────────────────────────────────────────

TTL_UNIVERSITIES = 60 * 60 * 24   # 24 hours
TTL_SEARCH       = 60 * 5         # 5 minutes
TTL_LISTING      = 60 * 10        # 10 minutes
TTL_REVIEWS      = 60 * 5         # 5 minutes
TTL_ANALYTICS    = 60 * 30        # 30 minutes

# ─── Key builders ─────────────────────────────────────────────────────────────

def key_universities() -> str:
    return "universities:all"

def key_search(university_id, radius_km, price_min, price_max, min_rating, page) -> str:
    raw = f"{university_id}:{radius_km}:{price_min}:{price_max}:{min_rating}:{page}"
    return f"search:{hashlib.md5(raw.encode()).hexdigest()}"

def key_listing(accommodation_id: int) -> str:
    return f"listing:{accommodation_id}"

def key_reviews(accommodation_id: int) -> str:
    return f"reviews:{accommodation_id}"

def key_analytics(accommodation_id: int) -> str:
    return f"analytics:{accommodation_id}"

# ─── Core helpers ─────────────────────────────────────────────────────────────

async def cache_get(key: str) -> Optional[Any]:
    try:
        redis = await get_redis()
        value = await redis.get(key)
        if value:
            return json.loads(value)
    except Exception as e:
        print(f"Cache GET failed for {key}: {e}")
    return None

async def cache_set(key: str, value: Any, ttl: int) -> None:
    try:
        redis = await get_redis()
        await redis.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as e:
        print(f"Cache SET failed for {key}: {e}")

async def cache_delete(*keys: str) -> None:
    try:
        redis = await get_redis()
        await redis.delete(*keys)
    except Exception as e:
        print(f"Cache DELETE failed: {e}")

async def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching a pattern e.g. 'search:*'"""
    try:
        redis = await get_redis()
        keys = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)
    except Exception as e:
        print(f"Cache DELETE pattern failed for {pattern}: {e}")