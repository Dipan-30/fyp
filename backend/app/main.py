"""
FastAPI application entry point — Phase 2.

Phase 2 adds:
  - MongoDB connection (via app lifespan)
  - Index creation on startup
  - Routers: dataset, products, reviews, sales
  - Health check now includes DB connectivity status
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.connection import ping_db, close_client
from app.db.indexes import create_indexes
from app.routers import dataset, products, reviews, sales


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: create MongoDB indexes.
    Shutdown: close the MongoClient.
    """
    try:
        create_indexes()
        print("[startup] MongoDB indexes created/verified.")
    except Exception as e:
        # Don't crash on startup if DB is unreachable; health endpoint will report it
        print(f"[startup] WARNING: Could not create indexes — {e}")
    yield
    close_client()
    print("[shutdown] MongoDB client closed.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(dataset.router)
app.include_router(products.router)
app.include_router(reviews.router)
app.include_router(sales.router)


# ── Core routes ───────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
def health_check():
    """
    Liveness + readiness probe.
    Returns backend status and MongoDB connectivity.
    """
    db_ok = ping_db()
    return {
        "status":   "ok",
        "app":      settings.APP_NAME,
        "version":  settings.APP_VERSION,
        "database": "connected" if db_ok else "unreachable",
    }


@app.get("/", include_in_schema=False)
def root():
    return {"message": "API is running. Visit /api/docs for documentation."}
