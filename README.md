# LLM-Based Customer Review Sentiment Analysis and E-Commerce Sales Forecasting

> **Final Year Project** — Phase 1: Project Foundation

---

## Stack

| Layer       | Technology                                    |
|-------------|-----------------------------------------------|
| Frontend    | React 18, Vite, JavaScript, Tailwind CSS      |
| Backend     | Python, FastAPI, Uvicorn                      |
| Database    | MongoDB Atlas (Phase 2+)                      |
| LLM         | Ollama — llama3.1:8b, qwen2.5:7b, gemma3:4b  |
| Forecasting | statsmodels — SARIMA, SARIMAX                 |

---

## Project Structure

```
project/
├── frontend/            React + Vite frontend
│   ├── src/
│   │   ├── components/  Sidebar, Header, Layout
│   │   ├── pages/       Dashboard, Reviews, Products, Sentiment, Forecasting, Results
│   │   ├── services/    Axios API client (api.js)
│   │   ├── hooks/       (future custom hooks)
│   │   └── utils/       (future helpers)
│   ├── package.json
│   └── vite.config.js
│
├── backend/             FastAPI backend
│   ├── app/
│   │   ├── main.py      FastAPI app + CORS
│   │   ├── config.py    Environment variable config
│   │   ├── db/          MongoDB connection (Phase 2+)
│   │   ├── models/      Pydantic models (Phase 2+)
│   │   ├── routers/     API route groups (Phase 2+)
│   │   ├── services/    Business logic (Phase 2+)
│   │   ├── llm/         Ollama integration (Phase 3+)
│   │   ├── workers/     Background workers (Phase 3+)
│   │   └── prompts/     LLM prompt templates (Phase 3+)
│   ├── requirements.txt
│   └── .env.example
│
└── README.md
```

---

## Running Locally

### Backend

```bash
cd backend

# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and configure environment variables
cp .env.example .env
# Edit .env with your real MONGODB_URI, etc.

# 4. Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: http://localhost:8000  
API docs: http://localhost:8000/api/docs

### Frontend

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Start the dev server
npm run dev
```

Frontend will be available at: http://localhost:5173

---

## API Endpoints (Phase 1)

| Method | Endpoint      | Description          |
|--------|---------------|----------------------|
| GET    | /api/health   | Backend liveness check |
| GET    | /api/docs     | Swagger UI           |
| GET    | /api/redoc    | ReDoc UI             |

---

## Dataset Files (Phase 2+)

- `customer_reviews_data.csv`
- `customer_purchase_data.csv`

---

## Phases

| Phase | Description                                    | Status      |
|-------|------------------------------------------------|-------------|
| 1     | Project foundation, folder structure, health API | ✅ Complete |
| 2     | Dataset preprocessing + MongoDB integration    | 🔜 Planned  |
| 3     | Multi-model LLM sentiment analysis via Ollama  | 🔜 Planned  |
| 4     | SARIMA / SARIMAX forecasting                   | 🔜 Planned  |
| 5     | Evaluation, results, UI polish                 | 🔜 Planned  |
