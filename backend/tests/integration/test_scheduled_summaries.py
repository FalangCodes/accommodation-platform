"""Azure-only: isolated PostgreSQL/Redis; no real Gemini requests."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select
from test_published_metrics import metrics_app
from test_gemini_quota import admission
from test_review_resubmission import isolated_reviews, historical_review
from app.models.user import User
from app.models.student import Student
from app.models.review import Review, ReviewNLPResult
from app.models.insight import AccommodationInsight
from app.services import scheduled_summaries as summaries, gemini_gateway as gate, insight_engine

BASE_TIME = datetime(2026, 10, 25, 8, tzinfo=timezone.utc)
WORDING = "Residents report unreliable WiFi during study sessions."


async def add_review(sessions, identifier, status="analysed"):
    async with sessions() as db:
        db.add(User(id=identifier, email=f"summary{identifier}@spu.ac.za", role="student",
                    is_active=True, password_hash="unused"))
        await db.flush()
        db.add(Student(id=identifier, user_id=identifier, university_id=1, verification_tier=1))
        await db.flush()
        review = Review(student_id=identifier, accommodation_id=1, rating=2,
            body="The WiFi is unreliable and disconnects during evening study sessions.", status=status)
        db.add(review)
        await db.flush()
        if status == "analysed":
            db.add(ReviewNLPResult(review_id=review.id, sentiment="negative", sentiment_score=.9,
                                  aspects={"wifi and internet": .95}, spam_flag=False))
        await db.commit()
        return review.id


@pytest_asyncio.fixture
async def scheduled(metrics_app, admission, monkeypatch):
    client, sessions, headers, _, _, _, _ = metrics_app
    redis, prefix = admission
    monkeypatch.setattr(summaries, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(summaries, "get_redis", gate.get_redis)
    clock = [BASE_TIME]
    monkeypatch.setattr(summaries, "now", lambda: clock[0])
    first = await historical_review(sessions, deleted=False)
    async with sessions() as db:
        review = await db.get(Review, first)
        review.body = "The WiFi is unreliable and disconnects during evening study sessions."
        db.add(ReviewNLPResult(review_id=first, sentiment="negative", sentiment_score=.9,
                              aspects={"wifi and internet": .95}, spam_flag=False))
        await db.commit()
    second = await add_review(sessions, 4)
    async with sessions() as db:
        await insight_engine.regenerate_accommodation_insights(1, db)
        row = (await db.execute(select(AccommodationInsight))).scalar_one()
        assert "wifi and internet" in row.insights
    calls = []
    state = {"error": None, "payload": None}
    def generate(**kwargs):
        calls.append(kwargs)
        if state["error"]:
            raise state["error"]
        evidence = json.loads(kwargs["contents"])
        payload = state["payload"] or {"topics": [{"aspect": aspect, "opinion": WORDING,
                "recommendation": "Log evening outages and test WiFi coverage with residents."} for aspect in evidence]}
        return SimpleNamespace(text=json.dumps(payload))
    monkeypatch.setattr(gate, "create_client", lambda: SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    return client, sessions, headers, redis, prefix, clock, calls, state, first, second


async def row_data(sessions):
    async with sessions() as db:
        row = (await db.execute(select(AccommodationInsight))).scalar_one()
        return deepcopy(row.insights), deepcopy(row.recommendations), row.review_count


@pytest.mark.asyncio
async def test_persisted_fortnight_schedule_unchanged_evidence_and_private_metadata(scheduled):
    client, sessions, headers, _, _, clock, calls, _, _, _ = scheduled
    assert await summaries.refresh_summary(1) == "saved"
    data, recs, _ = await row_data(sessions)
    topic = data["wifi and internet"]
    assert topic["overall_opinion"] == WORDING and topic["summary_review_count"] == 2
    assert recs[0]["summary_generated_at"] == BASE_TIME.isoformat()
    response = (await client.get("/api/v1/accommodations/1/insights", headers=headers)).json()
    public = response["insights"]["wifi and internet"]
    assert public["summary_generated_at"] == BASE_TIME.isoformat()
    assert "summary_source_ids" not in public and "summary_retry_after" not in public
    assert "summary_signature" not in public
    clock[0] += timedelta(days=13)
    assert await summaries.refresh_summary(1) == "not_due"
    clock[0] += timedelta(days=1)
    assert await summaries.refresh_summary(1) == "unchanged"
    data, _, _ = await row_data(sessions)
    assert data["wifi and internet"]["summary_generated_at"] == BASE_TIME.isoformat()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_new_reviews_update_figures_but_retain_saved_wording_until_due(scheduled):
    _, sessions, _, redis, prefix, clock, calls, _, _, _ = scheduled
    await summaries.refresh_summary(1)
    await add_review(sessions, 5)
    async with sessions() as db:
        await insight_engine.regenerate_accommodation_insights(1, db)
    data, _, count = await row_data(sessions)
    assert count == 3 and data["wifi and internet"]["mention_count"] == 3
    assert data["wifi and internet"]["summary_review_count"] == 2
    assert data["wifi and internet"]["overall_opinion"] == WORDING
    assert await summaries.refresh_summary(1) == "not_due"
    clock[0] += timedelta(days=14)
    await redis.delete(prefix + gate.KEYS[3])
    assert await summaries.refresh_summary(1) == "saved"
    data, _, _ = await row_data(sessions)
    assert data["wifi and internet"]["summary_review_count"] == 3 and len(calls) == 2


@pytest.mark.asyncio
async def test_removed_source_immediately_invalidates_wording_and_advice(scheduled):
    _, sessions, _, _, _, _, calls, _, first, _ = scheduled
    await summaries.refresh_summary(1)
    await add_review(sessions, 5)
    async with sessions() as db:
        await insight_engine.regenerate_accommodation_insights(1, db)
        review = await db.get(Review, first)
        review.deleted_at, review.deleted_by = BASE_TIME, 2
        await db.commit()
        await insight_engine.regenerate_accommodation_insights(1, db)
    data, recs, count = await row_data(sessions)
    assert count == 2 and WORDING not in json.dumps(data)
    assert "summary_generated_at" not in data["wifi and internet"]
    assert "Log evening outages" not in json.dumps(recs)
    assert data["wifi and internet"]["summary_next_due_at"] is not None
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_temporary_failure_retains_safe_summary_and_retries_later(scheduled):
    _, sessions, _, redis, prefix, clock, calls, state, _, _ = scheduled
    await summaries.refresh_summary(1)
    await add_review(sessions, 5)
    clock[0] += timedelta(days=14)
    await redis.delete(prefix + gate.KEYS[3])
    state["error"] = RuntimeError("503 unavailable")
    assert await summaries.refresh_summary(1) == "deferred"
    data, _, _ = await row_data(sessions)
    assert data["wifi and internet"]["overall_opinion"] == WORDING
    assert data["wifi and internet"]["summary_failures"] == 1
    assert await summaries.refresh_summary(1) == "not_due"
    assert len(calls) == 2
    state["error"] = None
    clock[0] += timedelta(hours=1, seconds=1)
    await redis.delete(prefix + gate.KEYS[1], prefix + gate.KEYS[3])
    assert await summaries.refresh_summary(1) == "saved"
    data, _, _ = await row_data(sessions)
    assert data["wifi and internet"]["summary_failures"] == 0 and len(calls) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{"topics": []}, {"topics": [{"aspect": "invented", "opinion": WORDING, "recommendation": None}]},
                                     {"topics": [{"aspect": "wifi and internet", "opinion": " ", "recommendation": None}]}])
async def test_invalid_batches_never_overwrite_safe_fallbacks(scheduled, payload):
    _, sessions, _, _, _, _, calls, state, _, _ = scheduled
    state["payload"] = payload
    assert await summaries.refresh_summary(1) == "failed"
    data, _, _ = await row_data(sessions)
    assert "summary_generated_at" not in data["wifi and internet"]
    assert await summaries.refresh_summary(1) == "not_due" and len(calls) == 1


@pytest.mark.asyncio
async def test_quota_pauses_job_without_repeated_provider_calls(scheduled):
    _, sessions, _, redis, prefix, _, calls, state, _, _ = scheduled
    state["error"] = RuntimeError("429 RESOURCE_EXHAUSTED")
    await summaries.run_due_summaries()
    assert len(calls) == 1 and await gate.pause_seconds() >= 86395
    await summaries.run_due_summaries()
    assert len(calls) == 1 and not await redis.exists(prefix + summaries.RUN_KEY)
    data, _, _ = await row_data(sessions)
    assert data["wifi and internet"]["summary_failures"] == 1
    assert data["wifi and internet"]["summary_retry_after"] >= (BASE_TIME + timedelta(days=1)).isoformat()


@pytest.mark.asyncio
async def test_review_analysis_has_priority_over_summaries(scheduled):
    _, sessions, _, _, _, _, calls, _, _, _ = scheduled
    await add_review(sessions, 5, status="pending_analysis")
    await summaries.run_due_summaries()
    assert not calls


@pytest.mark.asyncio
async def test_source_removed_during_generation_cannot_be_saved(scheduled, monkeypatch):
    _, sessions, _, _, _, _, _, _, first, _ = scheduled
    async def changing_batch(insights):
        async with sessions() as db:
            review = await db.get(Review, first)
            review.deleted_at, review.deleted_by = BASE_TIME, 2
            await db.commit()
            await insight_engine.regenerate_accommodation_insights(1, db)
        return {aspect: summaries.TopicSummary(aspect=aspect, opinion=WORDING, recommendation=None) for aspect in insights}
    monkeypatch.setattr(summaries, "generate_batch", changing_batch)
    assert await summaries.refresh_summary(1) == "changed"
    data, _, count = await row_data(sessions)
    assert count == 1 and WORDING not in json.dumps(data)


@pytest.mark.asyncio
async def test_concurrent_job_checks_only_generate_once(scheduled):
    _, _, _, redis, prefix, _, calls, _, _, _ = scheduled
    await asyncio.gather(summaries.run_due_summaries(), summaries.run_due_summaries())
    assert len(calls) == 1 and not await redis.exists(prefix + summaries.RUN_KEY)
