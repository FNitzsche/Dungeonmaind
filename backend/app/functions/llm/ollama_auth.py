"""Helpers for constructing Ollama request headers."""

import os

from app.core.config import settings


def ollama_headers() -> dict[str, str]:
    """Build headers for Ollama requests.

    Returns:
        A dictionary of headers with JSON content-type and an optional bearer token.
    """
    headers = {'Content-Type': 'application/json'}
    token = settings.ollama_api_key or os.getenv('OLLAMA_AUTH_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers
