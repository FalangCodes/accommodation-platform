"""Evidence-based management reports. No external AI calls or personal data."""
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from statistics import mean

from sqlalchemy import select, func
from app.models.accommodation import Accommodation, AccommodationView, AccommodationImage, accommodation_universities
from app.models.review import Review, ReviewNLPResult, ReviewReply
from app.models.user import User
from app.models.landlord import Landlord
from app.models.student import Student
from app.models.university import University
from app.models.moderation import ModerationLog, Appeal

PUBLISHED = ("analysed", "released")
TOPICS = {
    "Safety": ("safe", "secur", "crime", "safety"),
    "WiFi & Internet": ("wifi", "internet", "connection"),
    "Cleanliness": ("clean", "hygiene"),
    "Noise Levels": ("nois", "quiet"),
    "Landlord Responsiveness": ("landlord", "respons", "management"),
    "Water & Electricity": ("water", "electric", "power"),
    "Maintenance & Repairs": ("mainten", "repair"),
    "Value for Money": ("value", "money", "price", "cost"),
}
ADVICE = {
    "Safety": ("Inspect entrance lighting and access control, and ask residents to distinguish property security from concerns about surrounding routes.", "Record the inspection findings and confirm that agreed security actions have been completed."),
    "WiFi & Internet": ("Test room coverage and evening peak-hour speeds before purchasing equipment; log outages and provider response times.", "Compare peak-hour test results and logged outages after the changes."),
    "Cleanliness": ("Review the cleaning schedule with residents and inspect shared kitchens, bathrooms and waste areas.", "Track completed inspections and repeat cleanliness concerns."),
    "Noise Levels": ("Identify recurring noisy times and locations, agree quiet hours and explain how residents can report disturbances.", "Track repeat noise complaints and whether agreed quiet hours are being followed."),
    "Landlord Responsiveness": ("Provide one clear contact channel, acknowledge requests and keep a log of unresolved issues.", "Measure acknowledgment time and outstanding requests each week."),
    "Water & Electricity": ("Inspect supply interruptions, backup arrangements and communication during outages.", "Track outage duration and completion of backup-system checks."),
    "Maintenance & Repairs": ("Prioritise outstanding repairs, give residents expected completion dates and confirm closure with the resident.", "Track overdue repairs and time to close each request."),
    "Value for Money": ("Explain what rent includes and compare advertised charges with the facilities and services actually delivered.", "Check that residents understand the charges and track recurring value concerns."),
}


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def month_start(year, month):
    return datetime(year, month, 1, tzinfo=timezone.utc)


def next_month(value):
    return month_start(value.year + (value.month == 12), 1 if value.month == 12 else value.month + 1)


def period_bounds(year, month, now):
    start = month_start(year, month)
    end = min(next_month(start), aware(now))
    if start >= end:
        raise ValueError("Choose the current month or an earlier month.")
    previous = month_start(year - (month == 1), 12 if month == 1 else month - 1)
    previous_end = min(start, previous + (end - start)) if end < next_month(start) else start
    return start, end, previous, previous_end


def comparison(current, previous, label):
    delta = None if current is None or previous is None else round(current - previous, 2)
    return {"previous": previous, "label": label, "delta": delta,
            "percent": round(delta / previous * 100, 1) if delta is not None and previous else None}


def topic_name(key):
    lowered = str(key).lower()
    return next((name for name, words in TOPICS.items() if any(word in lowered for word in words)), None)


def build_topics(reviews):
    """Sentiment belongs to the review, not to a separately scored topic."""
    buckets = defaultdict(Counter)
    for review in reviews:
        raw_aspects = review.get("aspects")
        aspects = raw_aspects if isinstance(raw_aspects, dict) else {}
        topics = {topic_name(key) for key, score in aspects.items()
                  if isinstance(score, (int, float)) and not isinstance(score, bool) and score >= 0.4}
        for name in topics - {None}:
            sentiment = str(review.get("sentiment") or "unclassified").strip().lower()
            buckets[name][sentiment if sentiment in ("positive", "neutral", "negative") else "unclassified"] += 1
    output = []
    for name, counts in buckets.items():
        mentions = sum(counts.values())
        negatives = counts["negative"]
        priority = "High" if name == "Safety" and negatives and mentions >= 3 else "Medium" if negatives and mentions >= 3 else "Validate" if negatives else "Maintain"
        action, measure = ADVICE[name]
        output.append({"name": name, "mentions": mentions, "positive": counts["positive"],
                       "neutral": counts["neutral"], "negative": negatives,
                       "unclassified": counts["unclassified"], "priority": priority,
                       "evidence": f"{mentions} reviews are AI-tagged with this topic; {negatives} of those reviews have negative overall sentiment.",
                       "action": action, "success_measure": measure})
    return sorted(output, key=lambda item: ({"High": 0, "Medium": 1, "Validate": 2, "Maintain": 3}[item["priority"]], -item["mentions"], item["name"]))


async def collect_report_data(db, report_type, entity_id, cutoff):
    listing_query = (select(Accommodation.id, Accommodation.title, Accommodation.address,
                           Accommodation.status, Accommodation.created_at, Accommodation.landlord_id,
                           Accommodation.gender_policy, Accommodation.funding_type,
                           Accommodation.price_min, Accommodation.price_max,
                           Landlord.verification_status.label("landlord_verification"),
                           User.is_active.label("owner_active"))
        .select_from(Accommodation).join(Landlord, Landlord.id == Accommodation.landlord_id)
        .join(User, User.id == Landlord.user_id))
    if report_type == "accommodation":
        listing_query = listing_query.where(Accommodation.id == entity_id)
    elif report_type == "university":
        listing_query = listing_query.join(accommodation_universities,
            accommodation_universities.c.accommodation_id == Accommodation.id).where(
                accommodation_universities.c.university_id == entity_id)
    listings = [dict(row) for row in (await db.execute(listing_query)).mappings().all()]
    ids = [row["id"] for row in listings]
    # Select stable columns rather than the optional, uncommitted aspect_details field.
    query = select(Review.id, Review.accommodation_id, Review.rating, Review.created_at,
                   ReviewNLPResult.sentiment, ReviewNLPResult.aspects).outerjoin(
        ReviewNLPResult, ReviewNLPResult.review_id == Review.id).where(
            Review.accommodation_id.in_(ids), Review.deleted_at.is_(None),
            Review.status.in_(PUBLISHED), Review.created_at < cutoff)
    reviews = [dict(row) for row in (await db.execute(query)).mappings().all()]
    month_bucket = func.date_trunc("month", AccommodationView.viewed_at, "UTC")
    view_rows = (await db.execute(select(AccommodationView.accommodation_id,
        month_bucket.label("month"),
        func.count().label("views")).where(AccommodationView.accommodation_id.in_(ids),
        AccommodationView.viewed_at < cutoff).group_by(AccommodationView.accommodation_id,
        month_bucket))).mappings().all()
    replied = set((await db.execute(select(ReviewReply.review_id).where(
        ReviewReply.review_id.in_([row["id"] for row in reviews]),
        ReviewReply.created_at < cutoff))).scalars().all())
    return {"listings": listings, "reviews": reviews, "views": [dict(row) for row in view_rows], "replied": replied}


def compose_document(data, report_type, year, month, generated_at, title):
    start, end, previous, previous_end = period_bounds(year, month, generated_at)
    partial = end < next_month(start)
    comparison_label = "Same elapsed portion of previous month" if partial else "Previous calendar month"
    listings, reviews = data["listings"], data["reviews"]
    current = [r for r in reviews if start <= aware(r["created_at"]) < end]
    prior = [r for r in reviews if previous <= aware(r["created_at"]) < previous_end]
    # Aggregated month buckets are exact for closed months. Partial comparison is
    # supplied separately by SQL date-range counts rather than a whole-month bucket.
    views = sum(row["views"] for row in data["views"] if aware(row["month"]) == start)
    prior_views = data.get("previous_views", sum(row["views"] for row in data["views"] if aware(row["month"]) == previous))
    average = lambda rows: round(mean(row["rating"] for row in rows), 2) if rows else None
    rating_change = comparison(average(current), average(prior), comparison_label)
    rating_change["percent"] = None  # Ratings are compared in rating points, not growth percentages.
    rating_change["unit"] = "rating points"
    kpis = [
        {"key": "monthly_views", "label": "Recorded page views this period", "value": views, "comparison": comparison(views, prior_views, comparison_label)},
        {"key": "monthly_reviews", "label": "Published reviews submitted this period", "value": len(current), "comparison": comparison(len(current), len(prior), comparison_label)},
        {"key": "monthly_avg_rating", "label": "Rating of this period's published reviews", "value": average(current), "comparison": rating_change},
        {"key": "alltime_avg_rating", "label": "Published review rating through cutoff", "value": average(reviews)},
        {"key": "total_published_reviews", "label": "Published reviews through cutoff", "value": len(reviews)},
        {"key": "cumulative_views", "label": "Recorded views through cutoff", "value": sum(row["views"] for row in data["views"])},
    ]
    sentiments = Counter(str(row.get("sentiment") or "unclassified").strip().lower() for row in reviews)
    classified = sum(sentiments[label] for label in ("positive", "neutral", "negative"))
    distribution = {label: sentiments[label] for label in ("positive", "neutral", "negative")}
    first = min([aware(row["created_at"]) for row in listings] +
                [aware(row["month"]) for row in data["views"]], default=start)
    cursor = min(month_start(first.year, first.month), start)
    monthly = Counter()
    for row in data["views"]:
        monthly[aware(row["month"])] += row["views"]
    history, running = [], 0
    while cursor <= start:
        running += monthly[cursor]
        history.append({"month_label": cursor.strftime("%b %Y"), "month": cursor.strftime("%Y-%m"), "views": monthly[cursor], "cumulative": running})
        cursor = next_month(cursor)
    topics = build_topics(reviews)
    actions = [{"priority": row["priority"], "title": row["name"], "evidence": row["evidence"],
                "action": row["action"], "owner": "Property manager" if report_type == "accommodation" else "Admin / landlord liaison",
                "success_measure": row["success_measure"]} for row in topics if row["negative"]][:5]
    strengths = [f"Preserve the practices associated with {row['name'].lower()}: {row['positive']} positive reviews mention this topic. Confirm which practices residents value."
                 for row in topics if row["positive"] >= 2 and not row["negative"]]
    summary = [f"{views} recorded page views and {len(current)} currently published reviews submitted during the reporting period."]
    if views and prior_views:
        change = comparison(views, prior_views, comparison_label)["percent"]
        summary.append(f"Recorded visibility changed from {prior_views} to {views} page views ({change:+g}%) against the comparison period. This measures attention, not applications or bookings.")
        if min(views, prior_views) < 20:
            summary.append("The view-count baseline is small; a large percentage movement can represent only a few visits. Investigate the trend before changing spending.")
    elif views and not prior_views:
        summary.append("The comparison period has no recorded views; a percentage growth claim would be misleading.")
    elif not views:
        summary.append("No page views are recorded for this period. Check listing visibility and whether buffered views have reached the database before concluding that demand is absent.")
    summary.append(f"The evidence base is {len(reviews)} published reviews; {classified} have a recognised sentiment result.")
    if topics and actions:
        summary.append(f"Feedback-specific attention: {actions[0]['title'].lower()}. {actions[0]['evidence']} Investigate the underlying issue before committing expenditure.")
    if len(reviews) < 10:
        summary.append("The review sample is small. Treat the findings as directional feedback rather than a representative satisfaction survey.")
    if not actions:
        maintain = bool(topics and sentiments["positive"] >= 2 and sentiments["positive"] >= .6 * classified)
        actions.append({"priority": "Maintain" if maintain else "Validate", "title": "Preserve service strengths and monitor feedback" if maintain else "Clarify mixed or neutral feedback" if topics else "Check feedback analysis coverage" if reviews else "Build the feedback evidence base", "evidence": f"{len(reviews)} published reviews; no supported negative-topic priority is available.",
                        "action": "Continue the practices highlighted by positive feedback and monitor new concerns without treating a lack of negative tags as proof that every issue is resolved." if maintain else "Ask residents what is working and what could improve, and review the context of neutral feedback before deciding on expenditure." if topics else "Check topic-analysis coverage and ask residents about specific experiences before making topic-specific decisions." if reviews else "Invite residents to leave honest reviews without incentives tied to positive ratings. Ask about specific experiences through the normal support channel.",
                        "owner": "Property manager" if report_type == "accommodation" else "Platform operations", "success_measure": "Track new published reviews and whether previously unassessed topics receive feedback."})
    unanswered = [r for r in reviews if r["id"] not in data["replied"]]
    if any(r["rating"] <= 2 for r in unanswered):
        actions.append({"priority": "Medium", "title": "Respond to unresolved public feedback", "evidence": f"{sum(r['rating'] <= 2 for r in unanswered)} low-rated published reviews have no public landlord reply through the cutoff.",
                        "action": "Acknowledge the concerns publicly without identifying residents and explain the next step or resolution.",
                        "owner": "Property manager" if report_type == "accommodation" else "Landlord liaison", "success_measure": "Track reply coverage on low-rated reviews; a reply alone does not prove an issue is resolved."})
    quality = ["Reporting month boundaries and comparison cutoffs use UTC.",
               "Page views are visits, not unique students, enquiries, applications, occupied beds or revenue.",
               "View timestamps reflect when buffered counts were flushed to the database. Unflushed views are excluded; daily activity and precise visit times cannot be reconstructed.",
               "Published-review metrics exclude deleted, pending and quarantined reviews using their review status at generation. Historical snapshots are not reconstructed from today's listing/account status.",
               "Available feedback from scoped off-market properties can still be included. Review figures do not imply that the listing is currently visible; current listing statuses are shown separately.",
               "Topic counts use the latest stored AI tags (score >= 0.4) and whole-review sentiment at generation. They are not independent topic sentiment scores or verified safety assessments.",
               "Action priorities guide investigation. Negative overall sentiment does not establish which of the tagged topics caused dissatisfaction.",
               "Verified student counts refer to active student-role accounts with verified institutional emails, not confirmed current enrolment or housing demand.",
               "Percentages use reviews with recognised sentiment results as their denominator; sample sizes are shown. No individual student names, emails or verification documents are included."]
    if partial:
        quality.append("This is a month-to-date report, not a complete month. Comparisons use the same elapsed duration in the preceding month, capped at its month end.")
    missing = sum(not row["gender_policy"] or not row["funding_type"] for row in listings)
    if missing:
        quality.append(f"{missing} scoped listings have an unspecified gender policy or funding type; complete these fields to improve discovery filters.")
    rows = []
    for listing in listings:
        feedback = [r for r in reviews if r["accommodation_id"] == listing["id"]]
        negative = sum(str(r.get("sentiment")).strip().lower() == "negative" for r in feedback)
        listing_views = sum(r["views"] for r in data["views"] if r["accommodation_id"] == listing["id"] and aware(r["month"]) == start)
        blocked_contact = listing["status"] == "approved" and not listing["owner_active"]
        verification_gap = listing["status"] == "approved" and listing["landlord_verification"] != "verified"
        reason = "Published listing has inactive owner" if blocked_contact else "Review publication / verification mismatch" if verification_gap else "Follow up on negative feedback" if negative else "Invite honest feedback" if not feedback else "Monitor and maintain"
        rows.append({"id": listing["id"], "title": listing["title"], "views": listing_views,
                     "reviews": len(feedback), "rating": average(feedback), "negative": negative, "status": listing["status"], "reason": reason,
                     "readiness_gap": blocked_contact or verification_gap})
    rows.sort(key=lambda r: (not r["readiness_gap"], -r["negative"], -r["views"], r["id"]))
    return {"version": 2, "title": title, "report_type": report_type,
            "audience": "Landlord / property manager" if report_type == "accommodation" else "Platform administrator",
            "period": {"label": start.strftime("%B %Y"), "start": start.isoformat(), "cutoff": end.isoformat(),
                       "partial": partial, "comparison_label": comparison_label},
            "generated_at": aware(generated_at).isoformat(), "summary": summary, "kpis": kpis,
            "view_history": history, "ratings": {str(n): sum(r["rating"] == n for r in reviews) for n in range(1, 6)},
            "sentiment": {"counts": distribution, "classified": classified, "published": len(reviews)},
            "topics": topics, "actions": actions, "strengths": strengths,
            "reply_coverage": {"replied": len(reviews) - len(unanswered), "published": len(reviews)},
            "listing_priorities": rows[:10] if report_type != "accommodation" else [],
            "operations": [], "campus_coverage": [], "data_quality": quality}


async def build_report_document(db, report_type, year, month, entity_id=None, generated_at=None):
    now = generated_at or datetime.now(timezone.utc)
    start, end, previous, previous_end = period_bounds(year, month, now)
    title = "Platform performance and operations"
    if report_type == "accommodation":
        title = (await db.execute(select(Accommodation.title).where(Accommodation.id == entity_id))).scalar_one_or_none()
    elif report_type == "university":
        title = (await db.execute(select(University.name).where(University.id == entity_id))).scalar_one_or_none()
    if title is None:
        raise ValueError("Report entity does not exist.")
    data = await collect_report_data(db, report_type, entity_id, end)
    ids = [row["id"] for row in data["listings"]]
    data["previous_views"] = (await db.execute(select(func.count()).select_from(AccommodationView).where(
        AccommodationView.accommodation_id.in_(ids), AccommodationView.viewed_at >= previous,
        AccommodationView.viewed_at < previous_end))).scalar_one()
    document = compose_document(data, report_type, year, month, now, title)
    if report_type == "accommodation":
        landlord_id = data["listings"][0]["landlord_id"]
        status = (await db.execute(select(Landlord.verification_status).where(Landlord.id == landlord_id))).scalar_one()
        listing = data["listings"][0]
        photo_count = (await db.execute(select(func.count(AccommodationImage.id)).where(AccommodationImage.accommodation_id == entity_id))).scalar_one()
        document["property_address"] = listing["address"]
        document["property_profile"] = [
            {"label": "Advertised monthly rent", "value": f"R{listing['price_min']:,.2f} - R{listing['price_max']:,.2f}"},
            {"label": "Gender policy", "value": {"male":"Male only","female":"Female only","mixed":"Mixed"}.get(listing["gender_policy"],"Not specified")},
            {"label": "Funding", "value": {"self_funded":"Self-funded","bursary":"Bursary / NSFAS","both":"Self-funded and bursary"}.get(listing["funding_type"],"Not specified")},
        ]
        document["operations"] = [{"label": "Current listing status", "value": data["listings"][0]["status"]},
                                   {"label": "Current landlord verification", "value": status},
                                   {"label": "Current owner account status", "value": "Active" if listing["owner_active"] else "Inactive"},
                                   {"label": "Current listing photo count", "value": photo_count}]
        values = {row["key"]: row["value"] for row in document["kpis"]}
        missing = [label for label, absent in [("listing photos", not photo_count),
            ("gender policy", not listing["gender_policy"]), ("funding type", not listing["funding_type"])] if absent]
        if missing:
            document["actions"].append({"priority": "Medium", "title": "Complete discovery and presentation details",
                "evidence": "Missing current details: " + ", ".join(missing) + ". These are gaps in the listing record, not a proven cause of low traffic.",
                "action": "Add representative property photos and check advertised profile fields using the dashboard or platform support. Keep the information accurate rather than overstating facilities.",
                "owner": "Landlord / platform support", "success_measure": "Confirm that photos and discovery fields are complete, then monitor recorded visibility in the next comparable period."})
        view_metric = next(row for row in document["kpis"] if row["key"] == "monthly_views")
        prior_views = view_metric["comparison"]["previous"]
        if prior_views >= 20 and values["monthly_views"] < prior_views * .75:
            document["actions"].append({"priority": "Medium", "title": "Investigate the recorded visibility decline",
                "evidence": f"Recorded views fell from {prior_views} to {values['monthly_views']} in comparable reporting windows.",
                "action": "Confirm that view flushing is current, check publication status and discovery filters, and review listing presentation. Consider term/application timing before concluding that housing demand has fallen.",
                "owner": "Landlord / platform support", "success_measure": "Compare recorded views over the next equivalent window and record which listing changes were made."})
        if values["monthly_views"] >= 20 and len(data["reviews"]) < 3:
            document["actions"].append({"priority": "Medium", "title": "Build trust alongside visitor attention",
                "evidence": f"{values['monthly_views']} recorded views this period, but only {len(data['reviews'])} published reviews through the cutoff.",
                "action": "Invite existing residents to share honest experiences without rewards tied to positive ratings. Visitors and reviewers are different populations; do not interpret their ratio as conversion.",
                "owner": "Property manager", "success_measure": "Track published feedback coverage and the questions prospective residents still need answered."})
        if status != "verified" or data["listings"][0]["status"] != "approved" or not listing["owner_active"]:
            document["actions"].insert(0, {"priority": "High", "title": "Resolve publication readiness",
                "evidence": f"Current listing status: {data['listings'][0]['status']}; landlord verification: {status}; owner account: {'active' if listing['owner_active'] else 'inactive'}.",
                "action": "Check verification, account and listing requirements with the administrator. Inactive owners cannot receive platform enquiries; make a clear publication decision while resolving the requirements.",
                "owner": "Landlord / administrator", "success_measure": "Confirm active owner status, completed verification and appropriate listing visibility."})
    else:
        counts = Counter(row["status"] for row in data["listings"])
        pending = [row for row in data["listings"] if row["status"] == "pending"]
        older = sum((aware(now) - aware(row["created_at"])).days >= 7 for row in pending)
        document["operations"] = [{"label": f"Current listings: {status}", "value": count} for status, count in sorted(counts.items())]
        inactive_published = sum(row["status"] == "approved" and not row["owner_active"] for row in data["listings"])
        unverified_published = sum(row["status"] == "approved" and row["landlord_verification"] != "verified" for row in data["listings"])
        document["operations"] += [{"label": "Current approved listings with inactive owners", "value": inactive_published},
                                   {"label": "Current approved listings with unverified owners", "value": unverified_published}]
        if inactive_published or unverified_published:
            document["actions"].insert(0, {"priority": "High", "title": "Resolve publication and ownership readiness gaps",
                "evidence": f"{inactive_published} approved listings have inactive owner accounts; {unverified_published} have owners whose verification is not complete. These groups may overlap.",
                "action": "Review the affected listings before promoting them. Inactive owners cannot receive enquiries through the platform; check contact availability and verification requirements and make an explicit publication decision.",
                "owner": "Administrator / verification lead", "success_measure": "Confirm that publicly promoted listings have active owners, completed verification and a working enquiry path."})
        if report_type == "platform_summary":
            verified = (await db.execute(select(func.count(User.id)).where(User.role == "student", User.is_active.is_(True), User.email_verified_at.is_not(None)))).scalar_one()
            verification = (await db.execute(select(func.count(Landlord.id)).where(Landlord.verification_status == "pending"))).scalar_one()
            appeals = (await db.execute(select(func.count(Appeal.id)).where(Appeal.status == "pending"))).scalar_one()
            queue = (await db.execute(select(func.count(Review.id)).where(Review.deleted_at.is_(None), Review.status == "pending_analysis"))).scalar_one()
            quarantined = (await db.execute(select(func.count(Review.id)).where(Review.deleted_at.is_(None), Review.status == "quarantined"))).scalar_one()
            stalled = (await db.execute(select(func.count(Review.id)).where(Review.deleted_at.is_(None),
                Review.status == "pending_analysis", Review.created_at < aware(now) - timedelta(minutes=5)))).scalar_one()
            new_students = (await db.execute(select(func.count(User.id)).where(User.role == "student", User.created_at >= start, User.created_at < end))).scalar_one()
            new_landlords = (await db.execute(select(func.count(User.id)).where(User.role == "landlord", User.created_at >= start, User.created_at < end))).scalar_one()
            unverified_landlords = (await db.execute(select(func.count(Landlord.id)).where(Landlord.verification_status == "unverified"))).scalar_one()
            actions = (await db.execute(select(func.count(ModerationLog.id)).where(ModerationLog.created_at >= start, ModerationLog.created_at < end))).scalar_one()
            document["operations"] += [{"label": "Current active verified students", "value": verified},
                {"label": "New student registrations this period", "value": new_students},
                {"label": "New landlord registrations this period", "value": new_landlords},
                {"label": "Listing records created this period", "value": sum(start <= aware(row["created_at"]) < end for row in data["listings"])},
                {"label": "Current unverified landlord profiles", "value": unverified_landlords},
                {"label": "Current pending landlord verifications", "value": verification},
                {"label": "Current pending appeals", "value": appeals},
                {"label": "Current reviews awaiting analysis", "value": queue},
                {"label": "Current quarantined reviews", "value": quarantined},
                {"label": "Current pending reviews older than five minutes", "value": stalled},
                {"label": "Moderation actions during period", "value": actions}]
            if verification or appeals or stalled or quarantined:
                document["actions"].insert(0, {"priority": "High" if stalled else "Medium", "title": "Reduce trust and processing backlogs",
                    "evidence": f"Current queues: {verification} landlord verifications, {appeals} appeals, {quarantined} quarantined reviews and {queue} pending analyses ({stalled} older than five minutes).",
                    "action": "Assign queue owners, inspect stalled NLP jobs and prioritise outstanding verification, quarantine and appeal decisions.",
                    "owner": "Administrator / moderation lead", "success_measure": "Track queue size, oldest outstanding items and decisions completed each week."})
            universities = (await db.execute(select(University.id, University.name).order_by(University.name))).all()
            for university in universities:
                supply = (await db.execute(select(func.count()).select_from(accommodation_universities)
                    .join(Accommodation, Accommodation.id == accommodation_universities.c.accommodation_id)
                    .where(accommodation_universities.c.university_id == university.id, Accommodation.status == "approved"))).scalar_one()
                students = (await db.execute(select(func.count()).select_from(Student).join(User, User.id == Student.user_id)
                    .where(Student.university_id == university.id, User.role == "student", User.is_active.is_(True), User.email_verified_at.is_not(None)))).scalar_one()
                document["campus_coverage"].append({"name": university.name, "approved_listings": supply, "verified_students": students})
            uncovered = [row for row in document["campus_coverage"] if row["verified_students"] and not row["approved_listings"]]
            if uncovered:
                document["actions"].append({"priority": "Medium", "title": "Investigate gaps in campus discovery coverage",
                    "evidence": f"{len(uncovered)} universities have active verified student accounts but no approved linked listings.",
                    "action": "Check listing-campus links and identify relevant landlords to onboard after normal verification.",
                    "owner": "Platform operations", "success_measure": "Track approved linked listings per campus; student accounts are not a measure of housing demand or available beds."})
            if unverified_landlords:
                document["actions"].append({"priority": "Medium", "title": "Help landlords complete publication requirements",
                    "evidence": f"{unverified_landlords} landlord profiles currently remain unverified.",
                    "action": "Review the verification instructions and identify incomplete onboarding steps. Make the evidence requirements clear before expecting listings to become public.",
                    "owner": "Landlord onboarding / administrator", "success_measure": "Track movement from unverified to pending and verified profiles without bypassing document checks."})
        if pending:
            document["actions"].insert(0, {"priority": "Medium", "title": "Unblock listing publication",
                "evidence": f"{len(pending)} current pending listings; {older} were created at least seven days ago (creation age is not time spent in the queue).",
                "action": "Check ownership evidence and outstanding landlord responses. Review older cases and make clear publication decisions.",
                "owner": "Administrator / moderation lead", "success_measure": "Track pending listings and completed decisions; verify that publication requirements remain satisfied."})
    document["actions"].sort(key=lambda action: {"High": 0, "Medium": 1, "Validate": 2, "Maintain": 3}.get(action["priority"], 4))
    document["actions"] = document["actions"][:8]
    document["summary"].append("Management priorities: " + "; ".join(action["title"] for action in document["actions"][:3]) + ". The action plan identifies responsibility and a follow-up measure for each.")
    return document
