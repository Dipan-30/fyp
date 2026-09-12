"""
services/product_forecast_service.py — Service layer for individual product sales forecasting.
"""
from typing import Dict, Any
import numpy as np
import pandas as pd
from datetime import timedelta
from statsmodels.tsa.arima.model import ARIMA
from app.db.connection import get_db

def compute_metrics(actuals: np.ndarray, predictions: np.ndarray) -> Dict[str, float]:
    errors = actuals - predictions
    abs_errors = np.abs(errors)
    sq_errors = errors ** 2
    
    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(sq_errors)))
    
    # safe mape
    with np.errstate(divide='ignore', invalid='ignore'):
        mape_array = np.where(actuals == 0, 0, np.abs(errors / actuals))
        mape = float(np.mean(mape_array) * 100.0)
        
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 4)
    }

def get_product_forecast(product_id: str) -> Dict[str, Any]:
    db = get_db()
    
    # 1. Fetch Sales and Aggregate Weekly
    sales_docs = list(db["sales"].find({"product_id": str(product_id)}))
    if not sales_docs:
        return {"forecast_feasible": False, "reason": "No sales data found for product."}
    
    sales_df = pd.DataFrame(sales_docs)
    sales_df["purchase_date"] = pd.to_datetime(sales_df["purchase_date"])
    sales_df["quantity"] = sales_df["quantity"].astype(float)
    
    # Group by week starting Monday
    # Set purchase_date as index
    sales_df.set_index("purchase_date", inplace=True)
    weekly_sales = sales_df.resample('W-MON')["quantity"].sum().reset_index()
    weekly_sales.columns = ["week_start", "weekly_sales"]
    
    # Filter out empty periods to some extent? Or keep them. Keep them to maintain time series structure.
    # To avoid huge gaps, we only consider the range from first purchase to last purchase
    if weekly_sales.empty:
        return {"forecast_feasible": False, "reason": "Could not aggregate sales data."}
        
    first_week = weekly_sales["week_start"].min()
    last_week = weekly_sales["week_start"].max()
    
    # Reindex to ensure all weeks are present, fill missing with 0
    full_idx = pd.date_range(start=first_week, end=last_week, freq='W-MON')
    weekly_sales.set_index("week_start", inplace=True)
    weekly_sales = weekly_sales.reindex(full_idx, fill_value=0).reset_index()
    weekly_sales.columns = ["week_start", "weekly_sales"]
    
    total_obs = len(weekly_sales)
    
    if total_obs < 10:
        return {
            "forecast_feasible": False, 
            "reason": f"Insufficient historical observations. Found {total_obs} weekly periods, minimum required is 10."
        }
        
    # 2. Fetch Sentiment and Aggregate Weekly
    sent_docs = list(db["sentiment_indexes"].find({"product_id": str(product_id)}))
    sentiment_available = False
    
    if sent_docs:
        sent_df = pd.DataFrame(sent_docs)
        sent_df["date"] = pd.to_datetime(sent_df["date"])
        sent_df["daily_sentiment_score"] = sent_df["daily_sentiment_score"].astype(float)
        
        sent_df.set_index("date", inplace=True)
        weekly_sent = sent_df.resample('W-MON')["daily_sentiment_score"].mean().reset_index()
        weekly_sent.columns = ["week_start", "weekly_sentiment"]
        
        # Merge with weekly sales
        weekly_sales = pd.merge(weekly_sales, weekly_sent, on="week_start", how="left")
        weekly_sales["weekly_sentiment"] = weekly_sales["weekly_sentiment"].fillna(0.0) # Assume 0 sentiment if no reviews
        
        # Create lag-1 sentiment
        weekly_sales["lag1_sentiment"] = weekly_sales["weekly_sentiment"].shift(1)
        sentiment_available = True
    else:
        weekly_sales["weekly_sentiment"] = 0.0
        weekly_sales["lag1_sentiment"] = 0.0

    # 3. Train / Test Split
    # We will use 80% train, 20% test chronologically
    train_size = int(total_obs * 0.8)
    # Ensure test size is at least 1
    if train_size == total_obs:
        train_size = total_obs - 1
        
    train_df = weekly_sales.iloc[1:train_size].copy() # Skip row 0 due to null lag-1
    test_df = weekly_sales.iloc[train_size:].copy()
    
    actual_vals = []
    naive_preds = []
    arima_preds = []
    arimax_preds = []
    
    # 4. Rolling Evaluation on Test Set
    order = (1, 0, 0)
    for t in range(train_size, total_obs):
        hist_df = weekly_sales.iloc[1:t].copy()
        current_test_row = weekly_sales.iloc[t]
        
        y_hist = hist_df["weekly_sales"].values.astype(float)
        actual_y = float(current_test_row["weekly_sales"])
        
        # Naive: last observed value
        y_naive = y_hist[-1] if len(y_hist) > 0 else 0
        
        # ARIMA
        try:
            m_arima = ARIMA(y_hist, order=order).fit()
            y_arima = float(m_arima.forecast(steps=1)[0])
        except:
            y_arima = y_naive
            
        # ARIMAX
        y_arimax = y_arima
        if sentiment_available:
            X_hist = hist_df["lag1_sentiment"].values.astype(float)
            test_x = float(current_test_row["lag1_sentiment"])
            try:
                m_arimax = ARIMA(y_hist, exog=X_hist, order=order).fit()
                y_arimax = float(m_arimax.forecast(steps=1, exog=[test_x])[0])
            except:
                pass
                
        actual_vals.append(actual_y)
        naive_preds.append(y_naive)
        arima_preds.append(y_arima)
        arimax_preds.append(y_arimax)
        
    naive_metrics = compute_metrics(np.array(actual_vals), np.array(naive_preds))
    arima_metrics = compute_metrics(np.array(actual_vals), np.array(arima_preds))
    
    arimax_metrics = None
    if sentiment_available:
        arimax_metrics = compute_metrics(np.array(actual_vals), np.array(arimax_preds))
        
    # 5. Future Forecasting (Next 7 periods)
    future_periods = 7
    full_y = weekly_sales["weekly_sales"].values.astype(float)
    full_X = weekly_sales["lag1_sentiment"].values.astype(float) if sentiment_available else None
    
    future_arima = []
    future_arimax = []
    
    try:
        m_arima_full = ARIMA(full_y, order=order).fit()
        future_arima = m_arima_full.forecast(steps=future_periods).tolist()
    except:
        future_arima = [full_y[-1]] * future_periods
        
    if sentiment_available:
        try:
            m_arimax_full = ARIMA(full_y, exog=full_X, order=order).fit()
            # For future exog, we assume neutral (0.0) sentiment for simplicity since we don't know future lag-1 sentiment
            # Wait, for step 1, lag-1 sentiment is the current week's sentiment!
            # For steps > 1, we don't have it. We assume 0.0.
            future_exog = [float(weekly_sales.iloc[-1]["weekly_sentiment"])] + [0.0] * (future_periods - 1)
            future_arimax = m_arimax_full.forecast(steps=future_periods, exog=future_exog).tolist()
        except:
            future_arimax = future_arima
    
    # Format output
    last_week_date = weekly_sales.iloc[-1]["week_start"]
    future_dates = [(last_week_date + timedelta(weeks=i)).strftime("%Y-%m-%d") for i in range(1, future_periods + 1)]
    
    future_predictions = []
    for i in range(future_periods):
        future_predictions.append({
            "date": future_dates[i],
            "arima_pred": round(future_arima[i], 2) if len(future_arima) > i else 0,
            "arimax_pred": round(future_arimax[i], 2) if sentiment_available and len(future_arimax) > i else None
        })
        
    improvement = None
    if sentiment_available and arima_metrics["mae"] > 0:
        improvement = round((arima_metrics["mae"] - arimax_metrics["mae"]) / arima_metrics["mae"] * 100, 2)
        
    # Prepare historical chart data
    chart_data = []
    for _, row in weekly_sales.iterrows():
        chart_data.append({
            "date": row["week_start"].strftime("%Y-%m-%d"),
            "actual_sales": float(row["weekly_sales"])
        })
        
    return {
        "forecast_feasible": True,
        "historical_observations": total_obs,
        "train_observations": train_size,
        "test_observations": len(actual_vals),
        "sentiment_available": sentiment_available,
        "metrics": {
            "naive": naive_metrics,
            "arima": arima_metrics,
            "arimax": arimax_metrics
        },
        "improvement_pct": improvement,
        "future_predictions": future_predictions,
        "historical_chart": chart_data
    }
