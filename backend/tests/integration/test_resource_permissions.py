"""Isolated HTTP permission tests; blobs, Redis and production data are untouched.

Users, profiles and appeals use SQLite. Geometry/JSONB resources are scripted;
their equality predicates are evaluated, but PostGIS execution is not tested.
"""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
import operator

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql.elements import BinaryExpression
from sqlalchemy.sql.visitors import iterate

import app.db.models
from app.api.v1.routes import accommodations, appeals, reviews
from app.core.security import create_access_token
from app.db.base import get_db
from app.models.accommodation import Accommodation, AccommodationImage
from app.models.insight import AccommodationInsight
from app.models.landlord import Landlord
from app.models.moderation import Appeal, ModerationLog
from app.models.review import Review
from app.models.student import Student
from app.models.user import User


class Result:
    def __init__(self, rows):
        self.rows = rows

    def scalar_one_or_none(self):
        assert len(self.rows) <= 1
        return self.rows[0] if self.rows else None


@pytest.fixture
def resources(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool)
    for model in (User, Student, Landlord, ModerationLog, Appeal):
        model.__table__.create(engine)
    session = Session(engine, expire_on_commit=False)
    for i, role in enumerate(("landlord", "landlord", "student", "student", "admin", "moderator"), 1):
        session.add(User(id=i, email=f"user{i}@spu.ac.za", role=role, password_hash="unused",
                         is_active=True, email_verified_at=datetime.now(timezone.utc)))
    session.commit()
    session.add_all([Landlord(id=1, user_id=1, display_name="Owner"),
                     Landlord(id=2, user_id=2, display_name="Other owner"),
                     Student(id=1, user_id=3, university_id=1, verification_tier=1),
                     Student(id=2, user_id=4, university_id=1, verification_tier=1)])
    session.add_all([ModerationLog(id=1, moderator_id=6, action="suspend_listing", resource_type="accommodation", resource_id=1),
                     ModerationLog(id=2, moderator_id=6, action="remove_review", resource_type="review", resource_id=1),
                     ModerationLog(id=3, moderator_id=6, action="landlord_verification_rejected", resource_type="landlord", resource_id=1),
                     ModerationLog(id=4, moderator_id=6, action="suspend_listing", resource_type="accommodation", resource_id=2)])
    session.commit()
    listing = SimpleNamespace(id=1, landlord_id=1, status="pending", ownership_doc_url=None)
    scripted = {
        Accommodation: [listing, SimpleNamespace(id=2, landlord_id=2, status="approved")],
        AccommodationImage: [SimpleNamespace(id=1, accommodation_id=1, blob_url="mock://image1"),
                             SimpleNamespace(id=2, accommodation_id=2, blob_url="mock://image2")],
        Review: [SimpleNamespace(id=1, student_id=1), SimpleNamespace(id=2, student_id=2)],
        AccommodationInsight: [SimpleNamespace(accommodation_id=1, insights={"safety": {"summary": "Hidden insight"}},
                                                recommendations=[], review_count=1, generated_at=datetime.now(timezone.utc))],
    }
    cache = {"listing:1": {"id": 1, "title": "Hidden listing", "status": "approved"},
             "reviews:1": [{"id": 1, "body": "Hidden review"}],
             "analytics:1": {"total_views": 99}, "search:mock": {"cover_image": "mock://image1"},
             "featured:listings": [{"cover_image": "mock://image1"}]}
    effects = []

    class Database:
        def add(self, value):
            session.add(value)

        async def execute(self, statement):
            entity = statement.column_descriptions[0]["entity"]
            if entity not in scripted:
                return session.execute(statement)
            found = scripted[entity][:]
            for expression in statement._where_criteria:
                for condition in iterate(expression):
                    if isinstance(condition, BinaryExpression):
                        assert condition.operator is operator.eq
                        found = [row for row in found if getattr(row, condition.left.name) == condition.right.value]
            return Result(found)

        async def delete(self, value):
            scripted[AccommodationImage].remove(value)
            effects.append("database_delete")

        async def commit(self):
            session.commit()

        async def refresh(self, value):
            session.refresh(value)

    async def isolated_db():
        yield Database()

    async def get(key):
        effects.append(f"cache_read:{key}")
        return deepcopy(cache.get(key))

    async def remove(*keys):
        for key in keys:
            cache.pop(key, None)

    async def remove_pattern(pattern):
        assert pattern == "search:*"
        for key in list(cache):
            if key.startswith("search:"):
                del cache[key]

    async def delete_blob(url):
        effects.append(f"blob_delete:{url}")

    async def increment(accommodation_id):
        effects.append("view_increment")

    for module in (accommodations, reviews):
        monkeypatch.setattr(module, "cache_get", get)
    monkeypatch.setattr(accommodations, "cache_delete", remove)
    monkeypatch.setattr(accommodations, "cache_delete_pattern", remove_pattern)
    monkeypatch.setattr(accommodations, "delete_image", delete_blob)
    monkeypatch.setattr(accommodations, "increment_view", increment)
    application = FastAPI()
    for module in (accommodations, reviews, appeals):
        application.include_router(module.router, prefix="/api/v1")
    application.dependency_overrides[get_db] = isolated_db

    def headers(actor):
        ids = {"owner": 1, "other_landlord": 2, "student": 3, "other_student": 4, "admin": 5, "moderator": 6}
        return {} if actor == "guest" else {"Authorization": f"Bearer {create_access_token(str(ids[actor]))}"}

    yield application, headers, listing, cache, effects, session
    session.close()
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "rejected", "suspended", "removed"])
@pytest.mark.parametrize("actor", ["guest", "student", "other_landlord", "owner", "moderator", "admin"])
@pytest.mark.parametrize("path", ["accommodations/1", "reviews/accommodation/1", "accommodations/1/insights"])
async def test_hidden_listing_access_checks_precede_cache(resources, status, actor, path):
    app, headers, listing, cache, effects, _ = resources
    listing.status = status
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/{path}", headers=headers(actor))
    if actor in ("owner", "moderator", "admin"):
        assert response.status_code == 200
        if path == "accommodations/1":
            assert response.json()["status"] == status
    else:
        assert response.status_code in ((401, 403) if actor == "guest" and path.endswith("insights") else (404,))
        assert "Hidden" not in response.text
        assert not effects


@pytest.mark.asyncio
async def test_approved_listing_stays_public_then_becomes_hidden(resources):
    app, headers, listing, cache, effects, _ = resources
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        listing.status = "approved"
        for path in ("accommodations/1", "reviews/accommodation/1"):
            assert (await client.get(f"/api/v1/{path}")).status_code == 200
        listing.status = "suspended"
        for path in ("accommodations/1", "reviews/accommodation/1"):
            assert (await client.get(f"/api/v1/{path}")).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", ["guest", "student", "other_landlord"])
async def test_hidden_listing_cannot_receive_unauthorized_views(resources, actor):
    app, headers, _, _, effects, _ = resources
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/v1/accommodations/1/view", headers=headers(actor))).status_code == 404
    assert "view_increment" not in effects


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", ["other_landlord", "student", "admin", "moderator", "guest"])
async def test_image_delete_denied_without_blob_or_database_side_effects(resources, actor):
    app, headers, _, _, effects, _ = resources
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/api/v1/accommodations/1/images/1", headers=headers(actor))
        assert response.status_code in (401, 403)
    assert not effects


@pytest.mark.asyncio
async def test_owner_image_delete_rejects_wrong_parent_then_invalidates_caches(resources):
    app, headers, _, cache, effects, _ = resources
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        auth = headers("owner")
        assert (await client.delete("/api/v1/accommodations/1/images/2", headers=auth)).status_code == 404
        assert not effects
        assert (await client.delete("/api/v1/accommodations/1/images/1", headers=auth)).status_code == 200
    assert effects == ["blob_delete:mock://image1", "database_delete"]
    assert not any(key in cache for key in ("listing:1", "search:mock", "featured:listings"))


@pytest.mark.asyncio
async def test_analytics_cache_does_not_bypass_ownership(resources):
    app, headers, _, _, effects, _ = resources
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/v1/accommodations/1/analytics", headers=headers("other_landlord"))).status_code == 403
        assert not effects
        response = await client.get("/api/v1/accommodations/1/analytics", headers=headers("owner"))
        assert response.json()["total_views"] == 99


@pytest.mark.asyncio
@pytest.mark.parametrize("resource_type,actor,other,action", [("review", "student", "other_student", 2),
                                                           ("listing", "owner", "other_landlord", 1),
                                                           ("landlord", "owner", "other_landlord", 3)])
@pytest.mark.parametrize("explicit", [False, True])
async def test_appeal_requires_ownership_and_preserves_duplicate_check(resources, resource_type, actor, other, action, explicit):
    app, headers, _, _, _, session = resources
    body = {"resource_type": resource_type, "resource_id": 1, "reason": "Please reconsider this moderation decision."}
    if explicit:
        body["original_action_id"] = action
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/v1/appeals", json=body, headers=headers(other))).status_code == 404
        assert session.query(Appeal).count() == 0
        response = await client.post("/api/v1/appeals", json=body, headers=headers(actor))
        assert response.status_code == 201
        assert response.json()["original_action_id"] == action
        assert (await client.post("/api/v1/appeals", json=body, headers=headers(actor))).status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("action", [2, 4])
async def test_appeal_rejects_mismatched_action_type_or_resource(resources, action):
    app, headers, _, _, _, session = resources
    body = {"resource_type": "listing", "resource_id": 1, "original_action_id": action,
            "reason": "Please reconsider this moderation decision."}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/v1/appeals", json=body, headers=headers("owner"))).status_code == 422
    assert session.query(Appeal).count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("actor,kind", [("student", "listing"), ("student", "landlord"),
                                       ("owner", "review"), ("admin", "listing"), ("moderator", "review")])
async def test_appeal_rejects_wrong_role(resources, actor, kind):
    app, headers, _, _, _, session = resources
    body = {"resource_type": kind, "resource_id": 1, "reason": "Please reconsider this moderation decision."}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/v1/appeals", json=body, headers=headers(actor))).status_code == 403
    assert session.query(Appeal).count() == 0
