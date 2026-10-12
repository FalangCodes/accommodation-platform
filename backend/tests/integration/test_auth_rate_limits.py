"""Run on Azure: real Redis Lua in private namespaces; isolated SQLite auth data."""
import asyncio
import uuid

import httpx
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from fastapi import HTTPException
from starlette.requests import Request

from test_auth_email_flows import setup, create_user, STUDENT
from app.api.v1.routes import auth
from app.core.config import settings
from app.services import auth_rate_limit as limiter


def request(ip="198.51.100.1", forwarded=None):
    headers = [] if forwarded is None else [(b"x-forwarded-for", forwarded.encode())]
    return Request({"type": "http", "client": (ip, 1234), "headers": headers})


@pytest_asyncio.fixture
async def private_limits(setup, monkeypatch):
    prefix = "test_auth_limits_" + uuid.uuid4().hex + ":"
    redis = redis_async.from_url(settings.REDIS_URL, decode_responses=True)

    class PrivateRedis:
        async def eval(self, script, count, *args):
            return await redis.eval(script, count,
                                    *(prefix + key for key in args[:count]), *args[count:])

    async def isolated_redis():
        return PrivateRedis()

    monkeypatch.setattr(limiter, "get_redis", isolated_redis)
    monkeypatch.setattr(auth, "enforce_auth_limit", limiter.enforce_auth_limit)
    monkeypatch.setattr(settings, "AUTH_TRUSTED_PROXY_IPS", "")
    monkeypatch.setattr(settings, "MODERATOR_INVITE_KEY", "rate-limit-test-invite")
    try:
        yield redis, prefix, setup
    finally:
        keys = [key async for key in redis.scan_iter(match=prefix + "*")]
        assert all(key.startswith(prefix) for key in keys)
        if keys:
            await redis.delete(*keys)
        await redis.aclose()


@pytest.mark.asyncio
async def test_concurrent_account_budget_and_case_normalisation(private_limits):
    redis, prefix, _ = private_limits

    async def attempt(i):
        try:
            await limiter.enforce_auth_limit(request(f"198.51.100.{i+1}"), "login",
                                             " STUDENT@SPU.AC.ZA " if i % 2 else "student@spu.ac.za")
            return 200
        except HTTPException as error:
            assert error.status_code == 429 and 1 <= int(error.headers["Retry-After"]) <= 900
            return error.status_code

    results = await asyncio.gather(*(attempt(i) for i in range(20)))
    assert results.count(200) == 10 and results.count(429) == 10
    keys = [key async for key in redis.scan_iter(match=prefix + "*")]
    assert all("student" not in key and "198.51" not in key for key in keys)
    assert all([0 < await redis.ttl(key) <= 900 for key in keys])


@pytest.mark.asyncio
async def test_ip_budget_stops_address_rotation_and_expires(private_limits):
    redis, prefix, _ = private_limits
    for i in range(60):
        await limiter.enforce_auth_limit(request(), "login", f"student{i}@spu.ac.za")
    with pytest.raises(HTTPException) as error:
        await limiter.enforce_auth_limit(request(), "login", "new@spu.ac.za")
    assert error.value.status_code == 429
    key = prefix + "auth-limit:login:ip:" + limiter.identity_digest("198.51.100.1")
    await redis.pexpire(key, 1)
    await asyncio.sleep(0.02)
    await limiter.enforce_auth_limit(request(), "login", "new@spu.ac.za")
    await limiter.enforce_auth_limit(request("198.51.100.2"), "login", "other@spu.ac.za")


@pytest.mark.asyncio
async def test_real_login_unknown_and_known_accounts_have_same_budget(private_limits):
    _, _, (app, session, _) = private_limits
    create_user(session)
    for email in (STUDENT["email"], "unknown@spu.ac.za"):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(10):
                response = await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
                assert response.status_code == 401
            response = await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
            assert response.status_code == 429 and response.headers.get("retry-after")


@pytest.mark.asyncio
async def test_email_routes_share_budget_and_do_not_send_after_limit(private_limits):
    _, _, (app, session, emails) = private_limits
    create_user(session)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for i in range(5):
            path = "request-password-reset" if i % 2 == 0 else "resend-verification"
            assert (await client.post(f"/api/v1/auth/{path}", json={"email": STUDENT["email"]})).status_code == 200
        count = len(emails)
        response = await client.post("/api/v1/auth/request-password-reset", json={"email": STUDENT["email"]})
        assert response.status_code == 429 and len(emails) == count


@pytest.mark.asyncio
async def test_registration_variants_share_budget_before_side_effects(private_limits):
    _, _, (app, _, emails) = private_limits
    # Invalid moderator invitations consume the shared registration attempt budget.
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(3):
            response = await client.post("/api/v1/auth/register/moderator", json={
                "email": "moderator@example.test", "password": "TestPass123!", "invite_key": "invalid"})
            assert response.status_code == 403
        response = await client.post("/api/v1/auth/register/moderator", json={
            "email": "moderator@example.test", "password": "TestPass123!", "invite_key": "invalid"})
        assert response.status_code == 429 and not emails


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", ["registration", "email", "token", "refresh"])
async def test_each_policy_blocks_at_ip_budget(private_limits, policy):
    _, _, _ = private_limits
    window, budget, _ = limiter.POLICIES[policy]
    for _ in range(budget):
        await limiter.enforce_auth_limit(request(), policy)
    with pytest.raises(HTTPException) as error:
        await limiter.enforce_auth_limit(request(), policy)
    assert error.value.status_code == 429
    assert 0 < int(error.value.headers["Retry-After"]) <= window


@pytest.mark.asyncio
async def test_redis_outage_prevents_auth_work(private_limits, monkeypatch):
    _, _, (app, _, emails) = private_limits

    async def unavailable():
        raise RuntimeError("Deliberate outage containing private diagnostics")

    monkeypatch.setattr(limiter, "get_redis", unavailable)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/login", json=STUDENT)
        assert response.status_code == 503 and response.headers["retry-after"] == "60"
        assert "private diagnostics" not in response.text and not emails


def test_proxy_headers_require_trusted_peer_and_use_last_address(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_TRUSTED_PROXY_IPS", "172.18.0.1")
    assert limiter.client_ip(request("198.51.100.1", "203.0.113.9")) == "198.51.100.1"
    assert limiter.client_ip(request("172.18.0.1", "203.0.113.9, 198.51.100.2")) == "198.51.100.2"
    assert limiter.client_ip(request("172.18.0.1", "not-an-ip")) == "172.18.0.1"
    assert limiter.client_ip(request("::ffff:198.51.100.1")) == "198.51.100.1"
