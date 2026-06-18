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

# ─── View counter ─────────────────────────────────────────────────────────────

def key_views(accommodation_id: int) -> str:
    return f"views:{accommodation_id}"

async def increment_view(accommodation_id: int) -> None:
    """Increment Redis view counter for an accommodation."""
    try:
        redis = await get_redis()
        await redis.incr(key_views(accommodation_id))
    except Exception as e:
        print(f"View increment failed for {accommodation_id}: {e}")

async def get_today_views(accommodation_id: int) -> int:
    """Get today's buffered view count from Redis."""
    try:
        redis = await get_redis()
        val = await redis.get(key_views(accommodation_id))
        return int(val) if val else 0
    except Exception as e:
        print(f"Get views failed for {accommodation_id}: {e}")
        return 0

async def flush_views_to_db(db) -> None:
    """Flush all Redis view counters to the accommodation_views table."""
    try:
        redis = await get_redis()
        keys = await redis.keys("views:*")
        if not keys:
            print("No view counters to flush")
            return

        from app.models.accommodation import AccommodationView
        from datetime import datetime, timezone
        import hashlib

        for key in keys:
            accommodation_id = int(key.split(":")[1])
            count = await redis.get(key)
            if not count or int(count) == 0:
                continue

            count = int(count)

            # Insert one row per view count
            for _ in range(count):
                view = AccommodationView(
                    accommodation_id=accommodation_id,
                    viewer_ip_hash=hashlib.md5(b"buffered").hexdigest(),
                    viewed_at=datetime.now(timezone.utc)
                )
                db.add(view)

            # Reset counter
            await redis.delete(key)
            print(f"Flushed {count} views for accommodation {accommodation_id}")

        await db.commit()
        print("View flush complete")

    except Exception as e:
        print(f"View flush failed: {e}")