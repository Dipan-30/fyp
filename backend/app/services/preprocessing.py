"""
services/preprocessing.py — Dataset-specific CSV preprocessing.

IMPORTANT: Preprocessing is hardcoded for these two specific files:
  - customer_reviews_data_10.csv (and the full dataset later)
  - customer_purchase_data_10.csv (and the full dataset later)

Actual column names (inspected from the CSV headers):

Reviews:   ReviewID, CustomerID, ProductID, ReviewText, ReviewDate
Purchases: TransactionID, CustomerID, CustomerName, ProductID, ProductName,
           ProductCategory, PurchaseQuantity, PurchasePrice, PurchaseDate, Country
"""

import re
import pandas as pd
from pathlib import Path
from datetime import datetime


# ── Path helpers ─────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

REVIEWS_FILE = DATA_DIR / "customer_reviews_data_10.csv"
PURCHASES_FILE = DATA_DIR / "customer_purchase_data_10.csv"


# ── Date normalisation ────────────────────────────────────────────────────────

def _parse_date(value: str) -> str | None:
    """
    Try common date formats and return YYYY-MM-DD string, or None if unparseable.

    Reviews use M/D/YYYY format. Purchases use YYYY-MM-DD (already ISO).
    We try both so the function is robust.
    """
    if pd.isna(value) or str(value).strip() == "":
        return None
    value = str(value).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ── Text cleaning ─────────────────────────────────────────────────────────────

def _clean_text(value) -> str:
    """
    Light cleaning for ReviewText:
    - Strip leading/trailing whitespace
    - Collapse internal whitespace runs
    - Remove non-printable control characters
    Meaning is preserved; no stemming or stopword removal.
    """
    if pd.isna(value):
        return ""
    text = str(value).strip()
    # Remove non-printable characters (keep normal punctuation)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Collapse multiple spaces/tabs into one
    text = re.sub(r"[ \t]+", " ", text)
    return text


# ── Reviews preprocessing ─────────────────────────────────────────────────────

def load_reviews() -> list[dict]:
    """
    Load, clean, and return review records ready for MongoDB insertion.

    Each document shape:
    {
        "review_id":   str,   # from ReviewID  — unique key for dedup
        "customer_id": str,   # from CustomerID
        "product_id":  str,   # from ProductID
        "review_text": str,   # from ReviewText (lightly cleaned)
        "review_date": str,   # YYYY-MM-DD (normalised from M/D/YYYY)
    }

    Rows with missing review_id or unparseable review_date are dropped and
    reported. Exact duplicate rows are removed before returning.
    """
    if not REVIEWS_FILE.exists():
        raise FileNotFoundError(f"Reviews CSV not found: {REVIEWS_FILE}")

    df = pd.read_csv(REVIEWS_FILE, dtype=str)  # read all as str first

    # ── Drop fully empty rows ────────────────────────────────────────────────
    df.dropna(how="all", inplace=True)

    # ── Remove exact duplicate rows ──────────────────────────────────────────
    before = len(df)
    df.drop_duplicates(inplace=True)
    dupes_removed = before - len(df)

    # ── Normalise IDs ────────────────────────────────────────────────────────
    df["ReviewID"]   = df["ReviewID"].astype(str).str.strip()
    df["CustomerID"] = df["CustomerID"].astype(str).str.strip()
    df["ProductID"]  = df["ProductID"].astype(str).str.strip()

    # ── Normalise dates ──────────────────────────────────────────────────────
    df["_review_date_norm"] = df["ReviewDate"].apply(_parse_date)

    # ── Clean review text ────────────────────────────────────────────────────
    df["_review_text_clean"] = df["ReviewText"].apply(_clean_text)

    # ── Drop rows with missing critical fields ────────────────────────────────
    bad_id   = df["ReviewID"].isin(["", "nan", "None"])
    bad_date = df["_review_date_norm"].isna()
    invalid  = bad_id | bad_date
    if invalid.any():
        print(f"[preprocessing] Dropping {invalid.sum()} review row(s) with invalid ID or date")
        df = df[~invalid]

    # ── Build document list ───────────────────────────────────────────────────
    records = []
    for _, row in df.iterrows():
        records.append({
            "review_id":   row["ReviewID"],
            "customer_id": row["CustomerID"],
            "product_id":  row["ProductID"],
            "review_text": row["_review_text_clean"],
            "review_date": row["_review_date_norm"],
        })

    print(
        f"[preprocessing] Reviews loaded: {len(records)} valid records "
        f"(duplicate rows removed: {dupes_removed})"
    )
    return records


# ── Purchases preprocessing ───────────────────────────────────────────────────

def load_sales() -> list[dict]:
    """
    Load, clean, and return purchase (sales) records ready for MongoDB insertion.

    Each document shape:
    {
        "transaction_id":   str,    # from TransactionID — unique key for dedup
        "customer_id":      str,    # from CustomerID
        "customer_name":    str,    # from CustomerName
        "product_id":       str,    # from ProductID
        "product_name":     str,    # from ProductName
        "product_category": str,    # from ProductCategory
        "quantity":         int,    # from PurchaseQuantity
        "purchase_price":   float,  # from PurchasePrice
        "purchase_date":    str,    # YYYY-MM-DD (already ISO in source)
        "country":          str,    # from Country
    }

    NOTE: Each original transaction is preserved as a separate document.
    Daily aggregation is NOT done here (reserved for forecasting phase).
    """
    if not PURCHASES_FILE.exists():
        raise FileNotFoundError(f"Purchases CSV not found: {PURCHASES_FILE}")

    df = pd.read_csv(PURCHASES_FILE, dtype=str)  # read all as str first

    # ── Drop fully empty rows ────────────────────────────────────────────────
    df.dropna(how="all", inplace=True)

    # ── Remove exact duplicate rows ──────────────────────────────────────────
    before = len(df)
    df.drop_duplicates(inplace=True)
    dupes_removed = before - len(df)

    # ── Normalise IDs ────────────────────────────────────────────────────────
    df["TransactionID"] = df["TransactionID"].astype(str).str.strip()
    df["CustomerID"]    = df["CustomerID"].astype(str).str.strip()
    df["ProductID"]     = df["ProductID"].astype(str).str.strip()

    # ── Normalise strings ────────────────────────────────────────────────────
    for col in ["CustomerName", "ProductName", "ProductCategory", "Country"]:
        df[col] = df[col].astype(str).str.strip()

    # ── Normalise dates ──────────────────────────────────────────────────────
    df["_purchase_date_norm"] = df["PurchaseDate"].apply(_parse_date)

    # ── Convert numeric fields safely ────────────────────────────────────────
    df["_quantity"] = pd.to_numeric(df["PurchaseQuantity"], errors="coerce")
    df["_price"]    = pd.to_numeric(df["PurchasePrice"],    errors="coerce")

    # ── Drop rows with missing critical fields ────────────────────────────────
    bad_id   = df["TransactionID"].isin(["", "nan", "None"])
    bad_date = df["_purchase_date_norm"].isna()
    bad_qty  = df["_quantity"].isna()
    bad_price= df["_price"].isna()
    invalid  = bad_id | bad_date | bad_qty | bad_price
    if invalid.any():
        print(f"[preprocessing] Dropping {invalid.sum()} sales row(s) with invalid fields")
        df = df[~invalid]

    # ── Build document list ───────────────────────────────────────────────────
    records = []
    for _, row in df.iterrows():
        records.append({
            "transaction_id":   row["TransactionID"],
            "customer_id":      row["CustomerID"],
            "customer_name":    row["CustomerName"],
            "product_id":       row["ProductID"],
            "product_name":     row["ProductName"],
            "product_category": row["ProductCategory"],
            "quantity":         int(row["_quantity"]),
            "purchase_price":   round(float(row["_price"]), 2),
            "purchase_date":    row["_purchase_date_norm"],
            "country":          row["Country"],
        })

    print(
        f"[preprocessing] Sales loaded: {len(records)} valid records "
        f"(duplicate rows removed: {dupes_removed})"
    )
    return records
