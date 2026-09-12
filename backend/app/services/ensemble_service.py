"""
services/ensemble_service.py — Review-level ensemble sentiment calculation.

After all three models have been run, this service aggregates their individual
results into a single ensemble sentiment per review using majority voting.

If all three models disagree (three-way split), a deterministic confidence-based
tie-break selects the sentiment with the highest confidence score.

DO NOT CALL THIS DURING PHASE 3 IMPLEMENTATION.
The ensemble is calculated only after all three model runs are complete.
"""

from datetime import datetime, timezone
from typing import Optional

from app.db.connection import get_db
from app.prompts.sentiment_prompt import PROMPT_VERSION, VALID_SENTIMENTS


# ── Constants ─────────────────────────────────────────────────────────────────

MODELS = ["llama3.1:8b", "qwen2.5:7b", "gemma3:4b"]
ENSEMBLE_COLLECTION = "ensemble_results"
ANALYSIS_COLLECTION = "model_analysis_results"


# ── Core ensemble logic ───────────────────────────────────────────────────────

def compute_ensemble_for_review(
    review_id: str,
    model_results: list[dict],
) -> dict:
    """
    Compute ensemble sentiment for a single review from its model results.

    Parameters
    ----------
    review_id    : The review's unique identifier.
    model_results: List of successful model result dicts (from MongoDB).
                   Each must have: model_name, sentiment, confidence.

    Returns
    -------
    dict with:
        review_id        : str
        ensemble_sentiment: "positive" | "neutral" | "negative"
        agreement_count  : int (1–3) — how many models agreed on winning sentiment
        agreement_rate   : float — agreement_count / total_models_provided
        model_votes      : dict — {model_name: sentiment}
        model_confidences: dict — {model_name: confidence}
        tie_break_used   : bool — True if confidence-based tie-break was needed
        prompt_version   : str
        created_at       : str (ISO 8601 UTC)

    Raises
    ------
    ValueError if model_results is empty or contains invalid sentiments.
    """
    if not model_results:
        raise ValueError(f"No model results provided for review_id={review_id!r}")

    # ── Build vote map ────────────────────────────────────────────────────────
    votes: dict[str, str] = {}          # model_name → sentiment
    confidences: dict[str, float] = {}  # model_name → confidence

    for result in model_results:
        model = result.get("model_name", "unknown")
        sentiment = result.get("sentiment", "").lower()
        confidence = float(result.get("confidence", 0.0))

        if sentiment not in VALID_SENTIMENTS:
            continue  # Skip invalid sentiments (safety guard)

        votes[model] = sentiment
        confidences[model] = confidence

    if not votes:
        raise ValueError(
            f"No valid sentiment votes found for review_id={review_id!r}"
        )

    # ── Majority voting ───────────────────────────────────────────────────────
    # Count how many models voted for each sentiment
    vote_counts: dict[str, int] = {}
    for sentiment in votes.values():
        vote_counts[sentiment] = vote_counts.get(sentiment, 0) + 1

    max_count = max(vote_counts.values())
    winning_sentiments = [s for s, c in vote_counts.items() if c == max_count]

    tie_break_used = False

    if len(winning_sentiments) == 1:
        # Clear majority or unanimous agreement
        ensemble_sentiment = winning_sentiments[0]
    else:
        # Tie: use confidence-based tie-break (deterministic)
        # Among the tied sentiments, pick the one backed by highest total confidence
        tie_break_used = True
        ensemble_sentiment = _confidence_tie_break(
            winning_sentiments, votes, confidences
        )

    # ── Calculate agreement metrics ───────────────────────────────────────────
    agreement_count = vote_counts.get(ensemble_sentiment, 0)
    total_models = len(votes)
    agreement_rate = round(agreement_count / total_models, 4)

    return {
        "review_id":          review_id,
        "ensemble_sentiment": ensemble_sentiment,
        "agreement_count":    agreement_count,
        "agreement_rate":     agreement_rate,
        "model_votes":        votes,
        "model_confidences":  confidences,
        "tie_break_used":     tie_break_used,
        "prompt_version":     PROMPT_VERSION,
        "created_at":         datetime.now(timezone.utc).isoformat(),
    }


def _confidence_tie_break(
    tied_sentiments: list[str],
    votes: dict[str, str],
    confidences: dict[str, float],
) -> str:
    """
    Deterministic tie-break: among tied sentiments, pick the one whose
    supporting models have the highest TOTAL confidence score.

    If still equal (extremely rare), fall back to alphabetical order
    (negative < neutral < positive) for full determinism.
    """
    # Sum confidence for each tied sentiment from the models that voted for it
    sentiment_confidence_totals: dict[str, float] = {s: 0.0 for s in tied_sentiments}
    for model, sentiment in votes.items():
        if sentiment in sentiment_confidence_totals:
            sentiment_confidence_totals[sentiment] += confidences.get(model, 0.0)

    # Pick the highest; break ties alphabetically
    return max(
        tied_sentiments,
        key=lambda s: (sentiment_confidence_totals[s], s),
    )


# ── MongoDB helpers ───────────────────────────────────────────────────────────

def get_successful_results_for_review(review_id: str, prompt_version: str = PROMPT_VERSION) -> list[dict]:
    """
    Fetch all successful model analysis results for a given review from MongoDB.

    Returns a list of result documents (may be empty if no models completed yet).
    """
    db = get_db()
    cursor = db[ANALYSIS_COLLECTION].find(
        {
            "review_id":      review_id,
            "prompt_version": prompt_version,
            "status":         "success",
        },
        projection={"_id": 0, "model_name": 1, "sentiment": 1, "confidence": 1},
    )
    return list(cursor)


def save_ensemble_result(ensemble: dict) -> None:
    """
    Upsert an ensemble result into the ensemble_results collection.

    The upsert key is (review_id, prompt_version) so re-running is safe.
    """
    db = get_db()
    db[ENSEMBLE_COLLECTION].update_one(
        {
            "review_id":      ensemble["review_id"],
            "prompt_version": ensemble["prompt_version"],
        },
        {"$set": ensemble},
        upsert=True,
    )


def run_ensemble_for_all_reviews(prompt_version: str = PROMPT_VERSION) -> dict:
    """
    Calculate and save ensemble sentiment for every review that has results
    from all three models.

    DO NOT CALL THIS DURING IMPLEMENTATION PHASE.

    Returns a summary dict with counts.
    """
    db = get_db()

    # Find all reviews that have successful results from all three models
    pipeline = [
        {
            "$match": {
                "prompt_version": prompt_version,
                "status": "success",
                "model_name": {"$in": MODELS},
            }
        },
        {
            "$group": {
                "_id": "$review_id",
                "model_count": {"$sum": 1},
            }
        },
        {
            "$match": {"model_count": len(MODELS)}
        },
    ]

    eligible_review_ids = [doc["_id"] for doc in db[ANALYSIS_COLLECTION].aggregate(pipeline)]

    processed = 0
    skipped = 0
    errors = 0

    for review_id in eligible_review_ids:
        # Skip if ensemble already exists
        existing = db[ENSEMBLE_COLLECTION].find_one(
            {"review_id": review_id, "prompt_version": prompt_version}
        )
        if existing:
            skipped += 1
            continue

        # Fetch model results
        model_results = get_successful_results_for_review(review_id, prompt_version)

        try:
            ensemble = compute_ensemble_for_review(review_id, model_results)
            save_ensemble_result(ensemble)
            processed += 1
        except (ValueError, Exception) as exc:
            print(f"[ensemble] ERROR for review_id={review_id}: {exc}")
            errors += 1

    summary = {
        "total_eligible": len(eligible_review_ids),
        "processed": processed,
        "skipped_existing": skipped,
        "errors": errors,
    }
    print(f"[ensemble] Complete: {summary}")
    return summary


def create_ensemble_indexes() -> None:
    """
    Create indexes for the ensemble_results collection.
    Called before running ensemble calculations.
    """
    db = get_db()
    collection = db[ENSEMBLE_COLLECTION]

    from pymongo import ASCENDING
    # Unique index per review + prompt_version
    collection.create_index(
        [
            ("review_id",      ASCENDING),
            ("prompt_version", ASCENDING),
        ],
        unique=True,
        name="idx_ensemble_unique_review_prompt",
    )
    # Query index for sentiment distribution analysis
    collection.create_index(
        [("ensemble_sentiment", ASCENDING)],
        name="idx_ensemble_sentiment",
    )
    print("[ensemble] ensemble_results indexes created/verified.")
