"""Gemini AI client initialization."""

import os
from google import genai


def get_ai_client(api_key: str | None = None) -> genai.Client:
    """Initialize and return a google.genai.Client.

    Uses the provided api_key, reads from GEMINI_API_KEY environment variable,
    or falls back to application Settings outside test environments.
    Raises ValueError if neither is provided.
    """
    key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
    if (not key or not key.strip()) and "PYTEST_CURRENT_TEST" not in os.environ:
        try:
            from src.core.config import get_settings

            cfg_key = get_settings().GEMINI_API_KEY
            if cfg_key and cfg_key.strip():
                key = cfg_key.strip()
        except Exception:
            pass

    if not key or not key.strip():
        raise ValueError("GEMINI_API_KEY environment variable is not set")

    return genai.Client(api_key=key.strip())
