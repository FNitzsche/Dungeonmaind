"""Pydantic models for timeline event request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class TimelineEventOut(BaseModel):
    """Response model for a single timeline event.

    Attributes:
        id: Unique event identifier.
        session_id: Session this event belongs to.
        title: Event title.
        description: Event description.
        event_type: Categorization (combat, discovery, etc.).
        order: Ordinal position in the session.
        timestamp: Float timestamp.
        transcription_chunk_id: Related transcription chunk ID.
        player_id: Associated player ID.
        speaker_name: Associated speaker name.
        temporal_entities: Time-related entities.
        location_entities: Location entities.
        created_at: Event creation timestamp.
    """

    id: str
    session_id: str
    title: str
    description: str
    event_type: str
    order: int
    timestamp: float = 0.0
    transcription_chunk_id: str | None = None
    player_id: str | None = None
    speaker_name: str | None = None
    temporal_entities: list[str] = Field(default_factory=list)
    location_entities: list[str] = Field(default_factory=list)
    characters: list[str] = Field(default_factory=list)
    display_time: str | None = None
    created_at: datetime


class TimelineEventListResponse(BaseModel):
    """Response model for a paginated list of timeline events."""

    session_id: str
    events: list[TimelineEventOut]
    total: int


class TimelineGenerateRequest(BaseModel):
    """Request model for generating timeline events from transcriptions."""

    session_id: str = 'default'


class TimelineGenerateResponse(BaseModel):
    """Response model after generating timeline events."""

    session_id: str
    events_generated: int
    events: list[TimelineEventOut]


class TimelineDeleteResponse(BaseModel):
    """Response model for a timeline event deletion result."""

    deleted: bool
    event_id: str | None = None
