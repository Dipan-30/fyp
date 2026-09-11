"""
routers/products.py — Product-level aggregation endpoint.

Endpoint:
  GET /api/products — per-product summary from reviews + sales collections
"""

from fastapi import APIRouter, HTTPException
from app.db.connection import get_db

router = APIRouter(prefix="/api/products", tags=["Products"])


@router.get("")
def get_products():
    """
    Return a list of products with review count, purchase count, and total quantity.

    ProductID is the canonical join key. ProductName is pulled from the sales
    collection (it does not exist in reviews).
    """
    try:
        db = get_db()

        # ── Aggregate reviews per product ─────────────────────────────────────
        review_pipeline = [
            {"$group": {
                "_id":          "$product_id",
                "review_count": {"$sum": 1},
            }},
        ]
        review_stats = {
            doc["_id"]: doc
            for doc in db["reviews"].aggregate(review_pipeline)
        }

        # ── Aggregate sales per product (keep product_name from sales) ─────────
        sales_pipeline = [
            {"$group": {
                "_id":            "$product_id",
                "product_name":   {"$first": "$product_name"},
                "product_category": {"$first": "$product_category"},
                "purchase_count": {"$sum": 1},
                "total_quantity": {"$sum": "$quantity"},
            }},
        ]
        sales_stats = {
            doc["_id"]: doc
            for doc in db["sales"].aggregate(sales_pipeline)
        }

        # ── Merge on product_id ───────────────────────────────────────────────
        all_product_ids = set(review_stats.keys()) | set(sales_stats.keys())
        products = []
        for pid in sorted(all_product_ids):
            r = review_stats.get(pid, {})
            s = sales_stats.get(pid, {})
            products.append({
                "product_id":       pid,
                "product_name":     s.get("product_name", None),
                "product_category": s.get("product_category", None),
                "review_count":     r.get("review_count", 0),
                "purchase_count":   s.get("purchase_count", 0),
                "total_quantity":   s.get("total_quantity", 0),
            })

        # Sort by review_count desc so most-reviewed products appear first
        products.sort(key=lambda x: x["review_count"], reverse=True)

        return {"products": products, "total": len(products)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Products query failed: {str(e)}")
