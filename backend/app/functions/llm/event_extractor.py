"""Extract timeline events from session transcriptions using an LLM."""

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.domain.models import TimelineEvent, TimelineEventType
from app.functions.embedding.entity_extractor import (
    _dedupe_preserving_order,
    _extract_entities_with_local_llm,
)
from app.functions.llm.ollama_auth import ollama_headers

EVENT_EXTRACTION_PROMPT = (
    'You are analyzing a Dungeons & Dragons session transcript. '
    'Identify the most significant events in the text below. '
    'An event is something meaningful that happens: a combat encounter, a discovery, '
    'an important dialogue with an NPC, a travel milestone, a quest started or completed, '
    'a rest period, or any other notable occurrence.\n\n'
    'Return a JSON array of objects. Each object must have these fields:\n'
    '- "title": a short, concise title (5-10 words)\n'
    '- "description": a 1-2 sentence description of what happened\n'
    '- "event_type": one of "combat", "discovery", "dialogue", "travel", "rest", "quest", "other"\n\n'
    'Rules:\n'
    '- Titles must be specific, not generic\n'
    '- Limit to the most important 3-5 events in the text\n'
    '- Do not include meta-discussion or out-of-character chatter\n'
    '- Return ONLY valid JSON, no other text\n'
)


def _safe_json_from_llm_response(content: str) -> list[dict[str, Any]]:
    """Safely parse JSON from an LLM response string.

    Args:
        content: The raw LLM response string.

    Returns:
        A list of dicts parsed from the JSON, or empty list on failure.
    """
    content = content.strip()
    if not content:
        return []

    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            events = parsed.get('events') or parsed.get('results') or []
            return events if isinstance(events, list) else []
    except json.JSONDecodeError:
        pass

    start = content.find('[')
    end = content.rfind(']')
    if start < 0 or end <= start:
        return []

    try:
        parsed = json.loads(content[start : end + 1])
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _sanitize_event_text(value: Any) -> str:
    """Sanitize and normalize event text.

    Args:
        value: Raw text value.

    Returns:
        Cleaned, single-line string or empty string if not a string.
    """
    if not isinstance(value, str):
        return ''
    return ' '.join(value.strip().split())


def _parse_event_type(raw: Any) -> TimelineEventType:
    """Parse a raw event type string into a TimelineEventType enum.

    Args:
        raw: Raw event type value.

    Returns:
        The matching TimelineEventType, or TimelineEventType.other if unknown.
    """
    if not isinstance(raw, str):
        return TimelineEventType.other
    normalized = raw.strip().lower()
    for member in TimelineEventType:
        if member.value == normalized:
            return member
    return TimelineEventType.other


def _split_metadata_entities(value: Any) -> list[str]:
    """Split comma-separated Chroma metadata into clean entity strings."""
    if isinstance(value, list):
        raw_entities = value
    elif isinstance(value, str):
        raw_entities = value.split(',')
    else:
        raw_entities = []

    return _dedupe_preserving_order(
        entity.strip() for entity in raw_entities if isinstance(entity, str) and entity.strip()
    )


def _one_line_description(text: str, max_length: int = 180) -> str:
    """Build a compact one-line description from transcript text."""
    cleaned = ' '.join(text.strip().split())
    if not cleaned:
        return 'A session moment was recorded with extracted time and location clues.'

    sentence_match = re.search(r'(.+?[.!?])(?:\s|$)', cleaned)
    description = sentence_match.group(1) if sentence_match else cleaned
    if len(description) <= max_length:
        return description
    return description[: max_length - 3].rstrip() + '...'


def _timeline_title(temporal_entities: list[str], location_entities: list[str]) -> str:
    """Create a readable timeline title from time and location entities."""
    time_part = temporal_entities[0] if temporal_entities else 'Session moment'
    if location_entities:
        return f'{time_part} at {location_entities[0]}'
    return time_part


def _event_type_from_text(text: str) -> TimelineEventType:
    """Infer a broad event type from transcript wording."""
    lowered = text.lower()
    if any(word in lowered for word in ('departed', 'traveled', 'travel', 'journey', 'reached', 'crossed', 'headed')):
        return TimelineEventType.travel
    if any(word in lowered for word in ('discovered', 'found', 'reported', 'scouts')):
        return TimelineEventType.discovery
    if any(word in lowered for word in ('messenger', 'letter', 'told', 'asked', 'said')):
        return TimelineEventType.dialogue
    if any(word in lowered for word in ('camp', 'rest', 'night')):
        return TimelineEventType.rest
    return TimelineEventType.other


def build_timeline_events_from_transcription_documents(
    docs: list[Any], session_id: str = 'default'
) -> list[TimelineEvent]:
    """Build timeline events directly from transcription metadata.

    Args:
        docs: Chroma transcription documents with metadata.
        session_id: Session identifier.

    Returns:
        Timeline events containing temporal and location entities.
    """
    events: list[TimelineEvent] = []
    for index, doc in enumerate(docs):
        metadata = getattr(doc, 'metadata', {}) or {}
        text = getattr(doc, 'page_content', '') or ''
        temporal_entities = _split_metadata_entities(metadata.get('temporal_entities'))
        location_entities = _split_metadata_entities(metadata.get('location_entities'))

        if not temporal_entities and not location_entities:
            continue

        timestamp = metadata.get('start_time')
        try:
            timestamp_value = float(timestamp)
        except (TypeError, ValueError):
            timestamp_value = float(index)

        event = TimelineEvent(
            id='',
            session_id=session_id,
            title=_timeline_title(temporal_entities, location_entities),
            description=_one_line_description(text),
            event_type=_event_type_from_text(text),
            order=index,
            timestamp=timestamp_value,
            transcription_chunk_id=f'chunk_{index}',
            player_id=metadata.get('player_id'),
            speaker_name=metadata.get('player_id'),
            temporal_entities=temporal_entities,
            location_entities=location_entities,
        )
        events.append(event)

    return events


def extract_events_from_text(
    text: str,
    session_id: str = 'default',
    chunk_index: int = 0,
    chunk_start_time: float = 0.0,
    speaker_name: str | None = None,
    player_id: str | None = None,
) -> list[TimelineEvent]:
    """Extract timeline events from a single text chunk using an LLM.

    Args:
        text: The transcription text to analyze.
        session_id: Session identifier (default 'default').
        chunk_index: Index of this chunk for ordering.
        chunk_start_time: Start time of this chunk in seconds.
        speaker_name: Name of the speaker if known.
        player_id: Player ID associated with the text.

    Returns:
        List of extracted TimelineEvent objects.
    """
    entities = _extract_entities_with_local_llm(text)

    if not text.strip():
        return []

    try:
        from app.core.config import settings

        llm_model = settings.llm_model
        ollama_url = settings.ollama_url.rstrip('/')
    except Exception:
        llm_model = 'hf.co/bartowski/mistralai_Ministral-3-3B-Instruct-2512-GGUF:Q5_K_M'
        ollama_url = 'http://localhost:11434'

    payload = {
        'model': llm_model,
        'stream': False,
        'messages': [
            {'role': 'system', 'content': EVENT_EXTRACTION_PROMPT},
            {
                'role': 'user',
                'content': f'Analyze this transcript segment and extract events:\n\nTEXT:\n{text}',
            },
        ],
    }

    try:
        request = Request(
            f'{ollama_url}/api/chat',
            data=json.dumps(payload).encode('utf-8'),
            headers=ollama_headers(),
            method='POST',
        )
        with urlopen(request, timeout=120.0) as response:
            response_json = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return []

    message = response_json.get('message', {})
    content = message.get('content', '') if isinstance(message, dict) else ''
    raw_events = _safe_json_from_llm_response(content)

    events = []
    for i, raw in enumerate(raw_events):
        if not isinstance(raw, dict):
            continue
        title = _sanitize_event_text(raw.get('title'))
        description = _sanitize_event_text(raw.get('description'))
        if not title or not description:
            continue

        event = TimelineEvent(
            id='',
            session_id=session_id,
            title=title,
            description=description,
            event_type=_parse_event_type(raw.get('event_type')),
            order=chunk_index + i,
            timestamp=chunk_start_time,
            transcription_chunk_id=f'chunk_{chunk_index}',
            player_id=player_id,
            speaker_name=speaker_name,
            temporal_entities=_dedupe_preserving_order(entities.temporal_entities),
            location_entities=_dedupe_preserving_order(entities.location_entities),
        )
        events.append(event)

    return events


def extract_events_from_transcriptions(
    texts: list[str],
    speakers: list[str] | None = None,
    session_id: str = 'default',
    chunk_start_times: list[float] | None = None,
) -> list[TimelineEvent]:
    """Extract timeline events from multiple transcription texts.

    Args:
        texts: List of transcription text chunks.
        speakers: Optional list of speaker names corresponding to texts.
        session_id: Session identifier (default 'default').
        chunk_start_times: Optional start timestamps for each chunk in seconds.

    Returns:
        List of extracted TimelineEvent objects.
    """
    all_events: list[TimelineEvent] = []
    for i, text in enumerate(texts):
        if not text.strip():
            continue
        speaker = speakers[i] if speakers and i < len(speakers) else None
        chunk_start_time = 0.0
        if chunk_start_times is not None and i < len(chunk_start_times):
            chunk_start_time = float(chunk_start_times[i])
        events = extract_events_from_text(
            text=text,
            session_id=session_id,
            chunk_index=i,
            chunk_start_time=chunk_start_time,
            speaker_name=speaker,
        )
        all_events.extend(events)
    return all_events
