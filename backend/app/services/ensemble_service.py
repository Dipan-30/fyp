"""
services/ensemble_service.py — Review-level ensemble sentiment calculation.

Takes the already-stored results from model_analysis_results (3000 documents:
1000 per model × 3 models) and produces ONE ensemble document per review in the
sentiment_ensemble collection.

Ensemble logic:
  - Sentiment mapped to numerical scores: positive=+1, neutral=0, negative=-1
  - Majority voting selects ensemble_sentiment
  - Three-way tie (pos/neu/neg) → resolved by highest-confidence model
  - ensemble_score  = average of the three numerical sentiment scores
  - average_confidence = average of the three model confidence values

DO NOT call Ollama. DO NOT modify model_analysis_results.
This module only reads LLM results and writes ensemble documents.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pymongo import ASCENDING

from app.db.connection import get_db

# ── Constants ─────────────────────────────────────────────────────────────────

MODELS = ["llama3.1:8b", "qwen2.5:7b", "gemma3:4b"]

# Short alias used as a key prefix in ensemble documents (same order as MODELS)
MODEL_ALIASES = {
    "llama3.1:8b": "llama",
    "qwen2.5:7b":  "qwen",
    "gemma3:4b":   "gemma",
}

ANALYSIS_COLLECTION = "model_analysis_results"
ENSEMBLE_COLLECTION = "sentiment_ensemble"

PROMPT_VERSION = "v1"

# Numerical mapping for sentiment
SENTIMENT_SCORE: dict[str, float] = {
    "positive": 1.0,
    "neutral":  0.0,
    "negative": -1.0,
}

VALID_SENTIMENTS = set(SENTIMENT_SCORE.keys())


# ── Index creation ────────────────────────────────────────────────────────────

def create_ensemble_indexes() -> None:
    """
    Create/verify indexes on the sentiment_ensemble collection.
    Idempotent — safe to call multiple times.
    """
    db = get_db()
    col = db[ENSEMBLE_COLLECTION]

    # Unique key: one ensemble doc per (review_id, prompt_version)
    col.create_index(
        [("review_id", ASCENDING), ("prompt_version", ASCENDING)],
        unique=True,
        name="idx_ensemble_unique_review_prompt",
    )
    # Sentiment distribution queries
    col.create_index(
        [("ensemble_sentiment", ASCENDING)],
        name="idx_ensemble_sentiment",
    )
    # Product-level aggregation
    col.create_index(
        [("product_id", ASCENDING)],
        name="idx_ensemble_product_id",
    )
    print("[ensemble] sentiment_ensemble indexes created/verified.")


# ── Data loading ──────────────────────────────────────────────────────────────

def load_all_review_ids(prompt_version: str = PROMPT_VERSION) -> list[str]:
    """
    Return a sorted list of all distinct review_ids that have at least one
    successful result in model_analysis_results.
    """
    db = get_db()
    ids = db[ANALYSIS_COLLECTION].distinct(
        "review_id",
        {"prompt_version": prompt_version, "status": "success"},
    )
    return sorted(ids, key=lambda x: str(x))


def load_model_results_for_review(
    review_id: str,
    prompt_version: str = PROMPT_VERSION,
) -> dict[str, dict]:
    """
    Fetch successful results for all three models for a given review.

    Returns a dict: {model_name: {sentiment, confidence, product_id}} 
    Only includes models whose results exist and have status='success'.
    """
    db = get_db()
    cursor = db[ANALYSIS_COLLECTION].find(
        {
            "review_id":      review_id,
            "prompt_version": prompt_version,
            "status":         "success",
            "model_name":     {"$in": MODELS},
        },
        projection={
            "_id":        0,
            "model_name": 1,
            "sentiment":  1,
            "confidence": 1,
            "product_id": 1,
        },
    )
    results: dict[str, dict] = {}
    for doc in cursor:
        model = doc["model_name"]
        results[model] = {
            "sentiment":  doc.get("sentiment", "").lower(),
            "confidence": float(doc.get("confidence", 0.0)),
            "product_id": doc.get("product_id", ""),
        }
    return results


# ── Core ensemble logic ───────────────────────────────────────────────────────

def compute_ensemble(
    review_id: str,
    model_results: dict[str, dict],
    prompt_version: str = PROMPT_VERSION,
) -> dict:
    """
    Compute the ensemble document for one review.

    Parameters
    ----------
    review_id    : The review's unique ID.
    model_results: {model_name: {sentiment, confidence, product_id}}
                   Must contain all three models.

    Returns
    -------
    dict ready for upsert into sentiment_ensemble.

    Raises
    ------
    ValueError if any model's sentiment is invalid.
    """
    # ── Validate each model result ────────────────────────────────────────────
    for model in MODELS:
        result = model_results.get(model, {})
        sentiment = result.get("sentiment", "")
        if sentiment not in VALID_SENTIMENTS:
            raise ValueError(
                f"review_id={review_id!r}: model {model!r} has invalid sentiment {sentiment!r}"
            )

    llama_result = model_results["llama3.1:8b"]
    qwen_result  = model_results["qwen2.5:7b"]
    gemma_result = model_results["gemma3:4b"]

    llama_sentiment  = llama_result["sentiment"]
    qwen_sentiment   = qwen_result["sentiment"]
    gemma_sentiment  = gemma_result["sentiment"]

    llama_confidence = llama_result["confidence"]
    qwen_confidence  = qwen_result["confidence"]
    gemma_confidence = gemma_result["confidence"]

    product_id = llama_result.get("product_id") or qwen_result.get("product_id") or ""

    # ── Numerical scores ──────────────────────────────────────────────────────
    llama_score = SENTIMENT_SCORE[llama_sentiment]
    qwen_score  = SENTIMENT_SCORE[qwen_sentiment]
    gemma_score = SENTIMENT_SCORE[gemma_sentiment]

    ensemble_score    = round((llama_score + qwen_score + gemma_score) / 3, 6)
    average_confidence = round((llama_confidence + qwen_confidence + gemma_confidence) / 3, 6)

    # ── Majority voting ───────────────────────────────────────────────────────
    sentiments = [llama_sentiment, qwen_sentiment, gemma_sentiment]
    vote_counts: dict[str, int] = {}
    for s in sentiments:
        vote_counts[s] = vote_counts.get(s, 0) + 1

    max_count = max(vote_counts.values())
    winning = [s for s, c in vote_counts.items() if c == max_count]

    tie_break_used = False

    if len(winning) == 1:
        ensemble_sentiment = winning[0]
    else:
        # Three-way tie: positive + neutral + negative (each has count=1)
        # Use the model with the highest confidence to break the tie.
        tie_break_used = True
        model_conf_pairs = [
            (llama_sentiment, llama_confidence),
            (qwen_sentiment,  qwen_confidence),
            (gemma_sentiment, gemma_confidence),
        ]
        # Pick sentiment of the model with highest confidence;
        # break ties deterministically by alphabetical sentiment name.
        ensemble_sentiment = max(
            model_conf_pairs,
            key=lambda pair: (pair[1], pair[0]),  # (confidence, sentiment_name)
        )[0]

    # ── Agreement metrics ─────────────────────────────────────────────────────
    agreement_count = vote_counts.get(ensemble_sentiment, 0)
    model_agreement = (agreement_count == 3)

    return {
        "review_id":   review_id,
        "product_id":  product_id,

        "llama_sentiment":  llama_sentiment,
        "llama_confidence": llama_confidence,

        "qwen_sentiment":   qwen_sentiment,
        "qwen_confidence":  qwen_confidence,

        "gemma_sentiment":  gemma_sentiment,
        "gemma_confidence": gemma_confidence,

        "ensemble_sentiment": ensemble_sentiment,
        "ensemble_score":     ensemble_score,

        "average_confidence": average_confidence,

        "model_agreement": model_agreement,
        "agreement_count": agreement_count,

        "tie_break_used": tie_break_used,

        "prompt_version": prompt_version,
        "created_at":     datetime.now(timezone.utc).isoformat(),
    }


# ── Persistence ───────────────────────────────────────────────────────────────

def save_ensemble(doc: dict) -> None:
    """
    Upsert one ensemble document into sentiment_ensemble.
    Key: (review_id, prompt_version) — idempotent.
    """
    db = get_db()
    db[ENSEMBLE_COLLECTION].update_one(
        {"review_id": doc["review_id"], "prompt_version": doc["prompt_version"]},
        {"$set": doc},
        upsert=True,
    )


def ensemble_exists(review_id: str, prompt_version: str = PROMPT_VERSION) -> bool:
    """Return True if a successful ensemble document already exists for this review."""
    db = get_db()
    return (
        db[ENSEMBLE_COLLECTION].find_one(
            {"review_id": review_id, "prompt_version": prompt_version},
            projection={"_id": 1},
        )
        is not None
    )


# ── Validation helper ─────────────────────────────────────────────────────────

def validate_completeness(
    prompt_version: str = PROMPT_VERSION,
) -> tuple[list[str], dict[str, list[str]]]:
    """
    Check that every review in model_analysis_results has all three model results.

    Returns
    -------
    (complete_ids, incomplete_map)
        complete_ids   : list of review_ids that have all 3 models
        incomplete_map : {review_id: [missing_model, ...]}
    """
    db = get_db()

    # Aggregate: for each review_id, collect which models have a success record
    pipeline = [
        {"$match": {"prompt_version": prompt_version, "status": "success", "model_name": {"$in": MODELS}}},
        {"$group": {"_id": "$review_id", "models": {"$addToSet": "$model_name"}}},
    ]
    all_groups = list(db[ANALYSIS_COLLECTION].aggregate(pipeline))

    complete_ids: list[str] = []
    incomplete_map: dict[str, list[str]] = {}

    model_set = set(MODELS)
    for grp in all_groups:
        rid = grp["_id"]
        found = set(grp["models"])
        missing = sorted(model_set - found)
        if missing:
            incomplete_map[str(rid)] = missing
        else:
            complete_ids.append(str(rid))

    complete_ids.sort()
    return complete_ids, incomplete_map
