"""REST API router for backend configuration management."""

from fastapi import APIRouter, HTTPException, status

from app.base_models.config_base_models import (
    ConfigChangeResponse,
    ConfigGetResponse,
    ConfigRequest,
)
from app.core.chat_store import chat_store
from app.core.config import settings
from app.domain.store import store
from app.functions.embedding.embedding_model import (
    delete_transcription_embeddings,
    reembed_chroma_entries,
)
from app.functions.process_audio_data.transcribe_audio import reload_transcription_model

router = APIRouter()

VALID_MODELS = {
    'hf.co/bartowski/microsoft_Phi-4-mini-instruct-GGUF:Q5_K_M',
    'hf.co/bartowski/google_gemma-3-1b-it-qat-GGUF:Q5_K_M',
    'hf.co/bartowski/google_gemma-3-12b-it-qat-GGUF:Q5_K_M',
    'hf.co/bartowski/mistralai_Ministral-3-14B-Instruct-2512-GGUF:Q5_K_M',
    'hf.co/bartowski/mistralai_Ministral-3-3B-Instruct-2512-GGUF:Q5_K_M',
}

VALID_TRANS_MODELS = {'base', 'medium', 'large-v3'}

VALID_EMBEDDING_MODELS = {
    'all-MiniLM-L6-v2',
    'all-MiniLM-L12-v2',
    'paraphrase-multilingual-MiniLM-L12-v2',
}

VALID_EMBEDDING_Top_K = {3, 6, 9, 12}


@router.post('/changeConfig', response_model=ConfigChangeResponse)
async def change_config(request: ConfigRequest) -> ConfigChangeResponse:
    """Update backend configuration settings.

    Validates and applies changes to LLM model, transcription model,
    embedding model, and chat/transcription management.

    Args:
        request: ConfigRequest with the desired configuration changes.

    Returns:
        ConfigChangeResponse: ConfigChangeResponse with status confirmation.
    """
    try:
        if request.selected_LLM not in VALID_MODELS:
            raise HTTPException(status_code=400, detail='Invalid llm model selected.')
        if request.transcription_model not in VALID_TRANS_MODELS:
            raise HTTPException(status_code=400, detail='Invalid transcription model selected.')
        if request.embedding_model not in VALID_EMBEDDING_MODELS:
            raise HTTPException(status_code=400, detail='Invalid embedding model selected.')
        if request.embedding_top_k not in VALID_EMBEDDING_Top_K:
            raise HTTPException(status_code=400, detail='Invalid embedding TopK selected.')

        # save in config
        if settings.llm_model != request.selected_LLM:
            settings.llm_model = request.selected_LLM
            print(f'[CONFIG] LLM changed to: {settings.llm_model}')

        if settings.transcription_model != request.transcription_model:
            settings.transcription_model = request.transcription_model
            reload_transcription_model()
            print(f'[CONFIG] Transcription model changed to: {settings.transcription_model}')

        if request.clear_chat:
            try:
                store.group.get_player(request.player_id)
            except KeyError:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Player not found')
            await chat_store.clear_all()
            print('[CONFIG] Chat Verlauf gelöscht.')

        if request.delete_transcriptions:
            delete_transcription_embeddings()
            print('[CONFIG] Embedded transcriptions deleted')

        if settings.embedding_model != request.embedding_model:
            reembed_chroma_entries(request.embedding_model)
            settings.embedding_model = request.embedding_model
            print(f'[CONFIG] Embedding model changed to: {settings.embedding_model}')

        if settings.embedding_top_k != request.embedding_top_k:
            settings.embedding_top_k = request.embedding_top_k
            print(f'[CONFIG] Embedding TopK changed to: {settings.embedding_top_k}')

        return ConfigChangeResponse(status='success')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/getConfig', response_model=ConfigGetResponse)
async def get_config() -> ConfigGetResponse:
    """Retrieve the current backend configuration.

    Returns:
        ConfigGetResponse: ConfigGetResponse with the current settings.
    """
    return ConfigGetResponse(
        selected_LLM=settings.llm_model,
        transcription_model=settings.transcription_model,
        embedding_model=settings.embedding_model,
        embedding_top_k=settings.embedding_top_k,
    )
