"""Azure-only demo-seed regression checks in disposable PostgreSQL schemas."""
import asyncio
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, text
from test_review_resubmission import isolated_reviews, historical_review
from app.db import seed as demo
from app.core.security import verify_password
from app.core.config import Settings
from app.core.dependencies import ensure_account_access
from app.schemas.auth import LoginRequest
from app.models.user import User
from app.models.student import Student
from app.models.landlord import Landlord
from app.models.university import University
from app.models.accommodation import Accommodation
from app.models.review import Review, ReviewNLPResult
from app.services import gemini_gateway, nlp_service, email_service

PASSWORD = "Demo-test-password-2026"


def test_old_env_files_can_still_supply_the_retired_nlp_setting():
    settings = Settings(_env_file=None, NLP_SERVICE_URL="http://retired-service.invalid")
    assert settings.NLP_SERVICE_URL == "http://retired-service.invalid"


@pytest_asyncio.fixture
async def empty_demo(isolated_reviews, monkeypatch):
    _, sessions, _, _, _ = isolated_reviews
    async with sessions() as db:
        # This reset is strictly inside the existing disposable test fixture.
        schema = (await db.execute(text("SELECT current_schema()"))).scalar_one()
        assert schema.startswith("test_gap6_")
        for model in (Accommodation, Landlord, Student, User, University):
            await db.execute(delete(model))
        await db.commit()
    monkeypatch.setattr(demo, "LANDLORDS", [{"name": "Demo owner"}])
    monkeypatch.setattr(demo, "STUDENTS", [{"name": "Demo One"}, {"name": "Demo Two"}])
    monkeypatch.setattr(demo, "ACCOMMODATIONS", [{"title": "Demo residence", "description": "A synthetic student residence.",
        "address": "12 Demo Street", "lat": -28.75, "lng": 24.75, "price_min": 3000, "price_max": 4000, "landlord_idx": 0}])
    def forbidden(*args, **kwargs):
        pytest.fail("Demo seed must not make Gemini or email calls")
    monkeypatch.setattr(gemini_gateway, "create_client", forbidden)
    monkeypatch.setattr(nlp_service, "analyse_review", AsyncMock(side_effect=forbidden))
    monkeypatch.setattr(email_service, "send_email", AsyncMock(side_effect=forbidden))
    return sessions


@pytest.mark.asyncio
@pytest.mark.parametrize("confirmed,password", [(False, PASSWORD), (True, None), (True, "short"), (True, "é" * 40)])
async def test_seed_guard_runs_before_opening_any_database(confirmed, password):
    def forbidden():
        pytest.fail("Seed guard must run before connecting to a database")
    with pytest.raises(RuntimeError):
        await demo.seed(demo=confirmed, password=password, session_factory=forbidden)


@pytest.mark.asyncio
async def test_seed_refuses_existing_data_without_backfilling_reviews(isolated_reviews):
    _, sessions, _, _, _ = isolated_reviews
    review_id = await historical_review(sessions, deleted=False, status="pending_analysis")
    with pytest.raises(RuntimeError, match="non-empty"):
        await demo.seed(demo=True, password=PASSWORD, session_factory=sessions)
    async with sessions() as db:
        assert (await db.execute(select(func.count(User.id)))).scalar_one() == 3
        assert (await db.get(Review, review_id)).status == "pending_analysis"
        assert (await db.execute(select(func.count(ReviewNLPResult.id)))).scalar_one() == 0


@pytest.mark.asyncio
async def test_demo_seed_is_atomic_and_never_publishes_reviews(empty_demo):
    sessions = empty_demo
    result = await demo.seed(demo=True, password=PASSWORD, session_factory=sessions)
    assert result == {"landlords": 1, "students": 2, "accommodations": 1, "pending_reviews": 2}
    async with sessions() as db:
        users = (await db.execute(select(User))).scalars().all()
        assert len(users) == 3 and all(user.email.endswith("@example.com") for user in users)
        assert all(user.email_verified_at and verify_password(PASSWORD, user.password_hash) for user in users)
        for user in users:
            LoginRequest(email=user.email, password=PASSWORD)
            ensure_account_access(user)
        reviews = (await db.execute(select(Review))).scalars().all()
        assert len(reviews) == 2 and all(review.status == "pending_analysis" for review in reviews)
        assert len({(review.student_id, review.accommodation_id) for review in reviews}) == 2
        assert (await db.execute(select(func.count(ReviewNLPResult.id)))).scalar_one() == 0
        listing = (await db.execute(select(Accommodation))).scalar_one()
        assert listing.title.startswith("[DEMO]")
    with pytest.raises(RuntimeError, match="non-empty"):
        await demo.seed(demo=True, password=PASSWORD, session_factory=sessions)


@pytest.mark.asyncio
async def test_seed_failure_rolls_back_every_insert(empty_demo, monkeypatch):
    sessions = empty_demo
    broken = dict(demo.ACCOMMODATIONS[0], landlord_idx=99)
    monkeypatch.setattr(demo, "ACCOMMODATIONS", [broken])
    with pytest.raises(IndexError):
        await demo.seed(demo=True, password=PASSWORD, session_factory=sessions)
    async with sessions() as db:
        for model in (User, University, Accommodation, Review):
            assert (await db.execute(select(func.count(model.id)))).scalar_one() == 0


@pytest.mark.asyncio
async def test_concurrent_seed_commands_cannot_duplicate_demo_data(empty_demo):
    results = await asyncio.gather(*(demo.seed(demo=True, password=PASSWORD, session_factory=empty_demo)
                                     for _ in range(2)), return_exceptions=True)
    assert sum(isinstance(result, dict) for result in results) == 1
    assert sum(isinstance(result, RuntimeError) for result in results) == 1
    async with empty_demo() as db:
        assert (await db.execute(select(func.count(User.id)))).scalar_one() == 3
        assert (await db.execute(select(func.count(Review.id)))).scalar_one() == 2
