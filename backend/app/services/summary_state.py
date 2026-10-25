"""Fortnightly narrative metadata inside the existing insight JSON."""
import hashlib
import json
from datetime import datetime, timezone

SCHEDULE_FIELDS = ("summary_next_due_at", "summary_retry_after", "summary_failures")
PRIVATE_FIELDS = {"summary_source_ids", "summary_signature", *SCHEDULE_FIELDS}


def parse_time(value):
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (TypeError, ValueError):
        return None


def signature(insights, source_ids):
    facts = {aspect: {key: value for key, value in data.items()
                      if not key.startswith("summary_") and key != "overall_opinion"}
             for aspect, data in insights.items()}
    raw = json.dumps([facts, sorted(source_ids)], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def apply_recommendations(insights, recommendations):
    for recommendation in recommendations:
        data = insights.get(recommendation["aspect"], {})
        if data.get("summary_generated_at") and data.get("summary_recommendation"):
            recommendation["recommendation"] = data["summary_recommendation"]
            recommendation["summary_generated_at"] = data["summary_generated_at"]
            recommendation["summary_review_count"] = data["summary_review_count"]


def preserve_summaries(insights, recommendations, previous, source_ids):
    due_dates = [data.get("summary_next_due_at") for data in previous.values()
                 if isinstance(data, dict) and parse_time(data.get("summary_next_due_at"))]
    common_due = max(due_dates, key=parse_time) if due_dates else None
    for aspect, data in insights.items():
        old = previous.get(aspect, {})
        if not isinstance(old, dict):
            old = {}
        for key in SCHEDULE_FIELDS:
            if key in old:
                data[key] = old[key]
        if common_due and "summary_next_due_at" not in data:
            data["summary_next_due_at"] = common_due
        # Additions may wait for the next fortnight. Withdrawn evidence must
        # invalidate all wording based on it immediately, preserving the schedule.
        sources = old.get("summary_source_ids")
        if (old.get("summary_generated_at") and isinstance(sources, list)
                and set(sources).issubset(source_ids)):
            data.update({key: value for key, value in old.items()
                         if key.startswith("summary_")})
            data["overall_opinion"] = old["overall_opinion"]
    apply_recommendations(insights, recommendations)


def is_due(insights, now):
    if not insights:
        return False
    # One property-wide batch: a newly eligible topic joins the next due run.
    for key in ("summary_next_due_at", "summary_retry_after"):
        dates = [parse_time(data.get(key)) for data in insights.values()]
        if any(value and value > now for value in dates):
            return False
    return True


def public_insights(insights):
    return {aspect: {key: value for key, value in data.items() if key not in PRIVATE_FIELDS}
            for aspect, data in insights.items()}
