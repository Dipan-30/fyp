"""
Application configuration.

Values are read from environment variables so they can be overridden without
changing source code.  Copy .env.example → .env and fill in real values before
running the backend.
"""

import os
from dotenv import load_dotenv

# Load .env file if it exists (local development only)
load_dotenv()


class Settings:
    # ── MongoDB Atlas ─────────────────────────────────────────────────────────
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "fyp_db")

    # ── Ollama ────────────────────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "Sentiment Analysis & Sales Forecasting API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Origins allowed to call the API (adjust in production)
    ALLOWED_ORIGINS: list = [
        "http://localhost:5173",  # Vite default
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]


settings = Settings()
