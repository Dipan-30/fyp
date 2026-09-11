"""
routers/dataset.py — Dataset import and statistics endpoints.

Endpoints:
  POST /api/dataset/import   — trigger CSV → MongoDB import
  GET  /api/dataset/stats    — dataset-level statistics from MongoDB
"""

from fastapi import APIRouter, HTTPException
from app.db.connection import get_db
from app.services.import_service import import_all

router = APIRouter(prefix="/api/dataset", tags=["Dataset"])


@router.post("/import")
def trigger_import():
    """
    Load both CSVs, preprocess, and upsert into MongoDB.
    Safe to call multiple times — will not create duplicates.
    """
    try:
        result = import_all()
        return {"status": "ok", "result": result}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/stats")
def get_dataset_stats():
    """
    Return dataset-level statistics computed from live MongoDB data.
    """
    try:
        db = get_db()
        reviews_col = db["reviews"]
        sales_col   = db["sales"]

        # ── Counts ────────────────────────────────────────────────────────────
        review_count = reviews_col.count_documents({})
        sales_count  = sales_col.count_documents({})

        # ── Unique products ───────────────────────────────────────────────────
        review_products = reviews_col.distinct("product_id")
        sales_products  = sales_col.distinct("product_id")
        all_products    = set(review_products) | set(sales_products)
        overlap         = set(review_products) & set(sales_products)

        # ── Date ranges ───────────────────────────────────────────────────────
        def date_range(col, field):
            mn = col.find_one({field: {"$exists": True}}, sort=[(field, 1)])
            mx = col.find_one({field: {"$exists": True}}, sort=[(field, -1)])
            return (
                mn[field] if mn else None,
                mx[field] if mx else None,
            )

        r_min, r_max = date_range(reviews_col, "review_date")
        s_min, s_max = date_range(sales_col,   "purchase_date")

        # ── Totals ────────────────────────────────────────────────────────────
        qty_agg = list(sales_col.aggregate([
            {"$group": {"_id": None, "total": {"$sum": "$quantity"}}}
        ]))
        total_quantity = qty_agg[0]["total"] if qty_agg else 0

        # ── Averages ──────────────────────────────────────────────────────────
        num_review_products   = len(review_products)
        num_sales_products    = len(sales_products)
        avg_reviews_per_prod  = round(review_count / num_review_products, 2) if num_review_products else 0
        avg_purchases_per_prod = round(sales_count / num_sales_products, 2)  if num_sales_products  else 0

        return {
            "review_count":            review_count,
            "sales_transaction_count": sales_count,
            "unique_products_total":   len(all_products),
            "unique_products_reviews": num_review_products,
            "unique_products_sales":   num_sales_products,
            "product_overlap_count":   len(overlap),
            "review_date_min":         r_min,
            "review_date_max":         r_max,
            "sales_date_min":          s_min,
            "sales_date_max":          s_max,
            "total_purchase_quantity": total_quantity,
            "avg_reviews_per_product": avg_reviews_per_prod,
            "avg_purchases_per_product": avg_purchases_per_prod,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats query failed: {str(e)}")
