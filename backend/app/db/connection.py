"""
db/connection.py — MongoDB Atlas connection management.

Uses a module-level client so the connection is reused across requests
(PyMongo's MongoClient is thread-safe and manages its own connection pool).
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError
from app.config import settings


_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Return the shared MongoClient, creating it on first call."""
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_db():
    """Return the application database handle."""
    return get_client()[settings.MONGODB_DATABASE]


def ping_db() -> bool:
    """
    Send a ping command to verify the connection is alive.
    Returns True on success, False on failure.
    """
    try:
        get_client().admin.command("ping")
        return True
    except (ConnectionFailure, ConfigurationError, Exception):
        return False


def close_client():
    """Close the MongoClient (called on app shutdown)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
