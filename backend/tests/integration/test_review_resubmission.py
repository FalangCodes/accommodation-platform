"""Real PostgreSQL review/concurrency checks in a disposable, isolated schema.

Run only on Azure. No live rows, blobs, mail, Redis or NLP services are touched.
"""
import asyncio
import re
import uuid
import importlib.util
from pathlib import Path
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select, text, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from alembic.migration import MigrationContext
from alembic.operations import Operations

import app.db.models
from app.db.base import Base, get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.api.v1.routes import reviews, moderation
from app.models.user import User
from app.models.student import Student
from app.models.landlord import Landlord
from app.models.university import University
from app.models.accommodation import Accommodation
from app.models.review import Review, ReviewNLPResult, ReviewReply
from app.models.moderation import Appeal, ModerationLog
from app.services import review_policy

BODY = {"accommodation_id": 1, "rating": 4, "body": "This is a new review with enough meaningful text for submission."}


@pytest_asyncio.fixture
async def isolated_reviews(monkeypatch):
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://"), "Run these PostgreSQL tests on Azure"
    schema = "test_gap6_" + uuid.uuid4().hex
    assert re.fullmatch(r"test_gap6_[0-9a-f]{32}", schema)
    admin_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool,
                                 connect_args={"server_settings": {"search_path": f"{schema},public"}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            assert (await connection.execute(text("SELECT current_schema()"))).scalar() == schema
            await connection.run_sync(lambda sync: Base.metadata.create_all(sync, checkfirst=False))
        async with sessions() as db:
            db.add_all([User(id=1, email="test@spu.ac.za", role="student", is_active=True,
                             email_verified_at=datetime.now(timezone.utc), password_hash="unused"),
                        User(id=2, email="admin@example.test", role="admin", is_active=True, password_hash="unused"),
                        User(id=3, email="owner@example.test", role="landlord", is_active=True, password_hash="unused"),
                        University(id=1, name="Test university", domain="spu.ac.za", province="Test",
                                   campus_location="SRID=4326;POINT(24.75 -28.75)")])
            await db.flush()
            db.add_all([Student(id=1, user_id=1, university_id=1, verification_tier=1),
                        Landlord(id=1, user_id=3, display_name="Test owner")])
            await db.flush()
            db.add(Accommodation(id=1, landlord_id=1, title="Test listing", description="Test description",
                                 address="Test address", location="SRID=4326;POINT(24.75 -28.75)",
                                 price_min=1000, price_max=1500, status="approved"))
            # Explicit seed IDs do not advance PostgreSQL's sequence. Allow
            # subsequent automatic users, including the audit actor, to insert.
            await db.execute(text("SELECT setval(pg_get_serial_sequence('users','id'), (SELECT max(id) FROM users))"))
            await db.commit()
        effects = []

        async def no_cache(*args):
            effects.append(("cache", args))

        async def cache_miss(*args):
            return None

        async def no_nlp(*args):
            effects.append(("nlp", args))

        for module in (reviews, moderation):
            monkeypatch.setattr(module, "cache_delete", no_cache)
            monkeypatch.setattr(module, "cache_delete_pattern", no_cache)
        monkeypatch.setattr(reviews, "cache_get", cache_miss)
        monkeypatch.setattr(reviews, "cache_set", no_cache)
        monkeypatch.setattr(reviews, "process_review_nlp", no_nlp)
        application = FastAPI()
        application.include_router(reviews.router, prefix="/api/v1")
        application.include_router(moderation.router, prefix="/api/v1")

        async def isolated_db():
            async with sessions() as db:
                yield db

        application.dependency_overrides[get_db] = isolated_db
        headers = {"Authorization": f"Bearer {create_access_token('1')}"}
        mod_headers = {"Authorization": f"Bearer {create_access_token('2')}"}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url="http://test") as client:
            yield client, sessions, headers, mod_headers, effects
    finally:
        await engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin_engine.dispose()


async def historical_review(sessions, deadline=None, deleted=True, status="analysed"):
    async with sessions() as db:
        row = Review(student_id=1, accommodation_id=1, rating=2, body="Original review retained for history.",
                     status=status, deleted_at=datetime.now(timezone.utc) if deleted else None,
                     deleted_by=2 if deleted else None,
                     cooldown_expires_at=deadline)
        db.add(row)
        await db.commit()
        return row.id


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["analysed", "released", "pending_analysis", "quarantined"])
async def test_any_non_deleted_review_blocks_new_submission(isolated_reviews, status):
    client, sessions, headers, _, effects = isolated_reviews
    await historical_review(sessions, deleted=False, status=status)
    eligibility = await client.get("/api/v1/reviews/eligibility/1", headers=headers)
    assert eligibility.json()["code"] == "active_review"
    assert eligibility.json()["can_review"] is False
    response = await client.post("/api/v1/reviews", json=BODY, headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "active_review"
    assert not effects


@pytest.mark.asyncio
async def test_student_deletion_starts_cooldown_and_exact_boundary_allows_new_row(isolated_reviews, monkeypatch):
    client, sessions, headers, _, _ = isolated_reviews
    old_id = await historical_review(sessions, deleted=False)
    assert (await client.delete(f"/api/v1/reviews/{old_id}", headers=headers)).status_code == 204
    async with sessions() as db:
        old = await db.get(Review, old_id)
        assert old.cooldown_expires_at - old.deleted_at == timedelta(days=14)
        deadline = old.cooldown_expires_at
    monkeypatch.setattr(review_policy, "now", lambda: deadline - timedelta(microseconds=1))
    blocked = await client.post("/api/v1/reviews", json=BODY, headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "cooldown"
    monkeypatch.setattr(review_policy, "now", lambda: deadline)
    accepted = await client.post("/api/v1/reviews", json=BODY, headers=headers)
    assert accepted.status_code == 201
    assert accepted.json()["id"] != old_id
    async with sessions() as db:
        assert (await db.get(Review, old_id)).body == "Original review retained for history."
        assert (await db.execute(select(func.count(Review.id)))).scalar() == 2


@pytest.mark.asyncio
async def test_multiple_deleted_rows_use_latest_cooldown(isolated_reviews):
    client, sessions, headers, _, _ = isolated_reviews
    await historical_review(sessions, deadline=datetime.now(timezone.utc) - timedelta(days=1))
    deadline = datetime.now(timezone.utc) + timedelta(days=2)
    await historical_review(sessions, deadline=deadline)
    eligibility = (await client.get("/api/v1/reviews/eligibility/1", headers=headers)).json()
    assert eligibility["code"] == "cooldown"
    assert datetime.fromisoformat(eligibility["available_at"]) == deadline


@pytest.mark.asyncio
async def test_history_keeps_reply_analysis_and_only_new_review_is_public(isolated_reviews):
    client, sessions, headers, _, _ = isolated_reviews
    old_id = await historical_review(sessions, deadline=datetime.now(timezone.utc) - timedelta(days=1))
    async with sessions() as db:
        db.add_all([ReviewReply(review_id=old_id, landlord_id=1, body="Original landlord reply"),
                    ReviewNLPResult(review_id=old_id, sentiment="negative", sentiment_score=0.2,
                                    aspects={}, spam_flag=False)])
        await db.commit()
    response = await client.post("/api/v1/reviews", json=BODY, headers=headers)
    assert response.status_code == 201
    new_id = response.json()["id"]
    async with sessions() as db:
        new = await db.get(Review, new_id)
        new.status = "analysed"
        await db.commit()
        assert (await db.execute(select(ReviewReply.review_id))).scalar() == old_id
        assert (await db.execute(select(ReviewNLPResult.review_id))).scalar() == old_id
    public = (await client.get("/api/v1/reviews/accommodation/1")).json()
    assert [row["id"] for row in public["items"]] == [new_id]
    assert public["total"] == 1
    assert (await client.post("/api/v1/reviews", json=BODY, headers=headers)).status_code == 409


@pytest.mark.asyncio
async def test_concurrent_api_submissions_create_exactly_one_review(isolated_reviews):
    client, sessions, headers, _, effects = isolated_reviews
    responses = await asyncio.gather(*(client.post("/api/v1/reviews", json=BODY, headers=headers) for _ in range(2)))
    assert sorted(response.status_code for response in responses) == [201, 409]
    async with sessions() as db:
        assert (await db.execute(select(func.count(Review.id)).where(Review.deleted_at.is_(None)))).scalar() == 1
    assert len([effect for effect in effects if effect[0] == "nlp"]) == 1


@pytest.mark.asyncio
async def test_database_constraint_independently_rejects_second_active_row(isolated_reviews):
    _, sessions, _, _, _ = isolated_reviews
    await historical_review(sessions, deleted=False)
    async with sessions() as db:
        db.add(Review(student_id=1, accommodation_id=1, rating=4, body="Second active review"))
        with pytest.raises(IntegrityError) as failure:
            await db.commit()
        assert review_policy.is_active_review_conflict(failure.value)
        await db.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("new_active", [False, True])
async def test_appeal_restoration_preserves_one_active_review(isolated_reviews, new_active):
    client, sessions, _, mod_headers, _ = isolated_reviews
    old_id = await historical_review(sessions)
    if new_active:
        await historical_review(sessions, deleted=False)
    async with sessions() as db:
        log = ModerationLog(moderator_id=2, action="remove_review", resource_type="review", resource_id=old_id)
        db.add(log)
        await db.flush()
        appeal = Appeal(appellant_id=1, appellant_role="student", resource_type="review", resource_id=old_id,
                        original_action_id=log.id, reason="Please reconsider this review removal", status="pending")
        db.add(appeal)
        await db.commit()
        appeal_id = appeal.id
    response = await client.patch(f"/api/v1/moderation/appeals/{appeal_id}/resolve", headers=mod_headers,
                                  json={"decision": "upheld", "reason": "Test decision"})
    assert response.status_code == (409 if new_active else 200)
    async with sessions() as db:
        assert (await db.execute(select(func.count(Review.id)).where(Review.deleted_at.is_(None)))).scalar() == 1
        assert (await db.get(Appeal, appeal_id)).status == ("pending" if new_active else "upheld")


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_constraint", [True, False])
async def test_actual_migration_changes_only_the_constraint_and_preserves_history(isolated_reviews, existing_constraint):
    _, sessions, _, _, _ = isolated_reviews
    path = Path(__file__).resolve().parents[2] / "alembic/versions/c3f6a9b2d5e8_allow_deleted_review_history.py"
    spec = importlib.util.spec_from_file_location("gap6_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    async with sessions() as db:
        connection = await db.connection()
        def run_migration(sync):
            if existing_constraint:
                sync.execute(text("DROP INDEX uix_student_accommodation_review"))
                sync.execute(text("ALTER TABLE reviews ADD CONSTRAINT uix_student_accommodation_review UNIQUE (student_id, accommodation_id)"))
            with Operations.context(MigrationContext.configure(sync)):
                module.upgrade()
        await connection.run_sync(run_migration)
        await db.commit()
    await historical_review(sessions)
    await historical_review(sessions, deleted=False)
    async with sessions() as db:
        connection = await db.connection()
        def refuse_destructive_downgrade(sync):
            with Operations.context(MigrationContext.configure(sync)):
                with pytest.raises(RuntimeError):
                    module.downgrade()
        await connection.run_sync(refuse_destructive_downgrade)
        assert (await db.execute(select(func.count(Review.id)))).scalar() == 2


@pytest.mark.asyncio
async def test_concurrent_submission_and_appeal_restoration_create_one_active_review(isolated_reviews):
    client, sessions, headers, mod_headers, _ = isolated_reviews
    old_id = await historical_review(sessions)
    async with sessions() as db:
        log = ModerationLog(moderator_id=2, action="remove_review", resource_type="review", resource_id=old_id)
        db.add(log)
        await db.flush()
        appeal = Appeal(appellant_id=1, appellant_role="student", resource_type="review", resource_id=old_id,
                        original_action_id=log.id, reason="Please reconsider this review removal", status="pending")
        db.add(appeal)
        await db.commit()
        appeal_id = appeal.id
    responses = await asyncio.gather(
        client.post("/api/v1/reviews", json=BODY, headers=headers),
        client.patch(f"/api/v1/moderation/appeals/{appeal_id}/resolve", headers=mod_headers, json={"decision": "upheld"}),
    )
    assert sorted(response.status_code for response in responses) in ([200, 409], [201, 409])
    async with sessions() as db:
        assert (await db.execute(select(func.count(Review.id)).where(Review.deleted_at.is_(None)))).scalar() == 1
