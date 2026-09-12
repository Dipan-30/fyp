"""
services/product_analysis_service.py — Service layer for product-centric analysis.
"""
from typing import Dict, Any, List
import pandas as pd
from app.db.connection import get_db

def get_product_list() -> List[Dict[str, Any]]:
    db = get_db()
    
    # 1. Fetch all sales
    sales_docs = list(db["sales"].find())
    
    # 2. Fetch all reviews
    review_docs = list(db["reviews"].find())
    
    # 3. Fetch all sentiment
    sentiment_docs = list(db["sentiment_ensemble"].find())
    
    # Build product dictionary
    products = {}
    
    # Process sales
    for s in sales_docs:
        pid = str(s["product_id"])
        if pid not in products:
            products[pid] = {
                "product_id": pid,
                "product_name": s.get("product_name", f"Product {pid}"),
                "category": s.get("product_category", "Unknown"),
                "price": float(s.get("price", 0)),
                "units_sold": 0,
                "transactions": 0,
                "reviews": 0,
                "sentiment_positive": 0,
                "sentiment_neutral": 0,
                "sentiment_negative": 0,
                "sentiment_score": None,
                "sentiment": "No reviews",
                "recommendation": "Not Available"
            }
        products[pid]["units_sold"] += int(s.get("quantity", 1))
        products[pid]["transactions"] += 1
        
    # Process reviews
    review_counts = {}
    for r in review_docs:
        pid = str(r.get("product_id"))
        review_counts[pid] = review_counts.get(pid, 0) + 1
        
    for pid, count in review_counts.items():
        if pid in products:
            products[pid]["reviews"] = count
            
    # Process sentiment
    sentiment_agg = {}
    for s in sentiment_docs:
        pid = str(s.get("product_id"))
        score = float(s.get("ensemble_score", 0))
        label = s.get("ensemble_label", "neutral").lower()
        
        if pid not in sentiment_agg:
            sentiment_agg[pid] = {"sum": 0, "count": 0, "pos": 0, "neu": 0, "neg": 0}
            
        sentiment_agg[pid]["sum"] += score
        sentiment_agg[pid]["count"] += 1
        if label == "positive":
            sentiment_agg[pid]["pos"] += 1
        elif label == "negative":
            sentiment_agg[pid]["neg"] += 1
        else:
            sentiment_agg[pid]["neu"] += 1
            
    for pid, data in sentiment_agg.items():
        if pid in products:
            avg_score = round(data["sum"] / data["count"], 2)
            products[pid]["sentiment_positive"] = data["pos"]
            products[pid]["sentiment_neutral"] = data["neu"]
            products[pid]["sentiment_negative"] = data["neg"]
            products[pid]["sentiment_score"] = avg_score
            
            if avg_score >= 0.5:
                products[pid]["sentiment"] = "positive"
                products[pid]["recommendation"] = "recommended"
            elif avg_score > -0.25:
                products[pid]["sentiment"] = "neutral"
                products[pid]["recommendation"] = "consider"
            else:
                products[pid]["sentiment"] = "negative"
                products[pid]["recommendation"] = "not recommended"

    # Convert to list and sort by product_id
    result = list(products.values())
    result.sort(key=lambda x: int(x["product_id"]) if x["product_id"].isdigit() else str(x["product_id"]))
    return result

def get_product_overview(product_id: str) -> Dict[str, Any]:
    db = get_db()
    sales_docs = list(db["sales"].find({"product_id": str(product_id)}))
    review_docs = list(db["reviews"].find({"product_id": str(product_id)}))
    
    if not sales_docs and not review_docs:
        raise ValueError(f"Product {product_id} not found in sales or reviews.")
    
    total_units = sum(float(d.get("quantity", 0)) for d in sales_docs)
    tx_count = len(sales_docs)
    
    dates = [d.get("purchase_date") for d in sales_docs if d.get("purchase_date")]
    dates.sort()
    
    unique_dates = len(set(dates))
    
    name = sales_docs[0].get("product_name") if sales_docs else "Unknown"
    category = sales_docs[0].get("product_category") if sales_docs else "Unknown"
    price = sales_docs[0].get("price") if sales_docs else None
    
    return {
        "product_id": product_id,
        "product_name": name,
        "category": category,
        "price": price,
        "total_units_sold": total_units,
        "number_of_transactions": tx_count,
        "active_sales_days": unique_dates,
        "number_of_reviews": len(review_docs),
        "first_purchase_date": dates[0] if dates else None,
        "last_purchase_date": dates[-1] if dates else None,
        "average_units_per_transaction": round(total_units / tx_count, 2) if tx_count > 0 else 0
    }

def get_product_sales(product_id: str) -> List[Dict[str, Any]]:
    db = get_db()
    sales_docs = list(db["sales"].find({"product_id": str(product_id)}))
    if not sales_docs:
        return []
    
    df = pd.DataFrame(sales_docs)
    df["purchase_date"] = pd.to_datetime(df["purchase_date"])
    df["quantity"] = df["quantity"].astype(float)
    
    # Aggregate by date
    daily = df.groupby("purchase_date")["quantity"].sum().reset_index()
    daily = daily.sort_values("purchase_date")
    
    res = []
    for _, row in daily.iterrows():
        res.append({
            "date": row["purchase_date"].strftime("%Y-%m-%d"),
            "sales": float(row["quantity"])
        })
    return res

def get_product_sentiment(product_id: str) -> Dict[str, Any]:
    db = get_db()
    docs = list(db["sentiment_ensemble"].find({"product_id": str(product_id)}))
    
    if not docs:
        return {
            "review_count": 0,
            "positive_pct": 0,
            "neutral_pct": 0,
            "negative_pct": 0,
            "sentiment_score": 0,
            "average_confidence": 0,
            "agreement_pct": 0,
            "recommendation": "NOT ENOUGH DATA"
        }
    
    total = len(docs)
    labels = [d.get("ensemble_sentiment") for d in docs]
    pos = sum(1 for l in labels if l == "positive")
    neu = sum(1 for l in labels if l == "neutral")
    neg = sum(1 for l in labels if l == "negative")
    
    scores = [float(d.get("ensemble_score", 0)) for d in docs]
    confs = [float(d.get("ensemble_confidence", 0)) for d in docs]
    
    # Calculate agreement (average of agreement_count / 3)
    agreements = [int(d.get("agreement_count", 0)) for d in docs]
    avg_agreement = sum(agreements) / len(agreements) / 3.0 * 100.0
    
    avg_score = sum(scores) / total
    
    # Purchase Recommendation Logic
    if avg_score >= 0.50:
        recommendation = "RECOMMENDED"
    elif avg_score > -0.25:
        recommendation = "CONSIDER"
    else:
        recommendation = "NOT RECOMMENDED"
        
    return {
        "review_count": total,
        "positive_pct": round(pos / total * 100, 1),
        "neutral_pct": round(neu / total * 100, 1),
        "negative_pct": round(neg / total * 100, 1),
        "sentiment_score": round(avg_score, 3),
        "average_confidence": round(sum(confs) / total, 3) if confs else 0,
        "agreement_pct": round(avg_agreement, 1),
        "recommendation": recommendation
    }
