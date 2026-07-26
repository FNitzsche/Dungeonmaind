"""Application configuration loaded from environment variables and .env file."""

import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded via Pydantic from environment variables.

    Attributes:
        app_name: Name of the application.
        debug: Enable debug logging.
        host: Bind address for the server.
        port: Listening port for the server.
        hf_token: Hugging Face access token for diarization.
        llm_model: The default LLM model used by the backend.
        ollama_url: URL for local Ollama LLM server.
        transcription_model: Transcription model (base or medium).
        embedding_model: Embedding model name.
        embedding_top_k: Number of top_k embeddings (2-8).
        entity_llm_fallback: Enable local LLM fallback for entity extraction.
        backend_root_path: Root directory of the backend.
    """

    model_config = SettingsConfigDict(env_file='.env', case_sensitive=False)
    app_name: str = Field(
        default='Awesome API', validation_alias='APP_NAME', description='Name of the application'
    )
    debug: bool = Field(default=False, validation_alias='DEBUG', description='Enable debug logging')
    host: str = Field(default='0.0.0.0', validation_alias='HOST', description='Bind address')
    port: int = Field(default=8000, validation_alias='PORT', description='Listening port')

    hf_token: Optional[str] = Field(
        default=None, alias='HF_TOKEN', description='Hugging Face access token'
    )

    llm_model: str = Field(
        default='hf.co/bartowski/mistralai_Ministral-3-3B-Instruct-2512-GGUF:Q5_K_M',
        validation_alias='LLM_MODEL',
        description='The default LLM model used by the backend',
    )

    ollama_url: str = Field(
        default='http://localhost:11434',
        validation_alias='OLLAMA_URL',
        description='URL for local Ollama LLM server',
    )

    transcription_model: str = Field(
        default='base',
        validation_alias='TRANSCRIPTION_MODEL',
        description='Transcription model (base or medium)',
    )

    embedding_model: str = Field(
        default='all-MiniLM-L6-v2',
        validation_alias='EMBEDDING_MODEL',
        description='Embedding model',
    )

    embedding_top_k: int = Field(
        default=6,
        validation_alias='EMBEDDING_TOP_K',
        description='Number of top_k embeddings (2-8)',
    )

    entity_llm_fallback: bool = Field(
        default=True,
        validation_alias='ENTITY_LLM_FALLBACK',
        description='Enable local LLM fallback for temporal/location entity extraction during embedding',
    )

    enable_diarization: bool = Field(
        default=False,
        validation_alias='ENABLE_DIARIZATION',
        description='Enable speaker diarization during transcription',
    )

    ffmpeg_path: Optional[str] = Field(
        default=None,
        validation_alias='FFMPEG_PATH',
        description='Path to ffmpeg binary for audio processing',
    )

    run_startup_embedding_maintenance: bool = Field(
        default=False,
        validation_alias='RUN_STARTUP_EMBEDDING_MAINTENANCE',
        description='Run embedding maintenance tasks during backend startup',
    )

    backend_root_path: str = Field(
        default_factory=lambda: os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ),
        description='Root directory of the backend',
    )

    # @property
    # def chroma_db_path(self) -> str:
    #    return os.path.join(self.backend_root_path, "data", "chroma_db")

    _chroma_db_path: Optional[str] = None

    @property
    def chroma_db_path(self) -> str:
        """Return the ChromaDB path.

        If a custom path was set via the setter, returns it;
        otherwise returns the default path under data/chroma_db.

        Returns:
            The ChromaDB directory path.
        """
        return self._chroma_db_path or os.path.join(self.backend_root_path, 'data', 'chroma_db')

    @chroma_db_path.setter
    def chroma_db_path(self, value: str):
        """Set a custom ChromaDB path."""
        self._chroma_db_path = value


settings = Settings()
