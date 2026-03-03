"""
Feedback Store — Persistent JSON-based feedback storage for Meow responses.
Stores user ratings (thumbs up / thumbs down) alongside Q&A pairs.
Positive feedback is injected into future LLM context for response fine-tuning.
"""
import json
import os
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

FEEDBACK_DIR = Path("data/feedback")
FEEDBACK_FILE = FEEDBACK_DIR / "feedback_log.json"

# In-memory cache (loaded on first access)
_feedback_cache: list | None = None


def _ensure_dir():
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    if not FEEDBACK_FILE.exists():
        FEEDBACK_FILE.write_text("[]")


def _load_feedback() -> list:
    global _feedback_cache
    if _feedback_cache is not None:
        return _feedback_cache
    _ensure_dir()
    try:
        with open(FEEDBACK_FILE, "r") as f:
            _feedback_cache = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        _feedback_cache = []
    return _feedback_cache


def _save_feedback(data: list):
    global _feedback_cache
    _ensure_dir()
    _feedback_cache = data
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def log_feedback(query: str, response: str, rating: str, username: str = "unknown", agent_used: str = "unknown"):
    """
    Log a feedback entry.
    rating: "positive" or "negative"
    """
    feedback = _load_feedback()
    entry = {
        "timestamp": time.time(),
        "username": username,
        "query": query[:500],
        "response": response[:1000],
        "agent_used": agent_used,
        "rating": rating,
    }
    feedback.append(entry)
    # Keep only last 500 entries to prevent unbounded growth
    if len(feedback) > 500:
        feedback = feedback[-500:]
    _save_feedback(feedback)
    logger.info(f"[Feedback] {rating} logged for query: {query[:60]}...")


def get_positive_examples(limit: int = 3) -> list:
    """
    Retrieve the most recent positively-rated Q&A pairs.
    Used to inject into the LLM system prompt for response quality tuning.
    """
    feedback = _load_feedback()
    positives = [f for f in feedback if f.get("rating") == "positive"]
    # Return the most recent ones
    recent = positives[-limit:]
    return [{"query": f["query"], "response": f["response"][:500]} for f in recent]


def get_feedback_stats() -> dict:
    """Return summary stats for admin dashboard."""
    feedback = _load_feedback()
    pos = sum(1 for f in feedback if f.get("rating") == "positive")
    neg = sum(1 for f in feedback if f.get("rating") == "negative")
    return {"total": len(feedback), "positive": pos, "negative": neg}
