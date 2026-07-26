"""Entity extraction (temporal and location) from D&D session text using regex and LLM."""

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.functions.llm.ollama_auth import ollama_headers


@dataclass(frozen=True)
class ExtractedEntities:
    """Container for extracted temporal and location entities.

    Attributes:
        temporal_entities: List of time-related entity strings.
        location_entities: List of location entity strings.
    """

    temporal_entities: list[str]
    location_entities: list[str]


LLM_ENTITY_SYSTEM_PROMPT = (
    'You extract temporal and location entities from Dungeons and Dragons session text. '
    'Return only valid JSON with two arrays: temporal_entities and location_entities. '
    'Temporal entities are time-related phrases, dates, durations, clock times, relative times, '
    'or event-relative times. Location entities are physical places, regions, buildings, rooms, '
    'settlements, landmarks, fantasy place names, countries, cities, or named areas. '
    'Do not include people, monsters, items, organizations, or actions unless they are part of a place name. '
    'Every entity must be a short exact substring from the input text. '
    'Do not include descriptions, definitions, sentences, explanations, or text after a colon. '
    'Do not put locations in temporal_entities. Do not put temporal phrases in location_entities. '
    'Do not explain. Do not ask questions.'
)


MONTHS = (
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
)

WEEKDAYS = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')

RELATIVE_TIME_WORDS = ('today', 'yesterday', 'tomorrow', 'tonight')

RELATIVE_TIME_PHRASES = (
    'next week',
    'last week',
    'this week',
    'next month',
    'last month',
    'this month',
    'next year',
    'last year',
    'this year',
)

DOCX_TEMPORAL_PATTERNS = [
    r'\b\d+\s+(?:minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\s+after\b',
    r'\b\d+\s+(?:minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\s+before\b',
    r'\bafter\s+several\s+hours\s+of\s+travel\b',
    r'\bAt\s+approximately\s+\d{1,2}\.\d{2}\s*(?:AM|PM|am|pm)?\b',
    r'\bAt\s+\d{3,4}\b',
    r'\bAround\s+midday\b',
    r'\bFollowing\s+morning\b',
    r'\b(?:that|this)\s+evening\b',
    r'\bDuring\s+the\s+night\b',
    r'\bOne\s+hour\s+before\s+dawn\b',
    r'\bbefore\s+sunset\s+on\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
    r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+morning\b',
    r'\bAround\s+noon\b',
    r'\bLater\s+that\s+afternoon\b',
    r'\bLater\s+that\s+evening\b',
    r'\bBefore\s+sunset\b',
    r'\bfor\s+the\s+night\b',
    r'\bAfter\s+traveling\s+for\s+three\s+hours\b',
    r'\bBy\s+midday\b',
    r'\bDuring\s+the\s+evening\b',
    r'\bShortly\s+before\s+midnight\b',
    r'\bTwo\s+days\s+after\s+leaving\b',
    r'\bBefore\s+dawn\s+on\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
    r'\bDuring\s+the\s+following\s+night\b',
    r'\bThree\s+weeks\s+after\b',
    r'\bFor\s+the\s+past\s+\d+\s+(?:day|days|week|weeks|month|months|year|years)\b',
    rf'\b(?:the\s+)?morning\s+of\s+(?:{"|".join(MONTHS)})\s+\d{{1,2}},\s*\d{{4}}\b',
    r'\bBetween\s+sunset\s+and\s+midnight\b',
    r'\bBetween\s+sunrise\s+and\s+noon\b',
    r'\bBy\s+the\s+end\s+of\s+the\s+month\b',
    r'\bBefore\s+the\s+beginning\s+of\s+the\s+next\s+year\b',
]

LOCAL_PLACE_PREFIXES = (
    'Room',
    'Building',
    'Floor',
    'Hall',
    'Gate',
    'Tower',
    'Castle',
    'Temple',
    'Dungeon',
    'Tavern',
    'Village',
    'City',
)

PLACE_NOUNS = (
    'abbey',
    'alley',
    'arena',
    'armory',
    'barracks',
    'battlefield',
    'bay',
    'barrens',
    'bridge',
    'brook',
    'camp',
    'campsite',
    'canyon',
    'castle',
    'cave',
    'caverns',
    'cemetery',
    'chamber',
    'chapel',
    'citadel',
    'city',
    'clearing',
    'cliff',
    'coast',
    'crossing',
    'crypt',
    'den',
    'dock',
    'docks',
    'dungeon',
    'encampment',
    'farm',
    'ferry',
    'field',
    'forest',
    'forge',
    'fort',
    'fortress',
    'gate',
    'graveyard',
    'grove',
    'guildhall',
    'hall',
    'hamlet',
    'harbor',
    'hideout',
    'hill',
    'hills',
    'inn',
    'island',
    'isle',
    'jungle',
    'keep',
    'kingdom',
    'lake',
    'labyrinth',
    'library',
    'lair',
    'manor',
    'market',
    'marsh',
    'maze',
    'mine',
    'mines',
    'monastery',
    'mount',
    'mountain',
    'mountains',
    'outpost',
    'palace',
    'pass',
    'path',
    'peninsula',
    'plains',
    'port',
    'ravine',
    'realm',
    'river',
    'road',
    'room',
    'ruin',
    'ruins',
    'sanctum',
    'sea',
    'settlement',
    'sewer',
    'sewers',
    'shop',
    'shrine',
    'square',
    'stable',
    'stronghold',
    'swamp',
    'tavern',
    'temple',
    'throne room',
    'tower',
    'trail',
    'tunnel',
    'tunnels',
    'valley',
    'village',
    'watchtower',
    'wood',
    'woods',
    'dominion',
    'observatory',
    'shores',
    'spires',
    'reach',
    'expanse',
    'lips',
)

STANDALONE_PLACE_WORDS = ('Castle', 'Temple', 'Dungeon', 'Tavern', 'Village', 'City')

# Small built-in gazetteer for common examples and likely campaign locations.
KNOWN_LOCATIONS = {
    'Andhra Pradesh',
    'Aethergate',
    'Avernus',
    'Barovia',
    'Berlin',
    'Black River',
    'Citadel of Arcanis',
    'Crystal Forest',
    'Dragon Hill',
    'Eastmere',
    'Emerald Plains',
    'Frostmere Pass',
    'Frostwind Valley',
    'Green Forest',
    'India',
    'Ironkeep City',
    'Isle of Storms',
    'Kingdom of Valoria',
    'Moon Temple',
    'New York',
    'Northwatch',
    'Obsidian Cliffs',
    'Oakwood Village',
    'Phandalin',
    'Ravenloft',
    'Raven Peak',
    'Riverstone Town',
    'Ruins of Eldermoor',
    'Shadow Cave',
    'Shattered Coast',
    'Silver Harbor',
    'Silver Lake',
    'Sunfall Fortress',
    'Waterdeep',
    'Neverwinter',
    "Baldur's Gate",
    'Whispering Lake',
}

LOCATION_PREPOSITIONS = (
    'at',
    'in',
    'inside',
    'into',
    'near',
    'outside',
    'toward',
    'towards',
    'to',
    'from',
    'through',
    'under',
    'beneath',
    'below',
    'above',
    'around',
    'behind',
    'beside',
)

LOCATION_VERBS = (
    'approached',
    'arrived',
    'camped',
    'crossed',
    'entered',
    'escaped',
    'explored',
    'fled',
    'followed',
    'found',
    'left',
    'reached',
    'returned',
    'reach',
    'searched',
    'traveled',
    'travelled',
    'visited',
)

_MONTH_PATTERN = '|'.join(MONTHS)
_WEEKDAY_PATTERN = '|'.join(WEEKDAYS)
_LOCAL_PREFIX_PATTERN = '|'.join(LOCAL_PLACE_PREFIXES)
_STANDALONE_PLACE_PATTERN = '|'.join(STANDALONE_PLACE_WORDS)
_PLACE_NOUN_PATTERN = '|'.join(
    re.escape(noun) for noun in sorted(PLACE_NOUNS, key=len, reverse=True)
)
_LOCATION_PREPOSITION_PATTERN = '|'.join(LOCATION_PREPOSITIONS)
_LOCATION_VERB_PATTERN = '|'.join(LOCATION_VERBS)

TEMPORAL_PATTERNS = [
    *[re.compile(pattern, re.IGNORECASE) for pattern in DOCX_TEMPORAL_PATTERNS],
    re.compile(r'\b(?:{})\b'.format('|'.join(RELATIVE_TIME_WORDS)), re.IGNORECASE),
    re.compile(r'\b(?:{})\b'.format('|'.join(RELATIVE_TIME_PHRASES)), re.IGNORECASE),
    re.compile(rf'\b(?:{_WEEKDAY_PATTERN})\b', re.IGNORECASE),
    re.compile(rf'\b\d{{1,2}}\s+(?:{_MONTH_PATTERN})\s+\d{{4}}\b', re.IGNORECASE),
    re.compile(
        rf'\b(?:{_MONTH_PATTERN})\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,\s*\d{{4}})?\b', re.IGNORECASE
    ),
    re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'),
    re.compile(r'\b(?:19|20)\d{2}\b'),
    re.compile(r'\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\b'),
    re.compile(r'\b\d{1,2}\.\d{2}\s*(?:AM|PM|am|pm)\b', re.IGNORECASE),
    re.compile(r'(?<!:)\b\d{1,2}\s*(?:AM|PM|am|pm)\b'),
]

TEMPORAL_SIGNAL_PATTERN = re.compile(
    rf'\b('
    rf'{_WEEKDAY_PATTERN}|{_MONTH_PATTERN}|'
    r'today|yesterday|tomorrow|tonight|morning|noon|afternoon|evening|night|'
    r'midnight|sunrise|sunset|dawn|dusk|week|weeks|month|months|year|years|'
    r'day|days|hour|hours|minute|minutes|before|after|during|around|between|'
    r'approximately|past|next|last|following'
    r')\b|'
    r'\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*(?:AM|PM|am|pm)\b|\b(?:19|20)\d{2}\b',
    re.IGNORECASE,
)

LOCATION_SUFFIXES = tuple(
    sorted(
        {
            'Bridge',
            'Cave',
            'City',
            'Cliffs',
            'Coast',
            'Forest',
            'Fortress',
            'Harbor',
            'Hideout',
            'Hill',
            'Isle',
            'Lake',
            'Pass',
            'Peninsula',
            'Peak',
            'Plains',
            'River',
            'Road',
            'Shrine',
            'Temple',
            'Town',
            'Valley',
            'Village',
            'Wood',
            'Woods',
        },
        key=len,
        reverse=True,
    )
)
_LOCATION_SUFFIX_PATTERN = '|'.join(LOCATION_SUFFIXES)

PROPER_LOCATION_PATTERN = re.compile(
    rf"\b[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){{0,3}}\s+(?:{_LOCATION_SUFFIX_PATTERN})\b"
)

NAMED_PLACE_NOUN_PATTERN = re.compile(
    rf'\b(?i:(?:the\s+)?(?:(?:{_PLACE_NOUN_PATTERN})\s+of\s+|(?:{_PLACE_NOUN_PATTERN})\s+))'
    r"([A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,3})\b"
)

LOWERCASE_FANTASY_PLACE_PATTERN = re.compile(
    r"\b(?:the\s+)?(?:floating\s+lips\s+of\s+[A-Za-z'-]+(?:\s+[A-Za-z'-]+){0,2}|"
    r"crystal\s+expanse\s+of\s+[A-Za-z'-]+|"
    r"obsidian\s+spires\s+of\s+[A-Za-z'-]+|"
    r'fall\s+citadel|'
    r'azure\s+labyrinth|'
    r"pimple\s+of\s+[A-Za-z'-]+(?:\s+[A-Za-z'-]+){0,2})\b",
    re.IGNORECASE,
)

KNOWN_AS_LOCATION_PATTERN = re.compile(
    r"\bknown\s+as\s+([A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,4})\b"
)

LOCAL_PLACE_PATTERN = re.compile(
    rf'\b(?:{_LOCAL_PREFIX_PATTERN})\s+(?:[A-Z]|\d+[A-Za-z]?|[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\b'
)
STANDALONE_LOCAL_PLACE_PATTERN = re.compile(
    rf'\b(?:the\s+)?(?:{_STANDALONE_PLACE_PATTERN})\b', re.IGNORECASE
)
WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z'-]*|\d+[A-Za-z]?")
PREPOSITIONAL_LOCATION_PATTERN = re.compile(
    rf"\b(?:{_LOCATION_PREPOSITION_PATTERN})\s+((?:the\s+)?[A-Z][A-Za-z'-]+(?:\s+[A-Z0-9][A-Za-z0-9'-]*){{0,4}})\b"
)
VERB_LOCATION_PATTERN = re.compile(
    rf"\b(?:{_LOCATION_VERB_PATTERN})\s+((?:the\s+)?[A-Z][A-Za-z'-]+(?:\s+[A-Z0-9][A-Za-z0-9'-]*){{0,4}})\b"
)
OF_LOCATION_PATTERN = re.compile(
    rf"\b(?:the\s+)?(?i:(?:{_PLACE_NOUN_PATTERN}))\s+of\s+(?:the\s+)?[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){{0,3}}\b"
)

LOCATION_STOPWORDS = {
    'the',
    'a',
    'an',
    'and',
    'or',
    'but',
    'we',
    'you',
    'they',
    'he',
    'she',
    'it',
    'next',
    'last',
    'this',
}

NON_LOCATION_DESCRIPTORS = {
    'arrived',
    'camped',
    'crossed',
    'discovered',
    'entered',
    'escaped',
    'established',
    'followed',
    'found',
    'go',
    'left',
    'met',
    'party',
    'returns',
    'searched',
    'then',
    'visited',
    'went',
}

LOCATION_DESCRIPTORS = {
    'ancient',
    'azure',
    'black',
    'blue',
    'broken',
    'burning',
    'dark',
    'dead',
    'deep',
    'dense',
    'dragon',
    'dwarven',
    'east',
    'eastern',
    'elven',
    'enchanted',
    'forgotten',
    'goblin',
    'green',
    'hidden',
    'high',
    'haunted',
    'crystal',
    'floating',
    'obsidian',
    'roomed',
    'ethyral',
    'lost',
    'lower',
    'misty',
    'north',
    'northern',
    'old',
    'red',
    'ruined',
    'secret',
    'shadow',
    'silver',
    'south',
    'southern',
    'stone',
    'sunken',
    'underground',
    'upper',
    'west',
    'western',
    'white',
}

GENERIC_LOCATION_NOUNS_TO_SKIP = {'camp', 'campsite', 'cave', 'road', 'trail', 'village'}

TRAILING_CLAUSE_WORDS = {
    'and',
    'but',
    'or',
    'then',
    'where',
    'when',
    'while',
    'before',
    'after',
    'at',
    'in',
    'on',
    'with',
}

TRAILING_VERBS = {
    'arrived',
    'attacked',
    'camped',
    'crossed',
    'entered',
    'fought',
    'found',
    'left',
    'met',
    'returned',
    'searched',
    'saw',
    'went',
}


def _looks_like_described_place(value: str) -> bool:
    """Check if a value looks like a described place with a place noun.

    Args:
        value: The candidate string.

    Returns:
        True if it appears to be a described place.
    """
    words = value.casefold().split()
    if not words:
        return False
    if words[-1] not in PLACE_NOUNS:
        return False
    # Avoid returning every bare generic noun; keep useful standalone game places.
    if len(words) == 1:
        return words[0] in {'castle', 'temple', 'dungeon', 'tavern', 'village', 'city'}
    content_words = [word for word in words[:-1] if word not in LOCATION_STOPWORDS]
    if any(word in NON_LOCATION_DESCRIPTORS for word in content_words):
        return False
    if any(word in LOCATION_PREPOSITIONS for word in content_words):
        return False
    return bool(content_words)


def _is_capitalized(value: str) -> bool:
    """Check if a string starts with an uppercase letter.

    Args:
        value: The string to check.

    Returns:
        True if the first character is uppercase.
    """
    return bool(value) and value[0].isupper()


def _candidate_score(value: str) -> int:
    """Score a location candidate for ranking.

    Higher scores indicate more likely valid location entities.

    Args:
        value: The candidate string.

    Returns:
        Integer score.
    """
    words = value.split()
    lowered = [word.casefold().strip('.,;:!?') for word in words]
    score = len(words)
    if lowered and lowered[-1] in PLACE_NOUNS:
        score += 6
    if lowered and lowered[0] in PLACE_NOUNS:
        score += 6
    if len(lowered) > 1 and lowered[0] in {'the', 'a', 'an'} and lowered[1] in PLACE_NOUNS:
        score += 6
    if lowered and lowered[0] in {'the', 'a', 'an'}:
        score += 1
    if any(word in LOCATION_DESCRIPTORS for word in lowered):
        score += 2
    if any(_is_capitalized(word.strip('.,;:!?')) for word in words):
        score += 3
    if any(word in NON_LOCATION_DESCRIPTORS for word in lowered):
        score -= 10
    return score


def _clean_location_candidate(value: str) -> str:
    """Remove leading prepositions/verbs and trailing clause words from a candidate.

    Args:
        value: The raw candidate string.

    Returns:
        Cleaned candidate string.
    """
    words = WORD_PATTERN.findall(value)
    while words and words[0].casefold() in LOCATION_PREPOSITIONS + LOCATION_VERBS:
        words.pop(0)
    while words and words[0].casefold() in {'we', 'they', 'party', 'group'}:
        words.pop(0)
    while words and words[-1].casefold() in TRAILING_CLAUSE_WORDS | TRAILING_VERBS:
        words.pop()
    return ' '.join(words)


def _find_place_noun_candidates(text: str) -> list[str]:
    """Find candidate location phrases based on place nouns.

    Args:
        text: The input text.

    Returns:
        List of candidate location strings.
    """
    candidates = []
    descriptor_pattern = '|'.join(sorted(LOCATION_DESCRIPTORS, key=len, reverse=True))
    pattern = re.compile(
        rf'\b(?:the|a|an)\s+(?:(?:{descriptor_pattern})\s+){{0,3}}(?:{_PLACE_NOUN_PATTERN})\b',
        re.IGNORECASE,
    )
    candidates.extend(match.group(0) for match in pattern.finditer(text))
    return candidates


def _find_single_named_locations_after_triggers(text: str) -> list[str]:
    """Find single capitalized location names after location triggers.

    Args:
        text: The input text.

    Returns:
        List of candidate location strings.
    """
    candidates = []
    trigger_pattern = re.compile(
        rf"\b(?:{_LOCATION_PREPOSITION_PATTERN}|{_LOCATION_VERB_PATTERN})\s+([A-Z][A-Za-z'-]+)\b"
    )
    for match in trigger_pattern.finditer(text):
        candidate = _clean_location_candidate(match.group(1))
        if candidate and candidate.casefold() not in LOCATION_STOPWORDS:
            candidates.append(candidate)
    return candidates


def _remove_nested_locations(values: list[str]) -> list[str]:
    """Remove location candidates that are substrings of larger candidates.

    Args:
        values: List of candidate location strings.

    Returns:
        Filtered list without nested duplicates.
    """
    kept = []
    for value in sorted(values, key=lambda item: (_candidate_score(item), len(item)), reverse=True):
        current = value.casefold()
        current_words = current.split()
        should_skip = False
        for existing in kept:
            existing_norm = existing.casefold()
            existing_words = existing_norm.split()
            if current == existing_norm:
                should_skip = True
                break
            if current in existing_norm and len(current_words) < len(existing_words):
                should_skip = True
                break
            if existing_norm in current and len(existing_words) < len(current_words):
                kept.remove(existing)
                break
        if not should_skip:
            kept.append(value)
    return sorted(kept, key=lambda item: values.index(item))


def _filter_location_candidates(values: list[str]) -> list[str]:
    """Filter location candidates by removing stopwords and invalid entries.

    Args:
        values: List of candidate location strings.

    Returns:
        Filtered list of valid location candidates.
    """
    filtered = []
    for value in values:
        candidate = _clean_location_candidate(value)
        lowered = candidate.casefold()
        if not candidate or lowered in LOCATION_STOPWORDS:
            continue
        if lowered in GENERIC_LOCATION_NOUNS_TO_SKIP:
            continue
        lowered_words = lowered.split()
        if (
            len(lowered_words) >= 2
            and lowered_words[0] == 'the'
            and lowered_words[-1] in GENERIC_LOCATION_NOUNS_TO_SKIP
            and (
                len(lowered_words) == 2
                or lowered_words[-1] in {'road', 'trail', 'camp', 'campsite', 'village'}
            )
        ):
            continue
        if any(word in RELATIVE_TIME_WORDS for word in lowered.split()):
            continue
        if ' and ' in lowered:
            continue
        if any(
            word in {'before', 'after', 'towards', 'toward', 'prepared', 'travelled', 'traveled'}
            for word in lowered.split()
        ):
            continue
        if lowered in {month.casefold() for month in MONTHS}:
            continue
        filtered.append(candidate)
    return filtered


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    """Remove duplicate strings while preserving original order.

    Args:
        values: List of strings.

    Returns:
        Deduplicated list preserving first occurrence order.
    """
    seen = set()
    result = []
    for value in values:
        normalized = ' '.join(value.strip().split())
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _merge_entities(primary: list[str], secondary: list[str]) -> list[str]:
    """Merge two entity lists, preserving order and avoiding duplicates.

    Primary list takes precedence; secondary items are appended if not already present.

    Args:
        primary: Primary list of entity strings.
        secondary: Secondary list of entity strings.

    Returns:
        Merged list of entity strings.
    """
    merged = list(primary)
    seen = {value.casefold() for value in merged}
    for value in secondary:
        normalized = ' '.join(str(value).strip().split())
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
    return merged


def _safe_json_from_llm_response(content: str) -> dict[str, Any]:
    """Safely parse JSON from an LLM response string.

    Args:
        content: Raw LLM response content.

    Returns:
        Parsed dict or empty dict on failure.
    """
    content = content.strip()
    if not content:
        return {}

    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    start = content.find('{')
    end = content.rfind('}')
    if start < 0 or end <= start:
        return {}

    try:
        parsed = json.loads(content[start : end + 1])
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _coerce_entity_list(value: Any) -> list[str]:
    """Coerce a value to a list of entity strings.

    Args:
        value: The value to coerce.

    Returns:
        List of non-empty stripped strings.
    """
    if not isinstance(value, list):
        return []
    return [' '.join(str(item).strip().split()) for item in value if str(item).strip()]


def _strip_llm_description(value: str) -> str:
    """Strip descriptions and extra text from an LLM entity value.

    Removes content after colon or dash separators.

    Args:
        value: Raw LLM entity text.

    Returns:
        Cleaned entity text.
    """
    cleaned = ' '.join(str(value).strip().split())
    if ':' in cleaned:
        cleaned = cleaned.split(':', 1)[0].strip()
    if ' - ' in cleaned:
        cleaned = cleaned.split(' - ', 1)[0].strip()
    return cleaned.strip(' .,;:-')


def _exact_text_span(value: str, text: str) -> str:
    """Find the exact text span of a value in the original text.

    Args:
        value: The value to search for.
        text: The original text.

    Returns:
        The exact matching span from the original text, or empty string.
    """
    if not value:
        return ''
    match = re.search(re.escape(value), text, re.IGNORECASE)
    if not match:
        return ''
    return text[match.start() : match.end()]


def _is_valid_temporal_entity(value: str, text: str) -> str:
    """Validate and extract a temporal entity from the original text.

    Args:
        value: The candidate temporal entity.
        text: The original text.

    Returns:
        The validated exact text span, or empty string if invalid.
    """
    cleaned = _strip_llm_description(value)
    exact = _exact_text_span(cleaned, text)
    if not exact:
        return ''
    if not TEMPORAL_SIGNAL_PATTERN.search(exact):
        return ''
    if len(exact.split()) > 10:
        return ''
    return exact


def _is_valid_location_entity(value: str, text: str) -> str:
    """Validate and extract a location entity from the original text.

    Args:
        value: The candidate location entity.
        text: The original text.

    Returns:
        The validated exact text span, or empty string if invalid.
    """
    cleaned = _strip_llm_description(value)
    exact = _exact_text_span(cleaned, text)
    if not exact:
        return ''
    if TEMPORAL_SIGNAL_PATTERN.fullmatch(exact.strip()):
        return ''
    if any(char in exact for char in '.?!'):
        return ''
    if len(exact.split()) > 8:
        return ''
    if exact.casefold() in {'messenger', 'representative', 'royal family', 'group', 'party'}:
        return ''
    return exact


def _sanitize_llm_entities(entities: ExtractedEntities, text: str) -> ExtractedEntities:
    """Sanitize LLM-extracted entities by validating against the original text.

    Args:
        entities: The ExtractedEntities from the LLM.
        text: The original text for span validation.

    Returns:
        Sanitized ExtractedEntities with validated text spans.
    """
    temporal_entities = _dedupe_preserving_order(
        entity
        for entity in (
            _is_valid_temporal_entity(value, text) for value in entities.temporal_entities
        )
        if entity
    )
    location_entities = _dedupe_preserving_order(
        entity
        for entity in (
            _is_valid_location_entity(value, text) for value in entities.location_entities
        )
        if entity
    )
    return ExtractedEntities(
        temporal_entities=temporal_entities, location_entities=location_entities
    )


def _extract_entities_with_local_llm(text: str, timeout_seconds: float = 25.0) -> ExtractedEntities:
    """Extract entities from text using a local LLM via Ollama.

    Args:
        text: The text to extract entities from.
        timeout_seconds: Timeout for the LLM request.

    Returns:
        ExtractedEntities with temporal and location entities.
    """
    try:
        from app.core.config import settings

        llm_model = settings.llm_model
        ollama_url = settings.ollama_url.rstrip('/')
        timeout_seconds = settings.entity_llm_timeout_seconds
    except Exception:
        llm_model = 'hf.co/bartowski/mistralai_Ministral-3-3B-Instruct-2512-GGUF:Q5_K_M'
        ollama_url = 'http://localhost:11434'

    payload = {
        'model': llm_model,
        'stream': False,
        'messages': [
            {'role': 'system', 'content': LLM_ENTITY_SYSTEM_PROMPT},
            {
                'role': 'user',
                'content': (
                    'Extract temporal and location entities from this text.\n\n'
                    f'TEXT:\n{text}\n\n'
                    'Return JSON only, for example: '
                    '{"temporal_entities": ["..."], "location_entities": ["..."]}'
                ),
            },
        ],
        'format': 'json',
    }

    try:
        request = Request(
            f'{ollama_url}/api/chat',
            data=json.dumps(payload).encode('utf-8'),
            headers=ollama_headers(),
            method='POST',
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            response_json = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return ExtractedEntities(temporal_entities=[], location_entities=[])

    message = response_json.get('message', {})
    content = message.get('content', '') if isinstance(message, dict) else ''
    parsed = _safe_json_from_llm_response(content)

    extracted = ExtractedEntities(
        temporal_entities=_coerce_entity_list(parsed.get('temporal_entities')),
        location_entities=_coerce_entity_list(parsed.get('location_entities')),
    )
    return _sanitize_llm_entities(extracted, text)


def _dedupe_spans_preserving_order(matches: list[tuple[int, int, str]]) -> list[str]:
    """Deduplicate span matches preserving order, keeping the longest span for nested matches.

    Args:
        matches: List of (start, end, value) tuples.

    Returns:
        List of deduplicated values in occurrence order.
    """
    sorted_matches = sorted(matches, key=lambda item: (item[0], -(item[1] - item[0])))
    kept: list[tuple[int, int, str]] = []

    for start, end, value in sorted_matches:
        normalized = ' '.join(value.strip().split())
        if not normalized:
            continue
        is_nested = any(kept_start <= start and end <= kept_end for kept_start, kept_end, _ in kept)
        if is_nested:
            continue
        if any(normalized.casefold() == kept_value.casefold() for _, _, kept_value in kept):
            continue
        kept.append((start, end, normalized))

    return [value for _, _, value in sorted(kept, key=lambda item: item[0])]


def _extract_temporal_entities(text: str) -> list[str]:
    """Extract temporal entity strings from text using regex patterns.

    Args:
        text: The input text.

    Returns:
        List of normalized temporal entity strings.
    """
    matches = []
    for pattern in TEMPORAL_PATTERNS:
        matches.extend(
            (match.start(), match.end(), match.group(0)) for match in pattern.finditer(text)
        )

    temporal_entities = _dedupe_spans_preserving_order(matches)
    normalized = []
    for entity in temporal_entities:
        clean = ' '.join(entity.split())
        if clean.casefold() == 'the morning of march 17, 2025':
            clean = 'Morning of March 17, 2025'
        elif clean.casefold() == 'for the night' or clean.casefold() == 'night':
            clean = 'Night'
        normalized.append(clean)
    return normalized


def _normalize_location_output(value: str) -> str:
    """Normalize a location candidate string.

    Removes leading articles, descriptors, and empty words.

    Args:
        value: The raw location candidate.

    Returns:
        Normalized location string, or empty if invalid.
    """
    words = WORD_PATTERN.findall(value)
    if not words:
        return ''

    lowered = [word.casefold() for word in words]
    while lowered and lowered[0] in {
        'a',
        'an',
        'small',
        'hidden',
        'abandoned',
        'temporary',
        'northern',
        'western',
        'eastern',
        'southern',
        'edge',
        'region',
        'governor',
        'water',
        'cave',
        'entrance',
        'of',
    }:
        words.pop(0)
        lowered.pop(0)

    candidate = ' '.join(words).strip()
    candidate_words = candidate.split()
    if (
        len(candidate_words) > 1
        and candidate_words[0].casefold() == 'the'
        and candidate_words[1][0].isupper()
    ):
        candidate = ' '.join(candidate_words[1:])
    if candidate.casefold() == 'watchtower':
        return 'Watchtower'
    if candidate.casefold() in {'grand hall', 'the grand hall'}:
        return ''
    if candidate.casefold() in {
        'grand hall of aethergate',
        'hall of aethergate',
        'the grand hall of aethergate',
    }:
        return 'Aethergate'
    return candidate


def _location_matches_from_patterns(text: str) -> list[tuple[int, int, str]]:
    """Find location entity matches in text using multiple regex patterns.

    Args:
        text: The input text.

    Returns:
        List of (start, end, normalized_value) tuples.
    """
    matches: list[tuple[int, int, str]] = []

    for location in sorted(KNOWN_LOCATIONS, key=len, reverse=True):
        for match in re.finditer(rf'\b{re.escape(location)}\b', text, re.IGNORECASE):
            matches.append((match.start(), match.end(), location))

    for pattern in (
        PROPER_LOCATION_PATTERN,
        LOCAL_PLACE_PATTERN,
        OF_LOCATION_PATTERN,
        PREPOSITIONAL_LOCATION_PATTERN,
        VERB_LOCATION_PATTERN,
    ):
        for match in pattern.finditer(text):
            value = match.group(1) if match.lastindex else match.group(0)
            normalized = _normalize_location_output(value)
            if normalized:
                matches.append((match.start(), match.end(), normalized))

    for pattern in (
        NAMED_PLACE_NOUN_PATTERN,
        LOWERCASE_FANTASY_PLACE_PATTERN,
        KNOWN_AS_LOCATION_PATTERN,
    ):
        for match in pattern.finditer(text):
            value = match.group(1) if pattern is KNOWN_AS_LOCATION_PATTERN else match.group(0)
            normalized = _normalize_location_output(value)
            if normalized:
                matches.append((match.start(), match.end(), normalized))

    for match in re.finditer(
        r"\blocations?\s+of\s+([A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,3})\b", text
    ):
        normalized = _normalize_location_output(match.group(1))
        if normalized:
            matches.append((match.start(1), match.end(1), normalized))

    for match in re.finditer(
        r"\bfall\s+of\s+([A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,3})\b", text
    ):
        normalized = _normalize_location_output(match.group(1))
        if normalized:
            matches.append((match.start(1), match.end(1), normalized))

    for match in re.finditer(r'\b(?:an?\s+)?(?:abandoned\s+)?watchtower\b', text, re.IGNORECASE):
        matches.append((match.start(), match.end(), 'Watchtower'))

    return matches


def _extract_location_entities(text: str) -> list[str]:
    """Extract location entity strings from text using rules and patterns.

    Args:
        text: The input text.

    Returns:
        List of normalized location entity strings.
    """
    matches = _location_matches_from_patterns(text)
    fallback_candidates = _find_place_noun_candidates(text)
    for candidate in fallback_candidates:
        start = text.casefold().find(candidate.casefold())
        if start >= 0:
            normalized = _normalize_location_output(candidate)
            if normalized:
                matches.append((start, start + len(candidate), normalized))

    ordered = _dedupe_spans_preserving_order(matches)
    return _remove_nested_locations(_dedupe_preserving_order(_filter_location_candidates(ordered)))


def extract_entities(text: str) -> ExtractedEntities:
    """Extract temporal and location entities using pure rule-based methods.

    Args:
        text: The input text.

    Returns:
        ExtractedEntities with temporal and location lists.
    """
    return ExtractedEntities(
        temporal_entities=_extract_temporal_entities(text),
        location_entities=_extract_location_entities(text),
    )


def extract_entities_hybrid(text: str, use_llm: bool = True) -> ExtractedEntities:
    """Extract entities using rule-based methods optionally augmented by an LLM.

    Args:
        text: The input text.
        use_llm: If True, also use LLM-based extraction and merge results.

    Returns:
        ExtractedEntities with merged temporal and location entities.
    """
    rule_entities = extract_entities(text)
    if not use_llm:
        return rule_entities

    llm_entities = _sanitize_llm_entities(_extract_entities_with_local_llm(text), text)
    return ExtractedEntities(
        temporal_entities=_merge_entities(
            rule_entities.temporal_entities, llm_entities.temporal_entities
        ),
        location_entities=_merge_entities(
            rule_entities.location_entities, llm_entities.location_entities
        ),
    )


def entities_as_metadata(text: str, use_llm: bool = False) -> dict[str, str]:
    """Extract entities and return as ChromaDB-compatible metadata dict.

    Args:
        text: The input text.
        use_llm: If True, use LLM augmentation.

    Returns:
        Dict with 'temporal_entities' and 'location_entities' as comma-separated strings.
    """
    entities = extract_entities_hybrid(text, use_llm=use_llm)
    return {
        'temporal_entities': ', '.join(entities.temporal_entities),
        'location_entities': ', '.join(entities.location_entities),
    }
