import asyncio

from fastapi import APIRouter

from app.base_models.timeline_models import (
    TimelineEventCreate,
    TimelineGenerationResponse,
    TimelineResponse,
)
from app.functions.timeline.timeline_generator import (
    generate_timeline_from_embeddings,
)
from app.functions.timeline.timeline_store import timeline_store


router = APIRouter()


@router.get(
    "/events",
    response_model=TimelineResponse,
    summary="Return the stored timeline",
)
async def list_timeline_events() -> TimelineResponse:
    """Read existing timeline events without running generation."""
    events = await asyncio.to_thread(timeline_store.list_events)

    return TimelineResponse(
        events=events,
        total=len(events),
    )


def _generate_and_store_timeline() -> TimelineGenerationResponse:
    events, source_segment_count = generate_timeline_from_embeddings()
    # The store assigns IDs and timestamps; retain all generated event content.
    stored_events = timeline_store.replace_events([
        TimelineEventCreate.model_validate(event.model_dump())
        for event in events
    ])
    return TimelineGenerationResponse(
        events=stored_events,
        generated_count=len(stored_events),
        source_segment_count=source_segment_count,
    )


@router.post(
    "/generate",
    response_model=TimelineGenerationResponse,
    summary="Generate timeline from transcription embeddings",
)
async def generate_timeline() -> TimelineGenerationResponse:
    """
    Read all transcription documents from ChromaDB, arrange them by
    timestamp, group nearby segments and generate timeline events.

    Replace the stored timeline only after generation succeeds.
    """

    return await asyncio.to_thread(_generate_and_store_timeline)
