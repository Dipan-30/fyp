"""
llm/ollama_service.py — Reusable HTTP client for local Ollama inference.

Endpoint: http://localhost:11434
Method:   POST /api/chat

This module only defines the service — it does NOT call Ollama during import.
All Ollama requests are initiated only when call_ollama() is explicitly invoked
by the worker during the analysis phase.
"""

import json
import time
import httpx
from typing import Optional

from app.config import settings


# ── Constants ─────────────────────────────────────────────────────────────────

OLLAMA_CHAT_ENDPOINT = f"{settings.OLLAMA_BASE_URL}/api/chat"

# How long (in seconds) to wait for a single Ollama response.
# LLMs on consumer hardware can take 30–120 s per request.
DEFAULT_TIMEOUT_SECONDS = 180.0

# keep_alive instructs Ollama to keep the model warm in VRAM between calls.
# "5m" = keep loaded for 5 minutes after the last request.
DEFAULT_KEEP_ALIVE = "5m"


# ── Shared client ─────────────────────────────────────────────────────────────

# We create ONE httpx client per Python process so that TCP connections are
# reused across sequential requests to the same Ollama host.
# The client is intentionally NOT created at import time so that we can control
# timeouts and avoid any accidental network activity during testing/import.

_client: Optional[httpx.Client] = None


def _get_client(timeout: float = DEFAULT_TIMEOUT_SECONDS) -> httpx.Client:
    """Return a shared httpx.Client, creating it on first call."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={"Content-Type": "application/json"},
        )
    return _client


def close_client() -> None:
    """Explicitly close the shared httpx client (call on worker shutdown)."""
    global _client
    if _client is not None and not _client.is_closed:
        _client.close()
    _client = None


# ── Core call ─────────────────────────────────────────────────────────────────

def call_ollama(
    model: str,
    prompt: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    keep_alive: str = DEFAULT_KEEP_ALIVE,
) -> dict:
    """
    Send a single chat request to Ollama and return the parsed response.

    Parameters
    ----------
    model      : Ollama model name, e.g. "llama3.1:8b"
    prompt     : The full prompt string to send as the user message
    timeout    : Request timeout in seconds (default 180 s)
    keep_alive : How long Ollama should keep the model loaded (default "5m")

    Returns
    -------
    dict with keys:
        "content"          : str — raw response text from the model
        "model"            : str — model name echoed by Ollama
        "duration_seconds" : float — wall-clock time of the HTTP call

    Raises
    ------
    OllamaConnectionError  : Cannot reach Ollama (not running, wrong port)
    OllamaTimeoutError     : Request exceeded the timeout
    OllamaResponseError    : Unexpected HTTP status or malformed response body
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False,        # We want the full response in one shot
        "keep_alive": keep_alive,
        "options": {
            "temperature": 0.1,  # Low temperature for deterministic classification
        },
    }

    client = _get_client(timeout=timeout)

    t_start = time.perf_counter()
    try:
        response = client.post(
            OLLAMA_CHAT_ENDPOINT,
            content=json.dumps(payload),
        )
    except httpx.ConnectError as exc:
        raise OllamaConnectionError(
            f"Cannot connect to Ollama at {settings.OLLAMA_BASE_URL}. "
            "Is Ollama running? Try: ollama serve"
        ) from exc
    except httpx.TimeoutException as exc:
        raise OllamaTimeoutError(
            f"Ollama request timed out after {timeout} s "
            f"(model={model})"
        ) from exc
    except httpx.HTTPError as exc:
        raise OllamaResponseError(f"HTTP error talking to Ollama: {exc}") from exc

    duration = time.perf_counter() - t_start

    if response.status_code != 200:
        raise OllamaResponseError(
            f"Ollama returned HTTP {response.status_code}: {response.text[:500]}"
        )

    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise OllamaResponseError(
            f"Ollama response is not valid JSON: {response.text[:500]}"
        ) from exc

    # Ollama /api/chat non-streaming response shape:
    # { "model": "...", "message": {"role": "assistant", "content": "..."}, ... }
    try:
        content = body["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise OllamaResponseError(
            f"Unexpected Ollama response structure: {body}"
        ) from exc

    return {
        "content": content,
        "model": body.get("model", model),
        "duration_seconds": round(duration, 3),
    }


# ── Custom exceptions ─────────────────────────────────────────────────────────

class OllamaError(Exception):
    """Base class for all Ollama service errors."""


class OllamaConnectionError(OllamaError):
    """Raised when the Ollama server cannot be reached."""


class OllamaTimeoutError(OllamaError):
    """Raised when an Ollama request exceeds the configured timeout."""


class OllamaResponseError(OllamaError):
    """Raised for unexpected HTTP status codes or malformed response bodies."""
