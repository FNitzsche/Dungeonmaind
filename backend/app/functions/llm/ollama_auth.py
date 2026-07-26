"""Helpers for constructing Ollama request headers."""

import os


def ollama_headers() -> dict[str, str]:
    """Build headers for Ollama requests.

    Returns:
        A dictionary of headers with JSON content-type and an optional bearer token.
    """
    headers = {'Content-Type': 'application/json'}
    token = os.getenv('OLLAMA_AUTH_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers
