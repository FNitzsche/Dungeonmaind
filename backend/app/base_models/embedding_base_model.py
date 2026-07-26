"""Pydantic models for embedding request/response schemas."""

from pydantic import BaseModel, Field


class EmbeddRequest(BaseModel):
    """Request model for embedding a text string."""

    input_string: str = Field(..., description='Text to be embedded')


class EmbeddResponse(BaseModel):
    """Response model containing a list of markdown texts."""

    markdown_texts: list[str]


class EmbeddingSearch(BaseModel):
    """Request model for searching via embeddings."""

    input_string: str = Field(..., description='Search string for embedding search')
