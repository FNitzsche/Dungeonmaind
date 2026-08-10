from fastapi import APIRouter

from app.base_models.timeline_models import (
    TimelineGenerationResponse,
    TimelineResponse,
)
from app.functions.timeline.timeline_generator import (
    generate_timeline_from_embeddings,
)


router = APIRouter()


@router.get(
    "/events",
    response_model=TimelineResponse,
    summary="Generate and return the current timeline",
)
async def list_timeline_events() -> TimelineResponse:
    """
    Generate timeline events dynamically from the current transcription
    documents stored in ChromaDB.
    """

    events, _ = generate_timeline_from_embeddings()

    return TimelineResponse(
        events=events,
        total=len(events),
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

    The generated events are not stored separately.
    """

    events, source_segment_count = (
        generate_timeline_from_embeddings()
    )

    return TimelineGenerationResponse(
        events=events,
        generated_count=len(events),
        source_segment_count=source_segment_count,
    )