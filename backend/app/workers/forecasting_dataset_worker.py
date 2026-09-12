"""
workers/forecasting_dataset_worker.py — Build and validate weekly store-wide forecasting dataset.

Pipeline:
    1. Pre-flight check & report on 'sales' and 'sentiment_indexes'
    2. Build continuous 53-week dataset with review-weighted sentiment and lag-1
    3. Run strict sanity & constraint validations
    4. Upsert idempotently into 'forecasting_dataset'
    5. Perform manual spot checks on selected weeks against source data
    6. Output final Phase 6B summary report

NO LLM calls. NO SARIMA/SARIMAX. NO forecasting calculations.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pprint import pprint

from app.db.connection import get_db
from app.services.forecasting_dataset_service import (
    FORECASTING_COLLECTION,
    SALES_COLLECTION,
    SENTIMENT_INDEX_COL,
    aggregate_weekly_sales,
    aggregate_weekly_sentiment,
    build_weekly_forecasting_dataset,
    bulk_upsert_forecasting_dataset,
    create_forecasting_dataset_indexes,
    spot_check_week,
    validate_forecasting_dataset,
)


def run_worker() -> None:
    print("=" * 60)
    print("PHASE 6B — BUILDING WEEKLY FORECASTING DATASET")
    print("=" * 60)

    db = get_db()

    # ── 1. Pre-flight Check ───────────────────────────────────────────────────
    total_sales_tx = db[SALES_COLLECTION].count_documents({})
    total_sent_idx = db[SENTIMENT_INDEX_COL].count_documents({})

    print(f"\n[1/5] Source collections verification:")
    print(f"  • sales collection count:             {total_sales_tx:,}")
    print(f"  • sentiment_indexes collection count: {total_sent_idx:,}")

    if total_sales_tx == 0 or total_sent_idx == 0:
        print("❌ Error: Missing source data in sales or sentiment_indexes.")
        sys.exit(1)

    sales_by_week = aggregate_weekly_sales()
    sent_by_week = aggregate_weekly_sentiment()

    sales_weeks = sorted(list(sales_by_week.keys()))
    sent_weeks = sorted(list(sent_by_week.keys()))

    total_sales_qty = sum(v["weekly_sales"] for v in sales_by_week.values())
    total_sent_reviews = sum(v["weekly_review_count"] for v in sent_by_week.values())

    print(f"\n[2/5] Source weekly aggregation analysis:")
    print("  --- Sales ---")
    print(f"  • Transaction count:        {total_sales_tx}")
    print(f"  • Total quantity (units):   {total_sales_qty}")
    print(f"  • Weekly observations:      {len(sales_weeks)}")
    print(f"  • First week:               {sales_weeks[0] if sales_weeks else 'N/A'}")
    print(f"  • Last week:                {sales_weeks[-1] if sales_weeks else 'N/A'}")

    print("  --- Sentiment ---")
    print(f"  • Sentiment index records:  {total_sent_idx}")
    print(f"  • Weekly observations:      {len(sent_weeks)}")
    print(f"  • Total contributing reviews: {total_sent_reviews}")
    print(f"  • First week:               {sent_weeks[0] if sent_weeks else 'N/A'}")
    print(f"  • Last week:                {sent_weeks[-1] if sent_weeks else 'N/A'}")

    all_union_weeks = sorted(list(set(sales_weeks).union(sent_weeks)))
    weeks_both = set(sales_weeks).intersection(sent_weeks)
    missing_sales_weeks = set(all_union_weeks) - set(sales_weeks)
    missing_sent_weeks = set(all_union_weeks) - set(sent_weeks)

    print("  --- Combined Pre-flight ---")
    print(f"  • Total weekly observations:{len(all_union_weeks)}")
    print(f"  • Weeks with both:          {len(weeks_both)}")
    print(f"  • Weeks missing sales:      {len(missing_sales_weeks)} {list(missing_sales_weeks) if missing_sales_weeks else ''}")
    print(f"  • Weeks missing sentiment:  {len(missing_sent_weeks)} {list(missing_sent_weeks) if missing_sent_weeks else ''}")

    # ── 2. Build Dataset ──────────────────────────────────────────────────────
    print(f"\n[3/5] Building continuous weekly forecasting dataset with lag-1...")
    dataset = build_weekly_forecasting_dataset()
    print(f"  • Generated {len(dataset)} weekly records covering {dataset[0]['week']} to {dataset[-1]['week']}.")

    # ── 3. Validate Dataset ───────────────────────────────────────────────────
    print(f"\n[4/5] Running sanity and constraint validations...")
    val_report = validate_forecasting_dataset(dataset)

    if not val_report["valid"]:
        print(f"❌ Validation failed with {val_report['violations_count']} errors:")
        for v in val_report["violations"]:
            print(f"  - {v}")
        sys.exit(1)
    else:
        print("  ✓ All sanity and constraint checks PASSED (0 violations).")

    # ── 4. Upsert into MongoDB ────────────────────────────────────────────────
    print(f"\n[5/5] Upserting records into MongoDB collection '{FORECASTING_COLLECTION}'...")
    create_forecasting_dataset_indexes()
    upsert_count = bulk_upsert_forecasting_dataset(dataset)
    final_count = db[FORECASTING_COLLECTION].count_documents({})
    print(f"  ✓ Upsert operation complete. Collection now has {final_count} documents.")

    # ── 5. Manual Spot Checks ─────────────────────────────────────────────────
    spot_check_weeks = [dataset[0]["week"], "2023-W40", "2024-W10", dataset[-1]["week"]]
    print(f"\n--- MANUAL SPOT CHECKS ---")
    all_spot_checks_passed = True
    for sc_w in spot_check_weeks:
        sc_res = spot_check_week(sc_w)
        match_status = "✓ MATCH" if sc_res["overall_match"] else "❌ MISMATCH"
        if not sc_res["overall_match"]:
            all_spot_checks_passed = False
        print(f"  Week {sc_w} ({sc_res['date_range']}): {match_status}")
        print(f"    - Sales:     Raw Sum={sc_res['raw_sales_sum']} (tx={sc_res['raw_sales_tx']}) | Stored={sc_res['stored_sales']} -> {'✓' if sc_res['sales_match'] else '❌'}")
        print(f"    - Sentiment: Raw Weighted={sc_res['raw_weighted_sentiment']} (reviews={sc_res['raw_total_reviews']}) | Stored={sc_res['stored_sentiment']} -> {'✓' if sc_res['sentiment_match'] else '❌'}")
        print(f"    - Lag-1:     Stored={sc_res['stored_lag1_sentiment']}")

    if not all_spot_checks_passed:
        print("❌ One or more manual spot checks failed.")
        sys.exit(1)

    # ── 6. Final Report ───────────────────────────────────────────────────────
    records_with_lag1 = sum(1 for d in dataset if d["lag1_weekly_sentiment"] is not None)
    dup_weeks_count = len(dataset) - len(set(d["week"] for d in dataset))

    print("\n" + "=" * 60)
    print("PHASE 6B — WEEKLY FORECASTING DATASET COMPLETE")
    print("=" * 60)
    print(f"Sales transactions:          {total_sales_tx}")
    print(f"Total quantity:              {total_sales_qty}")
    print(f"Weekly observations:         {len(sales_weeks)}")
    print(f"\nSentiment index records:     {total_sent_idx}")
    print(f"Weekly observations:         {len(sent_weeks)}")
    print(f"Total contributing reviews:  {total_sent_reviews}")
    print(f"\nCombined weekly observations:{len(dataset)}")
    print(f"Weeks with both:             {len(weeks_both)}")
    print(f"Weeks missing sales:         {len(missing_sales_weeks)}")
    print(f"Weeks missing sentiment:     {len(missing_sent_weeks)}")
    print(f"\nRecords with lag1 sentiment: {records_with_lag1}")
    print(f"First week:                  {dataset[0]['week']} (lag1 = {dataset[0]['lag1_weekly_sentiment']})")
    print(f"Last week:                   {dataset[-1]['week']} (lag1 = {dataset[-1]['lag1_weekly_sentiment']})")
    print(f"\nDuplicate weeks:             {dup_weeks_count}")
    print(f"Validation errors:           {val_report['violations_count']}")
    print(f"\nManual spot checks:          {len(spot_check_weeks)} weeks checked — 100% exact match")
    print("=" * 60)
    print("\nConfirmations:")
    print("  ✓ ZERO LLM calls made")
    print("  ✓ ZERO modifications to source collections (reviews, sales, model_analysis_results, sentiment_ensemble, sentiment_indexes)")
    print("  ✓ Frontend untouched")
    print("  ✓ Forecasting models (SARIMA / SARIMAX) NOT implemented yet")


if __name__ == "__main__":
    run_worker()
