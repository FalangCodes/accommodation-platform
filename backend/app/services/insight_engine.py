import re
import httpx
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.review import Review, ReviewNLPResult
from app.models.insight import AccommodationInsight
from app.core.config import settings

# ─── Thresholds ───────────────────────────────────────────────────────────────

ASPECT_DETECTION_THRESHOLD = 0.4   # minimum confidence to consider aspect detected
SENTENCE_RELEVANCE_THRESHOLD = 0.35 # minimum score to consider sentence relevant to aspect
MIN_MENTIONS_STUDENT = 3            # minimum mentions to show insight to students
MIN_MENTIONS_LANDLORD = 2           # minimum mentions to show insight to landlords

# Student-facing thresholds (stricter)
STUDENT_POSITIVE_THRESHOLD = 0.70   # ≥70% positive → show as positive
STUDENT_NEGATIVE_THRESHOLD = 0.60   # ≥60% negative → show as negative

# Landlord-facing thresholds (more permissive)
LANDLORD_POSITIVE_THRESHOLD = 0.60
LANDLORD_NEGATIVE_THRESHOLD = 0.50

ASPECT_LABELS = [
    "cleanliness",
    "safety",
    "noise levels",
    "landlord responsiveness",
    "wifi and internet",
    "water and electricity",
    "maintenance and repairs",
    "value for money"
]

ASPECT_DISPLAY_NAMES = {
    "cleanliness": "Cleanliness",
    "safety": "Safety",
    "noise levels": "Noise Levels",
    "landlord responsiveness": "Landlord Responsiveness",
    "wifi and internet": "WiFi & Internet",
    "water and electricity": "Water & Electricity",
    "maintenance and repairs": "Maintenance & Repairs",
    "value for money": "Value for Money",
}

# ─── Recommendation templates ─────────────────────────────────────────────────

RECOMMENDATIONS = {
    "cleanliness": {
        "negative": "Students consistently report cleanliness issues. Consider scheduling more frequent cleaning of communal areas and establishing clear standards for room handovers.",
        "mixed": "Cleanliness receives mixed feedback. Some students are satisfied while others report concerns. A regular cleaning schedule and inspection routine could improve consistency.",
    },
    "safety": {
        "negative": "Safety is a significant concern for students at this property. Consider improving lighting, reinforcing access control, or increasing security presence.",
        "mixed": "Safety perceptions are mixed among students. Review your current security measures and consider communicating safety protocols more clearly to residents.",
    },
    "noise levels": {
        "negative": "Noise is a recurring complaint. Consider implementing and enforcing quiet hours, or improving sound insulation between units.",
        "mixed": "Some students find the noise levels disruptive. Clear house rules around quiet hours and communal area conduct may help.",
    },
    "landlord responsiveness": {
        "negative": "Students report difficulty reaching you or receiving slow responses. A dedicated communication channel and response time commitment could significantly improve satisfaction.",
        "mixed": "Response times are inconsistent according to students. Consider setting clear expectations around response windows and maintenance timelines.",
    },
    "wifi and internet": {
        "negative": "WiFi reliability is a top complaint. Unreliable internet directly impacts students' academic performance. Consider upgrading to a fibre connection or adding a secondary router.",
        "mixed": "WiFi performance is inconsistent. Students report it works well at times but becomes unreliable under load. A router upgrade or bandwidth management may help.",
    },
    "water and electricity": {
        "negative": "Students report recurring water or electricity disruptions. Ensure your property has adequate backup solutions and that utility issues are communicated proactively.",
        "mixed": "Utility reliability receives mixed reviews. Consider installing a backup water tank or generator to reduce the impact of municipal outages.",
    },
    "maintenance and repairs": {
        "negative": "Maintenance response time is your most critical issue. Students report waiting weeks for repairs. A dedicated maintenance schedule and clear escalation process is strongly recommended.",
        "mixed": "Maintenance turnaround is inconsistent. Some repairs are handled promptly while others take too long. A tracking system for maintenance requests could help.",
    },
    "value for money": {
        "negative": "Students feel the property does not offer good value for the price. Review your pricing relative to the amenities offered, or invest in improving facilities.",
        "mixed": "Value perceptions are split. Highlighting your amenities and any recent improvements in your listing description may help justify the pricing.",
    },
}


# ─── NLP service helpers ──────────────────────────────────────────────────────

async def score_sentence_for_aspect(sentence: str, aspect: str) -> float:
    """Reuse existing aspect model to score sentence relevance to aspect."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{settings.NLP_SERVICE_URL}/score_sentence",
                json={"sentence": sentence, "aspect": aspect}
            )
            if response.status_code == 200:
                return response.json().get("score", 0.0)
    except Exception as e:
        print(f"Sentence scoring failed: {e}")
    return 0.0


async def get_sentence_sentiment(sentence: str) -> str:
    """Get sentiment for a single sentence."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{settings.NLP_SERVICE_URL}/sentiment",
                json={"text": sentence}
            )
            if response.status_code == 200:
                return response.json().get("sentiment", "neutral")
    except Exception as e:
        print(f"Sentence sentiment failed: {e}")
    return "neutral"


# ─── Per-review aspect detail extraction ─────────────────────────────────────

async def extract_aspect_details(
    aspects: dict,
    sentences: list[str],
    overall_sentiment: str
) -> dict:
    """
    For each detected aspect, find relevant sentences, determine aspect sentiment,
    and extract evidence. Returns aspect_details dict.
    """
    aspect_details = {}

    detected = {
        aspect: score
        for aspect, score in aspects.items()
        if score >= ASPECT_DETECTION_THRESHOLD
    }

    if not detected or not sentences:
        return aspect_details

    for aspect, confidence in detected.items():
        # Score each sentence for relevance to this aspect
        sentence_scores = []
        for sentence in sentences:
            score = await score_sentence_for_aspect(sentence, aspect)
            sentence_scores.append((sentence, score))

        # Sort by relevance, take top 2
        sentence_scores.sort(key=lambda x: x[1], reverse=True)
        top_sentences = [
            (s, sc) for s, sc in sentence_scores
            if sc >= SENTENCE_RELEVANCE_THRESHOLD
        ][:2]

        if not top_sentences:
            # No clearly relevant sentences — use overall sentiment as fallback
            aspect_details[aspect] = {
                "aspect_sentiment": overall_sentiment,
                "confidence": confidence,
                "evidence": [],
                "strengths": [],
                "concerns": [],
                "fallback": True,
            }
            continue

        # Get sentiment for each top sentence
        sentiments = []
        evidence = []
        for sentence, _ in top_sentences:
            sentiment = await get_sentence_sentiment(sentence)
            sentiments.append(sentiment)
            evidence.append({"text": sentence, "sentiment": sentiment})

        # Determine aspect sentiment
        positive_count = sentiments.count("positive")
        negative_count = sentiments.count("negative")

        if positive_count > negative_count:
            aspect_sentiment = "positive"
        elif negative_count > positive_count:
            aspect_sentiment = "negative"
        else:
            aspect_sentiment = "mixed"

        # Separate into strengths and concerns
        strengths = [e["text"] for e in evidence if e["sentiment"] == "positive"]
        concerns = [e["text"] for e in evidence if e["sentiment"] in ("negative", "neutral")]

        aspect_details[aspect] = {
            "aspect_sentiment": aspect_sentiment,
            "confidence": confidence,
            "evidence": [e["text"] for e in evidence],
            "strengths": strengths,
            "concerns": concerns,
            "fallback": False,
        }

    return aspect_details


# ─── Cross-review aggregation ─────────────────────────────────────────────────

async def regenerate_accommodation_insights(
    accommodation_id: int,
    db: AsyncSession
) -> None:
    """
    Aggregate all NLP results for an accommodation into structured insights.
    Upserts accommodation_insights table.
    """
    # Fetch all non-deleted reviews with NLP results
    result = await db.execute(
        select(Review, ReviewNLPResult)
        .join(ReviewNLPResult, ReviewNLPResult.review_id == Review.id)
        .where(
            Review.accommodation_id == accommodation_id,
            Review.deleted_at == None,
            Review.status.in_(["analysed", "released"])
        )
    )
    rows = result.all()

    if not rows:
        return

    total_reviews = len(rows)

    # Aggregate per aspect
    aspect_data: dict = {aspect: {
        "mentions": 0,
        "positive": 0,
        "negative": 0,
        "mixed": 0,
        "strengths": [],
        "concerns": [],
    } for aspect in ASPECT_LABELS}

    for review, nlp in rows:
        if not nlp.aspect_details:
            continue
        for aspect, detail in nlp.aspect_details.items():
            if aspect not in aspect_data:
                continue
            aspect_data[aspect]["mentions"] += 1
            sentiment = detail.get("aspect_sentiment", "mixed")
            aspect_data[aspect][sentiment] = aspect_data[aspect].get(sentiment, 0) + 1
            aspect_data[aspect]["strengths"].extend(detail.get("strengths", []))
            aspect_data[aspect]["concerns"].extend(detail.get("concerns", []))

    # Build insights dict
    insights = {}
    recommendations = []

    for aspect, data in aspect_data.items():
        mentions = data["mentions"]
        if mentions < MIN_MENTIONS_LANDLORD:
            continue

        positive = data["positive"]
        negative = data["negative"]
        total = mentions

        positive_rate = round(positive / total * 100) if total > 0 else 0
        negative_rate = round(negative / total * 100) if total > 0 else 0

        # Determine overall sentiment using landlord thresholds
        if positive_rate >= LANDLORD_POSITIVE_THRESHOLD * 100:
            overall = "positive"
        elif negative_rate >= LANDLORD_NEGATIVE_THRESHOLD * 100:
            overall = "negative"
        else:
            overall = "mixed"

        # Student-facing sentiment (stricter thresholds)
        if mentions >= MIN_MENTIONS_STUDENT:
            if positive_rate >= STUDENT_POSITIVE_THRESHOLD * 100:
                student_sentiment = "positive"
            elif negative_rate >= STUDENT_NEGATIVE_THRESHOLD * 100:
                student_sentiment = "negative"
            else:
                student_sentiment = "mixed"
            show_to_students = True
        else:
            student_sentiment = overall
            show_to_students = False

        # Top evidence — deduplicate and take most common
        top_strengths = list(dict.fromkeys(data["strengths"]))[:3]
        top_concerns = list(dict.fromkeys(data["concerns"]))[:3]

        insights[aspect] = {
            "display_name": ASPECT_DISPLAY_NAMES.get(aspect, aspect),
            "mention_count": mentions,
            "positive_rate": positive_rate,
            "negative_rate": negative_rate,
            "overall_sentiment": overall,
            "student_sentiment": student_sentiment,
            "show_to_students": show_to_students,
            "top_strengths": top_strengths,
            "top_concerns": top_concerns,
        }

        # Generate recommendation if negative or mixed
        if overall in ("negative", "mixed") and aspect in RECOMMENDATIONS:
            template = RECOMMENDATIONS[aspect].get(overall)
            if template:
                recommendations.append({
                    "aspect": aspect,
                    "display_name": ASPECT_DISPLAY_NAMES.get(aspect, aspect),
                    "priority": "high" if overall == "negative" and negative_rate >= 70 else "medium",
                    "recommendation": template,
                    "positive_rate": positive_rate,
                    "mention_count": mentions,
                })

    # Sort recommendations by priority
    recommendations.sort(key=lambda x: x["priority"] == "high", reverse=True)

    # Upsert accommodation_insights
    stmt = pg_insert(AccommodationInsight.__table__).values(
        accommodation_id=accommodation_id,
        insights=insights,
        recommendations=recommendations,
        review_count=total_reviews,
    ).on_conflict_do_update(
        index_elements=["accommodation_id"],
        set_={
            "insights": insights,
            "recommendations": recommendations,
            "review_count": total_reviews,
            "generated_at": sa_func_now(),
        }
    )
    await db.execute(stmt)
    await db.commit()
    print(f"Accommodation insights regenerated for {accommodation_id}")


def sa_func_now():
    from sqlalchemy.sql import func
    return func.now()