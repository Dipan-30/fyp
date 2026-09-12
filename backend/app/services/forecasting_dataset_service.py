"""
services/forecasting_dataset_service.py — Weekly store-wide forecasting dataset builder.

Pipeline:
    1. Read 'sales' collection
       → Group by ISO week (e.g. '2023-W26')
       → Calculate weekly_sales = sum(quantity), transaction_count, weekly_revenue
    2. Read 'sentiment_indexes' collection
       → Group by ISO week
       → Calculate review-weighted:
           weekly_sentiment = SUM(daily_sentiment_score * review_count) / SUM(review_count)
           weekly_review_count = SUM(review_count)
           weekly_average_confidence = SUM(average_confidence * review_count) / SUM(review_count)
           weekly_agreement_rate = SUM(agreement_rate * review_count) / SUM(review_count)
    3. Construct continuous chronological ISO week grid covering min_week to max_week
    4. Compute lag-1 weekly sentiment (week t gets week t-1 sentiment; first week is None)
    5. Bulk upsert into 'forecasting_dataset' collection (unique on 'week')
    6. Validate all constraints and spot check against source collections

NO Ollama calls. NO LLM calls. Pure MongoDB → Python → MongoDB.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pymongo import ASCENDING, UpdateOne

from app.db.connection import get_db


# ── Constants ─────────────────────────────────────────────────────────────────

SALES_COLLECTION       = "sales"
SENTIMENT_INDEX_COL    = "sentiment_indexes"
FORECASTING_COLLECTION = "forecasting_dataset"


# ── ISO Week Helper Functions ─────────────────────────────────────────────────

def parse_iso_week(date_str: str) -> Tuple[str, str, str, int, int]:
    """
    Parse a YYYY-MM-DD date string into ISO week components.
    Returns:
        (week_str, week_start_date, week_end_date, iso_year, iso_week)
    Example:
        '2023-06-26' -> ('2023-W26', '2023-06-26', '2023-07-02', 2023, 26)
    """
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    iso_year, iso_week, _ = d.isocalendar()
    week_str = f"{iso_year}-W{iso_week:02d}"
    start_d = date.fromisocalendar(iso_year, iso_week, 1).strftime("%Y-%m-%d")
    end_d = date.fromisocalendar(iso_year, iso_week, 7).strftime("%Y-%m-%d")
    return week_str, start_d, end_d, iso_year, iso_week


def get_week_boundaries(week_str: str) -> Tuple[str, str]:
    """
    Given an ISO week string 'YYYY-Www', returns (week_start_date, week_end_date).
    """
    parts = week_str.split("-W")
    year = int(parts[0])
    week = int(parts[1])
    start_d = date.fromisocalendar(year, week, 1).strftime("%Y-%m-%d")
    end_d = date.fromisocalendar(year, week, 7).strftime("%Y-%m-%d")
    return start_d, end_d


def generate_iso_week_grid(start_week_str: str, end_week_str: str) -> List[str]:
    """
    Generate an ordered list of continuous ISO weeks from start_week_str to end_week_str inclusive.
    """
    s_parts = start_week_str.split("-W")
    e_parts = end_week_str.split("-W")
    cur_date = date.fromisocalendar(int(s_parts[0]), int(s_parts[1]), 1)
    end_date = date.fromisocalendar(int(e_parts[0]), int(e_parts[1]), 1)

    grid = []
    from datetime import timedelta
    while cur_date <= end_date:
        y, w, _ = cur_date.isocalendar()
        grid.append(f"{y}-W{w:02d}")
        cur_date += timedelta(days=7)
    return grid


# ── MongoDB Index Management ──────────────────────────────────────────────────

def create_forecasting_dataset_indexes() -> None:
    """
    Create unique index on 'week' in forecasting_dataset collection.
    Idempotent.
    """
    db = get_db()
    col = db[FORECASTING_COLLECTION]
    col.create_index(
        [("week", ASCENDING)],
        unique=True,
        name="idx_fd_unique_week",
    )
    col.create_index(
        [("week_start_date", ASCENDING)],
        name="idx_fd_week_start_date",
    )


# ── Step 1: Aggregate Sales by ISO Week ────────────────────────────────────────

def aggregate_weekly_sales() -> Dict[str, Dict[str, Any]]:
    """
    Read all records from sales collection and aggregate by ISO week.
    Returns a dict keyed by week_str:
        {
            "2023-W26": {
                "weekly_sales": 39,
                "transaction_count": 15,
                "weekly_revenue": 10423.5,
                "week_start_date": "2023-06-26",
                "week_end_date": "2023-07-02"
            },
            ...
        }
    """
    db = get_db()
    sales_docs = list(db[SALES_COLLECTION].find({}, {
        "purchase_date": 1,
        "quantity": 1,
        "purchase_price": 1,
    }))

    weekly_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "weekly_sales": 0,
        "transaction_count": 0,
        "weekly_revenue": 0.0,
        "week_start_date": "",
        "week_end_date": "",
    })

    for doc in sales_docs:
        p_date = doc.get("purchase_date")
        if not p_date:
            continue
        w_str, s_date, e_date, _, _ = parse_iso_week(p_date)
        qty = int(doc.get("quantity", 1) or 1)
        price = float(doc.get("purchase_price", 0.0) or 0.0)

        entry = weekly_data[w_str]
        entry["weekly_sales"] += qty
        entry["transaction_count"] += 1
        entry["weekly_revenue"] += price
        entry["week_start_date"] = s_date
        entry["week_end_date"] = e_date

    return dict(weekly_data)


# ── Step 2: Aggregate Sentiment Indexes by ISO Week ───────────────────────────

def aggregate_weekly_sentiment() -> Dict[str, Dict[str, Any]]:
    """
    Read all records from sentiment_indexes collection and aggregate by ISO week
    using review-weighted formulas.
    Returns a dict keyed by week_str:
        {
            "2023-W26": {
                "weekly_sentiment": 0.2833,
                "weekly_review_count": 20,
                "weekly_average_confidence": 0.945,
                "weekly_agreement_rate": 0.85,
                "sentiment_doc_count": 18,
                "week_start_date": "2023-06-26",
                "week_end_date": "2023-07-02"
            },
            ...
        }
    """
    db = get_db()
    sent_docs = list(db[SENTIMENT_INDEX_COL].find({}, {
        "date": 1,
        "daily_sentiment_score": 1,
        "review_count": 1,
        "average_confidence": 1,
        "agreement_rate": 1,
    }))

    weekly_accum: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "sum_score_x_reviews": 0.0,
        "sum_conf_x_reviews": 0.0,
        "sum_agree_x_reviews": 0.0,
        "total_reviews": 0,
        "sentiment_doc_count": 0,
        "week_start_date": "",
        "week_end_date": "",
    })

    for doc in sent_docs:
        d_str = doc.get("date")
        if not d_str:
            continue
        w_str, s_date, e_date, _, _ = parse_iso_week(d_str)

        reviews = int(doc.get("review_count", 1) or 1)
        score = float(doc.get("daily_sentiment_score", 0.0) or 0.0)
        conf = float(doc.get("average_confidence", 0.0) or 0.0)
        agree = float(doc.get("agreement_rate", 0.0) or 0.0)

        entry = weekly_accum[w_str]
        entry["sum_score_x_reviews"] += score * reviews
        entry["sum_conf_x_reviews"] += conf * reviews
        entry["sum_agree_x_reviews"] += agree * reviews
        entry["total_reviews"] += reviews
        entry["sentiment_doc_count"] += 1
        entry["week_start_date"] = s_date
        entry["week_end_date"] = e_date

    # Compute review-weighted values
    weekly_sentiment_data: Dict[str, Dict[str, Any]] = {}
    for w_str, accum in weekly_accum.items():
        tot_rev = accum["total_reviews"]
        if tot_rev > 0:
            w_score = round(accum["sum_score_x_reviews"] / tot_rev, 4)
            w_conf = round(accum["sum_conf_x_reviews"] / tot_rev, 4)
            w_agree = round(accum["sum_agree_x_reviews"] / tot_rev, 4)
        else:
            w_score = None
            w_conf = None
            w_agree = None

        weekly_sentiment_data[w_str] = {
            "weekly_sentiment": w_score,
            "weekly_review_count": tot_rev,
            "weekly_average_confidence": w_conf,
            "weekly_agreement_rate": w_agree,
            "sentiment_doc_count": accum["sentiment_doc_count"],
            "week_start_date": accum["week_start_date"],
            "week_end_date": accum["week_end_date"],
        }

    return weekly_sentiment_data


# ── Step 3: Build Combined Continuous Weekly Dataset with Lag-1 ───────────────

def build_weekly_forecasting_dataset() -> List[Dict[str, Any]]:
    """
    Build complete continuous weekly forecasting dataset combining sales and sentiment.
    Applies lag-1 calculation chronologically.
    Returns list of dicts ready for insertion.
    """
    sales_by_week = aggregate_weekly_sales()
    sentiment_by_week = aggregate_weekly_sentiment()

    # Determine universe of weeks
    all_observed_weeks = sorted(list(set(sales_by_week.keys()).union(sentiment_by_week.keys())))
    if not all_observed_weeks:
        return []

    min_week = all_observed_weeks[0]
    max_week = all_observed_weeks[-1]

    # Generate complete continuous ISO week grid
    full_week_grid = generate_iso_week_grid(min_week, max_week)

    dataset: List[Dict[str, Any]] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    prev_week_sentiment: Optional[float] = None

    for idx, week_str in enumerate(full_week_grid):
        start_d, end_d = get_week_boundaries(week_str)

        s_info = sales_by_week.get(week_str)
        sent_info = sentiment_by_week.get(week_str)

        # Sales metrics
        if s_info is not None:
            weekly_sales = int(s_info["weekly_sales"])
            transaction_count = int(s_info["transaction_count"])
            weekly_revenue = round(float(s_info["weekly_revenue"]), 2)
        else:
            # Missing sales week -> sales is 0
            weekly_sales = 0
            transaction_count = 0
            weekly_revenue = 0.0

        # Sentiment metrics
        if sent_info is not None:
            weekly_sentiment = sent_info["weekly_sentiment"]
            weekly_review_count = int(sent_info["weekly_review_count"])
            weekly_average_confidence = sent_info["weekly_average_confidence"]
            weekly_agreement_rate = sent_info["weekly_agreement_rate"]
        else:
            # Missing sentiment week -> null (do NOT assume zero/neutral)
            weekly_sentiment = None
            weekly_review_count = 0
            weekly_average_confidence = None
            weekly_agreement_rate = None

        # Lag-1 sentiment
        # First chronological week has lag1 = None
        if idx == 0:
            lag1_sentiment = None
        else:
            lag1_sentiment = prev_week_sentiment

        doc = {
            "week": week_str,
            "week_start_date": start_d,
            "week_end_date": end_d,
            "weekly_sales": weekly_sales,
            "transaction_count": transaction_count,
            "weekly_revenue": weekly_revenue,
            "weekly_sentiment": weekly_sentiment,
            "lag1_weekly_sentiment": lag1_sentiment,
            "weekly_review_count": weekly_review_count,
            "weekly_average_confidence": weekly_average_confidence,
            "weekly_agreement_rate": weekly_agreement_rate,
            "created_at": now_iso,
        }
        dataset.append(doc)

        # Update prev_week_sentiment for next week's lag-1
        prev_week_sentiment = weekly_sentiment

    return dataset


# ── Step 4: Bulk Upsert ───────────────────────────────────────────────────────

def bulk_upsert_forecasting_dataset(records: List[Dict[str, Any]]) -> int:
    """
    Idempotent bulk upsert into forecasting_dataset collection based on 'week'.
    Returns number of modified/upserted documents.
    """
    if not records:
        return 0

    create_forecasting_dataset_indexes()
    db = get_db()
    col = db[FORECASTING_COLLECTION]

    ops = []
    for rec in records:
        week = rec["week"]
        doc = dict(rec)
        doc.pop("_id", None)
        ops.append(
            UpdateOne(
                {"week": week},
                {"$set": doc},
                upsert=True,
            )
        )

    result = col.bulk_write(ops, ordered=True)
    return result.upserted_count + result.modified_count + result.matched_count


# ── Step 5: Sanity and Validation Checks ───────────────────────────────────────

def validate_forecasting_dataset(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Run all required sanity checks on the constructed dataset.
    Returns a dict with validation results and violations if any.
    """
    violations = []
    seen_weeks = set()
    prev_week_str = None
    prev_sentiment = None

    for i, rec in enumerate(records):
        w = rec.get("week")
        sales = rec.get("weekly_sales")
        sent = rec.get("weekly_sentiment")
        lag1 = rec.get("lag1_weekly_sentiment")
        conf = rec.get("weekly_average_confidence")
        agree = rec.get("weekly_agreement_rate")
        rev_count = rec.get("weekly_review_count")

        # 1. Duplicate weeks
        if w in seen_weeks:
            violations.append(f"Duplicate week found: {w}")
        seen_weeks.add(w)

        # 2. Chronological order
        if prev_week_str and w <= prev_week_str:
            violations.append(f"Chronological order violated: {prev_week_str} followed by {w}")

        # 3. weekly_sales >= 0
        if sales is None or sales < 0:
            violations.append(f"Invalid weekly_sales ({sales}) in week {w}")

        # 4. weekly_sentiment in [-1, 1] when not null
        if sent is not None and not (-1.0 <= sent <= 1.0):
            violations.append(f"weekly_sentiment ({sent}) out of range [-1, 1] in week {w}")

        # 5. lag1_weekly_sentiment in [-1, 1] when not null
        if lag1 is not None and not (-1.0 <= lag1 <= 1.0):
            violations.append(f"lag1_weekly_sentiment ({lag1}) out of range [-1, 1] in week {w}")

        # 6. confidence in [0, 1] when not null
        if conf is not None and not (0.0 <= conf <= 1.0):
            violations.append(f"weekly_average_confidence ({conf}) out of range [0, 1] in week {w}")

        # 7. agreement_rate in [0, 1] when not null
        if agree is not None and not (0.0 <= agree <= 1.0):
            violations.append(f"weekly_agreement_rate ({agree}) out of range [0, 1] in week {w}")

        # 8. review_count > 0 when sentiment is not null
        if sent is not None and (rev_count is None or rev_count <= 0):
            violations.append(f"weekly_review_count must be > 0 when sentiment is present in week {w}")

        # 9. first week has lag1 = None
        if i == 0 and lag1 is not None:
            violations.append(f"First week {w} must have lag1_weekly_sentiment = null, got {lag1}")

        # 10. subsequent weeks have correct lag-1
        if i > 0 and lag1 != prev_sentiment:
            violations.append(f"Week {w} lag1 ({lag1}) does not match previous week sentiment ({prev_sentiment})")

        prev_week_str = w
        prev_sentiment = sent

    return {
        "total_records": len(records),
        "valid": len(violations) == 0,
        "violations_count": len(violations),
        "violations": violations,
    }


# ── Step 6: Spot Check Tool ───────────────────────────────────────────────────

def spot_check_week(week_str: str) -> Dict[str, Any]:
    """
    Independently calculate sales and sentiment directly from raw sales and sentiment_indexes
    collections for a specific week and compare against forecasting_dataset.
    """
    db = get_db()
    start_d, end_d = get_week_boundaries(week_str)

    # Raw sales calculation
    raw_sales_cursor = db[SALES_COLLECTION].find({
        "purchase_date": {"$gte": start_d, "$lte": end_d}
    })
    raw_sales_list = list(raw_sales_cursor)
    raw_sales_sum = sum(int(s.get("quantity", 1) or 1) for s in raw_sales_list)
    raw_sales_tx = len(raw_sales_list)

    # Raw sentiment calculation
    raw_sent_cursor = db[SENTIMENT_INDEX_COL].find({
        "date": {"$gte": start_d, "$lte": end_d}
    })
    raw_sent_list = list(raw_sent_cursor)
    tot_rev = sum(int(s.get("review_count", 1) or 1) for s in raw_sent_list)
    weighted_score_sum = sum(float(s.get("daily_sentiment_score", 0.0) or 0.0) * int(s.get("review_count", 1) or 1) for s in raw_sent_list)
    raw_weighted_sentiment = round(weighted_score_sum / tot_rev, 4) if tot_rev > 0 else None

    # Stored record in forecasting_dataset
    stored_doc = db[FORECASTING_COLLECTION].find_one({"week": week_str})

    sales_match = (stored_doc is not None) and (stored_doc.get("weekly_sales") == raw_sales_sum)
    sentiment_match = (stored_doc is not None) and (stored_doc.get("weekly_sentiment") == raw_weighted_sentiment)

    return {
        "week": week_str,
        "date_range": f"{start_d} to {end_d}",
        "raw_sales_sum": raw_sales_sum,
        "raw_sales_tx": raw_sales_tx,
        "raw_total_reviews": tot_rev,
        "raw_weighted_sentiment": raw_weighted_sentiment,
        "stored_sales": stored_doc.get("weekly_sales") if stored_doc else None,
        "stored_sentiment": stored_doc.get("weekly_sentiment") if stored_doc else None,
        "stored_lag1_sentiment": stored_doc.get("lag1_weekly_sentiment") if stored_doc else None,
        "sales_match": sales_match,
        "sentiment_match": sentiment_match,
        "overall_match": sales_match and sentiment_match,
    }
