"""
db/analysis_indexes.py — MongoDB indexes for the model_analysis_results collection.

Called once before any analysis begins.
Indexes are created only if they do not already exist (idempotent).

The unique compound index on (review_id, model_name, prompt_version) enforces
the one-document-per-review-per-model-per-prompt-version constraint and provides
the cache lookup key used by the worker.
"""

from pymongo import ASCENDING
from app.db.connection import get_db


def create_analysis_indexes() -> None:
    """
    Ensure the model_analysis_results collection has the required indexes.

    Indexes created:
    1. UNIQUE compound: (review_id, model_name, prompt_version)
       → Prevents duplicate analysis results and enables fast cache lookups.
    2. Non-unique: (model_name, prompt_version, status)
       → Enables efficient progress queries (count successes per model).
    3. Non-unique: (review_id,)
       → Enables fast lookup of all results for a given review (ensemble step).
    """
    db = get_db()
    collection = db["model_analysis_results"]

    # ── 1. Unique cache key index ─────────────────────────────────────────────
    collection.create_index(
        [
            ("review_id",      ASCENDING),
            ("model_name",     ASCENDING),
            ("prompt_version", ASCENDING),
        ],
        unique=True,
        name="idx_result_unique_review_model_prompt",
    )

    # ── 2. Progress / status query index ──────────────────────────────────────
    collection.create_index(
        [
            ("model_name",     ASCENDING),
            ("prompt_version", ASCENDING),
            ("status",         ASCENDING),
        ],
        name="idx_result_model_prompt_status",
    )

    # ── 3. Review-level ensemble lookup index ─────────────────────────────────
    collection.create_index(
        [("review_id", ASCENDING)],
        name="idx_result_review_id",
    )

    print("[analysis_indexes] model_analysis_results indexes created/verified.")
