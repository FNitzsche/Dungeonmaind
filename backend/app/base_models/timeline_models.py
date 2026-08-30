from enum import Enum

from pydantic import BaseModel, Field


class TimelineCategory(str, Enum):
    travel = "travel"
    combat = "combat"
    dialogue = "dialogue"
    discovery = "discovery"
    rest = "rest"
    quest = "quest"
    item = "item"
    other = "other"


class TimelineSourceSegment(BaseModel):
    text: str
    speaker: str = "unknown"
    start_time: float = Field(default=0.0, ge=0.0)
    end_time: float = Field(default=0.0, ge=0.0)


class TimelineEventCreate(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=120,
    )

    description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )

    category: TimelineCategory = TimelineCategory.other

    start_time: float = Field(
        default=0.0,
        ge=0.0,
    )

    end_time: float = Field(
        default=0.0,
        ge=0.0,
    )

    speakers: list[str] = Field(
        default_factory=list,
    )

    locations: list[str] = Field(
        default_factory=list,
    )

    temporal_entities: list[str] = Field(
        default_factory=list,
    )

    source_segments: list[TimelineSourceSegment] = Field(
        default_factory=list,
    )

    created_automatically: bool = False


class TimelineEventUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )

    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=2000,
    )

    category: TimelineCategory | None = None

    start_time: float | None = Field(
        default=None,
        ge=0.0,
    )

    end_time: float | None = Field(
        default=None,
        ge=0.0,
    )

    speakers: list[str] | None = None
    locations: list[str] | None = None
    temporal_entities: list[str] | None = None


class TimelineEvent(TimelineEventCreate):
    id: str
    created_at: str
    updated_at: str


class TimelineResponse(BaseModel):
    events: list[TimelineEvent] = Field(
        default_factory=list,
    )

    total: int = Field(
        default=0,
        ge=0,
    )


class TimelineGenerationResponse(BaseModel):
    events: list[TimelineEvent] = Field(
        default_factory=list,
    )

    generated_count: int = Field(
        default=0,
        ge=0,
    )

    source_segment_count: int = Field(
        default=0,
        ge=0,
    )

