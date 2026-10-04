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
TTL_FEATURED     = 60 * 60 * 24   # 24 hours
TTL_ACTIVITY     = 60 * 60        # 1 hour

# ─── Key builders ─────────────────────────────────────────────────────────────

def key_universities() -> str:
    return "universities:all"

def key_search(university_id, radius_km, price_min, price_max, min_rating, page, gender_policy=None, funding_type=None, q=None):
    raw = f"{university_id}:{radius_km}:{price_min}:{price_max}:{min_rating}:{page}:{gender_policy}:{funding_type}:{q}"
    return f"search:{hashlib.md5(raw.encode()).hexdigest()}"

def key_listing(accommodation_id: int) -> str:
    return f"listing:{accommodation_id}"

def key_reviews(accommodation_id: int) -> str:
    return f"reviews:{accommodation_id}"

def key_analytics(accommodation_id: int) -> str:
    return f"analytics:{accommodation_id}"

def key_platform_stats() -> str:
    return "platform:stats"

def key_featured() -> str:
    return "featured:listings"

def key_activity() -> str:
    return "activity:feed"

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
        await redis.delete(key_analytics(accommodation_id))
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

# A retained Redis batch remains until PostgreSQL commits. Its stable marker uses
# the existing viewer_ip_hash column so retries need no schema migration.
_CLAIM_VIEWS = """
local pending = redis.call('GET', KEYS[2])
if pending then return pending end
local count = tonumber(redis.call('GET', KEYS[1]) or '0')
if count <= 0 then return nil end
local batch = cjson.encode({count=count, marker=ARGV[1]})
redis.call('SET', KEYS[2], batch)
redis.call('DEL', KEYS[1])
return batch
"""
_ACK_VIEWS = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


def key_view_batch(accommodation_id: int) -> str:
    return f"view-batch:{accommodation_id}"


async def _lock_views(db, accommodation_id):
    from sqlalchemy import text
    await db.execute(text("SELECT pg_advisory_xact_lock(193731, :listing)"),
                     {"listing": accommodation_id})


async def total_listing_views(db, accommodation_id: int) -> int:
    """Read committed and buffered counts while serializing batch handoffs."""
    from sqlalchemy import select, func
    from app.models.accommodation import AccommodationView
    await _lock_views(db, accommodation_id)
    count = (await db.execute(select(func.count(AccommodationView.id)).where(
        AccommodationView.accommodation_id == accommodation_id))).scalar() or 0
    try:
        redis = await get_redis()
        buffered = await redis.get(key_views(accommodation_id))
        count += int(buffered or 0)
        pending = await redis.get(key_view_batch(accommodation_id))
        if pending:
            batch = json.loads(pending)
            persisted = (await db.execute(select(func.count(AccommodationView.id)).where(
                AccommodationView.accommodation_id == accommodation_id,
                AccommodationView.viewer_ip_hash == batch["marker"]))).scalar() or 0
            count += max(0, int(batch["count"]) - persisted)
    except Exception as error:
        print(f"Buffered view lookup failed for {accommodation_id}: {error}")
    return count


async def flush_views_to_db(db) -> None:
    """Retry retained batches; acknowledge only after a successful DB commit."""
    import uuid
    from sqlalchemy import select, func
    from app.models.accommodation import AccommodationView
    redis = await get_redis()
    listing_ids = set()
    for pattern in ("views:*", "view-batch:*"):
        async for key in redis.scan_iter(match=pattern):
            suffix = key.rsplit(":", 1)[-1]
            if suffix.isdigit():
                listing_ids.add(int(suffix))
    for accommodation_id in sorted(listing_ids):
        try:
            await _lock_views(db, accommodation_id)
            raw = await redis.eval(_CLAIM_VIEWS, 2, key_views(accommodation_id),
                                   key_view_batch(accommodation_id), "batch:" + uuid.uuid4().hex)
            if not raw:
                await db.commit()
                continue
            batch = json.loads(raw)
            persisted = (await db.execute(select(func.count(AccommodationView.id)).where(
                AccommodationView.accommodation_id == accommodation_id,
                AccommodationView.viewer_ip_hash == batch["marker"]))).scalar() or 0
            # Partial inserts cannot commit: all rows in a batch share one transaction.
            if not persisted:
                db.add_all([AccommodationView(accommodation_id=accommodation_id,
                            viewer_ip_hash=batch["marker"]) for _ in range(int(batch["count"]))])
            await db.commit()
            await redis.eval(_ACK_VIEWS, 1, key_view_batch(accommodation_id), raw)
            await cache_delete(key_analytics(accommodation_id), key_featured())
        except Exception as error:
            await db.rollback()
            print(f"View flush failed for {accommodation_id}; batch retained: {error}")
