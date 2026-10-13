"""Azure-only report tests in disposable PostgreSQL schemas; no production reports."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json

import pytest
import pytest_asyncio
from pypdf import PdfReader
from sqlalchemy import select, func, text

from test_review_resubmission import isolated_reviews
from app.api.v1.routes import reports
from app.core.security import create_access_token
from app.models.user import User
from app.models.student import Student
from app.models.landlord import Landlord
from app.models.accommodation import Accommodation, AccommodationView, accommodation_universities
from app.models.review import Review, ReviewNLPResult, ReviewReply
from app.models.report import MonthlyReport, ReportMetric
from app.models.moderation import Appeal
from app.services import report_service
from app.services.report_analytics import build_report_document, period_bounds

NOW = datetime(2026, 10, 13, 10, tzinfo=timezone.utc)
SEPT_END = datetime(2026, 9, 30, 23, 59, 59, 999999, tzinfo=timezone.utc)


def headers(identifier):
    return {"Authorization": f"Bearer {create_access_token(str(identifier))}"}


@pytest_asyncio.fixture
async def report_app(isolated_reviews, monkeypatch):
    client, sessions, _, _, _ = isolated_reviews
    client._transport.app.include_router(reports.router, prefix="/api/v1")
    monkeypatch.setattr(report_service, "AsyncSessionLocal", sessions)
    async with sessions() as db:
        db.add_all([User(id=4, email="other-owner@example.test", role="landlord", is_active=True, password_hash="unused"),
                    User(id=5, email="moderator@example.test", role="moderator", is_active=True, password_hash="unused")])
        await db.flush()
        db.add(Landlord(id=2, user_id=4, display_name="Other owner"))
        listing = await db.get(Accommodation, 1)
        listing.created_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
        listing.gender_policy = "female"
        listing.funding_type = "self_funded"
        await db.flush()
        db.add(Accommodation(id=2, landlord_id=2, title="Other owner's private listing", description="Test",
            address="Private address", location="SRID=4326;POINT(24.75 -28.75)",
            price_min=1000, price_max=1500, status="pending", created_at=datetime(2026,8,1,tzinfo=timezone.utc)))
        await db.flush()
        await db.execute(accommodation_universities.insert().values(accommodation_id=1, university_id=1))
        for identifier, status, deleted, rating in [(1,"analysed",False,2),(6,"released",False,5),
                                                   (7,"pending_analysis",False,5),(8,"quarantined",False,1),(9,"analysed",True,1)]:
            if identifier != 1:
                db.add(User(id=identifier,email=f"student{identifier}@spu.ac.za",role="student",is_active=True,password_hash="unused"))
                await db.flush()
                db.add(Student(id=identifier,user_id=identifier,university_id=1,verification_tier=1))
                await db.flush()
            review = Review(student_id=identifier,accommodation_id=1,rating=rating,
                body="Private personal details should never appear in a management report. student-private@example.test",
                status=status, created_at=SEPT_END if identifier == 1 else datetime(2026,9,10,tzinfo=timezone.utc),
                deleted_at=NOW if deleted else None)
            db.add(review)
            await db.flush()
            db.add(ReviewNLPResult(review_id=review.id, sentiment="negative" if rating <=2 else "positive",
                sentiment_score=.9, aspects={"Safety":.9,"maintenance":.7}, spam_flag=False))
        db.add_all([AccommodationView(accommodation_id=1,viewer_ip_hash="test",viewed_at=value) for value in
            [datetime(2026,8,1,tzinfo=timezone.utc), datetime(2026,9,10,tzinfo=timezone.utc),
             SEPT_END, datetime(2026,10,1,tzinfo=timezone.utc)]])
        await db.commit()
    yield client, sessions


@pytest.mark.asyncio
async def test_month_end_filtering_and_snapshot_evidence(report_app):
    _, sessions = report_app
    async with sessions() as db:
        document = await build_report_document(db,"accommodation",2026,9,1,NOW)
    kpis = {row["key"]:row["value"] for row in document["kpis"]}
    assert kpis["monthly_views"] == 2 and kpis["monthly_reviews"] == 2
    assert kpis["alltime_avg_rating"] == 3.5
    assert document["sentiment"] == {"counts":{"positive":1,"neutral":0,"negative":1},"classified":2,"published":2}
    assert [row["views"] for row in document["view_history"]] == [1,2]
    assert all(row["mentions"] == 2 for row in document["topics"])
    assert document["topics"][0]["priority"] == "Validate"
    serialized = json.dumps(document)
    assert "student-private" not in serialized and "password" not in serialized


@pytest.mark.asyncio
async def test_partial_period_compares_equal_elapsed_previous_period(report_app):
    _, sessions = report_app
    async with sessions() as db:
        document = await build_report_document(db,"accommodation",2026,10,1,NOW)
    views = next(row for row in document["kpis"] if row["key"] == "monthly_views")
    assert views["comparison"]["previous"] == 1  # September 30 must not enter the Oct 13 comparison.
    assert document["period"]["partial"] is True
    assert any("month-to-date" in value for value in document["data_quality"])


@pytest.mark.asyncio
async def test_owner_generate_list_read_pdf_and_snapshot_stability(report_app):
    client, sessions = report_app
    generated = await client.post("/api/v1/reports/generate",headers=headers(3),json={
        "report_type":"accommodation","entity_id":1,"year":2026,"month":9})
    assert generated.status_code == 201, generated.text
    identifier = generated.json()["report_id"]
    detail = await client.get(f"/api/v1/reports/{identifier}",headers=headers(3))
    assert detail.status_code == 200 and detail.json()["document"]["version"] == 2
    original = detail.json()["document"]
    async with sessions() as db:
        review = (await db.execute(select(Review).where(Review.student_id == 1))).scalar_one()
        review.deleted_at = NOW
        await db.commit()
    assert (await client.get(f"/api/v1/reports/{identifier}",headers=headers(3))).json()["document"] == original
    listing = await client.get("/api/v1/reports",headers=headers(3))
    assert [row["id"] for row in listing.json()] == [identifier]
    pdf = await client.get(f"/api/v1/reports/{identifier}/pdf",headers=headers(3))
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["cache-control"] == "private, no-store"
    reader = PdfReader(BytesIO(pdf.content))
    pages = [page.extract_text() for page in reader.pages]
    assert all("AccomFind" in page and f"Page {i+1}" in page for i,page in enumerate(pages))
    assert "Executive assessment" in "\n".join(pages) and "Prioritised action plan" in "\n".join(pages)


@pytest.mark.asyncio
@pytest.mark.parametrize("actor",[1,5])
async def test_students_and_moderators_cannot_access_reports(report_app,actor):
    client,_ = report_app
    for path in ("/api/v1/reports","/api/v1/reports/1","/api/v1/reports/1/pdf"):
        assert (await client.get(path,headers=headers(actor))).status_code == 403


@pytest.mark.asyncio
async def test_other_owner_cannot_generate_read_export_or_trend(report_app):
    client,sessions = report_app
    identifier = (await client.post("/api/v1/reports/generate",headers=headers(2),json={
        "report_type":"accommodation","entity_id":1,"year":2026,"month":9})).json()["report_id"]
    for path in (f"/api/v1/reports/{identifier}",f"/api/v1/reports/{identifier}/pdf","/api/v1/reports/accommodation/1/trend"):
        assert (await client.get(path,headers=headers(4))).status_code == 403
    assert (await client.get("/api/v1/reports",headers=headers(4))).json() == []
    assert (await client.post("/api/v1/reports/generate",headers=headers(4),json={
        "report_type":"accommodation","entity_id":1,"year":2026,"month":9})).status_code == 403
    assert (await client.post("/api/v1/reports/generate",headers=headers(3),json={
        "report_type":"platform_summary","year":2026,"month":9})).status_code == 403
    async with sessions() as db:
        assert (await db.execute(select(func.count(MonthlyReport.id)))).scalar_one() == 1


@pytest.mark.asyncio
async def test_platform_university_operational_context_and_real_trend(report_app):
    client,sessions = report_app
    async with sessions() as db:
        platform = await build_report_document(db,"platform_summary",2026,9,generated_at=NOW)
        university = await build_report_document(db,"university",2026,9,1,NOW)
    assert platform["campus_coverage"][0]["approved_listings"] == 1
    assert any(row["label"] == "Current pending reviews older than five minutes" and row["value"] == 1 for row in platform["operations"])
    assert len(university["listing_priorities"]) == 1
    assert any(row["title"] == "Unblock listing publication" for row in platform["actions"])
    trend = await client.get("/api/v1/reports/accommodation/1/trend",headers=headers(3))
    assert trend.status_code == 200 and len(trend.json()) == 6
    assert sum(row["views"] for row in trend.json()) == 4  # No generated-report history needed.


@pytest.mark.asyncio
async def test_empty_report_preserves_no_data_without_fake_percentages(report_app):
    _,sessions = report_app
    async with sessions() as db:
        document = await build_report_document(db,"accommodation",2026,9,2,NOW)
    assert document["sentiment"]["classified"] == 0
    assert next(row["value"] for row in document["kpis"] if row["key"] == "monthly_avg_rating") is None
    assert document["topics"] == [] and document["actions"]


@pytest.mark.asyncio
async def test_readiness_cross_checks_and_visibility_decline_are_actionable(report_app):
    _,sessions = report_app
    async with sessions() as db:
        owner=await db.get(User,3)
        owner.is_active=False
        db.add_all([AccommodationView(accommodation_id=1,viewer_ip_hash="test",viewed_at=datetime(2026,8,5,tzinfo=timezone.utc)) for _ in range(19)])
        await db.commit()
        platform=await build_report_document(db,"platform_summary",2026,9,generated_at=NOW)
        property_report=await build_report_document(db,"accommodation",2026,9,1,NOW)
    assert any(row["label"] == "Current approved listings with inactive owners" and row["value"] == 1 for row in platform["operations"])
    assert platform["listing_priorities"][0]["reason"] == "Published listing has inactive owner"
    assert any(row["title"] == "Resolve publication and ownership readiness gaps" for row in platform["actions"])
    assert any(row["title"] == "Investigate the recorded visibility decline" for row in property_report["actions"])
    assert any(row["title"] == "Complete discovery and presentation details" for row in property_report["actions"])


@pytest.mark.asyncio
@pytest.mark.parametrize("body",[
    {"report_type":"accommodation","entity_id":999,"year":2026,"month":9},
    {"report_type":"platform_summary","year":2026,"month":13},
    {"report_type":"platform_summary","year":2099,"month":1},
])
async def test_invalid_report_request_leaves_no_partial_records(report_app,body):
    client,sessions = report_app
    response = await client.post("/api/v1/reports/generate",headers=headers(2),json=body)
    assert response.status_code in (404,422)
    async with sessions() as db:
        assert (await db.execute(select(func.count(MonthlyReport.id)))).scalar_one() == 0


def test_february_and_half_open_period_boundaries():
    start,end,previous,previous_end = period_bounds(2024,2,datetime(2024,3,2,tzinfo=timezone.utc))
    assert end == datetime(2024,3,1,tzinfo=timezone.utc)
    assert previous_end == start and (end-start).days == 29


@pytest.mark.asyncio
async def test_generation_failure_is_atomic_and_does_not_expose_diagnostics(report_app,monkeypatch):
    client,sessions = report_app

    async def fail(*args):
        raise RuntimeError("Private storage diagnostic")

    monkeypatch.setattr(report_service,"build_report_document",fail)
    response = await client.post("/api/v1/reports/generate",headers=headers(2),json={
        "report_type":"platform_summary","year":2026,"month":9})
    assert response.status_code == 503 and "Private storage diagnostic" not in response.text
    async with sessions() as db:
        assert (await db.execute(select(func.count(MonthlyReport.id)))).scalar_one() == 0


@pytest.mark.asyncio
async def test_legacy_pdf_preserves_original_figures_and_labels_limitations(report_app):
    client,sessions = report_app
    async with sessions() as db:
        report=MonthlyReport(report_type="platform_summary",period_year=2026,period_month=8,
                             status="complete",generated_by=2)
        db.add(report)
        await db.flush()
        identifier=report.id
        db.add(ReportMetric(report_id=identifier,metric_key="old_total",metric_value=7,
                           metric_label="Original total",metric_category="traffic"))
        await db.commit()
    response = await client.get(f"/api/v1/reports/{identifier}/pdf",headers=headers(2))
    assert response.status_code == 200
    text="\n".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
    assert "legacy statistics report" in text and "Original total" in text and "7" in text
