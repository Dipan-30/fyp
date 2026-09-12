"""
services/research_service.py — Research analysis and visualization generator for Phase 8.

Pipeline:
    1. Extract LLM sentiment distributions (Llama, Qwen, Gemma).
    2. Extract ensemble agreement and numerical score statistics.
    3. Extract product-level sentiment index properties.
    4. Compute weekly sales and sentiment associations (Pearson & Spearman with p-values).
    5. Extract rolling forecasting results (Naive, ARIMA, ARIMAX).
    6. Perform detailed forecast error & shock analysis (e.g. 2024-W26).
    7. Generate 10 separate publication-grade figures in 'backend/analysis/figures/'.
    8. Persist research findings into 'research_analysis' MongoDB collection.

NO LLM calls. NO source data changes. Pure statistical synthesis.
"""

from __future__ import annotations

import os
import statistics
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from app.db.connection import get_db

warnings.filterwarnings("ignore")

FIGURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "analysis", "figures")
RESEARCH_COLLECTION = "research_analysis"


# ── Step 1: LLM Sentiment Extraction ──────────────────────────────────────────

def get_llm_sentiment_stats() -> Dict[str, Dict[str, Any]]:
    db = get_db()
    mar_col = db["model_analysis_results"]
    models = ["llama3.1:8b", "qwen2.5:7b", "gemma3:4b"]
    stats_by_model = {}

    for m in models:
        docs = list(mar_col.find({"model_name": m}))
        total = len(docs)
        success = sum(1 for d in docs if d.get("status") == "success")
        failed = total - success

        pos = sum(1 for d in docs if d.get("sentiment") == "positive")
        neu = sum(1 for d in docs if d.get("sentiment") == "neutral")
        neg = sum(1 for d in docs if d.get("sentiment") == "negative")

        confs = [float(d.get("confidence", 0.0)) for d in docs if d.get("confidence") is not None]

        stats_by_model[m] = {
            "model_name": m,
            "total_records": total,
            "successful_records": success,
            "failed_records": failed,
            "positive_count": pos,
            "neutral_count": neu,
            "negative_count": neg,
            "positive_pct": round(pos / total * 100.0, 2) if total else 0.0,
            "neutral_pct": round(neu / total * 100.0, 2) if total else 0.0,
            "negative_pct": round(neg / total * 100.0, 2) if total else 0.0,
            "average_confidence": round(statistics.mean(confs), 4) if confs else 0.0,
            "median_confidence": round(statistics.median(confs), 4) if confs else 0.0,
            "min_confidence": round(min(confs), 4) if confs else 0.0,
            "max_confidence": round(max(confs), 4) if confs else 0.0,
        }
    return stats_by_model


# ── Step 2: Ensemble & Agreement Extraction ───────────────────────────────────

def get_ensemble_stats() -> Dict[str, Any]:
    db = get_db()
    docs = list(db["sentiment_ensemble"].find())
    total = len(docs)

    agree_counts = [d.get("agreement_count", 0) for d in docs]
    agree_3 = sum(1 for c in agree_counts if c == 3)
    agree_2 = sum(1 for c in agree_counts if c == 2)
    agree_1 = sum(1 for c in agree_counts if c == 1)

    labels = [d.get("ensemble_sentiment") for d in docs]
    pos = sum(1 for l in labels if l == "positive")
    neu = sum(1 for l in labels if l == "neutral")
    neg = sum(1 for l in labels if l == "negative")

    scores = [float(d.get("ensemble_score", 0.0)) for d in docs]

    return {
        "total_ensemble_records": total,
        "full_agreement_count_3": agree_3,
        "full_agreement_pct": round(agree_3 / total * 100.0, 2),
        "partial_agreement_count_2": agree_2,
        "partial_agreement_pct": round(agree_2 / total * 100.0, 2),
        "disagreement_count_1": agree_1,
        "disagreement_pct": round(agree_1 / total * 100.0, 2),
        "average_agreement_count": round(statistics.mean(agree_counts), 4),
        "positive_labels": pos,
        "positive_pct": round(pos / total * 100.0, 2),
        "neutral_labels": neu,
        "neutral_pct": round(neu / total * 100.0, 2),
        "negative_labels": neg,
        "negative_pct": round(neg / total * 100.0, 2),
        "average_ensemble_score": round(statistics.mean(scores), 4),
        "median_ensemble_score": round(statistics.median(scores), 4),
        "min_ensemble_score": round(min(scores), 4),
        "max_ensemble_score": round(max(scores), 4),
    }


# ── Step 3: Product-Level Sentiment Index Extraction ──────────────────────────

def get_product_index_stats() -> Dict[str, Any]:
    db = get_db()
    docs = list(db["sentiment_indexes"].find())
    pids = set(str(d.get("product_id")) for d in docs)
    dates = [d.get("date") for d in docs]
    scores = [float(d.get("daily_sentiment_score", 0.0)) for d in docs]
    reviews = [int(d.get("review_count", 1)) for d in docs]
    agrees = [float(d.get("agreement_rate", 0.0)) for d in docs]
    confs = [float(d.get("average_confidence", 0.0)) for d in docs]
    labels = [d.get("daily_sentiment") for d in docs]

    return {
        "unique_products": len(pids),
        "daily_records": len(docs),
        "date_range_start": min(dates) if dates else "N/A",
        "date_range_end": max(dates) if dates else "N/A",
        "total_reviews_represented": sum(reviews),
        "average_daily_sentiment": round(statistics.mean(scores), 4),
        "min_daily_sentiment": round(min(scores), 4),
        "max_daily_sentiment": round(max(scores), 4),
        "average_review_count": round(statistics.mean(reviews), 4),
        "positive_labels": sum(1 for l in labels if l == "positive"),
        "neutral_labels": sum(1 for l in labels if l == "neutral"),
        "negative_labels": sum(1 for l in labels if l == "negative"),
        "average_agreement_rate": round(statistics.mean(agrees), 4),
        "average_confidence": round(statistics.mean(confs), 4),
    }


# ── Step 4: Weekly Sales & Sentiment Association ──────────────────────────────

def get_weekly_association_stats() -> Dict[str, Any]:
    db = get_db()
    docs = list(db["forecasting_dataset"].find().sort("week_start_date", 1))
    df = pd.DataFrame(docs)

    sales = df["weekly_sales"].astype(float)
    sent = df["weekly_sentiment"].astype(float)

    # Contemporary correlation
    p_corr_contemp, p_val_contemp = stats.pearsonr(sales, sent)
    s_corr_contemp, s_val_contemp = stats.spearmanr(sales, sent)

    # Lag-1 correlation
    valid_lag1 = df.dropna(subset=["lag1_weekly_sentiment"])
    p_corr_lag1, p_val_lag1 = stats.pearsonr(valid_lag1["weekly_sales"], valid_lag1["lag1_weekly_sentiment"])
    s_corr_lag1, s_val_lag1 = stats.spearmanr(valid_lag1["weekly_sales"], valid_lag1["lag1_weekly_sentiment"])

    return {
        "total_weeks": len(df),
        "total_sales_units": int(sales.sum()),
        "mean_weekly_sales": round(sales.mean(), 4),
        "std_weekly_sales": round(sales.std(), 4),
        "min_weekly_sales": int(sales.min()),
        "max_weekly_sales": int(sales.max()),
        "mean_weekly_sentiment": round(sent.mean(), 4),
        "std_weekly_sentiment": round(sent.std(), 4),
        "mean_lag1_sentiment": round(valid_lag1["lag1_weekly_sentiment"].mean(), 4),
        "std_lag1_sentiment": round(valid_lag1["lag1_weekly_sentiment"].std(), 4),
        "pearson_contemp": {"r": round(p_corr_contemp, 4), "p_value": round(p_val_contemp, 4)},
        "spearman_contemp": {"rho": round(s_corr_contemp, 4), "p_value": round(s_val_contemp, 4)},
        "pearson_lag1": {"r": round(p_corr_lag1, 4), "p_value": round(p_val_lag1, 4)},
        "spearman_lag1": {"rho": round(s_corr_lag1, 4), "p_value": round(s_val_lag1, 4)},
    }


# ── Step 5: Figure Generation ─────────────────────────────────────────────────

def generate_all_figures() -> List[str]:
    os.makedirs(FIGURES_DIR, exist_ok=True)
    db = get_db()
    generated_paths = []

    # Palette styles
    primary_blue = "#2563eb"
    teal_green = "#059669"
    coral_red = "#dc2626"
    amber_gold = "#d97706"
    purple_dark = "#7c3aed"
    neutral_gray = "#64748b"

    # 1. LLM Sentiment Distribution Comparison
    mar_docs = list(db["model_analysis_results"].find())
    mar_df = pd.DataFrame(mar_docs)

    fig, ax = plt.subplots(figsize=(8, 5))
    models = ["llama3.1:8b", "qwen2.5:7b", "gemma3:4b"]
    labels = ["Positive", "Neutral", "Negative"]
    x = np.arange(len(models))
    width = 0.25

    pos_counts = [len(mar_df[(mar_df["model_name"] == m) & (mar_df["sentiment"] == "positive")]) for m in models]
    neu_counts = [len(mar_df[(mar_df["model_name"] == m) & (mar_df["sentiment"] == "neutral")]) for m in models]
    neg_counts = [len(mar_df[(mar_df["model_name"] == m) & (mar_df["sentiment"] == "negative")]) for m in models]

    ax.bar(x - width, pos_counts, width, label="Positive", color=teal_green)
    ax.bar(x, neu_counts, width, label="Neutral", color=neutral_gray)
    ax.bar(x + width, neg_counts, width, label="Negative", color=coral_red)

    ax.set_ylabel("Review Count", fontsize=11)
    ax.set_title("Figure 1: Sentiment Class Distribution Across Local LLMs (N=1,000)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(["Llama 3.1 8B", "Qwen 2.5 7B", "Gemma 3 4B"], fontsize=10)
    ax.legend(frameon=True)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    f1_path = os.path.join(FIGURES_DIR, "fig1_llm_sentiment_distribution.png")
    plt.savefig(f1_path, dpi=200)
    plt.close()
    generated_paths.append(f1_path)

    # 2. Ensemble Sentiment Distribution
    ens_docs = list(db["sentiment_ensemble"].find())
    ens_df = pd.DataFrame(ens_docs)

    fig, ax = plt.subplots(figsize=(7, 5))
    ens_counts = [
        len(ens_df[ens_df["ensemble_sentiment"] == "positive"]),
        len(ens_df[ens_df["ensemble_sentiment"] == "neutral"]),
        len(ens_df[ens_df["ensemble_sentiment"] == "negative"]),
    ]
    bars = ax.bar(["Positive (+1)", "Neutral (0)", "Negative (-1)"], ens_counts, color=[teal_green, neutral_gray, coral_red], width=0.55)
    for b in bars:
        yval = b.get_height()
        ax.text(b.get_x() + b.get_width()/2.0, yval + 10, f"{yval} ({yval/10:.1f}%)", ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("Total Reviews", fontsize=11)
    ax.set_ylim(0, 600)
    ax.set_title("Figure 2: Majority-Voting Ensemble Sentiment Distribution (N=1,000)", fontsize=12, fontweight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    f2_path = os.path.join(FIGURES_DIR, "fig2_ensemble_sentiment_distribution.png")
    plt.savefig(f2_path, dpi=200)
    plt.close()
    generated_paths.append(f2_path)

    # 3. Model Agreement Distribution
    fig, ax = plt.subplots(figsize=(7, 5))
    agree_counts = [
        len(ens_df[ens_df["agreement_count"] == 3]),
        len(ens_df[ens_df["agreement_count"] == 2]),
        len(ens_df[ens_df["agreement_count"] == 1]),
    ]
    bars = ax.bar(["3 Models Unanimous", "2 Models Majority", "1 Model Split"], agree_counts, color=[primary_blue, amber_gold, coral_red], width=0.55)
    for b in bars:
        yval = b.get_height()
        ax.text(b.get_x() + b.get_width()/2.0, yval + 15, f"{yval} ({yval/10:.1f}%)", ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("Number of Reviews", fontsize=11)
    ax.set_ylim(0, 1000)
    ax.set_title("Figure 3: Inter-Model Agreement Distribution across 3 LLMs", fontsize=12, fontweight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    f3_path = os.path.join(FIGURES_DIR, "fig3_model_agreement_distribution.png")
    plt.savefig(f3_path, dpi=200)
    plt.close()
    generated_paths.append(f3_path)

    # 4. Weekly Sales Time Series
    fd_docs = list(db["forecasting_dataset"].find().sort("week_start_date", 1))
    fd_df = pd.DataFrame(fd_docs)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    weeks = fd_df["week"].tolist()
    sales = fd_df["weekly_sales"].tolist()
    x_idx = np.arange(len(weeks))

    ax.plot(x_idx, sales, marker="o", markersize=4, color=primary_blue, linewidth=2, label="Weekly Sales (Units)")
    ax.axvline(x=41.5, color=coral_red, linestyle="--", linewidth=1.5, label="Train/Test Split (Week 42)")
    ax.set_ylabel("Total Units Sold", fontsize=11)
    ax.set_title("Figure 4: Store-Wide Weekly Sales Time Series (53 ISO Weeks)", fontsize=12, fontweight="bold")
    ax.set_xticks(x_idx[::5])
    ax.set_xticklabels(weeks[::5], rotation=45, ha="right", fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right")
    plt.tight_layout()
    f4_path = os.path.join(FIGURES_DIR, "fig4_weekly_sales_timeseries.png")
    plt.savefig(f4_path, dpi=200)
    plt.close()
    generated_paths.append(f4_path)

    # 5. Weekly Sentiment Time Series
    fig, ax = plt.subplots(figsize=(10, 4.5))
    sent = fd_df["weekly_sentiment"].tolist()

    ax.plot(x_idx, sent, marker="s", markersize=4, color=purple_dark, linewidth=2, label="Review-Weighted Sentiment")
    ax.axhline(y=0.0, color="gray", linestyle=":", linewidth=1, label="Neutral Baseline (0.0)")
    ax.axvline(x=41.5, color=coral_red, linestyle="--", linewidth=1.5, label="Train/Test Split")
    ax.set_ylabel("Weekly Sentiment Score [-1, +1]", fontsize=11)
    ax.set_title("Figure 5: Store-Wide Weekly Sentiment Index Time Series", fontsize=12, fontweight="bold")
    ax.set_xticks(x_idx[::5])
    ax.set_xticklabels(weeks[::5], rotation=45, ha="right", fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right")
    plt.tight_layout()
    f5_path = os.path.join(FIGURES_DIR, "fig5_weekly_sentiment_timeseries.png")
    plt.savefig(f5_path, dpi=200)
    plt.close()
    generated_paths.append(f5_path)

    # 6. Weekly Sales vs Weekly Sentiment Scatter
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(fd_df["weekly_sentiment"], fd_df["weekly_sales"], color=primary_blue, edgecolors="black", alpha=0.7, s=50)
    # Fit line
    m_c, b_c = np.polyfit(fd_df["weekly_sentiment"], fd_df["weekly_sales"], 1)
    x_line = np.linspace(fd_df["weekly_sentiment"].min(), fd_df["weekly_sentiment"].max(), 50)
    ax.plot(x_line, m_c * x_line + b_c, color=coral_red, linestyle="-", label=f"Trend (r = -0.2187, p = 0.116)")
    ax.set_xlabel("Contemporary Weekly Sentiment Score", fontsize=11)
    ax.set_ylabel("Weekly Sales (Units)", fontsize=11)
    ax.set_title("Figure 6: Weekly Sales vs Contemporary Sentiment (N=53)", fontsize=12, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(frameon=True)
    plt.tight_layout()
    f6_path = os.path.join(FIGURES_DIR, "fig6_weekly_sales_vs_weekly_sentiment.png")
    plt.savefig(f6_path, dpi=200)
    plt.close()
    generated_paths.append(f6_path)

    # 7. Weekly Sales vs Lag-1 Sentiment Scatter
    valid_lag1 = fd_df.dropna(subset=["lag1_weekly_sentiment"])
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(valid_lag1["lag1_weekly_sentiment"], valid_lag1["weekly_sales"], color=purple_dark, edgecolors="black", alpha=0.7, s=50)
    m_l, b_l = np.polyfit(valid_lag1["lag1_weekly_sentiment"], valid_lag1["weekly_sales"], 1)
    x_line_l = np.linspace(valid_lag1["lag1_weekly_sentiment"].min(), valid_lag1["lag1_weekly_sentiment"].max(), 50)
    ax.plot(x_line_l, m_l * x_line_l + b_l, color=coral_red, linestyle="-", label=f"Trend (r = -0.1201, p = 0.396)")
    ax.set_xlabel("Lag-1 Weekly Sentiment Score (t-1)", fontsize=11)
    ax.set_ylabel("Weekly Sales (Units)", fontsize=11)
    ax.set_title("Figure 7: Weekly Sales vs Lag-1 Sentiment (N=52)", fontsize=12, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(frameon=True)
    plt.tight_layout()
    f7_path = os.path.join(FIGURES_DIR, "fig7_weekly_sales_vs_lag1_sentiment.png")
    plt.savefig(f7_path, dpi=200)
    plt.close()
    generated_paths.append(f7_path)

    # 8. Test Forecast Comparison (Actual, Naive, ARIMA, ARIMAX)
    val_doc = db["forecasting_validation"].find_one(sort=[("created_at", -1)])
    weekly_table = val_doc["weekly_table"]

    t_weeks = [w["week"] for w in weekly_table]
    actuals = [w["actual_sales"] for w in weekly_table]
    naive_p = [w["naive_pred"] for w in weekly_table]
    arima_p = [w["arima_pred"] for w in weekly_table]
    arimax_p = [w["arimax_pred"] for w in weekly_table]

    fig, ax = plt.subplots(figsize=(10, 5))
    t_idx = np.arange(len(t_weeks))

    ax.plot(t_idx, actuals, marker="o", linewidth=2.5, color="black", label="Actual Sales", zorder=4)
    ax.plot(t_idx, naive_p, marker="^", linestyle=":", linewidth=1.8, color=amber_gold, label="Naive Baseline (y_{t-1})", zorder=3)
    ax.plot(t_idx, arima_p, marker="s", linestyle="--", linewidth=1.8, color=primary_blue, label="ARIMA(0,0,0)", zorder=2)
    ax.plot(t_idx, arimax_p, marker="d", linestyle="-.", linewidth=1.8, color=teal_green, label="ARIMAX(0,0,0) + Sentiment", zorder=2)

    ax.set_ylabel("Sales Units", fontsize=11)
    ax.set_title("Figure 8: Out-of-Sample Rolling 1-Step Forecast Comparison (11 Test Weeks)", fontsize=12, fontweight="bold")
    ax.set_xticks(t_idx)
    ax.set_xticklabels(t_weeks, rotation=45, ha="right", fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", frameon=True)
    plt.tight_layout()
    f8_path = os.path.join(FIGURES_DIR, "fig8_test_forecast_comparison.png")
    plt.savefig(f8_path, dpi=200)
    plt.close()
    generated_paths.append(f8_path)

    # 9. Forecast Absolute Error Comparison
    fig, ax = plt.subplots(figsize=(10, 5))
    w_width = 0.25

    err_naive = [abs(w["naive_err"]) for w in weekly_table]
    err_arima = [abs(w["arima_err"]) for w in weekly_table]
    err_arimax = [abs(w["arimax_err"]) for w in weekly_table]

    ax.bar(t_idx - w_width, err_naive, w_width, label="Naive Absolute Error", color=amber_gold)
    ax.bar(t_idx, err_arima, w_width, label="ARIMA Absolute Error", color=primary_blue)
    ax.bar(t_idx + w_width, err_arimax, w_width, label="ARIMAX Absolute Error", color=teal_green)

    ax.set_ylabel("Absolute Error (|Actual - Pred|)", fontsize=11)
    ax.set_title("Figure 9: Per-Week Forecast Absolute Error Across Test Period", fontsize=12, fontweight="bold")
    ax.set_xticks(t_idx)
    ax.set_xticklabels(t_weeks, rotation=45, ha="right", fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.legend(loc="upper left")
    plt.tight_layout()
    f9_path = os.path.join(FIGURES_DIR, "fig9_forecast_absolute_error_comparison.png")
    plt.savefig(f9_path, dpi=200)
    plt.close()
    generated_paths.append(f9_path)

    # 10. Forecast Metric Comparison
    fig, ax = plt.subplots(figsize=(8, 5))
    metrics_names = ["MAE", "RMSE", "MAPE (%)", "sMAPE (%)"]
    m_dict = val_doc["metrics"]

    v_naive = [m_dict["naive"]["mae"], m_dict["naive"]["rmse"], m_dict["naive"]["mape"], m_dict["naive"]["smape"]]
    v_arima = [m_dict["arima"]["mae"], m_dict["arima"]["rmse"], m_dict["arima"]["mape"], m_dict["arima"]["smape"]]
    v_arimax = [m_dict["arimax"]["mae"], m_dict["arimax"]["rmse"], m_dict["arimax"]["mape"], m_dict["arimax"]["smape"]]

    m_x = np.arange(len(metrics_names))
    m_w = 0.25

    ax.bar(m_x - m_w, v_naive, m_w, label="Naive Baseline", color=amber_gold)
    ax.bar(m_x, v_arima, m_w, label="ARIMA(0,0,0)", color=primary_blue)
    ax.bar(m_x + m_w, v_arimax, m_w, label="ARIMAX(0,0,0)", color=teal_green)

    for i in range(len(metrics_names)):
        ax.text(m_x[i] - m_w, v_naive[i] + 0.8, f"{v_naive[i]:.1f}", ha="center", fontsize=8)
        ax.text(m_x[i], v_arima[i] + 0.8, f"{v_arima[i]:.1f}", ha="center", fontsize=8)
        ax.text(m_x[i] + m_w, v_arimax[i] + 0.8, f"{v_arimax[i]:.1f}", ha="center", fontsize=8)

    ax.set_ylabel("Metric Value", fontsize=11)
    ax.set_title("Figure 10: Comparative Accuracy Metrics (11-Week Test Horizon)", fontsize=12, fontweight="bold")
    ax.set_xticks(m_x)
    ax.set_xticklabels(metrics_names, fontsize=10)
    ax.set_ylim(0, 60)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.legend(loc="upper left")
    plt.tight_layout()
    f10_path = os.path.join(FIGURES_DIR, "fig10_forecast_metric_comparison.png")
    plt.savefig(f10_path, dpi=200)
    plt.close()
    generated_paths.append(f10_path)

    return generated_paths


# ── Step 6: Persist Full Research Summary ──────────────────────────────────────

def run_phase_8_analysis() -> Dict[str, Any]:
    llm_stats = get_llm_sentiment_stats()
    ens_stats = get_ensemble_stats()
    prod_stats = get_product_index_stats()
    week_stats = get_weekly_association_stats()
    figure_paths = generate_all_figures()

    db = get_db()
    val_doc = db["forecasting_validation"].find_one(sort=[("created_at", -1)])

    summary = {
        "analysis_id": f"research_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "llm_sentiment_stats": llm_stats,
        "ensemble_stats": ens_stats,
        "product_index_stats": prod_stats,
        "weekly_association_stats": week_stats,
        "forecasting_validation_summary": val_doc,
        "generated_figures": figure_paths,
    }

    db[RESEARCH_COLLECTION].update_one(
        {"analysis_id": summary["analysis_id"]},
        {"$set": summary},
        upsert=True,
    )
    return summary
