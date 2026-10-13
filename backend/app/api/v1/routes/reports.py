import asyncio
from datetime import datetime, timezone
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.landlord import Landlord
from app.models.report import MonthlyReport, ReportMetric
from app.models.accommodation import Accommodation, AccommodationView
from app.models.university import University
from app.services.resource_access import owned_accommodation
from app.services.report_service import generate_platform_summary, generate_accommodation_report, generate_university_report
from app.services.report_analytics import period_bounds, month_start, next_month

router = APIRouter(prefix="/reports", tags=["Reports"])


async def report_viewer(user: User = Depends(get_current_user)):
    if user.role not in ("admin", "landlord"):
        raise HTTPException(status_code=403, detail="Reports are available to administrators and property owners.")
    return user


class GenerateReportBody(BaseModel):
    report_type: Literal["platform_summary", "accommodation", "university"] = "platform_summary"
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    entity_id: Optional[int] = Field(default=None, gt=0)


async def check_report_access(db, report, user):
    if user.role == "landlord":
        if report.report_type != "accommodation" or not report.entity_id:
            raise HTTPException(status_code=403, detail="You can only access reports for your own properties.")
        await owned_accommodation(db, report.entity_id, user)


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def trigger_report(body: GenerateReportBody, current_user: User = Depends(report_viewer), db: AsyncSession = Depends(get_db)):
    try:
        period_bounds(body.year, body.month, datetime.now(timezone.utc))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    if current_user.role == "landlord":
        if body.report_type != "accommodation" or body.entity_id is None:
            raise HTTPException(status_code=403, detail="You can only generate reports for your own properties.")
        await owned_accommodation(db, body.entity_id, current_user)
    if body.report_type != "platform_summary":
        model = Accommodation if body.report_type == "accommodation" else University
        if not body.entity_id or (await db.execute(select(model.id).where(model.id == body.entity_id))).scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Report entity not found")
    elif body.entity_id is not None:
        raise HTTPException(status_code=422, detail="Platform reports do not accept an entity_id.")
    try:
        if body.report_type == "platform_summary":
            report_id = await generate_platform_summary(body.year, body.month, current_user.id)
        elif body.report_type == "accommodation":
            report_id = await generate_accommodation_report(body.entity_id, body.year, body.month, current_user.id)
        else:
            report_id = await generate_university_report(body.entity_id, body.year, body.month, current_user.id)
    except Exception:
        raise HTTPException(status_code=503, detail="The report could not be generated. Please try again shortly.") from None
    return {"report_id": report_id, "status": "complete"}


@router.get("")
async def list_reports(report_type: Optional[str] = None, entity_id: Optional[int] = None,
                       current_user: User = Depends(report_viewer), db: AsyncSession = Depends(get_db)):
    query = select(MonthlyReport).order_by(MonthlyReport.generated_at.desc(), MonthlyReport.id.desc())
    if current_user.role == "landlord":
        query = query.join(Accommodation, Accommodation.id == MonthlyReport.entity_id).join(
            Landlord, Landlord.id == Accommodation.landlord_id).where(
                MonthlyReport.report_type == "accommodation", Landlord.user_id == current_user.id)
    if report_type:
        query = query.where(MonthlyReport.report_type == report_type)
    if entity_id is not None:
        query = query.where(MonthlyReport.entity_id == entity_id)
    reports = (await db.execute(query.limit(200))).scalars().all()
    output = []
    for report in reports:
        entity_name = None
        if report.entity_id:
            model = Accommodation if report.entity_type == "accommodation" else University
            column = model.title if model is Accommodation else model.name
            entity_name = (await db.execute(select(column).where(model.id == report.entity_id))).scalar_one_or_none()
        output.append({"id": report.id, "report_type": report.report_type, "period_year": report.period_year,
            "period_month": report.period_month, "generated_at": report.generated_at, "status": report.status,
            "entity_id": report.entity_id, "entity_type": report.entity_type, "entity_name": entity_name})
    return output


async def report_payload(db, report_id, current_user):
    report = (await db.execute(select(MonthlyReport).where(MonthlyReport.id == report_id))).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    await check_report_access(db, report, current_user)
    metrics = (await db.execute(select(ReportMetric).where(ReportMetric.report_id == report_id)
        .order_by(ReportMetric.metric_category, ReportMetric.id))).scalars().all()
    grouped, document = {}, None
    for metric in metrics:
        if metric.metric_key == "management_document_v2":
            document = metric.breakdown
            continue
        grouped.setdefault(metric.metric_category, []).append({"key": metric.metric_key,
            "label": metric.metric_label, "value": metric.metric_value, "breakdown": metric.breakdown})
    entity_name = document["title"] if document else None
    if document is None and report.entity_id and report.entity_type in ("accommodation", "university"):
        model = Accommodation if report.entity_type == "accommodation" else University
        column = model.title if model is Accommodation else model.name
        entity_name = (await db.execute(select(column).where(model.id == report.entity_id))).scalar_one_or_none()
    return {"id": report.id, "report_type": report.report_type, "period_year": report.period_year,
        "period_month": report.period_month, "generated_at": report.generated_at, "status": report.status,
        "entity_id": report.entity_id, "entity_type": report.entity_type,
        "entity_name": entity_name, "metrics": grouped, "document": document}


@router.get("/{report_id}")
async def get_report(report_id: int, current_user: User = Depends(report_viewer), db: AsyncSession = Depends(get_db)):
    return await report_payload(db, report_id, current_user)


@router.get("/{report_id}/pdf")
async def download_report(report_id: int, current_user: User = Depends(report_viewer), db: AsyncSession = Depends(get_db)):
    from app.services.report_pdf import render_report_pdf, legacy_document
    payload = await report_payload(db, report_id, current_user)
    if payload["status"] != "complete":
        raise HTTPException(status_code=409, detail="This report is not complete.")
    document = payload["document"] or legacy_document(payload)
    content = await asyncio.to_thread(render_report_pdf, document, report_id)
    filename = f"accomfind-{payload['report_type']}-{report_id}-{payload['period_year']}-{payload['period_month']:02d}.pdf"
    return Response(content, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/accommodation/{accommodation_id}/trend")
async def get_accommodation_trend(accommodation_id: int, current_user: User = Depends(report_viewer), db: AsyncSession = Depends(get_db)):
    if current_user.role == "landlord":
        await owned_accommodation(db, accommodation_id, current_user)
    elif (await db.execute(select(Accommodation.id).where(Accommodation.id == accommodation_id))).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Accommodation not found")
    now = datetime.now(timezone.utc)
    start = month_start(now.year, now.month)
    for _ in range(5):
        start = month_start(start.year - (start.month == 1), 12 if start.month == 1 else start.month - 1)
    month_bucket = func.date_trunc("month", AccommodationView.viewed_at, "UTC")
    rows = (await db.execute(select(month_bucket.label("month"),
        func.count().label("views")).where(AccommodationView.accommodation_id == accommodation_id,
        AccommodationView.viewed_at >= start, AccommodationView.viewed_at < now)
        .group_by(month_bucket))).all()
    counts = {row.month.strftime("%Y-%m"): row.views for row in rows}
    output = []
    while start <= month_start(now.year, now.month):
        output.append({"year": start.year, "month": start.month, "month_label": start.strftime("%b %Y"),
                       "views": counts.get(start.strftime("%Y-%m"), 0)})
        start = next_month(start)
    return output
