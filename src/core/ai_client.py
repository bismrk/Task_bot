"""Gemini AI client initialization."""

import os
from google import genai


def get_ai_client(api_key: str | None = None) -> genai.Client:
    """Initialize and return a google.genai.Client.

    Uses the provided api_key or reads from the GEMINI_API_KEY environment variable.
    Raises ValueError if neither is provided.
    """
    key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
    if not key or not key.strip():
        raise ValueError("GEMINI_API_KEY environment variable is not set")

    return genai.Client(api_key=key.strip())
