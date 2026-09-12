"""
services/forecasting_service.py — Rolling one-step-ahead forecasting service for ARIMA vs ARIMAX.

Pipeline:
    1. Load 'forecasting_dataset' (53 weekly observations, 2023-W26 to 2024-W26).
    2. Partition chronologically:
       - Train: First 42 weeks (2023-W26 to 2024-W15)
       - Aligned estimation train: Weeks 2 to 42 (41 observations, excluding week 1 null lag-1)
       - Test: Final 11 weeks (2024-W16 to 2024-W26)
    3. Model Selection:
       - Fit candidate orders on training data only
       - Compute AIC, BIC, Log-Likelihood, Ljung-Box residual autocorrelation test
    4. Rolling One-Step-Ahead Out-Of-Sample Forecasting (Expanding Window):
       - For each test week t (weeks 43 to 53):
         • Use all observations up to week t-1
         • Fit model on historical sales (and historical lag-1 sentiment for ARIMAX)
         • Predict week t sales using known week t lag-1 sentiment (which is sentiment from week t-1)
         • Record prediction and step forward
    5. Evaluate: MAE, RMSE, MAPE, sMAPE, and relative percentage improvement.
    6. Persist results in 'forecasting_results' and 'forecasting_runs' collections.

NO Ollama calls. NO LLM calls. Pure statistical modeling and validation.
"""

from __future__ import annotations

import uuid
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pymongo import ASCENDING, UpdateOne
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.arima.model import ARIMA

from app.db.connection import get_db

warnings.filterwarnings("ignore")


# ── Constants ─────────────────────────────────────────────────────────────────

DATASET_COLLECTION = "forecasting_dataset"
RESULTS_COLLECTION = "forecasting_results"
RUNS_COLLECTION    = "forecasting_runs"

CANDIDATE_ORDERS = [
    (0, 0, 0),
    (1, 0, 0),
    (0, 0, 1),
    (1, 0, 1),
    (0, 1, 0),
    (0, 1, 1),
    (1, 1, 0),
    (1, 1, 1),
]


# ── MongoDB Index Management ──────────────────────────────────────────────────

def create_forecasting_indexes() -> None:
    """
    Create indexes on forecasting_results and forecasting_runs collections.
    Idempotent.
    """
    db = get_db()
    res_col = db[RESULTS_COLLECTION]
    runs_col = db[RUNS_COLLECTION]

    res_col.create_index(
        [("run_id", ASCENDING), ("model_name", ASCENDING), ("week", ASCENDING)],
        unique=True,
        name="idx_fr_unique_run_model_week",
    )
    res_col.create_index([("run_id", ASCENDING)], name="idx_fr_run_id")

    # Drop old index if it was single field unique
    try:
        runs_col.drop_index("idx_fruns_unique_run_id")
    except Exception:
        pass

    runs_col.create_index(
        [("run_id", ASCENDING), ("model_name", ASCENDING)],
        unique=True,
        name="idx_fruns_unique_run_model",
    )
    runs_col.create_index([("model_name", ASCENDING)], name="idx_fruns_model_name")


# ── Data Loading & Splitting ──────────────────────────────────────────────────

def load_forecasting_data() -> pd.DataFrame:
    """
    Load forecasting_dataset chronologically sorted by week_start_date.
    """
    db = get_db()
    docs = list(db[DATASET_COLLECTION].find().sort("week_start_date", 1))
    if not docs:
        raise ValueError(f"Collection '{DATASET_COLLECTION}' is empty or does not exist.")
    df = pd.DataFrame(docs)
    df["weekly_sales"] = df["weekly_sales"].astype(float)
    return df


def get_train_test_split(df: pd.DataFrame, train_weeks: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Partition dataframe into:
      1. full_train_df: First 42 weeks (includes week 1 with null lag-1)
      2. aligned_train_df: Weeks 2 to 42 (41 weeks with valid lag-1 sentiment)
      3. test_df: Final 11 weeks (weeks 43 to 53)
    """
    full_train = df.iloc[:train_weeks].copy()
    aligned_train = df.iloc[1:train_weeks].copy()  # drop week 1 due to null lag-1
    test_df = df.iloc[train_weeks:].copy()
    return full_train, aligned_train, test_df


# ── Model Evaluation on Training Data ─────────────────────────────────────────

def evaluate_training_candidates(
    aligned_train_df: pd.DataFrame,
    orders: List[Tuple[int, int, int]] = CANDIDATE_ORDERS,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fit all candidate orders strictly on training data (aligned_train_df).
    Record AIC, BIC, Log-Likelihood, and Ljung-Box test p-value.
    """
    y_train = aligned_train_df["weekly_sales"].values.astype(float)
    X_train = aligned_train_df["lag1_weekly_sentiment"].values.astype(float)

    arima_candidates = []
    arimax_candidates = []

    for order in orders:
        # 1. ARIMA candidate
        try:
            m_arima = ARIMA(y_train, order=order).fit()
            lb_res = acorr_ljungbox(m_arima.resid, lags=[5], return_df=True)
            lb_p = float(lb_res["lb_pvalue"].iloc[0])
            arima_candidates.append({
                "order": order,
                "aic": float(round(m_arima.aic, 2)),
                "bic": float(round(m_arima.bic, 2)),
                "log_likelihood": float(round(m_arima.llf, 2)),
                "ljung_box_p5": float(round(lb_p, 4)),
                "residual_autocorr_clean": lb_p > 0.05,
            })
        except Exception as e:
            arima_candidates.append({
                "order": order,
                "error": str(e),
            })

        # 2. ARIMAX candidate
        try:
            m_arimax = ARIMA(y_train, exog=X_train, order=order).fit()
            lb_res = acorr_ljungbox(m_arimax.resid, lags=[5], return_df=True)
            lb_p = float(lb_res["lb_pvalue"].iloc[0])
            exog_p = float(m_arimax.pvalues[1]) if len(m_arimax.pvalues) > 1 else None
            arimax_candidates.append({
                "order": order,
                "aic": float(round(m_arimax.aic, 2)),
                "bic": float(round(m_arimax.bic, 2)),
                "log_likelihood": float(round(m_arimax.llf, 2)),
                "exog_pvalue": float(round(exog_p, 4)) if exog_p is not None else None,
                "ljung_box_p5": float(round(lb_p, 4)),
                "residual_autocorr_clean": lb_p > 0.05,
            })
        except Exception as e:
            arimax_candidates.append({
                "order": order,
                "error": str(e),
            })

    return {
        "arima": arima_candidates,
        "arimax": arimax_candidates,
    }


# ── Metric Computation ────────────────────────────────────────────────────────

def compute_forecast_metrics(actuals: np.ndarray, predictions: np.ndarray) -> Dict[str, float]:
    """
    Calculate MAE, RMSE, MAPE, sMAPE.
    """
    actuals = np.asarray(actuals, dtype=float)
    predictions = np.asarray(predictions, dtype=float)

    errors = actuals - predictions
    abs_errors = np.abs(errors)
    sq_errors = errors ** 2

    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(sq_errors)))
    mape = float(np.mean(abs_errors / actuals) * 100.0)
    smape = float(np.mean(2.0 * abs_errors / (np.abs(actuals) + np.abs(predictions))) * 100.0)

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 4),
        "smape": round(smape, 4),
    }


# ── Rolling One-Step-Ahead Forecaster ─────────────────────────────────────────

def run_rolling_forecast(
    df: pd.DataFrame,
    order: Tuple[int, int, int],
    use_exog: bool = False,
    train_start_idx: int = 1,
    test_start_idx: int = 42,
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """
    Execute rolling one-step-ahead forecasting over the test horizon using an expanding window.

    At each test week t:
      - Training history: indices [train_start_idx : t] (expanding history up to week t-1)
      - Predict target for week t
      - For ARIMAX: use known lag1_weekly_sentiment at week t (sentiment observed in week t-1)
      - Append actual observation after forecast generation (no future leakage)
    """
    predictions_records: List[Dict[str, Any]] = []
    actual_vals: List[float] = []
    pred_vals: List[float] = []

    total_obs = len(df)

    for t in range(test_start_idx, total_obs):
        # 1. Historical data up to week t-1
        hist_df = df.iloc[train_start_idx:t].copy()
        current_test_row = df.iloc[t]

        y_hist = hist_df["weekly_sales"].values.astype(float)
        actual_y = float(current_test_row["weekly_sales"])

        if use_exog:
            X_hist = hist_df["lag1_weekly_sentiment"].values.astype(float)
            test_x = float(current_test_row["lag1_weekly_sentiment"])
            # Fit expanding model
            model = ARIMA(y_hist, exog=X_hist, order=order).fit()
            y_pred = float(model.forecast(steps=1, exog=[test_x])[0])
        else:
            model = ARIMA(y_hist, order=order).fit()
            y_pred = float(model.forecast(steps=1)[0])

        error = round(actual_y - y_pred, 4)
        abs_err = round(abs(error), 4)
        sq_err = round(error ** 2, 4)

        record = {
            "week": current_test_row["week"],
            "week_start_date": current_test_row["week_start_date"],
            "week_end_date": current_test_row["week_end_date"],
            "actual_sales": actual_y,
            "predicted_sales": round(y_pred, 4),
            "error": error,
            "absolute_error": abs_err,
            "squared_error": sq_err,
        }
        predictions_records.append(record)
        actual_vals.append(actual_y)
        pred_vals.append(y_pred)

    metrics = compute_forecast_metrics(np.array(actual_vals), np.array(pred_vals))
    return predictions_records, metrics


# ── Database Storage ──────────────────────────────────────────────────────────

def save_experiment_results(
    run_id: str,
    model_name: str,
    order: Tuple[int, int, int],
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    predictions: List[Dict[str, Any]],
    metrics: Dict[str, float],
    training_aic: float,
    training_bic: float,
) -> None:
    """
    Persist detailed prediction records and run summary into MongoDB.
    """
    create_forecasting_indexes()
    db = get_db()
    res_col = db[RESULTS_COLLECTION]
    runs_col = db[RUNS_COLLECTION]

    now_iso = datetime.now(timezone.utc).isoformat()
    order_str = f"({order[0]},{order[1]},{order[2]})"

    # 1. Upsert prediction records
    bulk_ops = []
    for pred in predictions:
        doc = {
            "run_id": run_id,
            "model_name": model_name,
            "model_order": order_str,
            "week": pred["week"],
            "week_start_date": pred["week_start_date"],
            "week_end_date": pred["week_end_date"],
            "actual_sales": pred["actual_sales"],
            "predicted_sales": pred["predicted_sales"],
            "error": pred["error"],
            "absolute_error": pred["absolute_error"],
            "squared_error": pred["squared_error"],
            "created_at": now_iso,
        }
        bulk_ops.append(
            UpdateOne(
                {"run_id": run_id, "model_name": model_name, "week": pred["week"]},
                {"$set": doc},
                upsert=True,
            )
        )

    if bulk_ops:
        res_col.bulk_write(bulk_ops, ordered=True)

    # 2. Upsert run summary
    run_summary = {
        "run_id": run_id,
        "model_name": model_name,
        "model_order": order_str,
        "train_start": train_df.iloc[0]["week"],
        "train_end": train_df.iloc[-1]["week"],
        "test_start": test_df.iloc[0]["week"],
        "test_end": test_df.iloc[-1]["week"],
        "training_observations": len(train_df),
        "test_observations": len(test_df),
        "mae": metrics["mae"],
        "rmse": metrics["rmse"],
        "mape": metrics["mape"],
        "smape": metrics["smape"],
        "aic": training_aic,
        "bic": training_bic,
        "created_at": now_iso,
    }

    runs_col.update_one(
        {"run_id": run_id, "model_name": model_name},
        {"$set": run_summary},
        upsert=True,
    )
