import json
import os
from typing import AsyncGenerator

import httpx

from app.core.config import settings


OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434",
)


async def run_custom_model(
    chat_history: list[dict],
) -> AsyncGenerator[str, None]:
    """
    Send the chat history to Ollama and stream the generated answer.

    Ollama connection errors, missing models and malformed responses
    are returned as readable messages instead of producing blank output.
    """

    payload = {
        "model": settings.llm_model,
        "messages": chat_history,
        "stream": True,
    }

    timeout = httpx.Timeout(
        connect=20.0,
        read=None,
        write=20.0,
        pool=None,
    )

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
        ) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_URL}/api/chat",
                json=payload,
            ) as response:
                if response.status_code >= 400:
                    error_body = await response.aread()

                    error_text = error_body.decode(
                        "utf-8",
                        errors="replace",
                    )

                    yield (
                        "The language model could not answer. "
                        f"Ollama returned status "
                        f"{response.status_code}: {error_text}"
                    )
                    return

                answer_received = False

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if data.get("error"):
                        yield (
                            "Ollama error: "
                            f"{data['error']}"
                        )
                        return

                    content = (
                        data.get("message", {})
                        .get("content", "")
                    )

                    if content:
                        answer_received = True
                        yield content

                if not answer_received:
                    yield (
                        "The model returned an empty response. "
                        "Check that the configured Ollama model "
                        "is downloaded and running."
                    )

    except httpx.ConnectError:
        yield (
            "Could not connect to Ollama. "
            "Check that the Ollama container is running."
        )

    except httpx.ReadTimeout:
        yield (
            "The model request timed out."
        )

    except httpx.RequestError as error:
        yield (
            "Network error while contacting Ollama: "
            f"{error}"
        )

    except Exception as error:
        yield (
            "Unexpected language-model error: "
            f"{error}"
        )