"""Persist management report snapshots in the existing report/metric tables."""
from datetime import datetime, timezone
import logging
from sqlalchemy import text
from app.db.base import AsyncSessionLocal
from app.models.report import MonthlyReport, ReportMetric
from app.services.report_analytics import build_report_document, period_bounds

logger = logging.getLogger(__name__)


async def generate_report(report_type, year, month, generated_by=None, entity_id=None):
    generated_at = datetime.now(timezone.utc)
    period_bounds(year, month, generated_at)
    async with AsyncSessionLocal() as db:
        try:
            # One consistent database snapshot for the whole report.
            await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            document = await build_report_document(db, report_type, year, month, entity_id, generated_at)
            report = MonthlyReport(report_type=report_type, period_year=year, period_month=month,
                generated_by=generated_by, generated_at=generated_at, status="complete", entity_id=entity_id,
                entity_type="accommodation" if report_type == "accommodation" else "university" if report_type == "university" else None)
            db.add(report)
            await db.flush()
            db.add(ReportMetric(report_id=report.id, metric_key="management_document_v2",
                metric_value=None, metric_label="Management report snapshot", metric_category="document", breakdown=document))
            for metric in document["kpis"]:
                db.add(ReportMetric(report_id=report.id, metric_key=metric["key"], metric_value=metric["value"],
                    metric_label=metric["label"], metric_category="performance", breakdown=metric.get("comparison")))
            await db.commit()
            return report.id
        except Exception:
            await db.rollback()
            logger.exception("Management report generation failed")
            raise


async def generate_platform_summary(year, month, generated_by=None):
    return await generate_report("platform_summary", year, month, generated_by)


async def generate_accommodation_report(accommodation_id, year, month, generated_by=None):
    return await generate_report("accommodation", year, month, generated_by, accommodation_id)


async def generate_university_report(university_id, year, month, generated_by=None):
    return await generate_report("university", year, month, generated_by, university_id)


async def run_monthly_auto_reports():
    now = datetime.now(timezone.utc)
    previous = datetime(now.year - (now.month == 1), 12 if now.month == 1 else now.month - 1, 1)
    await generate_platform_summary(previous.year, previous.month)
