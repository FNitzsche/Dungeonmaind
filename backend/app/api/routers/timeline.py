"""REST API router for timeline event management and generation."""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.mappers.timeline_mapper import timeline_event_to_out
from app.base_models.timeline_base_models import (
    TimelineDeleteResponse,
    TimelineEventListResponse,
    TimelineEventOut,
    TimelineGenerateRequest,
    TimelineGenerateResponse,
)
from app.domain.timeline_store import timeline_store
from app.functions.embedding.embedding_model import get_all_transcription_documents
from app.functions.llm.event_extractor import (
    build_timeline_events_from_transcription_documents,
    extract_events_from_transcriptions,
)

router = APIRouter()


@router.get('/events', response_model=TimelineEventListResponse)
async def list_events(
    session_id: str = Query('default', description='Session identifier'),
) -> TimelineEventListResponse:
    """List all timeline events for a given session.

    Args:
        session_id (str): Session identifier (default 'default').

    Returns:
        TimelineEventListResponse: TimelineEventListResponse with events and total count.
    """
    events = await timeline_store.get_session_events(session_id)
    return TimelineEventListResponse(
        session_id=session_id, events=[timeline_event_to_out(e) for e in events], total=len(events)
    )


@router.get('/events/{event_id}', response_model=TimelineEventOut)
async def get_event(event_id: str) -> TimelineEventOut:
    """Get a single timeline event by its ID.

    Args:
        event_id (str): The event identifier.

    Returns:
        TimelineEventOut: TimelineEventOut for the requested event.

    Raises:
        HTTPException 404: If the event is not found.
    """
    event = await timeline_store.get_event(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Event not found')
    return timeline_event_to_out(event)


@router.delete('/events/{event_id}', response_model=TimelineDeleteResponse)
async def delete_event(event_id: str) -> TimelineDeleteResponse:
    """Delete a single timeline event by its ID.

    Args:
        event_id (str): The event identifier.

    Returns:
        TimelineDeleteResponse: TimelineDeleteResponse indicating success.
    """
    deleted = await timeline_store.delete_event(event_id)
    return TimelineDeleteResponse(deleted=deleted, event_id=event_id)


@router.delete('/events', response_model=TimelineDeleteResponse)
async def clear_session_events(
    session_id: str = Query('default', description='Session identifier'),
) -> TimelineDeleteResponse:
    """Clear all timeline events for a given session.

    Args:
        session_id (str): Session identifier (default 'default').

    Returns:
        TimelineDeleteResponse: TimelineDeleteResponse indicating success.
    """
    await timeline_store.clear_session(session_id)
    return TimelineDeleteResponse(deleted=True, event_id=None)


@router.post('/generate', response_model=TimelineGenerateResponse)
async def generate_events(req: TimelineGenerateRequest) -> TimelineGenerateResponse:
    """Generate timeline events from all available transcription documents.

    Args:
        req (TimelineGenerateRequest): TimelineGenerateRequest with session_id.

    Returns:
        TimelineGenerateResponse: TimelineGenerateResponse with the generated events.

    Raises:
        HTTPException 404: If no transcription documents are found.
    """
    docs = get_all_transcription_documents()
    if not docs:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail='No transcription documents found. Record and transcribe audio first.',
        )

    texts = [doc.page_content for doc in docs]
    speakers = [doc.metadata.get('player_id', 'unknown') for doc in docs]
    timestamps = [float(doc.metadata.get('start_time', 0.0)) for doc in docs]
    events = extract_events_from_transcriptions(
        texts=texts, speakers=speakers, timestamps=timestamps, session_id=req.session_id
    )
    if not events:
        events = build_timeline_events_from_transcription_documents(docs, session_id=req.session_id)

    await timeline_store.clear_session(req.session_id)
    added = await timeline_store.add_events(events)

    return TimelineGenerateResponse(
        session_id=req.session_id,
        events_generated=len(added),
        events=[timeline_event_to_out(e) for e in added],
    )
