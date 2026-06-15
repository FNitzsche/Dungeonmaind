from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse, JSONResponse
import os
import json
from app.base_models.llm_base_models import LLMRequest, ExtractedEntitiesResponse
from app.functions.llm.custom_model import run_custom_model
from app.functions.llm.system_prompt import get_system_prompt
from app.functions.llm.entity_extraction_prompt import get_local_entity_prompt, get_temporal_entity_prompt
from app.core.chat_store import chat_store
from app.domain.store import store
from app.functions.embedding.embedding_model import embedding_search, embed_text, embedding_search_on_chat_history
from app.core.config import settings


router = APIRouter()


@router.post("/run", response_class=StreamingResponse)
async def run_llm(req: LLMRequest):
    # 1) Spieler existiert?
    try:
        player = store.group.get_player(req.player_id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Player not found")

    # 2) Embeddings erhalten für system prompt
    retrieved_docs = embedding_search(req.input_string, req.use_rulebook)

    embedded_request = embed_text(req.input_string)
    top_k_chat_history = await embedding_search_on_chat_history(req.input_string, embedded_request, player.id)

    # Maybe move this to the end
    await chat_store.append(player.id, "user", req.input_string, embedded_request)

    context = ""
    for doc in retrieved_docs:
        context += "--Source-- " + doc.metadata.get("source") + "--End Source-- \n"
        if doc.metadata.get("path") is not None:
            full_path = doc.metadata.get("path")
            filename = os.path.basename(full_path).replace(".md", "")
            context += "-filename-" + filename + "-End filename- \n"
        if doc.metadata.get("source") == "transcriptions":
            context += "Player: " + doc.metadata.get("player_id") + "; Content: " + doc.page_content + "\n\n"
        else:
            context += doc.page_content + "\n\n"

    context += "The player asking questions is: " + player.name + " and has role " + player.role + "\n\n"

    system_message = get_system_prompt(context)

    # 4) Generator zum Streamen
    async def event_generator(system_prompt: dict, chat_history: list[dict]):
        llm_resp = ""
        chat_history.insert(0, system_prompt)
        async for chunk in run_custom_model(chat_history):
            llm_resp += chunk
            yield chunk
        
        embedded_response = embed_text(llm_resp)
        await chat_store.append(player.id, "assistant", llm_resp, embedded_response)

    return StreamingResponse(event_generator(system_message, top_k_chat_history), media_type="text/plain")


async def _extract_and_validate(prompt: str, key: str, lower_transcript: str) -> list[str]:
    """
    Helper function to run one extraction call, parse, and validate the result.
    This uses a "forced response" technique by providing the opening brace.
    """
    # This new structure forces the model to start with JSON.
    extraction_prompt_list = [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "{"}
    ]
    
    llm_response_str = ""
    async for chunk in run_custom_model(extraction_prompt_list):
        llm_response_str += chunk

    # We must prepend the opening brace that we forced the assistant to start with.
    full_json_str = "{" + llm_response_str

    try:
        # Clean up potential markdown code blocks which might still appear
        if "```json" in full_json_str:
            json_str = full_json_str.split("```json")[1].split("```")[0].strip()
        else:
            json_str = full_json_str
        
        extracted_data = json.loads(json_str)
        raw_entities = extracted_data.get(key, [])
        
        # Validate the extracted entities
        validated_entities = [entity for entity in raw_entities if entity.lower() in lower_transcript]
        return validated_entities

    except (json.JSONDecodeError, IndexError) as e:
        print(f"Failed to parse or validate for key '{key}': {e}")
        print(f"LLM Response was: {full_json_str}")
        return []


@router.post("/extract_entities", response_model=ExtractedEntitiesResponse)
async def extract_entities(req: LLMRequest):
    try:
        player = store.group.get_player(req.player_id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Player not found")

    # 1. Get the full chat history and format it as a simple transcript
    history = await chat_store.history(player.id)
    if not history:
        return JSONResponse(content={"local_entities": [], "temporal_entities": []})

    transcript = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in history])
    lower_transcript = transcript.lower()

    # 2. Call 1: Extract Local Entities
    local_prompt = get_local_entity_prompt(transcript)
    validated_local = await _extract_and_validate(local_prompt, "local_entities", lower_transcript)

    # 3. Call 2: Extract Temporal Entities
    temporal_prompt = get_temporal_entity_prompt(transcript)
    validated_temporal = await _extract_and_validate(temporal_prompt, "temporal_entities", lower_transcript)

    # 4. Combine and return the results
    response_data = {
        "local_entities": validated_local,
        "temporal_entities": validated_temporal
    }
    
    return JSONResponse(content=response_data)
