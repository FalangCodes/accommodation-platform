import re
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import func
from app.models.review import Review, ReviewNLPResult
from app.models.insight import AccommodationInsight

logger = logging.getLogger(__name__)

# ─── Thresholds ───────────────────────────────────────────────────────────────

ASPECT_DETECTION_THRESHOLD = 0.4

MIN_MENTIONS_STUDENT = 3
MIN_MENTIONS_LANDLORD = 2

STUDENT_POSITIVE_THRESHOLD = 0.70
STUDENT_NEGATIVE_THRESHOLD = 0.60
LANDLORD_POSITIVE_THRESHOLD = 0.60
LANDLORD_NEGATIVE_THRESHOLD = 0.50

# ─── Aspect configuration ─────────────────────────────────────────────────────

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

ASPECT_SIGNALS = {
    "wifi and internet": [
        "wifi", "wi-fi", "internet", "connection", "fibre", "fiber",
        "signal", "data", "online", "network", "bandwidth", "router",
        "connectivity", "streaming", "download", "upload", "speed"
    ],
    "safety": [
        "safe", "unsafe", "security", "guard", "gate", "cctv", "camera",
        "robbery", "robbed", "stolen", "dangerous", "crime", "lighting",
        "dark", "locked", "fence", "wall", "patrol", "pepper spray",
        "break-in", "assault", "threat", "secure"
    ],
    "cleanliness": [
        "clean", "dirty", "filthy", "spotless", "hygiene", "dust",
        "mold", "mould", "pest", "cockroach", "rats", "sweep", "mop",
        "tidy", "mess", "rubbish", "trash", "bin", "smell", "odor", "odour"
    ],
    "noise levels": [
        "noise", "noisy", "quiet", "loud", "music", "party", "sleep",
        "study", "disturbance", "bang", "neighbour", "neighbor", "shout",
        "screaming", "bass", "sound", "peaceful", "tranquil", "silent"
    ],
    "landlord responsiveness": [
        "landlord", "owner", "management", "respond", "reply", "ignore",
        "helpful", "unhelpful", "available", "contact", "call", "message",
        "communicate", "phone", "email", "follow up", "reached", "attentive",
        "caretaker", "agent", "unresponsive", "responsive"
    ],
    "water and electricity": [
        "water", "electricity", "power", "load shedding", "loadshedding",
        "blackout", "pressure", "hot water", "geyser", "prepaid", "generator",
        "solar", "inverter", "outage", "cut", "supply", "municipal", "eskom",
        "lights", "taps", "shower", "bath"
    ],
    "maintenance and repairs": [
        "maintenance", "repair", "fix", "broken", "plumbing", "leak",
        "crack", "damage", "weeks", "months", "response time", "handyman",
        "replace", "burst", "fault", "issue", "problem", "attended",
        "pending", "unattended", "ignored", "fixed quickly"
    ],
    "value for money": [
        "price", "expensive", "cheap", "affordable", "value", "worth",
        "money", "cost", "rent", "overpriced", "reasonable", "nsfas",
        "bursary", "budget", "fee", "pay", "charge", "rate", "costly"
    ],
}

# ─── Sentiment label mapping ──────────────────────────────────────────────────

def get_sentiment_label(positive_rate: float) -> str:
    if positive_rate >= 75:
        return "mostly_positive"
    elif positive_rate >= 60:
        return "generally_positive"
    elif positive_rate >= 40:
        return "mixed"
    elif positive_rate >= 25:
        return "generally_negative"
    else:
        return "mostly_negative"


SENTIMENT_DISPLAY = {
    "mostly_positive":    "Mostly Positive",
    "generally_positive": "Generally Positive",
    "mixed":              "Mixed",
    "generally_negative": "Generally Negative",
    "mostly_negative":    "Mostly Negative",
}

# ─── Opinion templates ────────────────────────────────────────────────────────

OPINION_TEMPLATES = {
    "wifi and internet": {
        "mostly_positive":    "Students generally report reliable WiFi at this property{concern}.",
        "generally_positive": "WiFi is generally satisfactory{concern}.",
        "mixed":              "WiFi receives mixed feedback — reliable for some but problematic for others{concern}.",
        "generally_negative": "WiFi reliability is a recurring concern among students{strength}.",
        "mostly_negative":    "Students consistently report significant WiFi problems at this property{strength}.",
    },
    "safety": {
        "mostly_positive":    "Students feel safe at this property and appreciate the security measures in place{concern}.",
        "generally_positive": "Safety is generally rated positively by students{concern}.",
        "mixed":              "Safety perceptions are divided among students{concern}.",
        "generally_negative": "Safety is a notable concern for students at this property{strength}.",
        "mostly_negative":    "Students consistently report feeling unsafe at this property{strength}.",
    },
    "cleanliness": {
        "mostly_positive":    "Students are satisfied with the cleanliness of this property{concern}.",
        "generally_positive": "Cleanliness is generally well maintained{concern}.",
        "mixed":              "Cleanliness receives mixed reviews from students{concern}.",
        "generally_negative": "Cleanliness standards are a concern for many students{strength}.",
        "mostly_negative":    "Students consistently report cleanliness issues at this property{strength}.",
    },
    "noise levels": {
        "mostly_positive":    "Students find this property quiet and conducive to studying{concern}.",
        "generally_positive": "Noise levels are generally manageable for most students{concern}.",
        "mixed":              "Noise levels receive mixed feedback from students{concern}.",
        "generally_negative": "Noise is a recurring complaint among students at this property{strength}.",
        "mostly_negative":    "Students consistently report disruptive noise levels{strength}.",
    },
    "landlord responsiveness": {
        "mostly_positive":    "Students praise the landlord for being approachable and responsive{concern}.",
        "generally_positive": "The landlord is generally responsive to student needs{concern}.",
        "mixed":              "Landlord responsiveness receives mixed feedback from students{concern}.",
        "generally_negative": "Slow landlord response times are a concern for many students{strength}.",
        "mostly_negative":    "Students consistently report difficulty reaching management{strength}.",
    },
    "water and electricity": {
        "mostly_positive":    "Students report reliable water and electricity supply at this property{concern}.",
        "generally_positive": "Utilities are generally reliable with few reported issues{concern}.",
        "mixed":              "Utility reliability receives mixed feedback from students{concern}.",
        "generally_negative": "Water and electricity disruptions are a concern for students{strength}.",
        "mostly_negative":    "Students consistently report significant utility issues at this property{strength}.",
    },
    "maintenance and repairs": {
        "mostly_positive":    "Students are satisfied with how maintenance issues are handled{concern}.",
        "generally_positive": "Maintenance requests are generally attended to in reasonable time{concern}.",
        "mixed":              "Maintenance response times receive mixed reviews from students{concern}.",
        "generally_negative": "Slow maintenance response is a recurring complaint among students{strength}.",
        "mostly_negative":    "Students consistently report unresolved maintenance issues{strength}.",
    },
    "value for money": {
        "mostly_positive":    "Students feel this property offers good value for the price charged{concern}.",
        "generally_positive": "Most students are satisfied with the value offered at this property{concern}.",
        "mixed":              "Value for money receives mixed opinions from students{concern}.",
        "generally_negative": "Many students feel the pricing does not reflect the quality offered{strength}.",
        "mostly_negative":    "Students consistently feel this property is overpriced for what is offered{strength}.",
    },
}

# ─── Recommendation templates ─────────────────────────────────────────────────

RECOMMENDATIONS = {
    "cleanliness": {
        "mostly_negative":    "Students consistently report cleanliness issues. Consider scheduling more frequent cleaning of communal areas and establishing clear standards for room handovers.",
        "generally_negative": "Cleanliness standards need attention. A regular inspection and cleaning schedule could significantly improve student satisfaction.",
        "mixed":              "Cleanliness receives inconsistent feedback. Establishing a reliable cleaning routine would help maintain consistent standards.",
    },
    "safety": {
        "mostly_negative":    "Safety is a critical concern. Urgently review your security infrastructure — consider additional lighting, reinforced access control, and increased security presence.",
        "generally_negative": "Safety concerns are being raised by students. Consider improving lighting, gate security, and perimeter measures.",
        "mixed":              "Safety perceptions are divided. Communicating your security measures more clearly to residents may help address concerns.",
    },
    "noise levels": {
        "mostly_negative":    "Noise is a persistent complaint. Implement and enforce quiet hours, and consider sound insulation improvements.",
        "generally_negative": "Noise disruption is affecting students' ability to study. Clear house rules and enforcement of quiet hours are recommended.",
        "mixed":              "Some students find noise levels disruptive. Clear communal area conduct rules may help.",
    },
    "landlord responsiveness": {
        "mostly_negative":    "Students report significant difficulty reaching management. A dedicated communication channel and committed response time would greatly improve satisfaction.",
        "generally_negative": "Response times are too slow according to students. Set clear expectations around how quickly you will respond to queries and maintenance requests.",
        "mixed":              "Responsiveness is inconsistent. Consider a structured communication system to ensure no student request goes unaddressed.",
    },
    "wifi and internet": {
        "mostly_negative":    "WiFi reliability is your most reported issue. Poor internet directly impacts academic performance. Upgrading to a dedicated fibre line is strongly recommended.",
        "generally_negative": "WiFi problems are affecting students. Consider upgrading your router, adding access points, or switching to a faster ISP.",
        "mixed":              "WiFi performance is inconsistent. A bandwidth management solution or router upgrade during peak hours may resolve the issue.",
    },
    "water and electricity": {
        "mostly_negative":    "Utility disruptions are severely impacting students. Consider installing a backup water tank and an inverter or generator for load shedding.",
        "generally_negative": "Water and electricity issues are being reported. Proactive communication during outages and backup solutions would help.",
        "mixed":              "Utility reliability is inconsistent. Consider backup solutions and communicate planned outages to residents in advance.",
    },
    "maintenance and repairs": {
        "mostly_negative":    "Maintenance response is your most critical issue. Students are waiting weeks for repairs. A dedicated maintenance schedule and tracking system is strongly recommended.",
        "generally_negative": "Maintenance turnaround is too slow. Consider setting a maximum response time commitment and communicating timelines to students.",
        "mixed":              "Maintenance consistency needs improvement. A simple request tracking system would help ensure nothing falls through the cracks.",
    },
    "value for money": {
        "mostly_negative":    "Students do not feel this property offers value for money. Review your pricing against the amenities provided, or invest in facility improvements.",
        "generally_negative": "Value perceptions are negative. Consider either improving facilities or reviewing your pricing structure.",
        "mixed":              "Value perceptions are split. Highlighting your amenities and any recent improvements in your listing may help justify the pricing.",
    },
}

# ─── Clause splitting ─────────────────────────────────────────────────────────

def split_to_clauses(text: str) -> list[str]:
    """Split review text into clauses handling multi-aspect sentences."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    clauses = []
    for sentence in sentences:
        parts = re.split(
            r'\s+(?:but|however|although|yet|while|though|whereas|except|'
            r'despite|still|nevertheless|on the other hand|that said)\s+',
            sentence,
            flags=re.IGNORECASE
        )
        for part in parts:
            part = part.strip().rstrip('.,!?')
            if len(part.split()) >= 5:
                clauses.append(part)
            elif clauses:
                clauses[-1] = clauses[-1] + '. ' + part
    return [c for c in clauses if c]


# ─── Keyword-phrase extraction ────────────────────────────────────────────────

def extract_phrases_for_aspect(
    text: str,
    aspect: str,
    sentiment: str,
    window: int = 9
) -> tuple[list[str], list[str]]:
    """
    Extract short descriptive phrases around signal words for an aspect.
    Returns (strengths, concerns) based on clause-level sentiment.
    """
    signals = ASPECT_SIGNALS.get(aspect, [])
    if not signals:
        return [], []

    clauses = split_to_clauses(text)
    strengths = []
    concerns = []

    for clause in clauses:
        clause_lower = clause.lower()

        # Check if any signal word appears in this clause
        matched = any(signal in clause_lower for signal in signals)
        if not matched:
            continue

        # Extract phrase window around the signal word
        words = clause.split()
        phrase = None
        for i, word in enumerate(words):
            if any(signal in word.lower() for signal in signals):
                start = max(0, i - 1)
                end = min(len(words), i + window)
                phrase = " ".join(words[start:end]).strip('.,!?').capitalize()
                break

        if not phrase or len(phrase.split()) < 3:
            continue

        # Assign to strength or concern based on overall review sentiment
        # Mixed reviews: assign based on clause content heuristics
        negative_signals = [
            "not", "no ", "never", "poor", "bad", "terrible", "awful",
            "slow", "broken", "fails", "cut", "off", "problem", "issue",
            "concern", "unsafe", "dirty", "noisy", "ignore", "expensive",
            "overpriced", "disappoint", "worse", "worst", "useless"
        ]
        positive_signals = [
            "good", "great", "excellent", "fast", "reliable", "clean",
            "safe", "quiet", "responsive", "affordable", "perfect", "love",
            "happy", "satisfied", "always", "consistent", "best", "helpful"
        ]

        clause_lower_check = clause.lower()
        neg_score = sum(1 for s in negative_signals if s in clause_lower_check)
        pos_score = sum(1 for s in positive_signals if s in clause_lower_check)

        cleaned = clean_phrase(phrase)
        if not cleaned:
            continue
        if pos_score > neg_score:
            strengths.append(cleaned)
        elif neg_score > pos_score:
            concerns.append(cleaned)
        else:
            # Use overall review sentiment as tiebreaker
            if sentiment == "positive":
                strengths.append(phrase)
            elif sentiment == "negative":
                concerns.append(phrase)
            # neutral/mixed — skip, not enough signal

    return strengths, concerns

WEAK_STARTS = {"and", "or", "but", "the", "a", "an", "so", "yet", "with", "of", "in", "at", "to", "for"}

def clean_phrase(phrase: str) -> str | None:
    if not phrase:
        return None
    words = phrase.split()
    # Remove leading weak words
    while words and words[0].lower() in WEAK_STARTS:
        words = words[1:]
    if len(words) < 3:
        return None
    return " ".join(words).capitalize()


def deduplicate_phrases(phrases: list[str], max_count: int = 3) -> list[str]:
    """Remove near-duplicate phrases and return top N."""
    seen = []
    for phrase in phrases:
        phrase_words = set(phrase.lower().split())
        is_duplicate = any(
            len(phrase_words & set(s.lower().split())) /
            max(len(phrase_words), len(set(s.lower().split()))) > 0.55
            for s in seen
        )
        if not is_duplicate:
            seen.append(phrase)
        if len(seen) >= max_count:
            break
    return seen


# ─── Aspect sentiment determination ──────────────────────────────────────────

def determine_aspect_sentiment(
    overall_sentiment: str,
    sentiment_score: float,
) -> str:
    """
    Determine aspect-level sentiment using overall review sentiment and confidence.
    Low confidence reviews are labelled mixed regardless.
    """
    if sentiment_score < 0.65:
        return "mixed"
    if overall_sentiment == "positive":
        return "positive"
    if overall_sentiment == "negative":
        return "negative"
    return "mixed"


# ─── Per-review aspect detail extraction ─────────────────────────────────────

def extract_aspect_details(
    aspects: dict,
    review_body: str,
    overall_sentiment: str,
    sentiment_score: float,
) -> dict:
    aspect_details = {}

    detected = {
        aspect: score
        for aspect, score in aspects.items()
        if score >= ASPECT_DETECTION_THRESHOLD
    }

    if not detected:
        return aspect_details

    for aspect in detected:
        signals = ASPECT_SIGNALS.get(aspect, [])
        body_lower = review_body.lower()

        # ── Gate: require at least one signal word to be present ──
        if not any(signal in body_lower for signal in signals):
            continue  # aspect model fired but no actual signal word found — skip

        aspect_sentiment = determine_aspect_sentiment(overall_sentiment, sentiment_score)
        strengths, concerns = extract_phrases_for_aspect(
            review_body, aspect, overall_sentiment
        )

        strengths = deduplicate_phrases(strengths, max_count=3)
        concerns = deduplicate_phrases(concerns, max_count=3)

        aspect_details[aspect] = {
            "aspect_sentiment": aspect_sentiment,
            "strengths": strengths,
            "concerns": concerns,
        }

    return aspect_details


# ─── Opinion generation (Gemini Flash — async, human-quality summaries) ───────

async def generate_opinion(
    aspect: str,
    sentiment_label: str,
    top_strength: str | None,
    top_concern: str | None,
    mention_count: int = 0,
    positive_rate: int = 0,
) -> str:
    """
    Generate a human-sounding 1-sentence opinion for an aspect using Gemini Flash.

    Falls back gracefully to the deterministic template if Gemini is unavailable,
    ensuring insight regeneration never fails due to an AI outage.
    """
    from app.core.config import settings

    # ── Template fallback (always available, zero latency) ────────────────────
    def _template_fallback() -> str:
        templates = OPINION_TEMPLATES.get(aspect, {})
        template = templates.get(sentiment_label, "Students have shared feedback about this aspect.")
        if sentiment_label in ("mostly_positive", "generally_positive"):
            concern_suffix = f", although {top_concern[0].lower() + top_concern[1:]}" if top_concern else ""
            strength_suffix = ""
        elif sentiment_label in ("mostly_negative", "generally_negative"):
            strength_suffix = f", though some students note {top_strength[0].lower() + top_strength[1:]}" if top_strength else ""
            concern_suffix = ""
        else:
            concern_suffix = f", although {top_concern[0].lower() + top_concern[1:]}" if top_concern else ""
            strength_suffix = ""
        return template.format(concern=concern_suffix, strength=strength_suffix)

    # ── Skip Gemini if key is not configured ─────────────────────────────────
    if not settings.GEMINI_API_KEY:
        return _template_fallback()

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        display_name = ASPECT_DISPLAY_NAMES.get(aspect, aspect)

        # Build context for Gemini
        evidence_parts = []
        if top_strength:
            evidence_parts.append(f'Positive evidence: "{top_strength}"')
        if top_concern:
            evidence_parts.append(f'Negative evidence: "{top_concern}"')
        evidence = " | ".join(evidence_parts) if evidence_parts else "No specific evidence phrases available."

        prompt = (
            f"Write exactly ONE concise sentence (max 25 words) summarising student opinions on "
            f"'{display_name}' for a student accommodation listing. "
            f"Overall sentiment: {sentiment_label.replace('_', ' ')} "
            f"({positive_rate}% positive, based on {mention_count} student mentions). "
            f"{evidence}. "
            f"Write in third person. Do not start with 'Students'. Be natural and factual."
        )

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=60,
            ),
        )

        opinion = response.text.strip().strip('"').strip("'")
        if opinion:
            return opinion
        return _template_fallback()

    except Exception as e:
        logger.warning(f"[InsightEngine] Gemini opinion generation failed for '{aspect}': {e} — using template fallback")
        return _template_fallback()


# ─── Cross-review aggregation ─────────────────────────────────────────────────

async def regenerate_accommodation_insights(
    accommodation_id: int,
    db: AsyncSession,
) -> None:
    """
    Aggregate all NLP results for an accommodation into structured insights.
    Upserts accommodation_insights table.
    """
    from sqlalchemy import text
    await db.execute(text("SELECT pg_advisory_xact_lock(193732, :listing)"),
                     {"listing": accommodation_id})
    result = await db.execute(
        select(Review, ReviewNLPResult)
        .outerjoin(ReviewNLPResult, ReviewNLPResult.review_id == Review.id)
        .where(
            Review.accommodation_id == accommodation_id,
            Review.deleted_at == None,
            Review.status.in_(["analysed", "released"])
        )
    )
    rows = result.all()

    total_reviews = len(rows)

    # Aggregate per aspect
    aspect_data: dict = {
        aspect: {
            "mentions": 0,
            "positive": 0,
            "negative": 0,
            "mixed": 0,
            "strengths": [],
            "concerns": [],
        }
        for aspect in ASPECT_SIGNALS.keys()
    }

    for review, nlp in rows:
        if nlp is None:
            continue
        details = getattr(nlp, "aspect_details", None) or extract_aspect_details(
            aspects=nlp.aspects or {}, review_body=review.body,
            overall_sentiment=nlp.sentiment, sentiment_score=nlp.sentiment_score,
        )
        if not details:
            continue
        for aspect, detail in details.items():
            if aspect not in aspect_data:
                continue
            d = aspect_data[aspect]
            d["mentions"] += 1
            sentiment = detail.get("aspect_sentiment", "mixed")
            d[sentiment] = d.get(sentiment, 0) + 1
            d["strengths"].extend(detail.get("strengths", []))
            d["concerns"].extend(detail.get("concerns", []))

    insights = {}
    recommendations = []

    for aspect, data in aspect_data.items():
        mentions = data["mentions"]
        if mentions < MIN_MENTIONS_LANDLORD:
            continue

        positive = data.get("positive", 0)
        negative = data.get("negative", 0)
        total = mentions

        positive_rate = round(positive / total * 100) if total > 0 else 0
        negative_rate = round(negative / total * 100) if total > 0 else 0

        sentiment_label = get_sentiment_label(positive_rate)

        # Deduplicate evidence
        top_strengths = deduplicate_phrases(data["strengths"], max_count=3)
        top_concerns = deduplicate_phrases(data["concerns"], max_count=3)

        # Generate opinion (async — uses Gemini Flash with template fallback)
        overall_opinion = await generate_opinion(
            aspect,
            sentiment_label,
            top_strengths[0] if top_strengths else None,
            top_concerns[0] if top_concerns else None,
            mention_count=mentions,
            positive_rate=positive_rate,
        )

        # Star rating
        star_rating = round((positive_rate / 100) * 5, 1)

        # Student visibility
        show_to_students = mentions >= MIN_MENTIONS_STUDENT

        # Student sentiment label (stricter thresholds)
        if positive_rate >= STUDENT_POSITIVE_THRESHOLD * 100:
            student_sentiment = "mostly_positive"
        elif negative_rate >= STUDENT_NEGATIVE_THRESHOLD * 100:
            student_sentiment = "mostly_negative"
        else:
            student_sentiment = "mixed"

        insights[aspect] = {
            "display_name": ASPECT_DISPLAY_NAMES.get(aspect, aspect),
            "sentiment_label": SENTIMENT_DISPLAY[sentiment_label],
            "student_sentiment": SENTIMENT_DISPLAY.get(student_sentiment, "Mixed"),
            "star_rating": star_rating,
            "overall_opinion": overall_opinion,
            "strengths": top_strengths,
            "concerns": top_concerns,
            "mention_count": mentions,
            "positive_rate": positive_rate,
            "negative_rate": negative_rate,
            "show_to_students": show_to_students,
            "overall_sentiment": sentiment_label,
        }

        # Recommendations for landlords
        if sentiment_label in ("mostly_negative", "generally_negative", "mixed"):
            rec_templates = RECOMMENDATIONS.get(aspect, {})
            rec_text = rec_templates.get(sentiment_label)
            if rec_text:
                recommendations.append({
                    "aspect": aspect,
                    "display_name": ASPECT_DISPLAY_NAMES.get(aspect, aspect),
                    "priority": "high" if sentiment_label == "mostly_negative" else "medium",
                    "recommendation": rec_text,
                    "positive_rate": positive_rate,
                    "mention_count": mentions,
                })

    # Sort recommendations by priority
    recommendations.sort(key=lambda x: x["priority"] == "high", reverse=True)

    # Upsert
    from sqlalchemy.dialects.postgresql import insert as pg_insert
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
            "generated_at": func.now(),
        }
    )
    await db.execute(stmt)
    await db.commit()
    print(f"Insights regenerated for accommodation {accommodation_id}")