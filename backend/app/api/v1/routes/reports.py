from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from datetime import datetime, timezone
from typing import Optional

from app.db.base import get_db
from app.core.dependencies import get_current_admin, get_current_moderator
from app.models.user import User
from app.models.report import MonthlyReport, ReportMetric
from app.models.accommodation import AccommodationView
from app.services.report_service import (
    generate_platform_summary,
    generate_accommodation_report,
    generate_university_report,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def trigger_report(
    body: dict,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    report_type = body.get("report_type", "platform_summary")
    now = datetime.now(timezone.utc)
    year = body.get("year", now.year)
    month = body.get("month", now.month)
    entity_id = body.get("entity_id")

    if report_type == "platform_summary":
        report_id = await generate_platform_summary(year, month, current_user.id)
    elif report_type == "accommodation" and entity_id:
        report_id = await generate_accommodation_report(entity_id, year, month, current_user.id)
    elif report_type == "university" and entity_id:
        report_id = await generate_university_report(entity_id, year, month, current_user.id)
    else:
        raise HTTPException(status_code=400, detail="Invalid report type or missing entity_id")

    return {"report_id": report_id, "status": "complete"}


@router.get("")
async def list_reports(
    report_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    query = select(MonthlyReport).order_by(
        MonthlyReport.period_year.desc(),
        MonthlyReport.period_month.desc(),
        MonthlyReport.generated_at.desc()
    )
    if report_type:
        query = query.where(MonthlyReport.report_type == report_type)
    if entity_id:
        query = query.where(MonthlyReport.entity_id == entity_id)

    result = await db.execute(query)
    reports = result.scalars().all()

    return [
        {
            "id": r.id,
            "report_type": r.report_type,
            "period_year": r.period_year,
            "period_month": r.period_month,
            "generated_at": r.generated_at,
            "status": r.status,
            "entity_id": r.entity_id,
            "entity_type": r.entity_type,
        }
        for r in reports
    ]


@router.get("/{report_id}")
async def get_report(
    report_id: int,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(MonthlyReport).where(MonthlyReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    result = await db.execute(
        select(ReportMetric).where(ReportMetric.report_id == report_id)
        .order_by(ReportMetric.metric_category, ReportMetric.metric_key)
    )
    metrics = result.scalars().all()

    # Group by category
    grouped: dict = {}
    for m in metrics:
        if m.metric_category not in grouped:
            grouped[m.metric_category] = []
        grouped[m.metric_category].append({
            "key": m.metric_key,
            "label": m.metric_label,
            "value": m.metric_value,
            "breakdown": m.breakdown,
        })

    return {
        "id": report.id,
        "report_type": report.report_type,
        "period_year": report.period_year,
        "period_month": report.period_month,
        "generated_at": report.generated_at,
        "status": report.status,
        "entity_id": report.entity_id,
        "entity_type": report.entity_type,
        "metrics": grouped,
    }


@router.get("/accommodation/{accommodation_id}/trend")
async def get_accommodation_trend(
    accommodation_id: int,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Get 6 months of view data for trend chart."""
    result = await db.execute(
        select(MonthlyReport)
        .where(
            MonthlyReport.report_type == "accommodation",
            MonthlyReport.entity_id == accommodation_id,
            MonthlyReport.status == "complete"
        )
        .order_by(
            MonthlyReport.period_year.desc(),
            MonthlyReport.period_month.desc()
        )
        .limit(6)
    )
    reports = result.scalars().all()

    trend = []
    for r in reversed(reports):
        # Get monthly_views metric
        metric_result = await db.execute(
            select(ReportMetric).where(
                ReportMetric.report_id == r.id,
                ReportMetric.metric_key == "monthly_views"
            )
        )
        metric = metric_result.scalar_one_or_none()
        trend.append({
            "year": r.period_year,
            "month": r.period_month,
            "month_label": datetime(r.period_year, r.period_month, 1).strftime("%b %Y"),
            "views": metric.metric_value if metric else 0,
        })

    return trend