"""
routers/reviews.py — Paginated reviews endpoint with optional product filter.

Endpoint:
  GET /api/reviews?page=1&limit=20&product_id=P001
"""

import math
from fastapi import APIRouter, HTTPException, Query
from app.db.connection import get_db

router = APIRouter(prefix="/api/reviews", tags=["Reviews"])


@router.get("")
def get_reviews(
    page:       int = Query(default=1,  ge=1,  description="Page number (1-based)"),
    limit:      int = Query(default=20, ge=1, le=100, description="Results per page"),
    product_id: str = Query(default=None, description="Filter by ProductID"),
):
    """
    Return paginated review records from MongoDB.

    Supports optional product_id filter. MongoDB _id is excluded from the response.
    """
    try:
        db = get_db()
        collection = db["reviews"]

        query_filter = {}
        if product_id:
            query_filter["product_id"] = product_id

        total = collection.count_documents(query_filter)
        total_pages = max(1, math.ceil(total / limit))
        skip = (page - 1) * limit

        cursor = (
            collection
            .find(query_filter, {"_id": 0})
            .sort("review_date", -1)
            .skip(skip)
            .limit(limit)
        )
        reviews = list(cursor)

        return {
            "reviews":     reviews,
            "total":       total,
            "page":        page,
            "limit":       limit,
            "total_pages": total_pages,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reviews query failed: {str(e)}")
