import re

from app.base_models.entity_extraction_models import ExtractedEntity


_NUMBER_WORDS = (
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    "thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    "twenty|thirty|forty|fifty|sixty"
)
_QUANTITY = rf"(?:an?|{_NUMBER_WORDS}|\d+)"
_APPROX_QUANTITY = rf"(?:{_QUANTITY}|a\s+couple\s+of|a\s+few|several)"
_TIME_UNIT = (
    r"(?:rounds?|turns?|seconds?|minutes?|hours?|days?|nights?|weeks?|"
    r"fortnights?|months?|seasons?|years?)"
)
_DAY_PART = r"(?:morning|afternoon|evening|night|day|week|month|season|year)"
_SOLAR_TIME = r"(?:sunrise|sunset|dawn|dusk|midnight|noon)"
_WEEKDAY = (
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
)
_MONTH = (
    r"(?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)"
)

# Forgotten Realms / Calendar of Harptos months. Keeping these explicit avoids
# interpreting arbitrary fantasy proper nouns (for example "the 12th of
# Waterdeep") as calendar dates.
_FANTASY_MONTH = (
    r"(?:hammer|alturiak|ches|tarsakh|mirtul|kythorn|flamerule|eleasis|"
    r"eleint|marpenoth|uktar|nightal)"
)

# Ordered from the most specific expressions to more general ones.  This makes
# overlap removal deterministic and keeps complete phrases such as
# "the next morning" instead of returning the nested "next morning".
TEMPORAL_PATTERNS: list[tuple[str, str]] = [
    (
        rf"\b(?:at|by|before|after|around|near|from|until)\s+(?:the\s+)?{_SOLAR_TIME}\b",
        "relative_time",
    ),
    (
        rf"\b(?:tomorrow|yesterday|today)\s+"
        rf"(?:morning|afternoon|evening|night)\b",
        "relative_date",
    ),
    (
        rf"\b(?:by|before|after|until)\s+(?:the\s+)?"
        rf"(?:next|following|previous)\s+{_DAY_PART}\b",
        "relative_time",
    ),
    (
        r"\b(?:before|after|during)\s+(?:a|the)\s+(?:short|long)\s+rest\b",
        "relative_time",
    ),
    (
        rf"\b(?:at\s+)?(?:the\s+)?end\s+of\s+(?:your|his|her|their|the)?\s*"
        rf"(?:next|current|this)\s+(?:round|turn)\b",
        "relative_time",
    ),
    (
        rf"\b(?:the\s+)?(?:next|last|this|previous|following)\s+{_DAY_PART}\b",
        "relative_date",
    ),
    (
        rf"\b(?:later|earlier)\s+(?:that|this|the\s+same)\s+{_DAY_PART}\b",
        "relative_date",
    ),
    (
        rf"\b(?:that|the\s+same)\s+(?:morning|afternoon|evening|night|day)\b",
        "relative_date",
    ),
    (
        r"\b(?:today|tomorrow|yesterday|tonight|now|right\s+now)\b",
        "relative_date",
    ),
    (
        r"\bhalf\s+(?:an?\s+)?(?:hour|day)\s+"
        r"(?:later|earlier|ago|from\s+now)\b",
        "relative_time",
    ),
    (
        rf"\b{_APPROX_QUANTITY}\s+{_TIME_UNIT}\s+"
        rf"(?:later|earlier|ago|from\s+now)\b",
        "relative_time",
    ),
    (
        rf"\b(?:in|within)\s+{_APPROX_QUANTITY}\s+{_TIME_UNIT}\b",
        "relative_time",
    ),
    (
        rf"\b(?:for|over)\s+(?:the\s+)?next\s+{_APPROX_QUANTITY}\s+"
        rf"{_TIME_UNIT}\b",
        "duration",
    ),
    (
        rf"\b(?:for|after|before|within|up\s+to)\s+{_APPROX_QUANTITY}\s+"
        rf"{_TIME_UNIT}\b",
        "duration",
    ),
    (
        rf"\b(?:for\s+)?half\s+(?:an?\s+)?(?:hour|day)\b",
        "duration",
    ),
    (
        rf"\b(?:every|each)\s+(?:other\s+)?(?:{_DAY_PART}|{_WEEKDAY}|{_SOLAR_TIME})\b",
        "recurrence",
    ),
    (
        rf"\b(?:once|twice)\s+(?:a|per)\s+(?:day|night|week|month|year)\b",
        "recurrence",
    ),
    (
        r"\b(?:at|around|about|by|before|after)\s+"
        r"(?:1[0-2]|0?[1-9])(?::[0-5]\d)?\s*(?:a\.?m\.?|p\.?m\.?)\b",
        "clock_time",
    ),
    (
        r"\b(?:1[0-2]|0?[1-9]):[0-5]\d(?:\s*(?:a\.?m\.?|p\.?m\.?))?\b",
        "clock_time",
    ),
    (
        r"\b(?:1[0-2]|0?[1-9])\s+o['’]?clock\b",
        "clock_time",
    ),
    (
        rf"\b(?:on\s+)?(?:next|last|this)?\s*{_WEEKDAY}\b",
        "weekday",
    ),
    (
        rf"\b(?:on\s+)?{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,\s*\d{{4}})?\b",
        "calendar_date",
    ),
    (
        rf"\b(?:on\s+)?(?:the\s+)?\d{{1,2}}(?:st|nd|rd|th)\s+of\s+"
        rf"{_FANTASY_MONTH}\b",
        "calendar_date",
    ),
    (
        r"\b\d{4}-\d{2}-\d{2}\b",
        "calendar_date",
    ),
]

SPATIAL_RELATIONS = [
    "north of",
    "south of",
    "east of",
    "west of",
    "north-east of",
    "northeast of",
    "north-west of",
    "northwest of",
    "south-east of",
    "southeast of",
    "south-west of",
    "southwest of",
    "near",
    "inside",
    "outside",
    "behind",
    "beside",
    "between",
    "under",
    "above",
    "below",
    "in front of",
    "next to",
    "across from",
]

GENERIC_LOCATIONS = [
    "castle",
    "village",
    "city",
    "town",
    "forest",
    "mountain",
    "river",
    "cave",
    "dungeon",
    "temple",
    "tavern",
    "harbour",
    "harbor",
    "road",
    "bridge",
    "tower",
    "kingdom",
    "island",
    "valley",
    "camp",
]


def _extract_regex_entities(
    text: str,
    patterns: list[tuple[str, str]],
) -> list[ExtractedEntity]:
    entities: list[ExtractedEntity] = []

    for pattern, entity_type in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            entities.append(
                ExtractedEntity(
                    text=match.group(0),
                    entity_type=entity_type,
                    start_character=match.start(),
                    end_character=match.end(),
                )
            )

    return entities


def _extract_terms(
    text: str,
    terms: list[str],
    entity_type: str,
) -> list[ExtractedEntity]:
    entities: list[ExtractedEntity] = []

    ordered_terms = sorted(terms, key=len, reverse=True)

    for term in ordered_terms:
        pattern = rf"\b{re.escape(term)}\b"

        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            entities.append(
                ExtractedEntity(
                    text=match.group(0),
                    entity_type=entity_type,
                    start_character=match.start(),
                    end_character=match.end(),
                )
            )

    return entities


def _extract_proper_place_candidates(
    text: str,
) -> list[ExtractedEntity]:
    """
    Simple Release 1 heuristic.

    It finds capitalized words that may represent fantasy place names,
    such as Neverwinter, Waterdeep or Blackwood Forest.

    This is only a prototype and may also find some non-location names.
    """

    pattern = (
        r"\b(?:Mount|Lake|River|Fort|Castle|Kingdom|Forest|City|Village)?"
        r"\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b"
    )

    ignored_words = {
        "The",
        "A",
        "An",
        "We",
        "They",
        "He",
        "She",
        "I",
        "After",
        "Before",
        "Later",
        "Then",
        "Next",
    }

    entities: list[ExtractedEntity] = []

    for match in re.finditer(pattern, text):
        value = match.group(0).strip()

        if value in ignored_words:
            continue

        entities.append(
            ExtractedEntity(
                text=value,
                entity_type="place_candidate",
                start_character=match.start(),
                end_character=match.end(),
            )
        )

    return entities


def _remove_duplicates(
    entities: list[ExtractedEntity],
) -> list[ExtractedEntity]:
    unique: list[ExtractedEntity] = []
    seen: set[tuple[str, str, int | None, int | None]] = set()

    for entity in entities:
        key = (
            entity.text.lower(),
            entity.entity_type,
            entity.start_character,
            entity.end_character,
        )

        if key not in seen:
            seen.add(key)
            unique.append(entity)

    return sorted(
        unique,
        key=lambda entity: (
            entity.start_character
            if entity.start_character is not None
            else 0
        ),
    )


def _remove_temporal_overlaps(
    entities: list[ExtractedEntity],
) -> list[ExtractedEntity]:
    """Keep the most informative temporal entity when regexes overlap.

    Temporal patterns intentionally overlap so broad forms can remain easy to
    extend.  Returning nested fragments (for example both "next morning" and
    "the next morning") is noisy for timeline consumers, so the longest match
    wins.  Pattern order is used as the stable tie-breaker.
    """

    candidates = _remove_duplicates(entities)
    ranked = sorted(
        enumerate(candidates),
        key=lambda pair: (
            -(
                (pair[1].end_character or 0)
                - (pair[1].start_character or 0)
            ),
            pair[0],
        ),
    )

    selected: list[ExtractedEntity] = []

    for _, candidate in ranked:
        if candidate.start_character is None or candidate.end_character is None:
            selected.append(candidate)
            continue

        overlaps = any(
            existing.start_character is not None
            and existing.end_character is not None
            and candidate.start_character < existing.end_character
            and existing.start_character < candidate.end_character
            for existing in selected
        )

        if not overlaps:
            selected.append(candidate)

    return sorted(
        selected,
        key=lambda entity: (
            entity.start_character
            if entity.start_character is not None
            else 0
        ),
    )


def extract_entities(
    text: str,
) -> tuple[list[ExtractedEntity], list[ExtractedEntity]]:
    temporal_entities = _remove_temporal_overlaps(
        _extract_regex_entities(
            text,
            TEMPORAL_PATTERNS,
        )
    )

    location_entities = []

    location_entities.extend(
        _extract_terms(
            text,
            SPATIAL_RELATIONS,
            "spatial_relation",
        )
    )

    location_entities.extend(
        _extract_terms(
            text,
            GENERIC_LOCATIONS,
            "generic_location",
        )
    )

    location_entities.extend(
        _extract_proper_place_candidates(text)
    )

    return (
        temporal_entities,
        _remove_duplicates(location_entities),
    )
