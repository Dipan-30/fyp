"""
workers/sentiment_analysis_worker.py — Model-by-model sequential LLM review analysis.

Processing order:
    llama3.1:8b  → ALL reviews (1 → N)
    qwen2.5:7b   → ALL reviews (1 → N)
    gemma3:4b    → ALL reviews (1 → N)

Concurrency: 1 (sequential — ONE Ollama request at a time, no batching)

Features:
- Resume capability: skips reviews already successfully analysed
- Retry: up to MAX_RETRIES per review/model on transient failures
- Cache: checks MongoDB before any LLM call
- Logging: structured per-review and per-model summary output
- CLI: --limit N, --model NAME, interactive confirmation prompt

IMPORTANT:
    This worker will NOT make any Ollama calls until the user explicitly
    answers "y" to the confirmation prompt.

Usage:
    python -m app.workers.sentiment_analysis_worker
    python -m app.workers.sentiment_analysis_worker --limit 10
    python -m app.workers.sentiment_analysis_worker --model llama3.1:8b
    python -m app.workers.sentiment_analysis_worker --model llama3.1:8b --limit 10
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.db.connection import get_db
from app.db.analysis_indexes import create_analysis_indexes
from app.llm.ollama_service import (
    call_ollama,
    close_client,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaResponseError,
)
from app.prompts.sentiment_prompt import (
    PROMPT_VERSION,
    build_prompt,
    parse_and_validate_response,
)


# ── Configuration ─────────────────────────────────────────────────────────────

MODELS = [
    "llama3.1:8b",
    "qwen2.5:7b",
    "gemma3:4b",
]

MODEL_DISPLAY_NAMES = {
    "llama3.1:8b": "Llama 3.1",
    "qwen2.5:7b":  "Qwen 2.5",
    "gemma3:4b":   "Gemma 3",
}

ANALYSIS_COLLECTION = "model_analysis_results"
REVIEWS_COLLECTION  = "reviews"

MAX_RETRIES = 2          # Number of retry attempts per review/model after first failure
OLLAMA_TIMEOUT = 180.0   # Seconds to wait for a single Ollama response


# ── MongoDB helpers ───────────────────────────────────────────────────────────

def load_reviews_from_mongo(limit: Optional[int] = None) -> list[dict]:
    """
    Load reviews from MongoDB in deterministic (review_id ascending) order.

    Returns a list of dicts with at minimum: review_id, product_id, review_text.
    Raises RuntimeError if the collection is empty.
    """
    db = get_db()
    query = {}
    cursor = db[REVIEWS_COLLECTION].find(
        query,
        projection={"_id": 0, "review_id": 1, "product_id": 1, "review_text": 1},
        sort=[("review_id", 1)],
    )
    if limit:
        cursor = cursor.limit(limit)
    reviews = list(cursor)
    return reviews


def check_cache(review_id: str, model_name: str, prompt_version: str) -> Optional[str]:
    """
    Check if a SUCCESSFUL result already exists in model_analysis_results.

    Returns:
        "success" if a successful result exists → caller should SKIP.
        None      if no successful result exists → caller should proceed.

    Note: Failed results are NOT cached — they are retried.
    """
    db = get_db()
    existing = db[ANALYSIS_COLLECTION].find_one(
        {
            "review_id":      review_id,
            "model_name":     model_name,
            "prompt_version": prompt_version,
            "status":         "success",
        },
        projection={"_id": 1},
    )
    return "success" if existing else None


def save_success(
    review_id: str,
    product_id: str,
    review_text: str,
    model_name: str,
    sentiment: str,
    confidence: float,
    reasoning: str,
    processing_time: float,
    prompt_version: str,
) -> None:
    """
    Upsert a successful analysis result into model_analysis_results.

    Using upsert (not insert) on the unique key means re-running is safe:
    a successful record will simply be updated in place (same data).
    """
    db = get_db()
    doc = {
        "review_id":               review_id,
        "product_id":              product_id,
        "review_text":             review_text,
        "model_name":              model_name,
        "sentiment":               sentiment,
        "confidence":              confidence,
        "reasoning":               reasoning,
        "status":                  "success",
        "prompt_version":          prompt_version,
        "processing_time_seconds": round(processing_time, 3),
        "created_at":              datetime.now(timezone.utc).isoformat(),
    }
    db[ANALYSIS_COLLECTION].update_one(
        {
            "review_id":      review_id,
            "model_name":     model_name,
            "prompt_version": prompt_version,
        },
        {"$set": doc},
        upsert=True,
    )


def save_failure(
    review_id: str,
    product_id: str,
    model_name: str,
    error: str,
    prompt_version: str,
) -> None:
    """
    Upsert a failed analysis result.

    Failed records are stored so we have an audit trail, but the cache check
    only skips on "success" status — so failures will be retried on next run.
    """
    db = get_db()
    doc = {
        "review_id":      review_id,
        "product_id":     product_id,
        "model_name":     model_name,
        "status":         "failed",
        "error":          error[:2000],   # Cap error message length
        "prompt_version": prompt_version,
        "created_at":     datetime.now(timezone.utc).isoformat(),
    }
    db[ANALYSIS_COLLECTION].update_one(
        {
            "review_id":      review_id,
            "model_name":     model_name,
            "prompt_version": prompt_version,
        },
        {"$set": doc},
        upsert=True,
    )


# ── Per-review analysis ───────────────────────────────────────────────────────

def analyse_one_review(
    review: dict,
    model_name: str,
    review_num: int,
    total_reviews: int,
    prompt_version: str = PROMPT_VERSION,
) -> str:
    """
    Analyse a single review with a single model.

    Returns:
        "skipped"  — already successfully analysed (cache hit)
        "success"  — newly analysed and saved
        "failed"   — all retry attempts exhausted

    Implements retry with up to MAX_RETRIES attempts after the initial failure.
    Each retry is a fresh Ollama call (no duplicates in MongoDB — upsert).
    """
    review_id  = review["review_id"]
    product_id = review.get("product_id", "")
    review_text = review.get("review_text", "")
    display    = MODEL_DISPLAY_NAMES.get(model_name, model_name)

    # ── Cache check ───────────────────────────────────────────────────────────
    cached = check_cache(review_id, model_name, prompt_version)
    if cached == "success":
        print(
            f"[{review_num:>4}/{total_reviews}] {display} — "
            f"ReviewID={review_id} — SKIPPED (cached)"
        )
        return "skipped"

    # ── Build prompt ──────────────────────────────────────────────────────────
    prompt = build_prompt(review_text)

    # ── Retry loop ────────────────────────────────────────────────────────────
    last_error = ""
    for attempt in range(1 + MAX_RETRIES):   # attempt 0 = first try, 1–2 = retries
        if attempt > 0:
            print(
                f"  ↳ Retry {attempt}/{MAX_RETRIES} for ReviewID={review_id} ..."
            )

        t_start = time.perf_counter()
        try:
            response = call_ollama(
                model=model_name,
                prompt=prompt,
                timeout=OLLAMA_TIMEOUT,
            )
        except OllamaConnectionError as exc:
            # Ollama not reachable — no point retrying, abort immediately
            last_error = f"Connection error: {exc}"
            print(f"  ✗ FATAL: {last_error}")
            save_failure(review_id, product_id, model_name, last_error, prompt_version)
            return "failed"
        except OllamaTimeoutError as exc:
            last_error = f"Timeout: {exc}"
            print(f"  ✗ Timeout (attempt {attempt + 1}): {exc}")
            continue
        except OllamaResponseError as exc:
            last_error = f"Response error: {exc}"
            print(f"  ✗ Response error (attempt {attempt + 1}): {exc}")
            continue
        except Exception as exc:
            last_error = f"Unexpected error: {exc}"
            print(f"  ✗ Unexpected error (attempt {attempt + 1}): {exc}")
            continue

        duration = time.perf_counter() - t_start

        # ── Validate response ─────────────────────────────────────────────────
        parsed = parse_and_validate_response(response["content"])

        if not parsed["valid"]:
            last_error = f"Validation failed: {parsed['error']}"
            print(f"  ✗ Invalid response (attempt {attempt + 1}): {parsed['error']}")
            continue

        # ── Save success ──────────────────────────────────────────────────────
        save_success(
            review_id=review_id,
            product_id=product_id,
            review_text=review_text,
            model_name=model_name,
            sentiment=parsed["sentiment"],
            confidence=parsed["confidence"],
            reasoning=parsed["reasoning"],
            processing_time=duration,
            prompt_version=prompt_version,
        )

        print(
            f"[{review_num:>4}/{total_reviews}] {display} — "
            f"ReviewID={review_id} — success — {duration:.2f}s"
        )
        return "success"

    # All attempts exhausted
    save_failure(review_id, product_id, model_name, last_error, prompt_version)
    print(
        f"[{review_num:>4}/{total_reviews}] {display} — "
        f"ReviewID={review_id} — FAILED — {last_error[:120]}"
    )
    return "failed"


# ── Per-model processing ──────────────────────────────────────────────────────

def run_model(
    model_name: str,
    reviews: list[dict],
    prompt_version: str = PROMPT_VERSION,
) -> dict:
    """
    Run sentiment analysis for ALL reviews with ONE model, sequentially.

    Finishes all reviews for this model before returning.
    """
    display = MODEL_DISPLAY_NAMES.get(model_name, model_name)
    total = len(reviews)

    print(f"\n{'='*60}")
    print(f"  Model: {display} ({model_name})")
    print(f"  Reviews: {total}")
    print(f"  Prompt version: {prompt_version}")
    print(f"{'='*60}")

    counts = {"success": 0, "failed": 0, "skipped": 0}
    t_model_start = time.perf_counter()

    for i, review in enumerate(reviews, start=1):
        result = analyse_one_review(
            review=review,
            model_name=model_name,
            review_num=i,
            total_reviews=total,
            prompt_version=prompt_version,
        )
        counts[result] = counts.get(result, 0) + 1

    total_elapsed = time.perf_counter() - t_model_start
    processed = counts["success"] + counts["failed"]
    avg_time = (total_elapsed / processed) if processed > 0 else 0.0

    print(f"\n{'─'*60}")
    print(f"  Model:        {model_name}")
    print(f"  Total:        {total}")
    print(f"  Success:      {counts['success']}")
    print(f"  Failed:       {counts['failed']}")
    print(f"  Skipped:      {counts['skipped']}")
    print(f"  Total time:   {total_elapsed:.1f}s")
    print(f"  Average time: {avg_time:.2f}s/review (new reviews only)")
    print(f"{'─'*60}")

    return {
        "model_name": model_name,
        **counts,
        "total_elapsed_seconds": round(total_elapsed, 1),
        "avg_time_seconds": round(avg_time, 2),
    }


# ── Main worker entry point ───────────────────────────────────────────────────

def run_analysis(
    models: list[str] = MODELS,
    limit: Optional[int] = None,
    prompt_version: str = PROMPT_VERSION,
) -> None:
    """
    Main analysis loop: runs each model sequentially over all reviews.

    Llama → ALL reviews → MongoDB
    Qwen  → ALL reviews → MongoDB
    Gemma → ALL reviews → MongoDB

    This function is ONLY called after the user confirms with "y".
    """
    print("\n[worker] Ensuring MongoDB indexes exist ...")
    create_analysis_indexes()

    print("[worker] Loading reviews from MongoDB ...")
    reviews = load_reviews_from_mongo(limit=limit)
    n_reviews = len(reviews)

    if n_reviews == 0:
        print("[worker] ERROR: No reviews found in MongoDB.")
        print("         Run the Phase 2 dataset import first:")
        print("         POST /api/dataset/import")
        sys.exit(1)

    print(f"[worker] Loaded {n_reviews} reviews from MongoDB reviews collection.")

    t_total_start = time.perf_counter()
    all_summaries = []

    for model_name in models:
        summary = run_model(
            model_name=model_name,
            reviews=reviews,
            prompt_version=prompt_version,
        )
        all_summaries.append(summary)

    total_wall = time.perf_counter() - t_total_start

    print(f"\n{'='*60}")
    print("  ANALYSIS COMPLETE")
    print(f"{'='*60}")
    for s in all_summaries:
        print(
            f"  {s['model_name']:20s}  "
            f"success={s['success']:>5}  "
            f"failed={s['failed']:>4}  "
            f"skipped={s['skipped']:>5}"
        )
    print(f"  Total wall time: {total_wall:.1f}s")
    print(f"{'='*60}\n")

    try:
        close_client()
    except Exception:
        pass


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.workers.sentiment_analysis_worker",
        description=(
            "LLM-based sentiment analysis worker.\n"
            "Processes all reviews with each model sequentially.\n"
            "Requires interactive confirmation before making any LLM calls."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Limit analysis to first N reviews (for testing). Default: all reviews.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        metavar="MODEL_NAME",
        choices=MODELS,
        help=(
            f"Process only one model. Choices: {MODELS}. "
            "Default: all three models."
        ),
    )
    parser.add_argument(
        "--prompt-version",
        type=str,
        default=PROMPT_VERSION,
        metavar="VERSION",
        help=f"Prompt version to use. Default: {PROMPT_VERSION}",
    )
    return parser.parse_args()


def _confirmation_prompt(
    n_reviews: int,
    models: list[str],
    limit: Optional[int],
) -> bool:
    """
    Display analysis plan and require explicit "y" confirmation.

    Any response other than "y" (case-insensitive) will exit safely
    WITHOUT making any Ollama calls.

    Returns True only if user enters "y".
    """
    max_calls = n_reviews * len(models)

    print("\n" + "="*60)
    print("  LLM REVIEW ANALYSIS")
    print("="*60)
    print(f"  Reviews:       {n_reviews}")
    print(f"  Models:        {len(models)} — {', '.join(models)}")
    print(f"  Maximum calls: {max_calls}")
    print(f"  Concurrency:   1 (sequential)")
    if limit:
        print(f"  Limit:         {limit} reviews (test mode)")
    print("="*60)

    try:
        answer = input("\nStart analysis? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        return False

    if answer != "y":
        print("Analysis cancelled. No Ollama calls were made.")
        return False

    return True


def main() -> None:
    """
    CLI entry point.

    Steps:
    1. Parse arguments.
    2. Load review count from MongoDB for the confirmation prompt.
    3. Show confirmation prompt — EXIT if not confirmed.
    4. Run analysis only after "y" confirmation.
    """
    args = _parse_args()

    # Determine which models to run
    selected_models = [args.model] if args.model else MODELS

    # ── Load review count (for the prompt — no LLM calls here) ───────────────
    print("[worker] Connecting to MongoDB ...")
    try:
        reviews = load_reviews_from_mongo(limit=args.limit)
    except Exception as exc:
        print(f"[worker] ERROR loading reviews from MongoDB: {exc}")
        sys.exit(1)

    n_reviews = len(reviews)

    if n_reviews == 0:
        print("[worker] ERROR: No reviews found in MongoDB.")
        print("         Run: POST /api/dataset/import  (Phase 2 import)")
        sys.exit(1)

    # ── Confirmation prompt ───────────────────────────────────────────────────
    confirmed = _confirmation_prompt(
        n_reviews=n_reviews,
        models=selected_models,
        limit=args.limit,
    )

    if not confirmed:
        sys.exit(0)

    # ── Run analysis ──────────────────────────────────────────────────────────
    run_analysis(
        models=selected_models,
        limit=args.limit,
        prompt_version=args.prompt_version,
    )


if __name__ == "__main__":
    main()
