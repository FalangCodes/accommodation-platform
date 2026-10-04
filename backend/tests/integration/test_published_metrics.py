"""Azure-only PostgreSQL/Redis checks, using disposable schemas and Redis keys."""
import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from sqlalchemy import select, func

from test_review_resubmission import isolated_reviews, historical_review
from app.api.v1.routes import accommodations
from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User
from app.models.student import Student
from app.models.review import Review, ReviewNLPResult
from app.models.accommodation import AccommodationView
from app.models.insight import AccommodationInsight
from app.services import cache_service, insight_engine


@pytest_asyncio.fixture
async def metrics_app(isolated_reviews, monkeypatch):
    client, sessions, headers, mod_headers, effects = isolated_reviews
    client._transport.app.include_router(accommodations.router, prefix="/api/v1")

    async def miss(*args):
        return None

    async def noop(*args):
        pass

    async def opinion(*args, **kwargs):
        return "Test opinion generated without contacting an external service."

    monkeypatch.setattr(accommodations, "cache_get", miss)
    monkeypatch.setattr(accommodations, "cache_set", noop)
    monkeypatch.setattr(cache_service, "cache_delete", noop)
    monkeypatch.setattr(insight_engine, "generate_opinion", opinion)
    prefix = "test_gap9_" + uuid.uuid4().hex + ":"
    redis = redis_async.from_url(settings.REDIS_URL, decode_responses=True)

    class PrivateRedis:
        async def get(self, key):
            return await redis.get(prefix + key)

        async def incr(self, key):
            return await redis.incr(prefix + key)

        async def delete(self, *keys):
            return await redis.delete(*(prefix + key for key in keys))

        async def eval(self, script, count, *args):
            return await redis.eval(script, count,
                                    *(prefix + key for key in args[:count]), *args[count:])

        async def scan_iter(self, match):
            async for key in redis.scan_iter(match=prefix + match):
                assert key.startswith(prefix)
                yield key[len(prefix):]

    private = PrivateRedis()

    async def get_private():
        return private

    monkeypatch.setattr(cache_service, "get_redis", get_private)
    try:
        yield client, sessions, headers, mod_headers, effects, redis, prefix
    finally:
        keys = [key async for key in redis.scan_iter(match=prefix + "*")]
        assert all(key.startswith(prefix) for key in keys)
        if keys:
            await redis.delete(*keys)
        await redis.aclose()


@pytest.mark.asyncio
async def test_metrics_exclude_unpublished_and_deleted_reviews(metrics_app):
    client, sessions, headers, _, _, _, _ = metrics_app
    await historical_review(sessions, deleted=False, status="analysed")  # rating 2
    async with sessions() as db:
        for identifier, status, deleted in [(4, "released", False), (5, "pending_analysis", False),
                                             (6, "quarantined", False), (7, "analysed", True)]:
            db.add(User(id=identifier, email=f"student{identifier}@spu.ac.za", role="student",
                        is_active=True, password_hash="unused"))
            await db.flush()
            db.add(Student(id=identifier, user_id=identifier, university_id=1, verification_tier=1))
            await db.flush()
            db.add(Review(student_id=identifier, accommodation_id=1, rating=4 if identifier == 4 else 5,
                          body="Review body for metric filtering tests.", status=status,
                          deleted_at=datetime.now(timezone.utc) if deleted else None))
        await db.commit()
    detail = await client.get("/api/v1/accommodations/1", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["total_reviews"] == 2
    assert detail.json()["average_rating"] == 3
    stats = await client.get("/api/v1/accommodations/platform-stats")
    assert stats.json()["reviews"] == 2
    search = await client.get("/api/v1/accommodations/search?min_rating=3.1", headers=headers)
    assert search.status_code == 200 and search.json()["total"] == 0
    owner = {"Authorization": f"Bearer {create_access_token('3')}"}
    analytics = await client.get("/api/v1/accommodations/1/analytics", headers=owner)
    assert analytics.status_code == 200
    assert analytics.json()["total_reviews"] == 2 and analytics.json()["average_rating"] == 3


@pytest.mark.asyncio
async def test_last_review_deletion_clears_insights_and_all_discovery_caches(metrics_app):
    client, sessions, headers, _, effects, _, _ = metrics_app
    identifier = await historical_review(sessions, deleted=False)
    async with sessions() as db:
        db.add(AccommodationInsight(accommodation_id=1, insights={"old": {"mention_count": 10}},
                                   recommendations=[{"old": True}], review_count=10))
        await db.commit()
    assert (await client.delete(f"/api/v1/reviews/{identifier}", headers=headers)).status_code == 204
    async with sessions() as db:
        insight = (await db.execute(select(AccommodationInsight))).scalar_one()
        assert insight.review_count == 0 and insight.insights == {} and insight.recommendations == []
    invalidated = {key for kind, args in effects if kind == "cache" for key in args}
    assert {"listing:1", "reviews:1", "analytics:1", "featured:listings", "activity:feed",
            "platform:stats", "search:*"}.issubset(invalidated)


@pytest.mark.asyncio
async def test_insights_work_without_optional_aspect_details_column(metrics_app):
    _, sessions, _, _, _, _, _ = metrics_app
    identifier = await historical_review(sessions, deleted=False)
    async with sessions() as db:
        db.add(ReviewNLPResult(review_id=identifier, sentiment="positive", sentiment_score=0.9,
                               aspects={"wifi and internet": 0.9}, spam_flag=False))
        await db.commit()
        await insight_engine.regenerate_accommodation_insights(1, db)
        insight = (await db.execute(select(AccommodationInsight))).scalar_one()
        assert insight.review_count == 1


@pytest.mark.asyncio
async def test_moderator_release_and_removal_refresh_published_insight_count(metrics_app):
    client, sessions, headers, admin_headers, _, _, _ = metrics_app
    identifier = await historical_review(sessions, deleted=False, status="quarantined")
    response = await client.patch(f"/api/v1/moderation/reviews/{identifier}/release", headers=admin_headers)
    assert response.status_code == 200
    insight = await client.get("/api/v1/accommodations/1/insights", headers=headers)
    assert insight.status_code == 200 and insight.json()["review_count"] == 1
    response = await client.request("DELETE", f"/api/v1/moderation/reviews/{identifier}",
                                    headers=admin_headers, json={"reason": "Test removal"})
    assert response.status_code == 200
    async with sessions() as db:
        insight = (await db.execute(select(AccommodationInsight))).scalar_one()
        assert insight.review_count == 0 and insight.insights == {}


async def persisted_views(sessions):
    async with sessions() as db:
        return (await db.execute(select(func.count(AccommodationView.id)))).scalar()


@pytest.mark.asyncio
async def test_failed_view_commit_retains_batch_and_retry_does_not_duplicate(metrics_app):
    _, sessions, _, _, _, redis, prefix = metrics_app
    await redis.set(prefix + "views:1", 3)
    async with sessions() as db:
        commit = db.commit

        async def fail():
            raise RuntimeError("Deliberate test failure before commit")

        db.commit = fail
        await cache_service.flush_views_to_db(db)
        db.commit = commit
    assert await persisted_views(sessions) == 0
    assert json.loads(await redis.get(prefix + "view-batch:1"))["count"] == 3
    await cache_service.increment_view(1)
    async with sessions() as db:
        assert await cache_service.total_listing_views(db, 1) == 4
    for _ in range(3):
        async with sessions() as db:
            await cache_service.flush_views_to_db(db)
    assert await persisted_views(sessions) == 4
    assert await redis.get(prefix + "view-batch:1") is None


@pytest.mark.asyncio
async def test_committed_batch_is_counted_once_after_ack_failure(metrics_app):
    _, sessions, _, _, _, redis, prefix = metrics_app
    marker = "batch:" + uuid.uuid4().hex
    await redis.set(prefix + "view-batch:1", json.dumps({"count": 2, "marker": marker}))
    async with sessions() as db:
        db.add_all([AccommodationView(accommodation_id=1, viewer_ip_hash=marker) for _ in range(2)])
        await db.commit()
        assert await cache_service.total_listing_views(db, 1) == 2
    async with sessions() as db:
        await cache_service.flush_views_to_db(db)
    assert await persisted_views(sessions) == 2
    assert await redis.get(prefix + "view-batch:1") is None


@pytest.mark.asyncio
async def test_concurrent_flushes_and_increments_preserve_all_views(metrics_app):
    _, sessions, _, _, _, redis, prefix = metrics_app
    await redis.set(prefix + "views:1", 10)

    async def flush():
        async with sessions() as db:
            await cache_service.flush_views_to_db(db)

    async def increment():
        for _ in range(10):
            await cache_service.increment_view(1)

    await asyncio.gather(flush(), flush(), increment())
    await flush()
    async with sessions() as db:
        assert await cache_service.total_listing_views(db, 1) == 20
    assert await persisted_views(sessions) == 20
