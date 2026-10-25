"""Azure-only real Redis admission tests; Gemini calls are always mocked."""
import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from app.core.config import settings
from app.services import gemini_gateway as gate, nlp_service


@pytest_asyncio.fixture
async def admission(monkeypatch):
    redis = redis_async.from_url(settings.REDIS_URL, decode_responses=True)
    prefix = "test_gemini_" + uuid.uuid4().hex + ":"

    class PrivateRedis:
        async def eval(self, script, count, *args):
            return await redis.eval(script, count, *(prefix + k for k in args[:count]), *args[count:])

    async def private_redis():
        return PrivateRedis()

    monkeypatch.setattr(gate, "get_redis", private_redis)
    monkeypatch.setattr(gate, "_quota_until", 0)
    try:
        yield redis, prefix
    finally:
        keys = [key async for key in redis.scan_iter(match=prefix + "*")]
        assert all(key.startswith(prefix) for key in keys)
        if keys:
            await redis.delete(*keys)
        await redis.aclose()


def provider(error=None):
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        if error:
            raise error
        return SimpleNamespace(text="ok")

    return lambda: SimpleNamespace(models=SimpleNamespace(generate_content=generate)), calls


@pytest.mark.asyncio
async def test_quota_blocks_all_callers_for_24_hours_and_recovers(admission, monkeypatch):
    redis, prefix = admission
    factory, calls = provider(RuntimeError("429 RESOURCE_EXHAUSTED"))
    with pytest.raises(gate.GeminiDeferred):
        await gate.generate_content(factory, model=gate.MODEL)
    assert 86395 <= await gate.pause_seconds() <= 86400
    assert await redis.ttl(prefix + gate.KEYS[0]) >= 86395
    healthy, healthy_calls = provider()
    # A separate caller/client still uses the same Redis pause.
    for _ in range(5):
        with pytest.raises(gate.GeminiDeferred):
            await gate.generate_content(healthy, model=gate.MODEL)
    assert len(calls) == 1 and not healthy_calls
    # Simulate a backend restart: the local fallback is lost, shared pause remains.
    monkeypatch.setattr(gate, "_quota_until", 0)
    assert await gate.pause_seconds() >= 86395
    # Simulate TTL expiry without waiting a day.
    await redis.delete(prefix + gate.KEYS[0], prefix + gate.KEYS[3])
    assert (await gate.generate_content(healthy, model=gate.MODEL)).text == "ok"
    assert len(healthy_calls) == 1


@pytest.mark.asyncio
async def test_concurrent_requests_and_pacing_allow_one_provider_call(admission):
    redis, prefix = admission
    factory, calls = provider()
    results = await asyncio.gather(*(gate.generate_content(factory) for _ in range(20)), return_exceptions=True)
    assert len(calls) == 1
    assert sum(isinstance(r, gate.GeminiDeferred) for r in results) == 19
    assert 0 < await redis.pttl(prefix + gate.KEYS[3]) <= 13000
    with pytest.raises(gate.GeminiDeferred):
        await gate.generate_content(factory)
    await redis.delete(prefix + gate.KEYS[3])
    await gate.generate_content(factory)
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_temporary_failure_uses_bounded_backoff_not_day_pause(admission):
    redis, prefix = admission
    factory, calls = provider(RuntimeError("503 unavailable"))
    for expected in (60, 120, 240, 480, 900, 900):
        with pytest.raises(gate.GeminiDeferred):
            await gate.generate_content(factory)
        assert expected - 2 <= await gate.pause_seconds() <= expected
        assert not await redis.exists(prefix + gate.KEYS[0])
        count = len(calls)
        with pytest.raises(gate.GeminiDeferred):
            await gate.generate_content(factory)
        assert len(calls) == count
        await redis.delete(prefix + gate.KEYS[1], prefix + gate.KEYS[3])
    healthy, _ = provider()
    await gate.generate_content(healthy)
    assert not await redis.exists(prefix + gate.KEYS[4])


@pytest.mark.asyncio
async def test_redis_unavailable_never_calls_gemini(monkeypatch):
    async def unavailable():
        raise ConnectionError("Redis unavailable")
    monkeypatch.setattr(gate, "get_redis", unavailable)
    factory, calls = provider()
    assert await gate.pause_seconds() == 60
    with pytest.raises(gate.GeminiDeferred):
        await gate.generate_content(factory)
    assert not calls


@pytest.mark.asyncio
async def test_quota_write_failure_is_republished_on_redis_recovery(admission, monkeypatch):
    redis, prefix = admission
    real_redis = await gate.get_redis()

    class FailingFinish:
        async def eval(self, script, count, *args):
            if script == gate.FINISH:
                raise ConnectionError("Temporary write failure")
            return await real_redis.eval(script, count, *args)

    async def failing_redis():
        return FailingFinish()
    monkeypatch.setattr(gate, "get_redis", failing_redis)
    factory, calls = provider(RuntimeError("429 RESOURCE_EXHAUSTED"))
    with pytest.raises(gate.GeminiDeferred):
        await gate.generate_content(factory)
    assert not await redis.exists(prefix + gate.KEYS[0])
    assert await gate.pause_seconds() >= 86395
    assert await redis.exists(prefix + gate.KEYS[0])
    with pytest.raises(gate.GeminiDeferred):
        await gate.generate_content(factory)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_nlp_returns_pending_during_shared_quota_pause(admission, monkeypatch):
    factory, calls = provider(RuntimeError("429 RESOURCE_EXHAUSTED"))
    monkeypatch.setattr(nlp_service, "_get_client", factory)
    for review_id in (1, 2, 3):
        assert await nlp_service.analyse_review(review_id, "The WiFi is unreliable.") is None
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_summary_calls_respect_review_quota_pause(admission, monkeypatch):
    from app.services.insight_engine import generate_opinion
    factory, calls = provider(RuntimeError("429 RESOURCE_EXHAUSTED"))
    with pytest.raises(gate.GeminiDeferred):
        await gate.generate_content(factory)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-placeholder")
    def forbidden():
        pytest.fail("Summary client must not be constructed during quota cooldown")
    monkeypatch.setattr(gate, "create_client", forbidden)
    opinion = await generate_opinion("safety", "mostly_positive", None, None,
                                     mention_count=3, positive_rate=100, allow_ai=True)
    assert opinion and len(calls) == 1


@pytest.mark.asyncio
async def test_sweep_skips_database_and_provider_during_cooldown(admission, monkeypatch):
    import app.main as main
    factory, calls = provider(RuntimeError("429 RESOURCE_EXHAUSTED"))
    with pytest.raises(gate.GeminiDeferred):
        await gate.generate_content(factory)
    def forbidden():
        pytest.fail("Sweep should skip its database scan during cooldown")
    monkeypatch.setattr(main, "AsyncSessionLocal", forbidden)
    await main.sweep_stuck_reviews()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_sweep_stops_batch_after_first_quota_failure(admission, monkeypatch):
    import app.main as main
    from app.services import review_service
    factory, calls = provider(RuntimeError("429 RESOURCE_EXHAUSTED"))
    seen = []
    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def execute(self, query):
            sql = str(query)
            assert "ORDER BY reviews.created_at, reviews.id" in sql
            assert "reviews.deleted_at IS NULL" in sql
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [
                SimpleNamespace(id=1, body="First review"), SimpleNamespace(id=2, body="Second review")]))
    async def process(review_id, body):
        seen.append(review_id)
        try:
            await gate.generate_content(factory)
        except gate.GeminiDeferred:
            pass
    sleep = AsyncMock()
    monkeypatch.setattr(main, "AsyncSessionLocal", Session)
    monkeypatch.setattr(review_service, "process_review_nlp", process)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    await main.sweep_stuck_reviews()
    assert seen == [1] and len(calls) == 1
    sleep.assert_not_awaited()


def test_sdk_has_one_attempt_and_a_bounded_timeout(monkeypatch):
    options = []
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-placeholder")
    monkeypatch.setattr(gate.genai, "Client", lambda **kwargs: options.append(kwargs))
    gate.create_client()
    assert options[0]["http_options"].retry_options.attempts == 1
    assert options[0]["http_options"].timeout == 60000
