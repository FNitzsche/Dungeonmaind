"""REST API router for backend configuration management."""

import logging

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

logger = logging.getLogger(__name__)

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


def _allowed(known: set, current_value: object) -> set:
    """Return the valid values for one setting, plus the one already in use.

    The backend can be pointed at a model that is not in the built-in list, for
    instance through ``LLM_MODEL`` in ``.env`` for a model served by Ollama.
    That value has to stay acceptable: the configuration page sends every field
    back, including the ones the user did not touch, so rejecting the backend's
    own current value would make it impossible to save any other change.

    Args:
        known: The built-in options for the setting.
        current_value: The value the backend is running with.

    Returns:
        The set of values accepted for this setting.
    """
    return {*known, current_value}


def _validate(request: ConfigRequest) -> None:
    """Check every selected value before any of them is applied.

    Args:
        request: The requested configuration.

    Raises:
        HTTPException 400: If a value is neither a known option nor the value
            the backend currently uses. The message names the offending value
            and the accepted ones.
    """
    checks = (
        ('llm model', request.selected_LLM, _allowed(VALID_MODELS, settings.llm_model)),
        (
            'transcription model',
            request.transcription_model,
            _allowed(VALID_TRANS_MODELS, settings.transcription_model),
        ),
        (
            'embedding model',
            request.embedding_model,
            _allowed(VALID_EMBEDDING_MODELS, settings.embedding_model),
        ),
        (
            'embedding TopK',
            request.embedding_top_k,
            _allowed(VALID_EMBEDDING_Top_K, settings.embedding_top_k),
        ),
    )
    for name, value, allowed in checks:
        if value not in allowed:
            options = ', '.join(sorted(str(option) for option in allowed))
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f'Invalid {name} selected: {value!r}. Allowed values: {options}',
            )


@router.post('/changeConfig', response_model=ConfigChangeResponse)
async def change_config(request: ConfigRequest) -> ConfigChangeResponse:
    """Update backend configuration settings.

    Validates and applies changes to LLM model, transcription model,
    embedding model, and chat/transcription management.

    Args:
        request: ConfigRequest with the desired configuration changes.

    Returns:
        ConfigChangeResponse: ConfigChangeResponse with status confirmation.

    Raises:
        HTTPException 400: If one of the selected values is not valid. Nothing
            is applied in that case.
        HTTPException 404: If the chat history of an unknown player should be cleared.
        HTTPException 500: If applying a valid change failed. The full traceback
            is written to the log.
    """
    _validate(request)

    try:
        # save in config
        if settings.llm_model != request.selected_LLM:
            settings.llm_model = request.selected_LLM
            logger.info('[CONFIG] LLM changed to: %s', settings.llm_model)

        if settings.transcription_model != request.transcription_model:
            settings.transcription_model = request.transcription_model
            reload_transcription_model()
            logger.info('[CONFIG] Transcription model changed to: %s', settings.transcription_model)

        if request.clear_chat:
            try:
                store.group.get_player(request.player_id)
            except KeyError:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Player not found')
            await chat_store.clear_all()
            logger.info('[CONFIG] Chat Verlauf gelöscht.')

        if request.delete_transcriptions:
            delete_transcription_embeddings()
            logger.info('[CONFIG] Embedded transcriptions deleted')

        if settings.embedding_model != request.embedding_model:
            reembed_chroma_entries(request.embedding_model)
            settings.embedding_model = request.embedding_model
            logger.info('[CONFIG] Embedding model changed to: %s', settings.embedding_model)

        if settings.embedding_top_k != request.embedding_top_k:
            settings.embedding_top_k = request.embedding_top_k
            logger.info('[CONFIG] Embedding TopK changed to: %s', settings.embedding_top_k)

    except HTTPException:
        # A deliberate 4xx (an unknown player, for instance) keeps its status.
        raise
    except Exception as e:
        # Without this the traceback never reaches the terminal, because the
        # exception is turned into a response instead of propagating.
        logger.exception('Applying the configuration change failed')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Could not apply the configuration change: {e}',
        ) from e

    return ConfigChangeResponse(status='success')


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
