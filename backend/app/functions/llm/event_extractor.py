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

_CLOCK_TIME_PATTERNS = [
    (
        re.compile(r'\b\d{1,2}\.\d{2}\s*(?:AM|PM)\b', re.IGNORECASE),
        lambda m: m.group(0).strip().replace('.', ':'),
    ),
    (re.compile(r'\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\b'), lambda m: m.group(0).strip()),
    (re.compile(r'\b\d{1,2}\s*(?:AM|PM|am|pm)\b'), lambda m: m.group(0).strip()),
]

_TIME_OF_DAY_WORDS = {
    'morning': 'Morning',
    'dawn': 'Morning',
    'sunrise': 'Morning',
    'early morning': 'Early Morning',
    'afternoon': 'Afternoon',
    'midday': 'Midday',
    'noon': 'Noon',
    'evening': 'Evening',
    'sunset': 'Evening',
    'dusk': 'Evening',
    'night': 'Night',
    'tonight': 'Tonight',
    'midnight': 'Midnight',
    'late night': 'Late Night',
}

_DURATION_PATTERNS = [
    (re.compile(r'\bfortnight\b', re.IGNORECASE), 'Fortnight'),
    (re.compile(r'\bnext\s+week\b', re.IGNORECASE), 'Next Week'),
    (re.compile(r'\blast\s+week\b', re.IGNORECASE), 'Last Week'),
    (re.compile(r'\bthis\s+week\b', re.IGNORECASE), 'This Week'),
    (re.compile(r'\bnext\s+month\b', re.IGNORECASE), 'Next Month'),
    (re.compile(r'\blast\s+month\b', re.IGNORECASE), 'Last Month'),
    (re.compile(r'\b(\d+)\s+days?\b', re.IGNORECASE), None),
    (re.compile(r'\b(\d+)\s+hours?\b', re.IGNORECASE), None),
    (re.compile(r'\b(\d+)\s+weeks?\b', re.IGNORECASE), None),
    (re.compile(r'\b(\d+)\s+months?\b', re.IGNORECASE), None),
]

_CONTEXT_TO_TIME_OF_DAY = {
    'dawn': 'Morning',
    'sunrise': 'Morning',
    'early': 'Morning',
    'breakfast': 'Morning',
    'rise': 'Morning',
    'wakeup': 'Morning',
    'wake up': 'Morning',
    'noon': 'Noon',
    'midday': 'Midday',
    'lunch': 'Afternoon',
    'afternoon': 'Afternoon',
    'sunset': 'Evening',
    'dusk': 'Evening',
    'dinner': 'Evening',
    'evening': 'Evening',
    'night': 'Night',
    'camp': 'Night',
    'rest': 'Night',
    'sleep': 'Night',
    'campfire': 'Night',
    'midnight': 'Midnight',
    'late': 'Late Night',
    'witching hour': 'Midnight',
    'before dawn': 'Night',
    'after dark': 'Night',
}

EVENT_EXTRACTION_PROMPT = (
    'You are analyzing a Dungeons & Dragons session transcript. '
    'Identify the most significant events in the text below. '
    'An event is something meaningful that happens: a combat encounter, a discovery, '
    'an important dialogue with an NPC, a travel milestone, a quest started or completed, '
    'a rest period, or any other notable occurrence.\n\n'
    'Return a JSON array of objects. Each object must have these fields:\n'
    '- "title": 2-5 words, action-oriented (e.g. "Combat Begins", "Treasure Found", '
    '"Explorers Depart"). Do NOT include time or location in the title.\n'
    '- "description": 1-2 sentences summarizing what happened. Include location and context '
    'here, not in the title.\n'
    '- "event_type": one of "combat", "discovery", "dialogue", "travel", "rest", "quest", "other"\n'
    '- "characters": optional array of character or NPC names involved\n\n'
    'Rules:\n'
    '- Titles describe what happened, not where (bad: "Session moment at Kharzul", '
    'good: "Explorers Depart")\n'
    '- Descriptions must not repeat the title verbatim\n'
    '- Limit to the most important 3-5 events in the text\n'
    '- Do not include meta-discussion or out-of-character chatter\n'
    '- Return ONLY valid JSON, no other text\n'
)

_TITLE_PATTERNS = [
    (r'(?:discovered|uncovered|located)\s+(?:a\s+|an\s+|the\s+)?(\w+)', '{} Discovered'),
    (r'(?:crossed|entered)\s+(?:a\s+|an\s+|the\s+)?(\w+)', 'Crossing the {}'),
    (r'(?:departed|left)\s+from\s+(\w+)', 'Departure from {}'),
    (r'(?:arrived\s+at|reached)\s+(?:\w+\s+)?(\w+)', 'Arrival at {}'),
    (
        r'(?:travelled|traveled|journeyed)\s+(?:to|towards|across|through|into)\s+(\w+)',
        'Travel to {}',
    ),
    (r'(?:encountered|met|fought)\s+(?:a\s+|an\s+|the\s+)?(\w+)', '{} Encountered'),
    (r'(?:ancient\s+)?(?:records|documents|notes)\s+found', None),
]

_FALLBACK_TITLES: dict[str, str] = {
    'records found': 'Ancient Records Found',
    'documents found': 'Ancient Records Found',
    'notes found': 'Notes Found',
}

_FALLBACK_ACTION_TITLES: dict[TimelineEventType, str] = {
    TimelineEventType.travel: 'Explorers Depart',
    TimelineEventType.discovery: 'Discovery Made',
    TimelineEventType.dialogue: 'NPC Encounter',
    TimelineEventType.rest: 'Camp Established',
    TimelineEventType.combat: 'Combat Begins',
    TimelineEventType.quest: 'Quest Update',
    TimelineEventType.other: 'Notable Event',
}


def _safe_json_from_llm_response(content: str) -> list[dict[str, Any]]:
    """Safely parse JSON from an LLM response string."""
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
    """Sanitize and normalize event text."""
    if not isinstance(value, str):
        return ''
    return ' '.join(value.strip().split())


def _parse_event_type(raw: Any) -> TimelineEventType:
    """Parse a raw event type string into a TimelineEventType enum."""
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


def _build_event_description(
    text: str, location_entities: list[str], max_length: int = 200
) -> str:
    """Build a concise event description with location context when missing."""
    cleaned = ' '.join(text.strip().split())
    if not cleaned:
        locations = ', '.join(location_entities[:2])
        if locations:
            return f'A notable event occurred at {locations}.'
        return 'A notable session event was recorded.'

    sentence_match = re.search(r'(.+?[.!?])(?:\s|$)', cleaned)
    description = sentence_match.group(1) if sentence_match else cleaned

    for location in location_entities[:2]:
        if location.lower() not in description.lower():
            base = description.rstrip('.!?')
            description = f'{base} at {location}.'
            break

    if len(description) <= max_length:
        return description
    return description[: max_length - 3].rstrip() + '...'


def _parse_characters(raw: Any, speaker_name: str | None = None) -> list[str]:
    """Parse character names from LLM output and include the speaker when known."""
    characters: list[str] = []
    if isinstance(raw, list):
        characters = [_sanitize_event_text(item) for item in raw]
    elif isinstance(raw, str) and raw.strip():
        characters = [_sanitize_event_text(item) for item in raw.split(',')]

    characters = [character for character in characters if character]
    if speaker_name and speaker_name not in characters:
        characters.insert(0, speaker_name)
    return _dedupe_preserving_order(characters)


def _event_type_from_text(text: str) -> TimelineEventType:
    """Infer a broad event type from transcript wording."""
    lowered = text.lower()
    if any(
        word in lowered
        for word in ('departed', 'traveled', 'travel', 'journey', 'reached', 'crossed', 'headed')
    ):
        return TimelineEventType.travel
    if any(word in lowered for word in ('discovered', 'found', 'reported', 'scouts')):
        return TimelineEventType.discovery
    if any(word in lowered for word in ('messenger', 'letter', 'told', 'asked', 'said')):
        return TimelineEventType.dialogue
    if any(word in lowered for word in ('camp', 'rest', 'night')):
        return TimelineEventType.rest
    return TimelineEventType.other


def _format_duration_match(entity: str) -> str | None:
    """Format a duration entity like '3 hours' or '2 days' into a clean display string."""
    entity_lower = entity.strip().lower()
    match = re.match(r'(\d+)\s+(minutes?|hours?|days?|weeks?|months?|years?)\b', entity_lower)
    if match:
        num = match.group(1)
        unit = match.group(2)
        return f'{num} {unit}'
    return None


def _format_timestamp(seconds: float) -> str | None:
    """Format a float timestamp in seconds to HH:MM:SS string."""
    if seconds is None or seconds <= 0:
        return None
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f'{hours:02d}:{minutes:02d}:{secs:02d}'


def _infer_from_text(text: str) -> str | None:
    """Infer time-of-day from transcript text using keyword context clues."""
    if not text:
        return None
    lowered = text.lower()
    sorted_keywords = sorted(_CONTEXT_TO_TIME_OF_DAY.keys(), key=len, reverse=True)
    for keyword in sorted_keywords:
        if re.search(rf'\b{re.escape(keyword)}\b', lowered):
            return _CONTEXT_TO_TIME_OF_DAY[keyword]
    return None


def compute_display_time(
    temporal_entities: list[str], text: str = '', timestamp: float | None = None
) -> str | None:
    """Compute a single human-readable time label for a timeline event."""
    ts = _format_timestamp(timestamp) if isinstance(timestamp, (int, float)) else None
    if ts:
        return ts

    if temporal_entities:
        sorted_entities = sorted(temporal_entities, key=len, reverse=True)
        for entity in sorted_entities:
            for pattern, formatter in _CLOCK_TIME_PATTERNS:
                match = pattern.search(entity)
                if match:
                    return formatter(match)

        for entity in temporal_entities:
            entity_lower = entity.strip().lower()
            if entity_lower in _TIME_OF_DAY_WORDS:
                return _TIME_OF_DAY_WORDS[entity_lower]
            for tod_word, tod_label in _TIME_OF_DAY_WORDS.items():
                if re.search(rf'\b{re.escape(tod_word)}\b', entity_lower):
                    return tod_label

        for entity in temporal_entities:
            entity_lower = entity.strip().lower()
            for pattern, label in _DURATION_PATTERNS:
                if label is not None:
                    if pattern.search(entity_lower):
                        return label
                else:
                    match = pattern.search(entity_lower)
                    if match:
                        return _format_duration_match(entity)

    inferred = _infer_from_text(text)
    if inferred:
        return inferred

    return None


def _clean_title_word(word: str) -> str:
    """Clean and title-case a captured title word."""
    word = word.strip().rstrip(',.')
    for article in ('a ', 'an ', 'the '):
        if word.lower().startswith(article):
            word = word[len(article) :]
            break
    return word.strip().title()


def _generate_title(text: str) -> str | None:
    """Generate a clean, action-based event title from transcript text."""
    if not text:
        return None
    lowered = text.lower()
    for pattern, template in _TITLE_PATTERNS:
        match = re.search(pattern, lowered)
        if not match:
            continue
        if template is None:
            matched_text = match.group(0)
            for key, title in _FALLBACK_TITLES.items():
                if key in matched_text:
                    return title
            return 'Records Found'
        obj = _clean_title_word(match.group(1))
        if obj:
            return template.format(obj)
    return None


def _fallback_action_title(text: str, event_type: TimelineEventType) -> str:
    """Return an action-oriented fallback title when pattern matching fails."""
    generated = _generate_title(text)
    if generated:
        return generated
    return _FALLBACK_ACTION_TITLES.get(event_type, 'Notable Event')


def build_timeline_events_from_transcription_documents(
    docs: list[Any], session_id: str = 'default'
) -> list[TimelineEvent]:
    """Build timeline events directly from transcription metadata."""
    events: list[TimelineEvent] = []
    for index, doc in enumerate(docs):
        metadata = getattr(doc, 'metadata', {}) or {}
        text = getattr(doc, 'page_content', '') or ''
        temporal_entities = _split_metadata_entities(metadata.get('temporal_entities'))
        location_entities = _split_metadata_entities(metadata.get('location_entities'))

        if not temporal_entities and not location_entities:
            continue

        start_time = float(metadata.get('start_time', 0.0))
        event_type = _event_type_from_text(text)
        speaker = metadata.get('player_id')
        events.append(
            TimelineEvent(
                id='',
                session_id=session_id,
                title=_fallback_action_title(text, event_type),
                description=_build_event_description(text, location_entities),
                event_type=event_type,
                order=index,
                timestamp=start_time,
                transcription_chunk_id=f'chunk_{index}',
                player_id=speaker,
                speaker_name=speaker,
                temporal_entities=temporal_entities,
                location_entities=location_entities,
                characters=_parse_characters([], speaker),
                display_time=compute_display_time(temporal_entities, text, start_time),
            )
        )

    return events


def extract_events_from_text(
    text: str,
    session_id: str = 'default',
    chunk_index: int = 0,
    chunk_start_time: float = 0.0,
    speaker_name: str | None = None,
    player_id: str | None = None,
) -> list[TimelineEvent]:
    """Extract timeline events from a single text chunk using an LLM."""
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
    temporal_entities = _dedupe_preserving_order(entities.temporal_entities)
    location_entities = _dedupe_preserving_order(entities.location_entities)
    for i, raw in enumerate(raw_events):
        if not isinstance(raw, dict):
            continue
        title = _sanitize_event_text(raw.get('title'))
        description = _sanitize_event_text(raw.get('description'))
        if not title or not description:
            continue

        events.append(
            TimelineEvent(
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
                temporal_entities=temporal_entities,
                location_entities=location_entities,
                characters=_parse_characters(raw.get('characters'), speaker_name),
                display_time=compute_display_time(temporal_entities, text, chunk_start_time),
            )
        )

    return events


def extract_events_from_transcriptions(
    texts: list[str],
    speakers: list[str] | None = None,
    timestamps: list[float] | None = None,
    session_id: str = 'default',
    *,
    chunk_start_times: list[float] | None = None,
) -> list[TimelineEvent]:
    """Extract timeline events from multiple transcription texts."""
    times = timestamps if timestamps is not None else chunk_start_times
    all_events: list[TimelineEvent] = []
    for i, text in enumerate(texts):
        if not text.strip():
            continue
        speaker = speakers[i] if speakers and i < len(speakers) else None
        chunk_time = float(times[i]) if times is not None and i < len(times) else 0.0
        all_events.extend(
            extract_events_from_text(
                text=text,
                session_id=session_id,
                chunk_index=i,
                chunk_start_time=chunk_time,
                speaker_name=speaker,
            )
        )
    return all_events
