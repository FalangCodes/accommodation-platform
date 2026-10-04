"""Azure-only PostgreSQL/Redis checks with isolated schemas/keys and mocked SMTP."""
import asyncio
import re
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from sqlalchemy import select, func

from test_review_resubmission import isolated_reviews, historical_review
from app.api.v1.routes import enquiries
from app.core.config import settings
from app.core.security import create_access_token
from app.models.accommodation import Accommodation
from app.models.student import Student
from app.models.landlord import Landlord
from app.models.user import User
from app.models.moderation import ModerationLog
from app.models.review import ReviewReply
from app.services import enquiry_service, email_service


def headers(user_id, request_id=None):
    result = {"Authorization": "Bearer " + create_access_token(str(user_id))}
    if request_id:
        result["Idempotency-Key"] = str(request_id)
    return result


BODY = {"message": "Is this property available for the next academic term?", "consent": True}


@pytest_asyncio.fixture
async def enquiries_app(isolated_reviews, monkeypatch):
    client, sessions, _, _, effects = isolated_reviews
    client._transport.app.include_router(enquiries.router, prefix="/api/v1")
    async with sessions() as db:
        db.add_all([
            User(id=4, email="other-owner@example.test", role="landlord", is_active=True, password_hash="unused"),
            User(id=5, email="unverified@spu.ac.za", role="student", is_active=True, password_hash="unused"),
            User(id=6, email="inactive@spu.ac.za", role="student", is_active=False,
                 email_verified_at=datetime.now(timezone.utc), password_hash="unused"),
            User(id=7, email="moderator@example.test", role="moderator", is_active=True, password_hash="unused"),
        ])
        await db.flush()
        db.add(Landlord(id=2, user_id=4, display_name="Other landlord"))
        student = await db.get(Student, 1)
        student.first_name, student.last_name = "Test", "Student"
        await db.commit()

    # All Lua keys are rewritten into a private test namespace; never use production keys.
    prefix = "test_gap8_" + uuid.uuid4().hex + ":"
    assert re.fullmatch(r"test_gap8_[0-9a-f]{32}:", prefix)
    redis = redis_async.from_url(settings.REDIS_URL, decode_responses=True)

    class IsolatedRedis:
        async def eval(self, script, number_of_keys, *args):
            keys = [prefix + key for key in args[:number_of_keys]]
            assert all(key.startswith(prefix) for key in keys)
            return await redis.eval(script, number_of_keys, *keys, *args[number_of_keys:])

    async def isolated_redis():
        return IsolatedRedis()

    sent = []
    async def capture(recipient, subject, body, *, reply_to=None):
        sent.append({"recipient": recipient, "subject": subject, "body": body, "reply_to": reply_to})
        await asyncio.sleep(0.05)

    monkeypatch.setattr(enquiry_service, "get_redis", isolated_redis)
    monkeypatch.setattr(enquiries, "send_email", capture)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example.test")
    try:
        yield client, sessions, sent, redis, prefix, effects
    finally:
        keys = [key async for key in redis.scan_iter(match=prefix + "*")]
        assert all(key.startswith(prefix) for key in keys)
        if keys:
            await redis.delete(*keys)
        await redis.aclose()


async def send(client, actor=1, request_id=None, body=None, listing_id=1):
    request_id = request_id or uuid.uuid4()
    return await client.post(f"/api/v1/accommodations/{listing_id}/enquiries",
                             headers=headers(actor, request_id), json=body or BODY)


@pytest.mark.asyncio
async def test_private_recipient_verified_reply_to_and_consent(enquiries_app):
    client, _, sent, redis, prefix, _ = enquiries_app
    request_id = uuid.uuid4()
    response = await send(client, request_id=request_id)
    assert response.status_code == 200
    assert len(sent) == 1
    assert sent[0]["recipient"] == "owner@example.test"
    assert sent[0]["reply_to"] == "test@spu.ac.za"
    assert "Test Student" in sent[0]["body"] and "test@spu.ac.za" in sent[0]["body"]
    assert BODY["message"] in sent[0]["body"] and "https://frontend.example.test/listings/1" in sent[0]["body"]
    assert "owner@example.test" not in response.text
    stored = await redis.get(prefix + f"enquiry:request:1:{request_id}")
    assert stored.endswith(":sent") and BODY["message"] not in stored and "@" not in stored
    assert 0 < await redis.ttl(prefix + "enquiry:hour:1") <= 3600
    assert 0 < await redis.ttl(prefix + "enquiry:cooldown:1:1") <= 60


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", [2, 3, 4, 5, 6, 7])
async def test_only_verified_active_students_can_enquire(enquiries_app, actor):
    client, _, sent, _, _, _ = enquiries_app
    assert (await send(client, actor=actor)).status_code == 403
    assert not sent


@pytest.mark.asyncio
async def test_guest_cannot_enquire(enquiries_app):
    client, _, sent, _, _, _ = enquiries_app
    assert (await client.post("/api/v1/accommodations/1/enquiries", json=BODY,
                              headers={"Idempotency-Key": str(uuid.uuid4())})).status_code == 401
    assert not sent


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [
    {"message": "short", "consent": True}, {"message": " " * 30, "consent": True},
    {"message": "x" * 3001, "consent": True}, {"message": BODY["message"], "consent": False},
    {"message": BODY["message"]}, {**BODY, "recipient": "attacker@example.test"},
    {**BODY, "reply_to": "attacker@example.test"},
])
async def test_invalid_or_forged_enquiries_send_nothing(enquiries_app, body):
    client, _, sent, _, _, _ = enquiries_app
    assert (await send(client, body=body)).status_code == 422
    assert not sent


@pytest.mark.asyncio
async def test_idempotency_header_is_required_and_validated(enquiries_app):
    client, _, sent, _, _, _ = enquiries_app
    assert (await client.post("/api/v1/accommodations/1/enquiries", json=BODY, headers=headers(1))).status_code == 422
    assert (await send(client, request_id="invalid")).status_code == 422
    assert not sent


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "rejected", "suspended", "removed"])
async def test_non_public_listings_cannot_receive_student_enquiries(enquiries_app, status):
    client, sessions, sent, _, _, _ = enquiries_app
    async with sessions() as db:
        (await db.get(Accommodation, 1)).status = status
        await db.commit()
    assert (await send(client)).status_code == 404
    assert not sent


@pytest.mark.asyncio
async def test_missing_listing_or_inactive_owner_does_not_send(enquiries_app):
    client, sessions, sent, _, _, _ = enquiries_app
    assert (await send(client, listing_id=999)).status_code == 404
    async with sessions() as db:
        (await db.get(User, 3)).is_active = False
        await db.commit()
    assert (await send(client)).status_code == 409
    assert not sent


@pytest.mark.asyncio
async def test_concurrent_retries_send_once_and_replay_success(enquiries_app):
    client, _, sent, _, _, _ = enquiries_app
    request_id = uuid.uuid4()
    results = await asyncio.gather(*[send(client, request_id=request_id) for _ in range(3)])
    assert sum(result.status_code == 200 for result in results) >= 1
    assert all(result.status_code in (200, 409) for result in results)
    assert len(sent) == 1
    assert (await send(client, request_id=request_id)).status_code == 200
    assert len(sent) == 1
    changed = await send(client, request_id=request_id, body={**BODY, "message": BODY["message"] + " Another question."})
    assert changed.status_code == 409 and len(sent) == 1


@pytest.mark.asyncio
async def test_cooldown_and_hourly_limit_are_enforced_by_real_redis(enquiries_app):
    client, _, sent, redis, prefix, _ = enquiries_app
    assert (await send(client)).status_code == 200
    limited = await send(client)
    assert limited.status_code == 429 and int(limited.headers["Retry-After"]) > 0
    for _ in range(4):
        # Simulate expiry only in this fixture's private Redis namespace.
        await redis.delete(prefix + "enquiry:cooldown:1:1")
        assert (await send(client)).status_code == 200
    await redis.delete(prefix + "enquiry:cooldown:1:1")
    limited = await send(client)
    assert limited.status_code == 429 and int(limited.headers["Retry-After"]) > 60
    assert len(sent) == 5


@pytest.mark.asyncio
async def test_smtp_failure_is_private_and_not_retried_automatically(enquiries_app, monkeypatch):
    client, _, sent, _, _, _ = enquiries_app
    async def fail(*args, **kwargs):
        sent.append("attempt")
        raise RuntimeError("Private SMTP diagnostics owner@example.test")
    monkeypatch.setattr(enquiries, "send_email", fail)
    request_id = uuid.uuid4()
    result = await send(client, request_id=request_id)
    assert result.status_code == 503 and "owner@example.test" not in result.text
    assert (await send(client, request_id=request_id)).status_code == 503
    assert len(sent) == 1
    assert (await send(client)).status_code == 429


@pytest.mark.asyncio
async def test_redis_outage_fails_closed_before_sending(enquiries_app, monkeypatch):
    client, _, sent, _, _, _ = enquiries_app
    async def fail():
        raise ConnectionError("Redis unavailable")
    monkeypatch.setattr(enquiry_service, "get_redis", fail)
    assert (await send(client)).status_code == 503
    assert not sent


@pytest.mark.asyncio
async def test_smtp_from_and_reply_to_headers_are_correct(enquiries_app, monkeypatch):
    client, _, _, _, _, _ = enquiries_app
    captured = []
    class SMTP:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def starttls(self, **kwargs): pass
        def login(self, *args): pass
        def send_message(self, message): captured.append(message)
    for name, value in {"SMTP_HOST": "smtp.example.test", "SMTP_FROM": "sender@example.test",
                        "SMTP_USERNAME": "sender@example.test", "SMTP_PASSWORD": "test-only",
                        "SMTP_SSL": False, "SMTP_STARTTLS": True}.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(email_service.smtplib, "SMTP", SMTP)
    monkeypatch.setattr(enquiries, "send_email", email_service.send_email)
    assert (await send(client)).status_code == 200
    assert captured[0]["From"] == "sender@example.test"
    assert captured[0]["To"] == "owner@example.test"
    assert captured[0]["Reply-To"] == "test@spu.ac.za"


@pytest.mark.asyncio
async def test_own_moderation_total_and_pagination_include_all_personal_actions(enquiries_app):
    client, sessions, _, _, _, _ = enquiries_app
    async with sessions() as db:
        db.add_all([ModerationLog(moderator_id=7 if i < 25 else 2, action="approve_listing",
                                  resource_type="accommodation", resource_id=1) for i in range(30)])
        await db.commit()
    first = await client.get("/api/v1/moderation/log?mine=true&page_size=10", headers=headers(7))
    second = await client.get("/api/v1/moderation/log?mine=true&page_size=10&page=2", headers=headers(7))
    assert first.status_code == second.status_code == 200
    assert first.json()["total"] == second.json()["total"] == 25
    assert len(first.json()["items"]) == len(second.json()["items"]) == 10
    assert all(item["moderator_id"] == 7 for item in first.json()["items"] + second.json()["items"])
    assert {item["id"] for item in first.json()["items"]}.isdisjoint(item["id"] for item in second.json()["items"])
    own_admin = await client.get("/api/v1/moderation/log?mine=true", headers=headers(2))
    assert own_admin.json()["total"] == 5
    all_logs = await client.get("/api/v1/moderation/log", headers=headers(2))
    assert all_logs.json()["total"] == 30
    assert (await client.get("/api/v1/moderation/log?mine=true", headers=headers(1))).status_code == 403


@pytest.mark.asyncio
async def test_concurrent_owner_replies_create_one_and_invalidate_reviews(enquiries_app):
    client, sessions, _, _, _, effects = enquiries_app
    review_id = await historical_review(sessions, deleted=False)
    response = await client.post(f"/api/v1/reviews/{review_id}/reply", headers=headers(4), json={"body": "Other owner's reply"})
    assert response.status_code == 403
    responses = await asyncio.gather(*[client.post(f"/api/v1/reviews/{review_id}/reply", headers=headers(3),
                                                   json={"body": "Thank you for sharing your experience."}) for _ in range(2)])
    assert sorted(response.status_code for response in responses) == [201, 409]
    async with sessions() as db:
        assert (await db.execute(select(func.count(ReviewReply.id)))).scalar() == 1
    assert any("reviews:1" in args for _, args in effects)
    public = await client.get("/api/v1/reviews/accommodation/1", headers=headers(1))
    assert public.status_code == 200
    assert public.json()["items"][0]["reply"]["body"] == "Thank you for sharing your experience."


@pytest.mark.asyncio
@pytest.mark.parametrize("status,deleted,expected", [("pending_analysis", False, 409), ("quarantined", False, 409),
                                                   ("analysed", True, 404), ("released", False, 201)])
async def test_reply_requires_published_non_deleted_review(enquiries_app, status, deleted, expected):
    client, sessions, _, _, _, _ = enquiries_app
    review_id = await historical_review(sessions, status=status, deleted=deleted)
    result = await client.post(f"/api/v1/reviews/{review_id}/reply", headers=headers(3), json={"body": "A meaningful landlord response."})
    assert result.status_code == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [" " * 20, "short", "x" * 3001])
async def test_invalid_replies_are_rejected(enquiries_app, body):
    client, sessions, _, _, _, _ = enquiries_app
    review_id = await historical_review(sessions, deleted=False)
    assert (await client.post(f"/api/v1/reviews/{review_id}/reply", headers=headers(3), json={"body": body})).status_code == 422
