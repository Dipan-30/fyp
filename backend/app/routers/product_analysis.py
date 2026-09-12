"""
routers/product_analysis.py — Endpoints for Product-Centric Intelligence System
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from app.services.product_analysis_service import (
    get_product_list,
    get_product_overview,
    get_product_sales,
    get_product_sentiment
)
from app.services.product_forecast_service import get_product_forecast

router = APIRouter(prefix="/api/products", tags=["Products"])

@router.get("")
def list_products() -> Dict[str, Any]:
    try:
        products = get_product_list()
        return {"products": products, "total": len(products)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{product_id}")
def product_overview(product_id: str) -> Dict[str, Any]:
    try:
        return get_product_overview(product_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{product_id}/sales")
def product_sales(product_id: str) -> Dict[str, Any]:
    try:
        sales = get_product_sales(product_id)
        return {"product_id": product_id, "sales": sales}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{product_id}/sentiment")
def product_sentiment(product_id: str) -> Dict[str, Any]:
    try:
        return get_product_sentiment(product_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{product_id}/forecast")
def product_forecast(product_id: str) -> Dict[str, Any]:
    try:
        return get_product_forecast(product_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
