"""
services/forecasting_validation_service.py — Forecasting validation & robustness analytics.

Features:
    1. Naive Previous-Week Baseline (y_hat_t = y_{t-1}).
    2. Exact exogenous sentiment alignment verification across all 11 test weeks (X_t == s_{t-1}).
    3. ARIMAX sentiment coefficient extraction: beta, std err, z-stat, p-value, 95% CI.
    4. Tri-model comparative metrics: Naive, ARIMA(0,0,0), ARIMAX(0,0,0) (MAE, RMSE, MAPE, sMAPE).
    5. Diebold-Mariano (DM) test with Harvey, Leybourne & Newbold (HLN) small-sample correction for h=1.
    6. Persistence into 'forecasting_validation' collection in MongoDB.

NO LLM calls. NO source modifications. Pure statistical validation.
"""

from __future__ import annotations

import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from pymongo import ASCENDING, UpdateOne
from scipy import stats
from statsmodels.tsa.arima.model import ARIMA

from app.db.connection import get_db
from app.services.forecasting_service import (
    DATASET_COLLECTION,
    compute_forecast_metrics,
    get_train_test_split,
    load_forecasting_data,
    run_rolling_forecast,
)

warnings.filterwarnings("ignore")

VALIDATION_COLLECTION = "forecasting_validation"


# ── MongoDB Index ─────────────────────────────────────────────────────────────

def create_validation_indexes() -> None:
    """
    Create unique index on forecasting_validation collection.
    """
    db = get_db()
    col = db[VALIDATION_COLLECTION]
    col.create_index([("validation_id", ASCENDING)], unique=True, name="idx_fv_unique_id")


# ── 1. Exogenous Sentiment Alignment Verification ─────────────────────────────

def verify_test_sentiment_alignment(df: pd.DataFrame, test_start_idx: int = 42) -> List[Dict[str, Any]]:
    """
    Verify for all test weeks that X_t (lag1_weekly_sentiment) strictly equals
    s_{t-1} (the actual sentiment observed in the immediately preceding week).
    """
    alignments = []
    for t in range(test_start_idx, len(df)):
        prev_row = df.iloc[t - 1]
        curr_row = df.iloc[t]

        actual_y = float(curr_row["weekly_sales"])
        prev_y = float(prev_row["weekly_sales"])
        curr_lag1_x = float(curr_row["lag1_weekly_sentiment"])
        prev_sent = float(prev_row["weekly_sentiment"])

        is_aligned = abs(curr_lag1_x - prev_sent) < 1e-6

        alignments.append({
            "week": curr_row["week"],
            "week_start_date": curr_row["week_start_date"],
            "week_end_date": curr_row["week_end_date"],
            "actual_sales": actual_y,
            "previous_sales": prev_y,
            "current_exog_lag1": curr_lag1_x,
            "previous_week_sentiment": prev_sent,
            "alignment_valid": is_aligned,
        })
    return alignments


# ── 2. ARIMAX Sentiment Coefficient Extraction ────────────────────────────────

def extract_arimax_parameters(
    train_df: pd.DataFrame,
    order: Tuple[int, int, int] = (0, 0, 0),
) -> Dict[str, Any]:
    """
    Fit ARIMAX on training dataset and extract sentiment coefficient beta,
    standard error, z-statistic, p-value, and 95% confidence interval.
    """
    y_train = train_df["weekly_sales"].values.astype(float)
    X_train = train_df["lag1_weekly_sentiment"].values.astype(float)

    model_fit = ARIMA(y_train, exog=X_train, order=order).fit()

    # Parameter index 1 corresponds to exogenous feature x1
    beta = float(model_fit.params[1])
    std_err = float(model_fit.bse[1])
    z_stat = float(model_fit.tvalues[1])
    p_val = float(model_fit.pvalues[1])
    ci = model_fit.conf_int()
    ci_lower = float(ci[1, 0])
    ci_upper = float(ci[1, 1])

    return {
        "model_order": f"({order[0]},{order[1]},{order[2]})",
        "beta_sentiment": round(beta, 4),
        "std_error": round(std_err, 4),
        "z_statistic": round(z_stat, 4),
        "p_value": round(p_val, 4),
        "conf_int_95": [round(ci_lower, 4), round(ci_upper, 4)],
        "statistically_significant_05": p_val < 0.05,
        "aic": round(float(model_fit.aic), 2),
        "bic": round(float(model_fit.bic), 2),
    }


# ── 3. Naive Baseline Rolling Forecast ────────────────────────────────────────

def run_naive_forecast(df: pd.DataFrame, test_start_idx: int = 42) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """
    Execute rolling one-step-ahead forecast using Naive previous-week sales (y_hat_t = y_{t-1}).
    """
    predictions_records: List[Dict[str, Any]] = []
    actual_vals: List[float] = []
    pred_vals: List[float] = []

    for t in range(test_start_idx, len(df)):
        prev_row = df.iloc[t - 1]
        curr_row = df.iloc[t]

        actual_y = float(curr_row["weekly_sales"])
        pred_y = float(prev_row["weekly_sales"])

        error = round(actual_y - pred_y, 4)
        abs_err = round(abs(error), 4)
        sq_err = round(error ** 2, 4)

        record = {
            "week": curr_row["week"],
            "week_start_date": curr_row["week_start_date"],
            "week_end_date": curr_row["week_end_date"],
            "actual_sales": actual_y,
            "predicted_sales": pred_y,
            "error": error,
            "absolute_error": abs_err,
            "squared_error": sq_err,
        }
        predictions_records.append(record)
        actual_vals.append(actual_y)
        pred_vals.append(pred_y)

    metrics = compute_forecast_metrics(np.array(actual_vals), np.array(pred_vals))
    return predictions_records, metrics


# ── 4. Diebold-Mariano Statistical Test ────────────────────────────────────────

def diebold_mariano_test(
    errors_model1: np.ndarray,
    errors_model2: np.ndarray,
    loss_type: str = "squared",
    h: int = 1,
) -> Tuple[float, float]:
    """
    Perform Diebold-Mariano test with Harvey, Leybourne and Newbold (HLN, 1997)
    small-sample correction for h-step-ahead forecasts.

    Returns:
        (hln_statistic, p_value)
        - Positive DM statistic indicates Model 1 has larger loss than Model 2 (Model 2 is better).
        - Two-tailed p-value evaluated against Student-t distribution with n-1 degrees of freedom.
    """
    e1 = np.asarray(errors_model1, dtype=float)
    e2 = np.asarray(errors_model2, dtype=float)

    if loss_type == "squared":
        d = e1 ** 2 - e2 ** 2
    elif loss_type == "absolute":
        d = np.abs(e1) - np.abs(e2)
    else:
        raise ValueError("loss_type must be 'squared' or 'absolute'")

    n = len(d)
    d_mean = np.mean(d)
    gamma0 = np.var(d, ddof=1)

    if gamma0 < 1e-12:
        return 0.0, 1.0

    # Standard DM statistic
    dm_stat = d_mean / np.sqrt(gamma0 / n)

    # HLN small sample adjustment factor
    hln_factor = np.sqrt((n + 1 - 2 * h + (h * (h - 1)) / n) / n)
    hln_stat = dm_stat * hln_factor

    # Two-tailed p-value under Student-t(n-1)
    p_val = 2.0 * (1.0 - stats.t.cdf(np.abs(hln_stat), df=n - 1))

    return round(float(hln_stat), 4), round(float(p_val), 4)


# ── 5. Run Full Phase 7C Validation Pipeline ──────────────────────────────────

def run_phase_7c_validation() -> Dict[str, Any]:
    """
    Executes all Phase 7C validation routines and returns a structured validation dict.
    """
    df = load_forecasting_data()
    _, aligned_train, test_df = get_train_test_split(df, train_weeks=42)

    # 1. Verify Exogenous Alignment
    alignment_checks = verify_test_sentiment_alignment(df, test_start_idx=42)
    all_aligned = all(a["alignment_valid"] for a in alignment_checks)

    # 2. Extract ARIMAX Parameters
    arimax_params = extract_arimax_parameters(aligned_train, order=(0, 0, 0))

    # 3. Forecasts
    naive_preds, naive_metrics = run_naive_forecast(df, test_start_idx=42)
    arima_preds, arima_metrics = run_rolling_forecast(df, order=(0, 0, 0), use_exog=False, train_start_idx=1, test_start_idx=42)
    arimax_preds, arimax_metrics = run_rolling_forecast(df, order=(0, 0, 0), use_exog=True, train_start_idx=1, test_start_idx=42)

    actuals = np.array([p["actual_sales"] for p in arima_preds])
    e_naive = np.array([p["error"] for p in naive_preds])
    e_arima = np.array([p["error"] for p in arima_preds])
    e_arimax = np.array([p["error"] for p in arimax_preds])

    # 4. Diebold-Mariano Tests
    dm_arimax_arima_sq, p_arimax_arima_sq = diebold_mariano_test(e_arimax, e_arima, loss_type="squared")
    dm_arimax_arima_abs, p_arimax_arima_abs = diebold_mariano_test(e_arimax, e_arima, loss_type="absolute")

    dm_arimax_naive_sq, p_arimax_naive_sq = diebold_mariano_test(e_arimax, e_naive, loss_type="squared")
    dm_arimax_naive_abs, p_arimax_naive_abs = diebold_mariano_test(e_arimax, e_naive, loss_type="absolute")

    dm_arima_naive_sq, p_arima_naive_sq = diebold_mariano_test(e_arima, e_naive, loss_type="squared")
    dm_arima_naive_abs, p_arima_naive_abs = diebold_mariano_test(e_arima, e_naive, loss_type="absolute")

    # Combine Week-by-Week comparison
    weekly_table = []
    for i in range(len(test_df)):
        w = test_df.iloc[i]["week"]
        act = actuals[i]
        weekly_table.append({
            "week": w,
            "date_range": f"{test_df.iloc[i]['week_start_date']}..{test_df.iloc[i]['week_end_date']}",
            "actual_sales": act,
            "naive_pred": naive_preds[i]["predicted_sales"],
            "naive_err": naive_preds[i]["error"],
            "arima_pred": arima_preds[i]["predicted_sales"],
            "arima_err": arima_preds[i]["error"],
            "arimax_pred": arimax_preds[i]["predicted_sales"],
            "arimax_err": arimax_preds[i]["error"],
            "exog_sentiment": test_df.iloc[i]["lag1_weekly_sentiment"],
        })

    validation_result = {
        "validation_id": f"val_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "alignment_checks": alignment_checks,
        "all_alignments_valid": all_aligned,
        "arimax_parameters": arimax_params,
        "metrics": {
            "naive": naive_metrics,
            "arima": arima_metrics,
            "arimax": arimax_metrics,
        },
        "diebold_mariano": {
            "arimax_vs_arima": {
                "squared_loss": {"dm_stat": dm_arimax_arima_sq, "p_value": p_arimax_arima_sq},
                "absolute_loss": {"dm_stat": dm_arimax_arima_abs, "p_value": p_arimax_arima_abs},
            },
            "arimax_vs_naive": {
                "squared_loss": {"dm_stat": dm_arimax_naive_sq, "p_value": p_arimax_naive_sq},
                "absolute_loss": {"dm_stat": dm_arimax_naive_abs, "p_value": p_arimax_naive_abs},
            },
            "arima_vs_naive": {
                "squared_loss": {"dm_stat": dm_arima_naive_sq, "p_value": p_arima_naive_sq},
                "absolute_loss": {"dm_stat": dm_arima_naive_abs, "p_value": p_arima_naive_abs},
            },
        },
        "weekly_table": weekly_table,
    }

    # Persist to MongoDB
    create_validation_indexes()
    db = get_db()
    db[VALIDATION_COLLECTION].update_one(
        {"validation_id": validation_result["validation_id"]},
        {"$set": validation_result},
        upsert=True,
    )

    return validation_result
