"""
workers/sentiment_index_worker.py — Build the daily product-level sentiment index.

Pipeline:
    sentiment_ensemble (1000 records)
        + reviews (join on review_id for review_date)
        ↓
    Group by (product_id, review_date)
        ↓
    daily_sentiment_score, daily_sentiment, review_count, average_confidence, agreement_rate
        ↓
    Per-product lag-1 sentiment
        ↓
    sentiment_indexes collection

NO LLM calls. NO Ollama. Pure MongoDB aggregation → Python calculation → MongoDB.

Usage:
    python -m app.workers.sentiment_index_worker
"""

import sys
import time
from pprint import pformat

from app.db.connection import get_db, ping_db
from app.services.sentiment_index_service import (
    INDEX_COLLECTION,
    aggregate_daily_sentiment,
    add_lag1_sentiment,
    bulk_upsert_daily_records,
    create_sentiment_index_indexes,
    load_ensemble_with_dates,
    validate_output,
)


# ── Pre-flight ─────────────────────────────────────────────────────────────────

def preflight() -> None:
    """Check MongoDB connectivity and collection readiness."""
    print("\n" + "=" * 60)
    print("  PRE-FLIGHT CHECK")
    print("=" * 60)

    if not ping_db():
        print("  ✗ MongoDB connection FAILED")
        sys.exit(1)
    print("  ✓ MongoDB connected")

    db = get_db()
    n_ensemble = db["sentiment_ensemble"].count_documents({})
    n_reviews  = db["reviews"].count_documents({})
    n_existing = db[INDEX_COLLECTION].count_documents({})

    print(f"  sentiment_ensemble documents:  {n_ensemble}")
    print(f"  reviews documents:             {n_reviews}")
    print(f"  existing sentiment_indexes:    {n_existing}")
    print("=" * 60)


# ── Validation report ─────────────────────────────────────────────────────────

def print_validation_summary(summary: dict) -> None:
    """Print the input data validation report."""
    print("\n" + "=" * 60)
    print("  SENTIMENT INPUT VALIDATION")
    print("=" * 60)
    print(f"  Ensemble records:     {summary['ensemble_total']}")
    print(f"  Matching reviews:     {summary['matched']}")
    print(f"  Missing reviews:      {summary['missing_review']}")
    print(f"  Product mismatches:   {summary['product_mismatch']}")
    print(f"  Invalid scores:       {summary['invalid_score']}")
    print("=" * 60)

    if summary["missing_review"] > 0:
        print(f"  ⚠ {summary['missing_review']} ensemble records have no matching review (will be skipped)")
    if summary["product_mismatch"] > 0:
        print(f"  ⚠ {summary['product_mismatch']} product_id mismatches detected (reviews.product_id used)")
    if summary["invalid_score"] > 0:
        print(f"  ⚠ {summary['invalid_score']} records with invalid ensemble_score (will be skipped)")


# ── Final report ──────────────────────────────────────────────────────────────

def print_final_report(
    validation: dict,
    output: dict,
    n_records: int,
    elapsed: float,
) -> None:
    """Print the post-processing summary."""
    print("\n" + "=" * 60)
    print("  SENTIMENT INDEX COMPLETE")
    print("=" * 60)
    print(f"  Ensemble reviews:               {validation['matched']}")
    print(f"  Daily product-date records:     {output['total_records']}")
    print(f"  Products covered:               {output['n_products']}")
    print(f"  Date range:                     {output['date_min']} → {output['date_max']}")
    print(f"  Records with lag1_sentiment:    {output['lag1_non_null_count']}")
    print(f"  Records without lag1_sentiment: {output['lag1_null_count']}")
    print(f"  Elapsed time:                   {elapsed:.1f}s")
    print("=" * 60)

    # Validation results
    print()
    print("  Output validation:")
    print(f"    Duplicates:                   {output['duplicates']} {'✓' if output['duplicates'] == 0 else '✗ FAIL'}")
    print(f"    Score out of [-1,1]:          {output['out_of_range_score']} {'✓' if output['out_of_range_score'] == 0 else '✗ FAIL'}")
    print(f"    Confidence out of [0,1]:      {output['out_of_range_conf']} {'✓' if output['out_of_range_conf'] == 0 else '✗ FAIL'}")
    print(f"    Agreement rate out of [0,1]:  {output['out_of_range_agr']} {'✓' if output['out_of_range_agr'] == 0 else '✗ FAIL'}")
    print(f"    First obs lag=null (correct): {output['first_obs_lag_null_ok']} products ✓")
    print(f"    First obs lag≠null (wrong):   {output['first_obs_lag_null_fail']} {'✓' if output['first_obs_lag_null_fail'] == 0 else '✗ FAIL'}")
    print("=" * 60)


# ── Test case ─────────────────────────────────────────────────────────────────

def run_test_case() -> None:
    """
    Verify review 267 (product 219) contributes correctly.
    Expected: ensemble_score = 1.0, review_date from reviews collection.
    """
    db = get_db()
    print("\n" + "=" * 60)
    print("  TEST CASE: review_id=267, product_id=219")
    print("=" * 60)

    # Find review date
    review = db["reviews"].find_one({"review_id": "267"}, {"_id": 0, "review_date": 1, "product_id": 1})
    if not review:
        print("  SKIP: review_id=267 not found in reviews collection")
        return

    date = review["review_date"]
    product_id = review["product_id"]
    print(f"  review_date = {date!r}")
    print(f"  product_id  = {product_id!r}")

    # Look up the computed sentiment index for that product/date
    idx_doc = db[INDEX_COLLECTION].find_one(
        {"product_id": product_id, "date": date},
        {"_id": 0},
    )
    if not idx_doc:
        print(f"  ERROR: No sentiment_index found for product_id={product_id!r}, date={date!r}")
        return

    print()
    print(f"  sentiment_indexes record for product={product_id!r}, date={date!r}:")
    for k, v in idx_doc.items():
        if k not in ("created_at",):
            print(f"    {k:30s}: {v}")

    # If it's the only review that day, score must be 1.0
    if idx_doc["review_count"] == 1:
        expected_score = 1.0
        match = abs(idx_doc["daily_sentiment_score"] - expected_score) < 1e-5
        print(f"\n  Only review that day → expected daily_sentiment_score = 1.0")
        print(f"  Actual score: {idx_doc['daily_sentiment_score']} {'✓' if match else '✗ FAIL'}")
    else:
        print(f"\n  {idx_doc['review_count']} reviews on this day → review 267 contributes +1.0 to aggregate")
        print(f"  daily_sentiment_score = {idx_doc['daily_sentiment_score']} (aggregate of {idx_doc['review_count']} reviews)")

    print("=" * 60)


# ── Main ───────────────────────────────────────────────────────────────────────

def run_sentiment_index_worker() -> None:
    """
    Main entry point for the sentiment index worker.
    """
    t_start = time.perf_counter()

    # ── Step 0: Pre-flight ────────────────────────────────────────────────────
    preflight()

    # ── Step 1: Create indexes ────────────────────────────────────────────────
    print("\n[sentiment_index] Creating/verifying indexes ...")
    create_sentiment_index_indexes()

    # ── Step 2: Load and join data ────────────────────────────────────────────
    print("\n[sentiment_index] Loading ensemble data and joining with reviews ...")
    valid_records, validation_summary = load_ensemble_with_dates()
    print_validation_summary(validation_summary)

    if not valid_records:
        print("\n[sentiment_index] ERROR: No valid records to process. Aborting.")
        sys.exit(1)

    print(f"\n[sentiment_index] Valid records for processing: {len(valid_records)}")

    # ── Step 3: Daily aggregation ─────────────────────────────────────────────
    print("\n[sentiment_index] Aggregating to daily product-date level ...")
    daily_records = aggregate_daily_sentiment(valid_records)
    print(f"[sentiment_index] Daily (product, date) combinations: {len(daily_records)}")

    # ── Step 4: Lag-1 sentiment ───────────────────────────────────────────────
    print("\n[sentiment_index] Computing per-product lag-1 sentiment ...")
    daily_records_with_lag = add_lag1_sentiment(daily_records)

    n_lag_null = sum(1 for r in daily_records_with_lag if r["lag1_sentiment"] is None)
    n_lag_set  = sum(1 for r in daily_records_with_lag if r["lag1_sentiment"] is not None)
    print(f"[sentiment_index] Records with lag1_sentiment:     {n_lag_set}")
    print(f"[sentiment_index] Records without (first obs):     {n_lag_null}")

    # ── Step 5: Upsert to MongoDB ─────────────────────────────────────────────
    print(f"\n[sentiment_index] Upserting {len(daily_records_with_lag)} records to sentiment_indexes ...")
    bulk_upsert_daily_records(daily_records_with_lag)
    print("[sentiment_index] Upsert complete.")

    # ── Step 6: Output validation ─────────────────────────────────────────────
    print("\n[sentiment_index] Validating output ...")
    output_validation = validate_output()

    elapsed = time.perf_counter() - t_start

    # ── Step 7: Final report ──────────────────────────────────────────────────
    print_final_report(
        validation=validation_summary,
        output=output_validation,
        n_records=len(daily_records_with_lag),
        elapsed=elapsed,
    )

    # ── Step 8: Test case ─────────────────────────────────────────────────────
    run_test_case()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_sentiment_index_worker()
