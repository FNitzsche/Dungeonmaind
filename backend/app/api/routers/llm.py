from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
import os

from app.base_models.llm_base_models import LLMRequest
from app.functions.llm.custom_model import run_custom_model
from app.functions.llm.system_prompt import get_system_prompt
from app.core.chat_store import chat_store
from app.domain.store import store
from app.functions.embedding.embedding_model import (
    embedding_search,
    embed_text,
    embedding_search_on_chat_history,
)


router = APIRouter()


MAX_RETRIEVED_DOCUMENTS = 5
MAX_TRANSCRIPTION_CHARACTERS = 900
MAX_RULEBOOK_CHARACTERS = 700
MAX_CHAT_HISTORY_MESSAGES = 4


def limit_text(
    text: str,
    maximum_characters: int,
) -> str:
    """
    Shorten retrieved text before sending it to Ollama.

    This prevents the complete prompt from exceeding the model's
    available context size.
    """

    cleaned = " ".join(text.split())

    if len(cleaned) <= maximum_characters:
        return cleaned

    shortened = cleaned[:maximum_characters].rsplit(
        " ",
        1,
    )[0]

    return f"{shortened}..."

def build_valid_chat_messages(
    system_message: dict,
    chat_history: list[dict],
    current_question: str,
) -> list[dict]:
    """
    Build a valid Ollama conversation.

    The model requires:
    system -> user -> assistant -> user -> assistant ...

    Invalid, empty, duplicated or out-of-order messages are skipped.
    This works dynamically for every player.
    """

    messages: list[dict] = [system_message]
    expected_role = "user"

    for message in chat_history:
        role = message.get("role")
        content = str(
            message.get("content", "")
        ).strip()

        if role not in {"user", "assistant"}:
            continue

        if not content:
            continue

        if role != expected_role:
            continue

        messages.append(
            {
                "role": role,
                "content": content,
            }
        )

        expected_role = (
            "assistant"
            if expected_role == "user"
            else "user"
        )

    # The final message sent to the model must be the current user question.
    if messages[-1].get("role") == "user":
        # Remove the unmatched previous user message.
        messages.pop()

    messages.append(
        {
            "role": "user",
            "content": current_question,
        }
    )

    return messages


def build_context(
    retrieved_docs: list,
    player,
) -> str:
    """
    Build a compact context from transcription and optional rulebook
    search results.
    """

    context_parts: list[str] = []

    for doc in retrieved_docs[:MAX_RETRIEVED_DOCUMENTS]:
        source = str(
            doc.metadata.get(
                "source",
                "unknown",
            )
        )

        if source == "transcriptions":
            player_name = str(
                doc.metadata.get(
                    "player_id",
                    "unknown",
                )
            )

            content = limit_text(
                doc.page_content,
                MAX_TRANSCRIPTION_CHARACTERS,
            )

            context_parts.append(
                "\n".join(
                    [
                        "--Source-- transcriptions --End Source--",
                        "-filename-none-End filename-",
                        f"Player: {player_name}; Content: {content}",
                    ]
                )
            )

        else:
            full_path = doc.metadata.get("path")

            if full_path:
                filename = os.path.basename(
                    str(full_path)
                ).replace(".md", "")
            else:
                filename = "unknown"

            content = limit_text(
                doc.page_content,
                MAX_RULEBOOK_CHARACTERS,
            )

            context_parts.append(
                "\n".join(
                    [
                        f"--Source-- {source} --End Source--",
                        f"-filename-{filename}-End filename-",
                        content,
                    ]
                )
            )

    context_parts.append(
        f"The player asking questions is: {player.name} "
        f"and has role {player.role}."
    )

    return "\n\n".join(context_parts)


def normalize_chat_history(
    chat_history: list[dict],
) -> list[dict]:
    """
    Keep only a small number of recent and valid chat-history messages.
    """

    valid_messages: list[dict] = []

    for message in chat_history:
        role = message.get("role")
        content = str(
            message.get(
                "content",
                "",
            )
        ).strip()

        if role not in {
            "user",
            "assistant",
        }:
            continue

        if not content:
            continue

        valid_messages.append(
            {
                "role": role,
                "content": limit_text(
                    content,
                    600,
                ),
            }
        )

    return valid_messages[
        -MAX_CHAT_HISTORY_MESSAGES:
    ]


@router.post(
    "/run",
    response_class=StreamingResponse,
)
async def run_llm(
    req: LLMRequest,
):
    """
    Answer questions using compact transcription, optional rulebook and
    recent chat-history context.
    """

    # 1. Check whether the player exists.
    try:
        print(
            f"Trying to get player ID: {req.player_id}"
        )
        print(
            f"Group size: {store.group.size()}"
        )

        player = store.group.get_player(
            req.player_id
        )

    except KeyError as error:
        print("Player not found")

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found",
        ) from error

    # 2. Retrieve relevant transcription documents.
    #
    # embedding_search should use req.use_rulebook to decide whether
    # rulebook entries should also be included.
    retrieved_docs = embedding_search(
        req.input_string,
        req.use_rulebook,
    )

    # Keep only a small number of results.
    retrieved_docs = retrieved_docs[
        :MAX_RETRIEVED_DOCUMENTS
    ]

    # 3. Embed the current request.
    embedded_request = embed_text(
        req.input_string
    )

    # 4. Retrieve a small amount of relevant chat history.
    top_k_chat_history = (
        await embedding_search_on_chat_history(
            req.input_string,
            embedded_request,
            player.id,
        )
    )

    top_k_chat_history = normalize_chat_history(
        top_k_chat_history
    )

    # Store the current user question.
    await chat_store.append(
        player.id,
        "user",
        req.input_string,
        embedded_request,
    )

    # 5. Build a compact context and system prompt.
    context = build_context(
        retrieved_docs,
        player,
    )

    system_message = get_system_prompt(
        context
    )

    # 6. Stream the model answer.
    async def event_generator():
        llm_response = ""

        messages = build_valid_chat_messages(
            system_message=system_message,
            chat_history=top_k_chat_history,
            current_question=req.input_string,
        )

        print(
            f"Sending {len(messages)} messages to Ollama "
            f"for player {player.id}"
        )

        async for chunk in run_custom_model(
            messages
        ):
            llm_response += chunk
            yield chunk

        print(llm_response)

        if llm_response.strip():
            embedded_response = embed_text(
                llm_response
            )

            await chat_store.append(
                player.id,
                "assistant",
                llm_response,
                embedded_response,
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/plain",
    )