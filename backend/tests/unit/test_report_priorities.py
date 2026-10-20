"""Report triage scenarios; run with the backend suite on Azure."""
from datetime import datetime, timezone

import pytest

from app.services.report_analytics import build_topics, compose_document


def feedback(positive=0, negative=0, neutral=0, unclassified=0, topic="Safety"):
    return [{"aspects": {topic: .9}, "sentiment": sentiment}
            for sentiment, count in [("positive", positive), ("negative", negative),
                                     ("neutral", neutral), (None, unclassified)]
            for _ in range(count)]


@pytest.mark.parametrize("counts, expected", [
    ({"positive": 45, "negative": 1, "neutral": 10}, "Validate"),
    ({"positive": 1, "negative": 1}, "Validate"),
    ({"negative": 4}, "Validate"),  # A wholly negative but tiny sample.
    ({"positive": 3, "negative": 2}, "Medium"),
    ({"positive": 8, "negative": 2}, "Medium"),
    ({"positive": 9, "negative": 2}, "Validate"),
    ({"positive": 5, "negative": 5}, "High"),
    ({"positive": 9, "negative": 6}, "High"),
    ({"positive": 10, "negative": 6}, "Medium"),
    ({"positive": 4, "negative": 5}, "Medium"),
    ({"positive": 30, "negative": 2}, "Validate"),
    ({"positive": 20}, "Maintain"),
    ({"unclassified": 12}, "Maintain"),
])
def test_topic_priorities_balance_frequency_proportion_and_sample(counts, expected):
    # Topic names do not themselves justify inflating a severity label.
    for name in ("Safety", "WiFi & Internet"):
        topic = build_topics(feedback(**counts, topic=name))[0]
        assert topic["priority"] == expected
        assert topic["negative"] == counts.get("negative", 0)


def test_unclassified_results_are_disclosed_and_do_not_dilute_known_sentiment():
    topic = build_topics(feedback(positive=5, negative=5, unclassified=100))[0]
    assert topic["priority"] == "High"
    assert "50.0% of 10 recognised sentiment results" in topic["evidence"]
    assert "100 unclassified results excluded" in topic["evidence"]
    unknown = build_topics(feedback(unclassified=10))[0]
    assert "Negative share: not available" in unknown["evidence"]


@pytest.mark.parametrize("scope", ["accommodation", "platform_summary", "university"])
def test_isolated_safety_signal_stays_visible_alongside_dominant_strength(scope):
    reviews = feedback(positive=45, negative=1, neutral=10)
    for index, review in enumerate(reviews):
        review.update(id=index, accommodation_id=1, rating=2 if review["sentiment"] == "negative" else 4,
                      created_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    document = compose_document({"listings": [], "reviews": reviews, "views": [],
                                 "replied": set(range(56))}, scope, 2026, 9,
                                datetime(2026, 10, 13, tzinfo=timezone.utc), "Example")
    action = next(row for row in document["actions"] if row["title"] == "Safety")
    assert action["priority"] == "Validate"
    assert "Promptly review the original feedback" in action["action"]
    assert "If confirmed, inspect" in action["action"]
    assert "1.8% of 56 recognised" in action["evidence"]
    assert any("45 of 56" in strength and "Negative overall results: 1" in strength for strength in document["strengths"])
    assert any("Safety" == row["title"] for row in document["actions"])
    assert any("triage rules" in note for note in document["data_quality"])


def test_repeated_non_safety_concerns_outrank_isolated_safety_signal():
    topics = build_topics(feedback(positive=45, negative=1, neutral=10) +
                          feedback(positive=5, negative=5, topic="WiFi & Internet"))
    assert [(topic["name"], topic["priority"]) for topic in topics] == [
        ("WiFi & Internet", "High"), ("Safety", "Validate")]


def test_sparse_positive_feedback_does_not_become_a_dominant_strength():
    reviews = feedback(positive=2, negative=1)
    for index, review in enumerate(reviews):
        review.update(id=index, accommodation_id=1, rating=3,
                      created_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    document = compose_document({"listings": [], "reviews": reviews, "views": [], "replied": set()},
                                "accommodation", 2026, 9,
                                datetime(2026, 10, 13, tzinfo=timezone.utc), "Example")
    assert document["strengths"] == []
