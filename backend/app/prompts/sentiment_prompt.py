"""
prompts/sentiment_prompt.py — Sentiment classification prompt and response validation.

prompt_version = "v1"

The prompt instructs the model to classify a review as positive, neutral, or negative
and return a structured JSON response.

ANALYSIS RULES:
- Analyze ONLY the ReviewText content.
- Do NOT use ReviewID, CustomerID, ProductID, ReviewDate.
- Do NOT use any existing rating or sentiment label from the data.
- Do NOT invent a sentiment when the model response is invalid.
"""

import json
import re
from typing import Union

# ── Prompt version ────────────────────────────────────────────────────────────

PROMPT_VERSION = "v1"

# ── Valid sentiments ──────────────────────────────────────────────────────────

VALID_SENTIMENTS = {"positive", "neutral", "negative"}

# ── Prompt template ───────────────────────────────────────────────────────────

_SYSTEM_INSTRUCTION = """\
You are a sentiment analysis assistant. Your task is to classify a customer review.

INSTRUCTIONS:
1. Read the review text carefully.
2. Classify the overall sentiment as exactly one of: positive, neutral, negative
3. Assign a confidence score between 0.0 and 1.0 (e.g., 0.92 means very confident).
4. Write a brief reasoning (1-2 sentences maximum).

RULES:
- Use ONLY the review text to determine sentiment.
- Do NOT consider any product rating, star rating, or numerical score.
- Do NOT make up information not present in the review.
- Your response MUST be valid JSON — nothing else before or after it.
- Do NOT wrap the JSON in markdown code fences.

OUTPUT FORMAT (return exactly this JSON structure):
{
  "sentiment": "positive",
  "confidence": 0.92,
  "reasoning": "Short explanation."
}

Where:
- "sentiment" is one of: positive, neutral, negative
- "confidence" is a float between 0.0 and 1.0
- "reasoning" is a short explanation (1-2 sentences)
"""


def build_prompt(review_text: str) -> str:
    """
    Build the full prompt string for a given review text.

    Parameters
    ----------
    review_text : The raw review text from the MongoDB reviews collection.

    Returns
    -------
    str : The full prompt to send to the Ollama model.
    """
    review_text = review_text.strip() if review_text else ""
    return (
        f"{_SYSTEM_INSTRUCTION}\n\n"
        f"REVIEW TEXT:\n{review_text}\n\n"
        f"Respond with only the JSON object:"
    )


# ── Response validation ───────────────────────────────────────────────────────

def parse_and_validate_response(raw_response: str) -> dict:
    """
    Safely parse and validate the model's response.

    Handles:
    - Markdown code fences (```json ... ```, ``` ... ```)
    - Leading/trailing whitespace
    - Malformed JSON
    - Missing required fields
    - Invalid sentiment value (must be positive/neutral/negative)
    - Invalid confidence value (must be float 0.0–1.0)
    - Empty or missing reasoning

    Parameters
    ----------
    raw_response : The raw string returned by the Ollama model.

    Returns
    -------
    On success:
        {
            "valid": True,
            "sentiment": "positive" | "neutral" | "negative",
            "confidence": float,
            "reasoning": str,
        }

    On failure:
        {
            "valid": False,
            "error": str,          # Human-readable description of what went wrong
            "raw_response": str,   # Original response (truncated for storage)
        }

    IMPORTANT: Never invents a sentiment. Returns {"valid": False} on any error.
    """
    if not raw_response or not raw_response.strip():
        return _failure("Empty response from model", raw_response)

    cleaned = _strip_markdown_fences(raw_response.strip())

    # Attempt JSON extraction even if there is surrounding text
    cleaned = _extract_json_object(cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return _failure(f"JSON parse error: {exc}", raw_response)

    if not isinstance(data, dict):
        return _failure(f"Response is not a JSON object, got: {type(data).__name__}", raw_response)

    # ── Validate sentiment ────────────────────────────────────────────────────
    sentiment = data.get("sentiment")
    if sentiment is None:
        return _failure("Missing field: 'sentiment'", raw_response)
    if not isinstance(sentiment, str):
        return _failure(f"'sentiment' must be a string, got: {type(sentiment).__name__}", raw_response)
    sentiment = sentiment.strip().lower()
    if sentiment not in VALID_SENTIMENTS:
        return _failure(
            f"Invalid sentiment value: '{sentiment}'. Must be one of: {sorted(VALID_SENTIMENTS)}",
            raw_response,
        )

    # ── Validate confidence ───────────────────────────────────────────────────
    confidence = data.get("confidence")
    if confidence is None:
        return _failure("Missing field: 'confidence'", raw_response)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        return _failure(f"'confidence' must be numeric, got: {confidence!r}", raw_response)
    if not (0.0 <= confidence <= 1.0):
        return _failure(
            f"'confidence' out of range: {confidence}. Must be between 0.0 and 1.0",
            raw_response,
        )

    # ── Validate reasoning ────────────────────────────────────────────────────
    reasoning = data.get("reasoning")
    if reasoning is None:
        return _failure("Missing field: 'reasoning'", raw_response)
    if not isinstance(reasoning, str):
        return _failure(f"'reasoning' must be a string, got: {type(reasoning).__name__}", raw_response)
    reasoning = reasoning.strip()
    if not reasoning:
        return _failure("'reasoning' is empty", raw_response)

    return {
        "valid": True,
        "sentiment": sentiment,
        "confidence": round(confidence, 4),
        "reasoning": reasoning,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _strip_markdown_fences(text: str) -> str:
    """
    Remove markdown code fences that some models wrap around JSON output.

    Handles:
        ```json\\n{...}\\n```
        ```\\n{...}\\n```
        `{...}`
    """
    # Match opening fence with optional language tag
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    # Match closing fence
    text = re.sub(r"\s*```$", "", text)
    # Match single backtick wrapping
    if text.startswith("`") and text.endswith("`"):
        text = text[1:-1]
    return text.strip()


def _extract_json_object(text: str) -> str:
    """
    If the text contains surrounding prose, try to extract just the JSON object.
    Looks for the first '{' and the last '}' and returns the substring.
    Falls back to returning the original text if no braces found.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _failure(error: str, raw_response: str) -> dict:
    """Return a structured parse failure. Never invents a sentiment."""
    return {
        "valid": False,
        "error": error,
        "raw_response": raw_response[:1000] if raw_response else "",
    }
