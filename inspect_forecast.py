import sys
import os
sys.path.append(os.path.abspath('backend'))
from app.db.connection import get_db
from statsmodels.tsa.arima.model import ARIMA
import pandas as pd
import numpy as np

def inspect():
    db = get_db()
    product_id = '219'
    
    sales_docs = list(db["sales"].find({"product_id": str(product_id)}))
    sales_df = pd.DataFrame(sales_docs)
    sales_df["purchase_date"] = pd.to_datetime(sales_df["purchase_date"])
    sales_df["quantity"] = sales_df["quantity"].astype(float)
    sales_df.set_index("purchase_date", inplace=True)
    weekly_sales = sales_df.resample('W-MON')["quantity"].sum().reset_index()
    weekly_sales.columns = ["week_start", "weekly_sales"]
    
    first_week = weekly_sales["week_start"].min()
    last_week = weekly_sales["week_start"].max()
    full_idx = pd.date_range(start=first_week, end=last_week, freq='W-MON')
    weekly_sales.set_index("week_start", inplace=True)
    weekly_sales = weekly_sales.reindex(full_idx, fill_value=0).reset_index()
    weekly_sales.columns = ["week_start", "weekly_sales"]
    
    sent_docs = list(db["sentiment_indexes"].find({"product_id": str(product_id)}))
    sent_df = pd.DataFrame(sent_docs)
    sent_df["date"] = pd.to_datetime(sent_df["date"])
    sent_df["daily_sentiment_score"] = sent_df["daily_sentiment_score"].astype(float)
    sent_df.set_index("date", inplace=True)
    weekly_sent = sent_df.resample('W-MON')["daily_sentiment_score"].mean().reset_index()
    weekly_sent.columns = ["week_start", "weekly_sentiment"]
    
    weekly_sales = pd.merge(weekly_sales, weekly_sent, on="week_start", how="left")
    weekly_sales["weekly_sentiment"] = weekly_sales["weekly_sentiment"].fillna(0.0)
    weekly_sales["lag1_sentiment"] = weekly_sales["weekly_sentiment"].shift(1)
    weekly_sales.fillna(0, inplace=True)
    
    full_y = weekly_sales["weekly_sales"].values.astype(float)
    full_X = weekly_sales["lag1_sentiment"].values.astype(float)
    
    order = (1, 0, 0)
    m_arima_full = ARIMA(full_y, order=order).fit()
    m_arimax_full = ARIMA(full_y, exog=full_X, order=order).fit()
    
    future_periods = 7
    future_exog = [float(weekly_sales.iloc[-1]["weekly_sentiment"])] + [0.0] * (future_periods - 1)
    
    print("--- Sentiment Values Used ---")
    print("Recent Lag1:", full_X[-5:])
    
    print("\n--- Coefficients ---")
    print("ARIMAX Parameters:", m_arimax_full.params)
    print("Is beta zero?:", m_arimax_full.params[1] == 0) # Usually params[1] is the exog
    
    future_arima = m_arima_full.forecast(steps=future_periods).tolist()
    future_arimax = m_arimax_full.forecast(steps=future_periods, exog=future_exog).tolist()
    
    print("\n--- Predictions ---")
    print("Sales-Only:", future_arima)
    print("Sales+Sent:", future_arimax)
    
    print("\nAre they mathematically identical?", future_arima == future_arimax)
    if not (future_arima == future_arimax):
        print("Diff:", [a - b for a, b in zip(future_arima, future_arimax)])
    
if __name__ == "__main__":
    inspect()
