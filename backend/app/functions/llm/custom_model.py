"""Integration with the Ollama LLM for streaming chat responses."""

import json
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings
from app.functions.llm.ollama_auth import ollama_headers


async def run_custom_model(chat_history: list[dict]) -> AsyncGenerator[str, None]:
    """Send a chat history to the Ollama model and stream the assistant reply.

    Args:
        chat_history: List of message dicts with 'role' and 'content' keys.

    Yields:
        Text chunks from the LLM response.

    Raises:
        httpx.ReadTimeout: If the backend request times out.
        httpx.HTTPStatusError: If the server returns an error status.
        httpx.RequestError: If a network error occurs.
    """
    print('MODEL BEING USED:', settings.llm_model)
    payload = {'model': settings.llm_model, 'messages': chat_history, 'stream': True}

    print('========== OLLAMA PAYLOAD ==========')
    print(payload)
    print('====================================')

    timeout = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=None)

    try:
        async with (
            httpx.AsyncClient(timeout=timeout) as client,
            client.stream(
                'POST',
                f'{settings.ollama_url.rstrip("/")}/api/chat',
                json=payload,
                headers=ollama_headers(),
            ) as resp,
        ):
            resp.raise_for_status()

            async for line in resp.aiter_lines():
                if not line:
                    continue

                line = line.strip()
                if line.startswith('data:'):
                    line = line[len('data:') :].strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                content = data.get('message', {}).get('content')
                if content:
                    yield content
    except httpx.ReadTimeout:
        yield '[Error: Backend request timed out]'
    except httpx.HTTPStatusError as e:
        yield f'[Error: Server returned {e.response.status_code}]'
    except httpx.RequestError as e:
        yield f'[Network error: {e}]'
    except Exception as e:
        yield f'[Unexpected error: {e}]'
