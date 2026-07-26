"""REST API router for LLM querying with rulebook and transcription context."""

import os

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.base_models.llm_base_models import LLMRequest
from app.core.chat_store import chat_store
from app.domain.store import store
from app.functions.embedding.embedding_model import (
    embed_text,
    embedding_search,
    embedding_search_on_chat_history,
    get_all_transcription_documents,
)
from app.functions.llm.custom_model import run_custom_model
from app.functions.llm.system_prompt import get_system_prompt

router = APIRouter()


def _is_entity_listing_request(text: str) -> bool:
    """Check if the user is asking about entities (temporal or location).

    Args:
        text: The user's input text.

    Returns:
        True if the request appears to be about entities.
    """
    normalized = text.casefold()
    asks_for_entities = 'entity' in normalized or 'entities' in normalized
    asks_for_time_or_place = any(
        word in normalized
        for word in ('temporal', 'time', 'location', 'local', 'place', 'where', 'when')
    )
    return asks_for_entities and asks_for_time_or_place


@router.post('/run', response_class=StreamingResponse)
async def run_llm(req: LLMRequest) -> StreamingResponse:
    """Query the LLM with a player's input, returning a streaming response.

    Retrieves relevant context from the rulebook and transcriptions,
    builds a system prompt, and streams the LLM response.

    Args:
        req: LLMRequest with player_id, input_string, and use_rulebook flag.

    Returns:
        StreamingResponse: StreamingResponse yielding LLM output chunks.
    """
    # 1) Spieler existiert?
    try:
        print(f'trying to get player ID + {req.player_id}')
        print(f'group size: {store.group.size()}')
        player = store.group.get_player(req.player_id)
    except KeyError:
        print('Player not found')
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Player not found')

    # 2) Nachricht speichern
    print('speichere nachricht')

    # 3) Embeddings erhalten für system prompt
    if not req.use_rulebook and _is_entity_listing_request(req.input_string):
        retrieved_docs = get_all_transcription_documents()
    else:
        retrieved_docs = embedding_search(req.input_string, req.use_rulebook)

    embedded_request = embed_text(req.input_string)
    top_k_chat_history = await embedding_search_on_chat_history(
        req.input_string, embedded_request, player.id
    )

    # Maybe move this to the end
    await chat_store.append(player.id, 'user', req.input_string, embedded_request)

    context = ''
    # sources = [doc.metadata.get("source") for doc in retrieved_docs]
    for doc in retrieved_docs:
        context += '--Source-- ' + doc.metadata.get('source') + '--End Source-- \n'
        if doc.metadata.get('path') is not None:
            full_path = doc.metadata.get('path')
            filename = os.path.basename(full_path).replace('.md', '')
            context += '-filename-' + filename + '-End filename- \n'
        if doc.metadata.get('source') == 'transcriptions':
            context += 'Player: ' + doc.metadata.get('player_id') + '; '
            temporal_entities = doc.metadata.get('temporal_entities')
            location_entities = doc.metadata.get('location_entities')
            if temporal_entities:
                context += 'Time entities: ' + temporal_entities + '; '
            if location_entities:
                context += 'Location entities: ' + location_entities + '; '
            context += 'Content: ' + doc.page_content + '\n\n'
        else:
            context += doc.page_content + '\n\n'

    context += (
        'The player asking questions is: ' + player.name + ' and has role ' + player.role + '\n\n'
    )

    # context = "\n\n".join([doc.page_content for doc in retrieved_docs])
    system_message = get_system_prompt(context)

    # 4) Generator zum Streamen
    async def event_generator(system_prompt: dict, chat_history: list[dict]):
        """Async generator that streams LLM response chunks.

        Args:
            system_prompt: The system prompt dict for the LLM.
            chat_history: The relevant chat history context.

        Yields:
            Text chunks from the LLM response.
        """
        # yield json.dumps({"type": "metadata", "markdown_texts": markdown_texts}) + "\n"

        llm_resp = ''
        # komplette History
        await chat_store.history(player.id)
        chat_history.insert(0, system_prompt)
        # print("----------")
        print(chat_history)
        async for chunk in run_custom_model(chat_history):
            llm_resp += chunk
            yield chunk
            # yield json.dumps({"type": "llm_chunk", "content": chunk}) + "\n"
        # 4) Antwort speichern
        print(llm_resp)
        embedded_response = embed_text(llm_resp)
        await chat_store.append(player.id, 'assistant', llm_resp, embedded_response)

    return StreamingResponse(
        event_generator(system_message, top_k_chat_history), media_type='text/plain'
    )
