"""Pydantic models for configuration request/response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class ConfigRequest(BaseModel):
    """Request model for updating backend configuration.

    Attributes:
        player_id: ID of the player making the config change.
        selected_LLM: The selected LLM model identifier.
        transcription_model: Transcription model (base or medium).
        embedding_model: Embedding model name.
        embedding_top_k: Number of top_k embeddings.
        clear_chat: Whether to clear all chat history.
        delete_transcriptions: Whether to delete transcriptions from ChromaDB.
    """

    player_id: UUID = Field(..., description='ID aus /players')
    selected_LLM: str = Field(..., description='User selected LLM')
    transcription_model: str = Field(..., description='Transcription model (base or medium)')
    embedding_model: str = Field(..., description='Embedding model')
    embedding_top_k: int = Field(2, description='Number of top_k embeddings')
    clear_chat: bool = Field(False, description='Whether to clear chat history')
    delete_transcriptions: bool = Field(
        False, description='Delete the transcirptions from the chroma_db'
    )


class ConfigChangeResponse(BaseModel):
    """Response model confirming a configuration change."""

    status: str = Field(..., description='Confirmation status')


class ConfigGetResponse(BaseModel):
    """Response model for retrieving the current configuration."""

    selected_LLM: str = Field(..., description='Current LLM model')
    transcription_model: str = Field(..., description='Current transcription model')
    embedding_model: str = Field(..., description='Current embedding model')
    embedding_top_k: int = Field(..., description='Current embedding top_k (1-4)')
