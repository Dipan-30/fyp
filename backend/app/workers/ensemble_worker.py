"""
workers/ensemble_worker.py — Review-level ensemble sentiment aggregation worker.

Reads 3000 existing LLM results from model_analysis_results and produces
1000 ensemble documents in sentiment_ensemble.

Pipeline:
    MongoDB (model_analysis_results) → Python calculation → MongoDB (sentiment_ensemble)

NO Ollama calls. NO LLM inference. Pure aggregation.

Usage:
    python -m app.workers.ensemble_worker
"""

import sys
import time
from datetime import datetime, timezone

from app.db.connection import get_db, ping_db
from app.services.ensemble_service import (
    ENSEMBLE_COLLECTION,
    MODELS,
    PROMPT_VERSION,
    compute_ensemble,
    create_ensemble_indexes,
    ensemble_exists,
    load_all_review_ids,
    load_model_results_for_review,
    save_ensemble,
    validate_completeness,
)


# ── Pre-flight checks ─────────────────────────────────────────────────────────

def preflight(prompt_version: str = PROMPT_VERSION) -> None:
    """
    Verify MongoDB connection and validate that LLM results are complete.
    Prints a detailed pre-flight report and aborts if the data is unusable.
    """
    print("\n" + "=" * 60)
    print("  PRE-FLIGHT CHECK")
    print("=" * 60)

    # MongoDB connection
    if not ping_db():
        print("  ✗ MongoDB connection FAILED. Check MONGODB_URI in .env")
        sys.exit(1)
    print("  ✓ MongoDB connected")

    db = get_db()

    # Count total successful records per model
    print("\n  LLM results in model_analysis_results:")
    total_success = 0
    for model in MODELS:
        count = db["model_analysis_results"].count_documents(
            {"model_name": model, "prompt_version": prompt_version, "status": "success"}
        )
        print(f"    {model:20s}  {count:>5} successful results")
        total_success += count
    print(f"    {'TOTAL':20s}  {total_success:>5} successful results")

    # Completeness check
    print("\n  Validating review completeness ...")
    complete_ids, incomplete_map = validate_completeness(prompt_version)
    print(f"    Complete reviews (all 3 models):   {len(complete_ids)}")
    print(f"    Incomplete reviews:                {len(incomplete_map)}")

    if incomplete_map:
        print("\n  ⚠ Incomplete reviews (will be SKIPPED):")
        for rid, missing in sorted(incomplete_map.items()):
            print(f"    review_id={rid!r}  missing models: {missing}")
    else:
        print("    ✓ All reviews have results from all 3 models")

    # Existing ensemble docs
    existing = db[ENSEMBLE_COLLECTION].count_documents({"prompt_version": prompt_version})
    print(f"\n  Existing ensemble documents:       {existing}")

    print("=" * 60)


# ── Main worker ───────────────────────────────────────────────────────────────

def run_ensemble_worker(prompt_version: str = PROMPT_VERSION) -> None:
    """
    Main ensemble calculation loop.

    For each review that has all three model results:
      1. Check if ensemble already exists (skip if yes — idempotent).
      2. Load model results from MongoDB.
      3. Compute ensemble (majority vote + numerical score + avg confidence).
      4. Save to sentiment_ensemble.

    Prints per-review progress and a final summary.
    """
    # Ensure indexes exist
    print("\n[ensemble_worker] Creating/verifying indexes ...")
    create_ensemble_indexes()

    # Pre-flight
    preflight(prompt_version)

    # Load all eligible review IDs (complete reviews only)
    complete_ids, incomplete_map = validate_completeness(prompt_version)
    all_review_ids = complete_ids  # Only process complete reviews

    total = len(all_review_ids)
    if total == 0:
        print("\n[ensemble_worker] No complete reviews found. Aborting.")
        sys.exit(1)

    print(f"\n[ensemble_worker] Processing {total} reviews ...")
    print(f"[ensemble_worker] Incomplete reviews that will be skipped: {len(incomplete_map)}")
    print()

    # Counters
    count_processed = 0
    count_skipped   = 0
    count_failed    = 0

    t_start = time.perf_counter()

    for i, review_id in enumerate(all_review_ids, start=1):
        # ── Idempotency check ─────────────────────────────────────────────────
        if ensemble_exists(review_id, prompt_version):
            count_skipped += 1
            # Print skip only occasionally to avoid wall of text on re-runs
            if i <= 5 or i % 100 == 0:
                print(f"  [{i:>4}/{total}] review_id={review_id!r} — SKIPPED (already exists)")
            continue

        # ── Load model results ────────────────────────────────────────────────
        model_results = load_model_results_for_review(review_id, prompt_version)

        # Verify all three models present (should always be true given validate_completeness)
        missing = [m for m in MODELS if m not in model_results]
        if missing:
            print(f"  [{i:>4}/{total}] review_id={review_id!r} — SKIP (missing: {missing})")
            count_failed += 1
            continue

        # ── Compute ensemble ──────────────────────────────────────────────────
        try:
            doc = compute_ensemble(review_id, model_results, prompt_version)
        except (ValueError, Exception) as exc:
            print(f"  [{i:>4}/{total}] review_id={review_id!r} — ERROR: {exc}")
            count_failed += 1
            continue

        # ── Persist ───────────────────────────────────────────────────────────
        try:
            save_ensemble(doc)
        except Exception as exc:
            print(f"  [{i:>4}/{total}] review_id={review_id!r} — SAVE ERROR: {exc}")
            count_failed += 1
            continue

        count_processed += 1

        # Progress: print every review for the first 10, then every 50
        if i <= 10 or i % 50 == 0 or i == total:
            tie = " [tie-break]" if doc.get("tie_break_used") else ""
            print(
                f"  [{i:>4}/{total}] review_id={review_id!r} — "
                f"{doc['ensemble_sentiment']:8s}  score={doc['ensemble_score']:+.4f}  "
                f"conf={doc['average_confidence']:.3f}  "
                f"agree={doc['agreement_count']}/3{tie}"
            )

    elapsed = time.perf_counter() - t_start

    # ── Final count from DB ───────────────────────────────────────────────────
    db = get_db()
    total_in_db = db[ENSEMBLE_COLLECTION].count_documents({"prompt_version": prompt_version})

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  ENSEMBLE COMPLETE")
    print("=" * 60)
    print(f"  Total reviews:          {total}")
    print(f"  Successfully processed: {count_processed}")
    print(f"  Skipped (existing):     {count_skipped}")
    print(f"  Incomplete (skipped):   {len(incomplete_map)}")
    print(f"  Failed:                 {count_failed}")
    print(f"  Elapsed time:           {elapsed:.1f}s")
    print("=" * 60)
    print(f"  Total ensemble documents in MongoDB: {total_in_db}")
    print("=" * 60)

    if incomplete_map:
        print("\n  Incomplete reviews (missing model results):")
        for rid, missing in sorted(incomplete_map.items()):
            print(f"    review_id={rid!r}  missing: {missing}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_ensemble_worker()
