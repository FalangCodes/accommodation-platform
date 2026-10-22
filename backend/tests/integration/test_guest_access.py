"""HTTP access checks with isolated users, scripted discovery rows and in-memory cache.

Run on Azure alongside the auth tests. These do not touch live listings or Redis,
and do not exercise PostgreSQL/PostGIS query execution.
"""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.db.models
from app.api.v1.routes import accommodations, reviews
from app.core.security import create_access_token, create_refresh_token
from app.db.base import get_db
from app.models.user import User
from app.models.accommodation import Accommodation
from app.models.review import Review, ReviewNLPResult, ReviewReply
from app.models.student import Student
from app.models.insight import AccommodationInsight


class Result:
    def __init__(self, rows=(), value=None):
        self.rows, self.value = list(rows), value

    def scalar(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def mappings(self):
        return self

    def all(self):
        return self.rows


@pytest.fixture
def discovery(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool)
    User.__table__.create(engine)
    session = Session(engine, expire_on_commit=False)
    rows = [{"id": i, "title": f"Listing {i}", "address": f"Address {i}"} for i in range(1, 13)]
    review_rows = [SimpleNamespace(id=i, student_id=1, accommodation_id=1, rating=4,
                                  body=f"Review secret {i}", status="analysed",
                                  created_at=datetime.now(timezone.utc)) for i in range(1, 6)]
    cache, search_calls = {}, []

    class Database:
        async def execute(self, statement, params=None):
            entities = [d.get("entity") for d in getattr(statement, "column_descriptions", [])]
            if User in entities:
                return session.execute(statement)
            if Accommodation in entities:
                return Result(value=SimpleNamespace(id=1, status="approved", landlord_id=1))
            if Review in entities:
                return Result(review_rows)
            if any(entity in entities for entity in (ReviewNLPResult, ReviewReply, Student)):
                return Result()
            if AccommodationInsight in entities:
                return Result(value=SimpleNamespace(insights={"safety": {"summary": "Private insight", "publication_policy_version": 2}},
                                                   recommendations=["Private recommendation"], review_count=5,
                                                   generated_at=datetime.now(timezone.utc)))
            if str(statement).strip().upper().startswith("SELECT COUNT(*) FROM ("):
                return Result(value=len(rows))
            search_calls.append(dict(params))
            return Result(rows[params["offset"]:params["offset"] + params["limit"]])

    async def isolated_db():
        yield Database()

    async def get(key):
        return deepcopy(cache.get(key))

    async def put(key, value, ttl):
        cache[key] = deepcopy(value)

    for module in (accommodations, reviews):
        monkeypatch.setattr(module, "cache_get", get)
        monkeypatch.setattr(module, "cache_set", put)
    application = FastAPI()
    application.include_router(accommodations.router, prefix="/api/v1")
    application.include_router(reviews.router, prefix="/api/v1")
    application.dependency_overrides[get_db] = isolated_db

    def headers(role="student", active=True, verified=True, version=0, token_version=0):
        user = User(email=f"user-{len(session.new)}-{session.query(User).count()}@spu.ac.za",
                    password_hash="unused", role=role, is_active=active, token_version=version,
                    email_verified_at=datetime.now(timezone.utc) if verified else None)
        session.add(user)
        session.commit()
        return {"Authorization": f"Bearer {create_access_token(str(user.id), token_version=token_version)}"}

    yield application, headers, cache, search_calls
    session.close()
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["student", "landlord", "moderator", "admin"])
@pytest.mark.parametrize("warm", [False, True])
async def test_guest_search_cannot_receive_cached_full_results(discovery, role, warm):
    app, headers, cache, calls = discovery
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        if warm:
            full = await client.get("/api/v1/accommodations/search", headers=headers(role))
            assert len(full.json()["items"]) == 10
        response = await client.get("/api/v1/accommodations/search?page_size=50")
        data = response.json()
        assert response.status_code == 200
        assert len(data["items"]) == 7
        assert data["locked_count"] == 3
        assert data["page_size"] == 10
        assert all(item["id"] <= 7 for item in data["items"])
        assert "Listing 8" not in response.text
        assert (await client.get("/api/v1/accommodations/search?page=2")).status_code == 401
        full = await client.get("/api/v1/accommodations/search?page=2&page_size=10", headers=headers(role))
        assert [item["id"] for item in full.json()["items"]] == [11, 12]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["student", "landlord", "moderator", "admin"])
@pytest.mark.parametrize("warm", [False, True])
async def test_guest_reviews_cannot_receive_cached_full_content(discovery, role, warm):
    app, headers, cache, calls = discovery
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        auth = headers(role)
        if warm:
            assert len((await client.get("/api/v1/reviews/accommodation/1", headers=auth)).json()["items"]) == 5
        response = await client.get("/api/v1/reviews/accommodation/1")
        assert response.json()["total"] == 5
        assert response.json()["locked_count"] == 3
        assert len(response.json()["items"]) == 2
        assert "Review secret 3" not in response.text
        full = await client.get("/api/v1/reviews/accommodation/1", headers=auth)
        assert len(full.json()["items"]) == 5
        assert full.json()["locked_count"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["student", "landlord", "moderator", "admin"])
async def test_detailed_insights_require_authenticated_account(discovery, role):
    app, headers, _, _ = discovery
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        guest = await client.get("/api/v1/accommodations/1/insights")
        assert guest.status_code in (401, 403)
        assert "Private insight" not in guest.text
        response = await client.get("/api/v1/accommodations/1/insights", headers=headers(role))
        assert response.status_code == 200
        assert "Private insight" in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("options", [{"active": False}, {"verified": False}, {"version": 1}])
async def test_ineligible_sessions_only_receive_guest_previews(discovery, options):
    app, headers, _, _ = discovery
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        auth = headers(**options)
        assert len((await client.get("/api/v1/accommodations/search", headers=auth)).json()["items"]) == 7
        assert len((await client.get("/api/v1/reviews/accommodation/1", headers=auth)).json()["items"]) == 2
        assert (await client.get("/api/v1/accommodations/search?page=2", headers=auth)).status_code == 401
        assert (await client.get("/api/v1/accommodations/1/insights", headers=auth)).status_code in (401, 403)


@pytest.mark.asyncio
async def test_search_cache_distinguishes_page_size_and_filters(discovery):
    app, headers, cache, calls = discovery
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        auth = headers()
        first = await client.get("/api/v1/accommodations/search?page_size=2", headers=auth)
        second = await client.get("/api/v1/accommodations/search?page_size=10", headers=auth)
        assert len(first.json()["items"]) == 2
        assert len(second.json()["items"]) == 10
        await client.get("/api/v1/accommodations/search?gender_policy=female&funding_type=bursary", headers=auth)
        assert len(cache) == 3
        assert calls[-1]["gender_policy"] == "female"
        assert calls[-1]["funding_type"] == "bursary"


@pytest.mark.asyncio
async def test_invalid_and_refresh_tokens_do_not_unlock_previews(discovery):
    app, _, _, _ = discovery
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for token in ("invalid", create_refresh_token("1")):
            auth = {"Authorization": f"Bearer {token}"}
            response = await client.get("/api/v1/reviews/accommodation/1", headers=auth)
            assert len(response.json()["items"]) == 2
            assert (await client.get("/api/v1/accommodations/1/insights", headers=auth)).status_code == 401


@pytest.mark.asyncio
async def test_empty_cached_reviews_have_the_same_response_shape(discovery):
    app, headers, cache, _ = discovery
    cache["reviews:1"] = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for auth in ({}, headers()):
            response = await client.get("/api/v1/reviews/accommodation/1", headers=auth)
            assert response.json() == {"items": [], "total": 0, "locked_count": 0}
