"""
db/indexes.py — Ensure all required MongoDB indexes exist.

Called once on application startup.
Indexes are created only if they do not already exist (idempotent).
"""

from pymongo import ASCENDING, DESCENDING
from app.db.connection import get_db


def create_indexes():
    """Create indexes for the reviews and sales collections."""
    db = get_db()

    # ── reviews collection ────────────────────────────────────────────────────
    reviews = db["reviews"]

    # Unique index on review_id — prevents duplicate imports
    reviews.create_index(
        [("review_id", ASCENDING)],
        unique=True,
        name="idx_review_id_unique",
    )
    # Query index: filter by product
    reviews.create_index(
        [("product_id", ASCENDING)],
        name="idx_review_product_id",
    )
    # Query index: filter/sort by date
    reviews.create_index(
        [("review_date", ASCENDING)],
        name="idx_review_date",
    )

    # ── sales collection ──────────────────────────────────────────────────────
    sales = db["sales"]

    # Unique index on transaction_id — prevents duplicate imports
    sales.create_index(
        [("transaction_id", ASCENDING)],
        unique=True,
        name="idx_sale_transaction_id_unique",
    )
    # Query index: filter by product
    sales.create_index(
        [("product_id", ASCENDING)],
        name="idx_sale_product_id",
    )
    # Query index: filter/sort by date
    sales.create_index(
        [("purchase_date", ASCENDING)],
        name="idx_sale_purchase_date",
    )
