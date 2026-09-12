"""
services/sentiment_index_service.py — Daily product-level sentiment index.

Pipeline:
    sentiment_ensemble + reviews
        ↓  (join on review_id to get product_id + review_date)
    Group by (product_id, review_date)
        ↓  (aggregate ensemble_score, confidence, agreement)
    Daily product sentiment index
        ↓  (lag-1 per product)
    sentiment_indexes collection

NO Ollama calls. NO LLM calls. Pure MongoDB → Python → MongoDB.

Important design notes:
- Sparse data: only create records where reviews exist. Never fill missing
  dates with zero (zero = neutral sentiment; missing = no reviews).
- lag1_sentiment is always per-product, never cross-product.
- First observation per product always has lag1_sentiment = None.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from pymongo import ASCENDING

from app.db.connection import get_db


# ── Constants ─────────────────────────────────────────────────────────────────

ENSEMBLE_COLLECTION = "sentiment_ensemble"
REVIEWS_COLLECTION  = "reviews"
INDEX_COLLECTION    = "sentiment_indexes"
PROMPT_VERSION      = "v1"


# ── Index creation ────────────────────────────────────────────────────────────

def create_sentiment_index_indexes() -> None:
    """
    Create/verify MongoDB indexes on sentiment_indexes.
    Idempotent — safe to call multiple times.
    """
    db = get_db()
    col = db[INDEX_COLLECTION]

    # Unique key: one record per (product_id, date)
    col.create_index(
        [("product_id", ASCENDING), ("date", ASCENDING)],
        unique=True,
        name="idx_si_unique_product_date",
    )
    # Fast lookup by product
    col.create_index(
        [("product_id", ASCENDING)],
        name="idx_si_product_id",
    )
    # Fast lookup/sort by date
    col.create_index(
        [("date", ASCENDING)],
        name="idx_si_date",
    )
    print("[sentiment_index] sentiment_indexes indexes created/verified.")


# ── Data loading ──────────────────────────────────────────────────────────────

def load_ensemble_with_dates() -> tuple[list[dict], dict]:
    """
    Load all sentiment_ensemble records and join with reviews to get review_date
    and validate product_id consistency.

    Returns
    -------
    (valid_records, validation_summary)

    valid_records: list of dicts, each with:
        review_id, product_id, review_date (YYYY-MM-DD),
        ensemble_score, average_confidence, model_agreement

    validation_summary: dict with counts:
        ensemble_total, matched, missing_review, product_mismatch, invalid_score
    """
    db = get_db()

    # Load all ensemble records
    ensemble_docs = list(db[ENSEMBLE_COLLECTION].find(
        {},
        projection={
            "_id":               0,
            "review_id":         1,
            "product_id":        1,
            "ensemble_score":    1,
            "average_confidence": 1,
            "model_agreement":   1,
        },
    ))

    # Build a lookup map: review_id → reviews doc
    review_docs = list(db[REVIEWS_COLLECTION].find(
        {},
        projection={
            "_id":        0,
            "review_id":  1,
            "product_id": 1,
            "review_date": 1,
        },
    ))
    review_map: dict[str, dict] = {r["review_id"]: r for r in review_docs}

    # Validation counters
    n_ensemble    = len(ensemble_docs)
    n_matched     = 0
    n_missing     = 0
    n_mismatch    = 0
    n_invalid     = 0

    valid_records: list[dict] = []

    for edoc in ensemble_docs:
        rid = edoc["review_id"]

        # Join with reviews
        rdoc = review_map.get(rid)
        if rdoc is None:
            print(f"  [validation] WARNING: review_id={rid!r} not found in reviews collection")
            n_missing += 1
            continue

        # Validate product_id consistency
        e_pid = str(edoc.get("product_id", "")).strip()
        r_pid = str(rdoc.get("product_id", "")).strip()
        if e_pid != r_pid:
            print(
                f"  [validation] WARNING: product_id mismatch for review_id={rid!r}: "
                f"ensemble={e_pid!r} vs reviews={r_pid!r} — using reviews.product_id"
            )
            n_mismatch += 1
            # Use reviews.product_id as source of truth; don't silently overwrite

        # Validate ensemble_score
        score = edoc.get("ensemble_score")
        if score is None or not isinstance(score, (int, float)):
            print(f"  [validation] WARNING: review_id={rid!r} has invalid ensemble_score={score!r} — SKIPPING")
            n_invalid += 1
            continue
        score = float(score)
        if not (-1.0 <= score <= 1.0):
            print(f"  [validation] WARNING: review_id={rid!r} ensemble_score={score} out of range — SKIPPING")
            n_invalid += 1
            continue

        # Validate review_date
        review_date = rdoc.get("review_date", "")
        if not review_date:
            print(f"  [validation] WARNING: review_id={rid!r} has no review_date — SKIPPING")
            n_invalid += 1
            continue

        n_matched += 1
        valid_records.append({
            "review_id":          rid,
            "product_id":         r_pid,        # use reviews as source of truth
            "review_date":        review_date,   # YYYY-MM-DD
            "ensemble_score":     score,
            "average_confidence": float(edoc.get("average_confidence", 0.0)),
            "model_agreement":    bool(edoc.get("model_agreement", False)),
        })

    validation_summary = {
        "ensemble_total":    n_ensemble,
        "matched":           n_matched,
        "missing_review":    n_missing,
        "product_mismatch":  n_mismatch,
        "invalid_score":     n_invalid,
    }

    return valid_records, validation_summary


# ── Daily aggregation ─────────────────────────────────────────────────────────

def _score_to_label(score: float) -> str:
    """Convert a numerical score to a sentiment label."""
    if score > 0:
        return "positive"
    elif score < 0:
        return "negative"
    else:
        return "neutral"


def aggregate_daily_sentiment(valid_records: list[dict]) -> list[dict]:
    """
    Aggregate valid review records into daily (product_id, date) sentiment indexes.

    For each (product_id, review_date):
        daily_sentiment_score = mean(ensemble_score)
        daily_sentiment       = label derived from score
        review_count          = number of reviews
        average_confidence    = mean(average_confidence)
        agreement_rate        = count(model_agreement=True) / total

    Returns a flat list of daily index dicts (no lag yet, no MongoDB ids).
    """
    # Group by (product_id, review_date)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for rec in valid_records:
        key = (rec["product_id"], rec["review_date"])
        groups[key].append(rec)

    daily_records: list[dict] = []

    for (product_id, date), reviews in groups.items():
        n = len(reviews)

        scores       = [r["ensemble_score"]     for r in reviews]
        confidences  = [r["average_confidence"] for r in reviews]
        agreements   = [r["model_agreement"]    for r in reviews]

        daily_score      = sum(scores) / n
        avg_confidence   = sum(confidences) / n
        agreement_rate   = sum(1 for a in agreements if a) / n

        daily_records.append({
            "product_id":           product_id,
            "date":                 date,
            "daily_sentiment_score": round(daily_score, 6),
            "daily_sentiment":       _score_to_label(daily_score),
            "review_count":          n,
            "average_confidence":    round(avg_confidence, 6),
            "agreement_rate":        round(agreement_rate, 6),
            # lag1_sentiment added in next step
        })

    return daily_records


# ── Lag-1 calculation ─────────────────────────────────────────────────────────

def add_lag1_sentiment(daily_records: list[dict]) -> list[dict]:
    """
    Add lag1_sentiment to each daily record.

    For each product independently:
        - Sort observations by date (ascending)
        - lag1_sentiment(t) = daily_sentiment_score(t-1)
        - First observation for each product → lag1_sentiment = None

    IMPORTANT:
        - Lag is computed only within each product's own time series.
        - It is NEVER computed across different products.
        - None (not 0) for the first observation.
    """
    # Group by product_id
    by_product: dict[str, list[dict]] = defaultdict(list)
    for rec in daily_records:
        by_product[rec["product_id"]].append(rec)

    result: list[dict] = []

    for product_id, records in by_product.items():
        # Sort by date (YYYY-MM-DD strings sort correctly lexicographically)
        records.sort(key=lambda r: r["date"])

        for i, rec in enumerate(records):
            if i == 0:
                rec["lag1_sentiment"] = None   # First observation has no lag
            else:
                rec["lag1_sentiment"] = records[i - 1]["daily_sentiment_score"]
            result.append(rec)

    return result


# ── Persistence ───────────────────────────────────────────────────────────────

def upsert_daily_record(doc: dict) -> None:
    """
    Upsert a single daily sentiment index record into sentiment_indexes.
    Key: (product_id, date) — idempotent.
    """
    db = get_db()
    db[INDEX_COLLECTION].update_one(
        {"product_id": doc["product_id"], "date": doc["date"]},
        {"$set": doc},
        upsert=True,
    )


def bulk_upsert_daily_records(records: list[dict]) -> None:
    """
    Upsert all daily records — adds created_at timestamp.
    Uses individual upserts for simplicity and idempotency.
    """
    now = datetime.now(timezone.utc).isoformat()
    for rec in records:
        rec["created_at"] = now
        upsert_daily_record(rec)


# ── Post-run validation ───────────────────────────────────────────────────────

def validate_output() -> dict:
    """
    Validate the sentiment_indexes collection after processing.

    Checks:
    1. No duplicate (product_id, date) pairs
    2. All daily_sentiment_score in [-1, 1]
    3. All agreement_rate in [0, 1]
    4. All average_confidence in [0, 1]
    5. lag1_sentiment = null for first observation of each product
    6. lag1_sentiment never crosses products

    Returns a dict with validation results.
    """
    db = get_db()
    col = db[INDEX_COLLECTION]

    total = col.count_documents({})

    # Check score range
    out_of_range_score = col.count_documents({
        "$or": [
            {"daily_sentiment_score": {"$gt": 1.0}},
            {"daily_sentiment_score": {"$lt": -1.0}},
        ]
    })

    # Check confidence range
    out_of_range_conf = col.count_documents({
        "$or": [
            {"average_confidence": {"$gt": 1.0}},
            {"average_confidence": {"$lt": 0.0}},
        ]
    })

    # Check agreement_rate range
    out_of_range_agr = col.count_documents({
        "$or": [
            {"agreement_rate": {"$gt": 1.0}},
            {"agreement_rate": {"$lt": 0.0}},
        ]
    })

    # Distinct products and date range
    products  = col.distinct("product_id")
    all_dates = col.distinct("date")
    date_min  = min(all_dates) if all_dates else None
    date_max  = max(all_dates) if all_dates else None

    # Count lag1 nulls vs non-nulls
    lag1_null    = col.count_documents({"lag1_sentiment": None})
    lag1_non_null = col.count_documents({"lag1_sentiment": {"$ne": None}})

    # Check for duplicates using aggregation
    pipeline = [
        {"$group": {"_id": {"product_id": "$product_id", "date": "$date"}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
        {"$count": "duplicates"},
    ]
    dup_result = list(col.aggregate(pipeline))
    duplicates = dup_result[0]["duplicates"] if dup_result else 0

    # Verify first observation per product has lag1_sentiment = null
    products_first_ok = 0
    products_first_fail = 0
    for pid in products:
        first = col.find_one(
            {"product_id": pid},
            sort=[("date", ASCENDING)],
        )
        if first and first.get("lag1_sentiment") is None:
            products_first_ok += 1
        else:
            products_first_fail += 1

    return {
        "total_records":          total,
        "n_products":             len(products),
        "date_min":               date_min,
        "date_max":               date_max,
        "lag1_null_count":        lag1_null,
        "lag1_non_null_count":    lag1_non_null,
        "duplicates":             duplicates,
        "out_of_range_score":     out_of_range_score,
        "out_of_range_conf":      out_of_range_conf,
        "out_of_range_agr":       out_of_range_agr,
        "first_obs_lag_null_ok":  products_first_ok,
        "first_obs_lag_null_fail": products_first_fail,
    }
