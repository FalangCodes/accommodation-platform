from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import pipeline

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading sentiment model...")
    ml_models["sentiment"] = pipeline(
        "sentiment-analysis",
        model="cardiffnlp/twitter-roberta-base-sentiment-latest",
        truncation=True,
        max_length=512
    )
    print("Sentiment model loaded.")
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

    text = request.text[:1000]  # Hard cap before tokenisation

    # Sentiment
    sentiment_result = ml_models["sentiment"](text)[0]
    sentiment_label = sentiment_result["label"].lower()  # positive/neutral/negative
    sentiment_score = float(sentiment_result["score"])

    # Toxicity
    toxicity_result = ml_models["toxicity"](text)[0]
    is_toxic = toxicity_result["label"] == "toxic" and toxicity_result["score"] > 0.75
    toxicity_score = float(toxicity_result["score"]) if toxicity_result["label"] == "toxic" else 0.0

    # Aspect extraction — returns dict of {label: score}
    aspect_result = ml_models["aspects"](text, ASPECT_LABELS, multi_label=True)
    aspects = {
        label: round(float(score), 4)
        for label, score in zip(aspect_result["labels"], aspect_result["scores"])
    }

    return {
        "review_id": request.review_id,
        "sentiment": sentiment_label,
        "sentiment_score": sentiment_score,
        "is_toxic": is_toxic,
        "toxicity_score": toxicity_score,
        "aspects": aspects
    }