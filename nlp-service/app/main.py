from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import pipeline
import re

class SentenceScoreRequest(BaseModel):
    sentence: str
    aspect: str

class SentimentRequest(BaseModel):
    text: str

ml_models = {}

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


def split_to_clauses(text: str) -> list[str]:
    """Split review text into clauses handling multi-aspect sentences."""
    # First split by sentence endings
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    clauses = []
    for sentence in sentences:
        # Split on contrast/conjunction markers
        parts = re.split(
            r'\s+(?:but|however|although|yet|while|though|whereas|except|despite|still|nevertheless)\s+',
            sentence,
            flags=re.IGNORECASE
        )
        for part in parts:
            part = part.strip().rstrip('.,!?')
            if len(part.split()) >= 4:
                clauses.append(part)
            elif clauses:
                # Too short to stand alone — append to previous clause
                clauses[-1] = clauses[-1] + '. ' + part
    return [c for c in clauses if c]


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading HuggingFace models...")

    ml_models["sentiment"] = pipeline(
        "sentiment-analysis",
        model="cardiffnlp/twitter-roberta-base-sentiment-latest",
        truncation=True,
        max_length=512
    )
    print("Sentiment model loaded.")

    ml_models["toxicity"] = pipeline(
        "text-classification",
        model="unitary/toxic-bert",
        truncation=True,
        max_length=512
    )
    print("Toxicity model loaded.")

    ml_models["aspects"] = pipeline(
        "zero-shot-classification",
        model="valhalla/distilbart-mnli-12-3",
        truncation=True,
    )
    print("Aspect model loaded.")

    print("All models loaded successfully.")
    yield
    ml_models.clear()


app = FastAPI(title="Accommodation NLP Engine", lifespan=lifespan)


class ReviewRequest(BaseModel):
    review_id: int
    text: str


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "models_loaded": list(ml_models.keys())
    }


@app.post("/analyze")
async def analyze_review(request: ReviewRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Review text cannot be empty")

    text = request.text[:1000]

    # Overall sentiment
    sentiment_result = ml_models["sentiment"](text)[0]
    sentiment_label = sentiment_result["label"].lower()
    sentiment_score = float(sentiment_result["score"])

    # Toxicity
    is_toxic = False
    toxicity_score = 0.0
    if "toxicity" in ml_models:
        toxicity_result = ml_models["toxicity"](text)[0]
        is_toxic = toxicity_result["label"] == "toxic" and toxicity_result["score"] > 0.75
        toxicity_score = float(toxicity_result["score"]) if toxicity_result["label"] == "toxic" else 0.0

    # Aspects
    aspects = {}
    if "aspects" in ml_models:
        aspect_result = ml_models["aspects"](text, ASPECT_LABELS, multi_label=True)
        aspects = {
            label: round(float(score), 4)
            for label, score in zip(aspect_result["labels"], aspect_result["scores"])
        }

    # Clause segmentation — new
    clauses = split_to_clauses(text)

    return {
        "review_id": request.review_id,
        "sentiment": sentiment_label,
        "sentiment_score": sentiment_score,
        "is_toxic": is_toxic,
        "toxicity_score": toxicity_score,
        "aspects": aspects,
        "sentences": clauses,  # ← new field
    }

@app.post("/score_sentence")
async def score_sentence(request: SentenceScoreRequest):
    """Score relevance of a sentence to an aspect using zero-shot classification."""
    if not request.sentence.strip():
        return {"score": 0.0}
    result = ml_models["aspects"](
        request.sentence,
        [request.aspect],
        multi_label=False
    )
    return {"score": round(float(result["scores"][0]), 4)}

@app.post("/sentiment")
async def get_sentiment(request: SentimentRequest):
    """Get sentiment for a short piece of text."""
    if not request.text.strip():
        return {"sentiment": "neutral", "score": 0.0}
    result = ml_models["sentiment"](request.text[:512])[0]
    return {
        "sentiment": result["label"].lower(),
        "score": round(float(result["score"]), 4)
    }