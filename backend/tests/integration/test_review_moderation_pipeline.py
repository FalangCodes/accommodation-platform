"""Azure-only tests in disposable schemas; all AI calls are mocked."""
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, func
from test_review_resubmission import isolated_reviews, historical_review
from test_published_metrics import metrics_app
from app.core.security import create_access_token
from app.models.user import User
from app.models.student import Student
from app.models.review import Review, ReviewNLPResult
from app.models.moderation import ModerationLog
from app.models.insight import AccommodationInsight
from app.services import review_service
from app.services.report_analytics import build_report_document


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["toxic", "clear", "failed"])
async def test_analysis_controls_publication_and_preserves_moderator_release(isolated_reviews, monkeypatch, decision):
    client,sessions,headers,mod_headers,effects=isolated_reviews
    identifier=await historical_review(sessions,deleted=False,status="pending_analysis")
    async def analyse(*args):
        return None if decision=="failed" else dict(sentiment="negative",sentiment_score=.9,
            aspects={},is_toxic=decision=="toxic",moderation_reason="Gemini flagged abusive/profane content.")
    async def noop(*args): pass
    monkeypatch.setattr(review_service,"analyse_review",analyse)
    monkeypatch.setattr(review_service,"AsyncSessionLocal",sessions)
    monkeypatch.setattr(review_service,"cache_delete",noop)
    monkeypatch.setattr(review_service,"cache_delete_pattern",noop)
    await review_service.process_review_nlp(identifier,"A test accommodation complaint.")
    async with sessions() as db:
        row=await db.get(Review,identifier)
        assert row.status=={"toxic":"quarantined","clear":"analysed","failed":"pending_analysis"}[decision]
        nlp=(await db.execute(select(ReviewNLPResult).where(ReviewNLPResult.review_id==identifier))).scalar_one_or_none()
        assert (nlp is None)==(decision=="failed")
        if nlp: assert nlp.spam_flag==(decision=="toxic")
        logs=(await db.execute(select(ModerationLog))).scalars().all()
        assert len(logs)==(1 if decision=="toxic" else 0)
        if logs: assert logs[0].reason=="Gemini flagged abusive/profane content."
    public=(await client.get("/api/v1/reviews/accommodation/1",headers=headers)).json()
    assert public["total"]==(1 if decision=="clear" else 0)
    if decision=="toxic":
        flagged=(await client.get("/api/v1/reviews/flagged",headers=mod_headers)).json()
        assert any(row["id"]==identifier for row in flagged)
        assert (await client.patch(f"/api/v1/moderation/reviews/{identifier}/release",headers=mod_headers)).status_code==200
        assert (await client.get("/api/v1/reviews/accommodation/1",headers=headers)).json()["total"]==1
        await review_service.process_review_nlp(identifier,"A retry must not undo human release.")
        async with sessions() as db:
            assert (await db.get(Review,identifier)).status=="released"


@pytest.mark.asyncio
async def test_flagged_analysed_reviews_are_excluded_everywhere_but_releases_are_kept(metrics_app):
    client,sessions,headers,_,_,_,_=metrics_app
    hidden=await historical_review(sessions,deleted=False,status="analysed")
    async with sessions() as db:
        db.add(ReviewNLPResult(review_id=hidden,sentiment="negative",sentiment_score=.9,
                              aspects={"safety":.9},spam_flag=True))
        for identifier,status,rating,flag in [(4,"released",4,True),(5,"analysed",5,False)]:
            db.add(User(id=identifier,email=f"student{identifier}@spu.ac.za",role="student",is_active=True,password_hash="unused"))
            await db.flush()
            db.add(Student(id=identifier,user_id=identifier,university_id=1,verification_tier=1))
            await db.flush()
            row=Review(student_id=identifier,accommodation_id=1,rating=rating,
                       body="The WiFi is fast and reliable for studying.",status=status)
            db.add(row)
            await db.flush()
            db.add(ReviewNLPResult(review_id=row.id,sentiment="positive",sentiment_score=.9,
                                  aspects={"wifi and internet":.9},spam_flag=flag))
        db.add(AccommodationInsight(accommodation_id=1,insights={"safety":{"overall_opinion":"OLD FLAGGED EVIDENCE"}},
                                   recommendations=[],review_count=3))
        await db.commit()
    public=(await client.get("/api/v1/reviews/accommodation/1",headers=headers)).json()
    assert public["total"]==2 and hidden not in [row["id"] for row in public["items"]]
    detail=(await client.get("/api/v1/accommodations/1",headers=headers)).json()
    assert detail["total_reviews"]==2 and detail["average_rating"]==4.5
    assert (await client.get("/api/v1/accommodations/platform-stats")).json()["reviews"]==2
    for path in ("/api/v1/accommodations/search?min_rating=4.4", "/api/v1/accommodations/search?university_id=1&min_rating=4.4"):
        assert (await client.get(path,headers=headers)).json()["total"]==1
    featured=(await client.get("/api/v1/accommodations/featured")).json()
    assert featured[0]["review_count"]==2 and featured[0]["avg_rating"]==4.5
    activity=(await client.get("/api/v1/accommodations/activity")).json()
    assert sorted(row["rating"] for row in activity if row["type"]=="review")==[4,5]
    owner={"Authorization":f"Bearer {create_access_token('3')}"}
    analytics=(await client.get("/api/v1/accommodations/1/analytics",headers=owner)).json()
    assert analytics["total_reviews"]==2 and analytics["average_rating"]==4.5
    insight=(await client.get("/api/v1/accommodations/1/insights",headers=headers)).json()
    assert insight["review_count"]==2 and "OLD FLAGGED EVIDENCE" not in json.dumps(insight)
    async with sessions() as db:
        now=datetime.now(timezone.utc)
        document=await build_report_document(db,"accommodation",now.year,now.month,1,now)
        assert next(row["value"] for row in document["kpis"] if row["key"]=="total_published_reviews")==2
        # No historical review decision was silently rewritten.
        assert (await db.get(Review,hidden)).status=="analysed"
