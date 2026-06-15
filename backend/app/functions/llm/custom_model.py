import httpx
import os
import json
from typing import AsyncGenerator

from app.core.config import settings

# The python script, will get the OLLAMA_URL = "http://ollama:11434" from the docker compose file, if docker is used.
# If docker is not used for running the project, then it will fallback to "http://localhost:11434", where the local Ollama
# LLM should be reachable.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


async def run_custom_model(chat_history: list[dict]) -> AsyncGenerator[str, None]:  # -> str:
    """
    Sends a chat history to the Ollama model and returns the assistant's reply.
    """
    payload = {
        "model": settings.llm_model,
        "messages": chat_history,
        "stream": True,
        "options": {
            "temperature": 0.1
        }
    }

    timeout = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=None)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as resp:
                async for line in resp.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            yield "[Malformed JSON]"
    except httpx.ReadTimeout:
        yield "[Error: Backend request timed out]"
    except httpx.HTTPStatusError as e:
        yield f"[Error: Server returned {e.response.status_code}]"
    except httpx.RequestError as e:
        yield f"[Network error: {e}]"
    except Exception as e:
        yield f"[Unexpected error: {e}]"
