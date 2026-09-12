# LLM-Based Customer Review Sentiment Analysis and E-Commerce Sales Forecasting

A final-year academic research project investigating the empirical utility of local Large Language Model (LLM) sentiment signals in individual product-centric sales forecasting.

---

## 1. Project Overview

### Research Question
**Does LLM-derived customer sentiment improve individual product sales forecasting?**

While modern Large Language Models excel at natural language understanding, their empirical value as exogenous predictors in operational forecasting remains an active area of empirical research. This project constructs an end-to-end reproducible product intelligence system to extract sentiment signals from customer text reviews using three open-weight LLMs. It then evaluates whether incorporating this product-specific sentiment into a time-series model (ARIMAX) yields statistically significant improvements over classical univariate baselines (ARIMA and Naive persistence) for that individual product.

---

## 2. Product-Centric Architecture

The complete end-to-end architecture is organized to analyze individual products:

```
                    PRODUCT
                       │
         ┌─────────────┴─────────────┐
         │                           │
         ▼                           ▼
  PURCHASE HISTORY              CUSTOMER REVIEWS
         │                           │
         │                    ┌──────┴──────┐
         │                    ▼             ▼
         │                  Llama         Qwen/Gemma
         │                    │             │
         │                    └──────┬──────┘
         │                           ▼
         │                   ENSEMBLE SENTIMENT
         │                           │
         │                           ▼
         │                  PRODUCT SENTIMENT
         │                           │
         │                           ▼
         │                  BUY RECOMMENDATION
         │
         ▼
   HISTORICAL SALES
         │
         ├──────────────────────┐
         │                      │
         ▼                      ▼
  SALES-ONLY MODEL       SALES + SENTIMENT MODEL
         │                      │
         └──────────┬───────────┘
                    ▼
             MODEL COMPARISON
                    │
                    ▼
            FUTURE SALES
              PREDICTION
                    │
                    ▼
            PRODUCT INSIGHTS
```

---

## 3. Technology Stack

- **Frontend**: React 18, Vite, JavaScript, Tailwind CSS, Recharts, Axios, Lucide React, React Router 6.
- **Backend**: Python 3.13, FastAPI, Uvicorn, Pandas, NumPy, statsmodels, SciPy, Matplotlib.
- **Database**: MongoDB Atlas (PyMongo driver, compound unique indexing for idempotency).
- **LLM Engine**: Ollama running quantized local open-weight models via REST API.

---

## 4. Dataset

The finalized dataset consists of empirical retail observations spanning a 1-year historical window:

- **Customer Reviews**: 1,000 distinct text reviews (`review_id`, `product_id`, `customer_id`, `review_date`, `review_text`).
- **Sales Transactions**: 1,000 purchase transactions (`transaction_id`, `product_id`, `customer_id`, `purchase_date`, `quantity`, `purchase_price`).
- **Product Catalog**: 100 distinct products with 100% mutual catalog overlap between reviews and sales.
- **Data Sparsity Limitation**: Product-level data exhibits significant sparsity. Individual products may only have transactions on a subset of active sales dates. The forecasting module explicitly handles this by determining observation feasibility dynamically per product.

---

## 5. LLM Models

Zero-shot structured sentiment extraction was executed sequentially using three local open-weight models via Ollama:

1. **Meta Llama 3.1 8B** (`llama3.1:8b`)
2. **Alibaba Qwen 2.5 7B** (`qwen2.5:7b`)
3. **Google Gemma 3 4B** (`gemma3:4b`)

---

## 6. Sentiment Ensemble & Recommendation

The multi-LLM ensemble resolves sentiment labels and numerical scores for each review:

### Scoring System
- **Positive**: $+1.0$
- **Neutral**: $0.0$
- **Negative**: $-1.0$

### Purchase Recommendation Logic
The product-specific sentiment is used to generate a purchase recommendation:
- **Strong Positive** (Score >= +0.50) → **RECOMMENDED**
- **Mixed / Neutral** (-0.25 < Score < +0.50) → **CONSIDER**
- **Negative** (Score <= -0.25) → **NOT RECOMMENDED**

---

## 7. Individual Product Forecasting

### Models Evaluated
1. **Historical Sales Only**: ARIMA fitted solely on historical weekly product sales.
2. **Historical Sales + Sentiment**: ARIMAX model incorporating lagged product sentiment as an exogenous regressor.
3. **Naive Baseline**: Simple persistence forecast.

### Strict Temporal Alignment & Leakage Prevention
- **Chronological Evaluation**: The system performs a chronological 80/20 train/test evaluation (no random shuffling).
- **No Future Information Leakage**: For target period $t$, only information (sales and sentiment) available *before* $t$ is utilized.

### Metrics Computed
- **MAE** (Mean Absolute Error)
- **RMSE** (Root Mean Squared Error)
- **MAPE** (Mean Absolute Percentage Error)

---

## 8. Limitations

1. **Sparse Transaction Structure**: Product-level daily data is highly sparse.
2. **Observational Data**: Non-experimental, synthetic e-commerce transaction benchmark.
3. **Unmodeled Exogenous Shocks**: Promotions, price adjustments, seasonal holidays, and stockouts were not controlled for.
4. **Limited Generalizability**: Findings represent the tested domain and model configurations and should not be generalized to all retail categories.

---

## 9. Setup & Reproduction Guide

### Prerequisites
- **Python**: 3.11, 3.12, or 3.13
- **Node.js**: 18+ and npm
- **MongoDB**: MongoDB Atlas cluster or local instance (v6.0+)
- **Ollama**: Local installation with models downloaded (`ollama pull llama3.1:8b`, `ollama pull qwen2.5:7b`, `ollama pull gemma3:4b`)

---

### Step 1: Environment Setup

#### Configure Backend Environment
```bash
cp backend/.env.example backend/.env
```
Edit `backend/.env` with your MongoDB credentials:
```env
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.example.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=fyp_db
OLLAMA_BASE_URL=http://localhost:11434
DEBUG=false
```

---

### Step 2: Backend Setup & Installation

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate    # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

### Step 3: Frontend Setup & Installation

```bash
cd frontend
npm install
```

---

### Step 4: Launching the Application

#### Start the FastAPI Backend
```bash
cd backend
source venv/bin/activate
PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- API Docs: `http://127.0.0.1:8000/api/docs`
- Health Probe: `http://127.0.0.1:8000/api/health`

#### Start the React Research Dashboard
```bash
cd frontend
npm run dev
```
- Open `http://127.0.0.1:5173` in your browser.
- Navigate to **Product Analysis** to select an individual product and execute sentiment-enhanced sales forecasting.
