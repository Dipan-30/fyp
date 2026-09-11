"""
services/import_service.py — Safe, repeatable import of preprocessed data into MongoDB.

Idempotency strategy:
  - Reviews: unique index on review_id; use update_one(upsert=True) keyed on review_id.
  - Sales:   unique index on transaction_id; use update_one(upsert=True) keyed on transaction_id.

Running the import multiple times will NOT create duplicates.
"""

from pymongo import UpdateOne
from pymongo.errors import BulkWriteError
from app.db.connection import get_db
from app.services.preprocessing import load_reviews, load_sales


def import_reviews() -> dict:
    """
    Load reviews from CSV and upsert into the reviews collection.
    Returns a summary dict with counts.
    """
    db = get_db()
    collection = db["reviews"]

    records = load_reviews()
    if not records:
        return {"inserted": 0, "updated": 0, "total_processed": 0}

    # Build bulk upsert operations keyed on review_id
    operations = [
        UpdateOne(
            {"review_id": doc["review_id"]},
            {"$set": doc},
            upsert=True,
        )
        for doc in records
    ]

    result = collection.bulk_write(operations, ordered=False)
    return {
        "inserted": result.upserted_count,
        "updated":  result.modified_count,
        "matched":  result.matched_count,
        "total_processed": len(records),
    }


def import_sales() -> dict:
    """
    Load sales from CSV and upsert into the sales collection.
    Returns a summary dict with counts.
    """
    db = get_db()
    collection = db["sales"]

    records = load_sales()
    if not records:
        return {"inserted": 0, "updated": 0, "total_processed": 0}

    # Build bulk upsert operations keyed on transaction_id
    operations = [
        UpdateOne(
            {"transaction_id": doc["transaction_id"]},
            {"$set": doc},
            upsert=True,
        )
        for doc in records
    ]

    result = collection.bulk_write(operations, ordered=False)
    return {
        "inserted": result.upserted_count,
        "updated":  result.modified_count,
        "matched":  result.matched_count,
        "total_processed": len(records),
    }


def import_all() -> dict:
    """Run both imports and return a combined summary."""
    reviews_result = import_reviews()
    sales_result   = import_sales()
    return {
        "reviews": reviews_result,
        "sales":   sales_result,
    }
