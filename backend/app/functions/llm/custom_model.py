import requests
import os
import json

from app.core.config import settings


# The python script, will get the OLLAMA_URL = "http://ollama:11434" from the docker compose file, if docker is used.
# If docker is not used for running the project, then it will fallback to "http://localhost:11434", where the local Ollama
# LLM should be reachable.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

def run_custom_model(chat_history: list[dict]) -> str:
    """
    Sends a chat history to the Ollama model and returns the assistant's reply.
    """
    try:
        payload = {
            "model": settings.llm_model,
            "messages": chat_history,
            "stream": True
        }

        with requests.post(f"{OLLAMA_URL}/api/chat", json=payload, stream=True) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode("utf-8"))
                        content = data.get("message", {}).get("content")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        yield "[Malformed JSON]"

    except requests.exceptions.RequestException as e:
        print("Ollama call failed:", e)
        return "[Ollama API error]"
    except Exception as e:
        print("Unexpected error:", e)
        return "[Unexpected backend error]"