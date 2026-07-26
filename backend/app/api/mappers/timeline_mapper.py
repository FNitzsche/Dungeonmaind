"""Mapper for converting domain TimelineEvent models to TimelineEventOut schemas."""

from app.base_models.timeline_base_models import TimelineEventOut
from app.domain.models import TimelineEvent as DomainTimelineEvent


def timeline_event_to_out(event: DomainTimelineEvent) -> TimelineEventOut:
    """Map a domain TimelineEvent to a TimelineEventOut Pydantic schema.

    Args:
        event: The domain TimelineEvent instance.

    Returns:
        A TimelineEventOut schema instance.
    """
    return TimelineEventOut(
        id=event.id,
        session_id=event.session_id,
        title=event.title,
        description=event.description,
        event_type=event.event_type.value,
        order=event.order,
        timestamp=event.timestamp,
        transcription_chunk_id=event.transcription_chunk_id,
        player_id=event.player_id,
        speaker_name=event.speaker_name,
        temporal_entities=list(event.temporal_entities),
        location_entities=list(event.location_entities),
        created_at=event.created_at,
    )
