from datetime import datetime, timezone
from calendar import monthrange
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_
from app.db.base import AsyncSessionLocal
from app.models.report import MonthlyReport, ReportMetric
from app.models.user import User
from app.models.student import Student
from app.models.landlord import Landlord
from app.models.accommodation import Accommodation, AccommodationView
from app.models.review import Review, ReviewNLPResult
from app.models.moderation import ModerationLog


async def generate_platform_summary(
    year: int,
    month: int,
    generated_by: int = None,
) -> int:
    """Generate platform summary report for given month. Returns report ID."""
    async with AsyncSessionLocal() as db:
        # Create report record
        report = MonthlyReport(
            report_type="platform_summary",
            period_year=year,
            period_month=month,
            generated_by=generated_by,
            status="generating",
        )
        db.add(report)
        await db.flush()
        report_id = report.id

        try:
            # Date range for this month
            _, last_day = monthrange(year, month)
            start = datetime(year, month, 1, tzinfo=timezone.utc)
            end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

            metrics = []

            # ── TRAFFIC ──────────────────────────────────────────────────────
            result = await db.execute(
                select(func.count(AccommodationView.id)).where(
                    AccommodationView.viewed_at >= start,
                    AccommodationView.viewed_at <= end
                )
            )
            total_views = result.scalar() or 0
            metrics.append(ReportMetric(report_id=report_id, metric_key="total_views",
                metric_value=total_views, metric_label="Total Accommodation Views",
                metric_category="traffic"))

            # Average views per listing
            result = await db.execute(select(func.count(Accommodation.id)).where(
                Accommodation.status == "approved"))
            total_listings = result.scalar() or 1
            metrics.append(ReportMetric(report_id=report_id, metric_key="avg_views_per_listing",
                metric_value=round(total_views / total_listings, 2),
                metric_label="Average Views Per Listing", metric_category="traffic"))

            # Most viewed accommodation
            result = await db.execute(
                select(Accommodation.id, Accommodation.title,
                       func.count(AccommodationView.id).label("views"))
                .join(AccommodationView, AccommodationView.accommodation_id == Accommodation.id)
                .where(AccommodationView.viewed_at >= start, AccommodationView.viewed_at <= end)
                .group_by(Accommodation.id, Accommodation.title)
                .order_by(func.count(AccommodationView.id).desc())
                .limit(1)
            )
            top = result.one_or_none()
            if top:
                metrics.append(ReportMetric(report_id=report_id, metric_key="most_viewed_listing",
                    metric_value=top.views,
                    metric_label=f"Most Viewed: {top.title}",
                    metric_category="traffic",
                    breakdown={"accommodation_id": top.id, "title": top.title, "views": top.views}))

            # ── USERS ─────────────────────────────────────────────────────────
            result = await db.execute(
                select(func.count(User.id)).where(
                    User.role == "student",
                    User.created_at >= start,
                    User.created_at <= end
                )
            )
            metrics.append(ReportMetric(report_id=report_id, metric_key="new_students",
                metric_value=result.scalar() or 0,
                metric_label="New Student Registrations", metric_category="users"))

            result = await db.execute(
                select(func.count(User.id)).where(
                    User.role == "landlord",
                    User.created_at >= start,
                    User.created_at <= end
                )
            )
            metrics.append(ReportMetric(report_id=report_id, metric_key="new_landlords",
                metric_value=result.scalar() or 0,
                metric_label="New Landlord Registrations", metric_category="users"))

            result = await db.execute(
                select(func.count(User.id)).where(
                    User.role == "student", User.is_active == True))
            metrics.append(ReportMetric(report_id=report_id, metric_key="total_active_students",
                metric_value=result.scalar() or 0,
                metric_label="Total Active Students", metric_category="users"))

            result = await db.execute(
                select(func.count(User.id)).where(
                    User.role == "landlord", User.is_active == False))
            metrics.append(ReportMetric(report_id=report_id, metric_key="deactivated_accounts",
                metric_value=result.scalar() or 0,
                metric_label="Deactivated Accounts (All Time)", metric_category="users"))

            # ── LISTINGS ──────────────────────────────────────────────────────
            result = await db.execute(
                select(func.count(Accommodation.id)).where(
                    Accommodation.created_at >= start,
                    Accommodation.created_at <= end
                )
            )
            metrics.append(ReportMetric(report_id=report_id, metric_key="new_listings",
                metric_value=result.scalar() or 0,
                metric_label="New Listings Submitted", metric_category="listings"))

            for status in ["approved", "rejected", "pending"]:
                result = await db.execute(
                    select(func.count(Accommodation.id)).where(
                        Accommodation.status == status))
                metrics.append(ReportMetric(report_id=report_id,
                    metric_key=f"listings_{status}",
                    metric_value=result.scalar() or 0,
                    metric_label=f"Listings {status.capitalize()} (Total)",
                    metric_category="listings"))

            # ── REVIEWS ───────────────────────────────────────────────────────
            result = await db.execute(
                select(func.count(Review.id)).where(
                    Review.created_at >= start,
                    Review.created_at <= end,
                    Review.deleted_at == None
                )
            )
            new_reviews = result.scalar() or 0
            metrics.append(ReportMetric(report_id=report_id, metric_key="new_reviews",
                metric_value=new_reviews,
                metric_label="New Reviews Submitted", metric_category="reviews"))

            result = await db.execute(
                select(func.count(Review.id)).where(
                    Review.created_at >= start,
                    Review.created_at <= end,
                    Review.status == "quarantined"
                )
            )
            metrics.append(ReportMetric(report_id=report_id, metric_key="quarantined_reviews",
                metric_value=result.scalar() or 0,
                metric_label="Reviews Quarantined (Toxic)", metric_category="reviews"))

            result = await db.execute(
                select(func.avg(Review.rating)).where(
                    Review.created_at >= start,
                    Review.created_at <= end,
                    Review.deleted_at == None
                )
            )
            avg = result.scalar()
            metrics.append(ReportMetric(report_id=report_id, metric_key="avg_rating",
                metric_value=round(float(avg), 2) if avg else 0,
                metric_label="Average Rating This Month", metric_category="reviews"))

            # ── NLP ───────────────────────────────────────────────────────────
            result = await db.execute(
                select(
                    ReviewNLPResult.sentiment,
                    func.count(ReviewNLPResult.id).label("count")
                )
                .join(Review, Review.id == ReviewNLPResult.review_id)
                .where(
                    Review.created_at >= start,
                    Review.created_at <= end
                )
                .group_by(ReviewNLPResult.sentiment)
            )
            sentiment_rows = result.all()
            sentiment_breakdown = {row.sentiment: row.count for row in sentiment_rows}
            total_nlp = sum(sentiment_breakdown.values()) or 1
            metrics.append(ReportMetric(report_id=report_id, metric_key="sentiment_distribution",
                metric_value=total_nlp,
                metric_label="Sentiment Distribution",
                metric_category="nlp",
                breakdown=sentiment_breakdown))

            result = await db.execute(
                select(func.count(ReviewNLPResult.id)).where(
                    ReviewNLPResult.spam_flag == True,
                )
            )
            metrics.append(ReportMetric(report_id=report_id, metric_key="toxicity_flags",
                metric_value=result.scalar() or 0,
                metric_label="Total Toxicity Flags (All Time)", metric_category="nlp"))

            # ── LANDLORD VERIFICATION ─────────────────────────────────────────
            for vstatus in ["verified", "pending", "rejected"]:
                result = await db.execute(
                    select(func.count(Landlord.id)).where(
                        Landlord.verification_status == vstatus))
                metrics.append(ReportMetric(report_id=report_id,
                    metric_key=f"landlords_{vstatus}",
                    metric_value=result.scalar() or 0,
                    metric_label=f"Landlords {vstatus.capitalize()}",
                    metric_category="verification"))

            # ── MODERATION ────────────────────────────────────────────────────
            result = await db.execute(
                select(func.count(ModerationLog.id)).where(
                    ModerationLog.created_at >= start,
                    ModerationLog.created_at <= end
                )
            )
            metrics.append(ReportMetric(report_id=report_id, metric_key="moderation_actions",
                metric_value=result.scalar() or 0,
                metric_label="Moderation Actions This Month", metric_category="moderation"))

            # Save all metrics
            for m in metrics:
                db.add(m)

            report.status = "complete"
            await db.commit()
            return report_id

        except Exception as e:
            report.status = "failed"
            await db.commit()
            print(f"Report generation failed: {e}")
            raise


async def generate_accommodation_report(
    accommodation_id: int,
    year: int,
    month: int,
    generated_by: int = None,
) -> int:
    async with AsyncSessionLocal() as db:
        report = MonthlyReport(
            report_type="accommodation",
            period_year=year,
            period_month=month,
            generated_by=generated_by,
            status="generating",
            entity_id=accommodation_id,
            entity_type="accommodation",
        )
        db.add(report)
        await db.flush()
        report_id = report.id

        try:
            _, last_day = monthrange(year, month)
            start = datetime(year, month, 1, tzinfo=timezone.utc)
            end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

            metrics = []

            # Views this month
            result = await db.execute(
                select(func.count(AccommodationView.id)).where(
                    AccommodationView.accommodation_id == accommodation_id,
                    AccommodationView.viewed_at >= start,
                    AccommodationView.viewed_at <= end
                )
            )
            monthly_views = result.scalar() or 0
            metrics.append(ReportMetric(report_id=report_id, metric_key="monthly_views",
                metric_value=monthly_views, metric_label="Views This Month",
                metric_category="traffic"))

            # Cumulative views
            result = await db.execute(
                select(func.count(AccommodationView.id)).where(
                    AccommodationView.accommodation_id == accommodation_id))
            metrics.append(ReportMetric(report_id=report_id, metric_key="cumulative_views",
                metric_value=result.scalar() or 0,
                metric_label="Total Views All Time", metric_category="traffic"))

            # Reviews this month
            result = await db.execute(
                select(func.count(Review.id)).where(
                    Review.accommodation_id == accommodation_id,
                    Review.created_at >= start,
                    Review.created_at <= end,
                    Review.deleted_at == None
                )
            )
            metrics.append(ReportMetric(report_id=report_id, metric_key="monthly_reviews",
                metric_value=result.scalar() or 0,
                metric_label="Reviews This Month", metric_category="reviews"))

            # Avg rating this month
            result = await db.execute(
                select(func.avg(Review.rating)).where(
                    Review.accommodation_id == accommodation_id,
                    Review.created_at >= start,
                    Review.created_at <= end,
                    Review.deleted_at == None
                )
            )
            avg = result.scalar()
            metrics.append(ReportMetric(report_id=report_id, metric_key="monthly_avg_rating",
                metric_value=round(float(avg), 2) if avg else 0,
                metric_label="Average Rating This Month", metric_category="reviews"))

            # All time avg rating
            result = await db.execute(
                select(func.avg(Review.rating)).where(
                    Review.accommodation_id == accommodation_id,
                    Review.deleted_at == None
                )
            )
            avg_all = result.scalar()
            metrics.append(ReportMetric(report_id=report_id, metric_key="alltime_avg_rating",
                metric_value=round(float(avg_all), 2) if avg_all else 0,
                metric_label="Average Rating All Time", metric_category="reviews"))

            # Sentiment this month
            result = await db.execute(
                select(ReviewNLPResult.sentiment, func.count(ReviewNLPResult.id).label("count"))
                .join(Review, Review.id == ReviewNLPResult.review_id)
                .where(
                    Review.accommodation_id == accommodation_id,
                    Review.created_at >= start,
                    Review.created_at <= end
                )
                .group_by(ReviewNLPResult.sentiment)
            )
            sentiment_breakdown = {row.sentiment: row.count for row in result.all()}
            metrics.append(ReportMetric(report_id=report_id, metric_key="sentiment_distribution",
                metric_value=sum(sentiment_breakdown.values()),
                metric_label="Sentiment Distribution",
                metric_category="nlp",
                breakdown=sentiment_breakdown))

            for m in metrics:
                db.add(m)

            report.status = "complete"
            await db.commit()
            return report_id

        except Exception as e:
            report.status = "failed"
            await db.commit()
            raise


async def generate_university_report(
    university_id: int,
    year: int,
    month: int,
    generated_by: int = None,
) -> int:
    from app.models.university import University
    from app.models.accommodation import accommodation_universities

    async with AsyncSessionLocal() as db:
        report = MonthlyReport(
            report_type="university",
            period_year=year,
            period_month=month,
            generated_by=generated_by,
            status="generating",
            entity_id=university_id,
            entity_type="university",
        )
        db.add(report)
        await db.flush()
        report_id = report.id

        try:
            _, last_day = monthrange(year, month)
            start = datetime(year, month, 1, tzinfo=timezone.utc)
            end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

            # Get all accommodation IDs for this university
            result = await db.execute(
                select(accommodation_universities.c.accommodation_id).where(
                    accommodation_universities.c.university_id == university_id
                )
            )
            acc_ids = [row[0] for row in result.all()]

            metrics = []

            # Total listings
            metrics.append(ReportMetric(report_id=report_id, metric_key="total_listings",
                metric_value=len(acc_ids),
                metric_label="Total Linked Listings", metric_category="listings"))

            if acc_ids:
                # Total views this month
                result = await db.execute(
                    select(func.count(AccommodationView.id)).where(
                        AccommodationView.accommodation_id.in_(acc_ids),
                        AccommodationView.viewed_at >= start,
                        AccommodationView.viewed_at <= end
                    )
                )
                metrics.append(ReportMetric(report_id=report_id, metric_key="monthly_views",
                    metric_value=result.scalar() or 0,
                    metric_label="Total Views This Month", metric_category="traffic"))

                # New listings this month
                result = await db.execute(
                    select(func.count(Accommodation.id)).where(
                        Accommodation.id.in_(acc_ids),
                        Accommodation.created_at >= start,
                        Accommodation.created_at <= end
                    )
                )
                metrics.append(ReportMetric(report_id=report_id, metric_key="new_listings",
                    metric_value=result.scalar() or 0,
                    metric_label="New Listings This Month", metric_category="listings"))

                # Avg rating across all listings
                result = await db.execute(
                    select(func.avg(Review.rating)).where(
                        Review.accommodation_id.in_(acc_ids),
                        Review.deleted_at == None
                    )
                )
                avg = result.scalar()
                metrics.append(ReportMetric(report_id=report_id, metric_key="avg_rating",
                    metric_value=round(float(avg), 2) if avg else 0,
                    metric_label="Average Rating Across All Listings",
                    metric_category="reviews"))

                # Most viewed listing
                result = await db.execute(
                    select(Accommodation.id, Accommodation.title,
                           func.count(AccommodationView.id).label("views"))
                    .join(AccommodationView, AccommodationView.accommodation_id == Accommodation.id)
                    .where(Accommodation.id.in_(acc_ids))
                    .group_by(Accommodation.id, Accommodation.title)
                    .order_by(func.count(AccommodationView.id).desc())
                    .limit(1)
                )
                top = result.one_or_none()
                if top:
                    metrics.append(ReportMetric(report_id=report_id,
                        metric_key="most_viewed_listing",
                        metric_value=top.views,
                        metric_label=f"Most Viewed: {top.title}",
                        metric_category="traffic",
                        breakdown={"accommodation_id": top.id, "title": top.title, "views": top.views}))

            for m in metrics:
                db.add(m)

            report.status = "complete"
            await db.commit()
            return report_id

        except Exception as e:
            report.status = "failed"
            await db.commit()
            raise


async def run_monthly_auto_reports():
    """Called by APScheduler on 1st of each month."""
    now = datetime.now(timezone.utc)
    # Generate for previous month
    if now.month == 1:
        year, month = now.year - 1, 12
    else:
        year, month = now.year, now.month - 1

    print(f"Auto-generating reports for {year}-{month:02d}...")
    await generate_platform_summary(year, month)
    print("Auto-reports complete.")