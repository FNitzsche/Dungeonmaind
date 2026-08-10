import re

from app.base_models.entity_extraction_models import ExtractedEntity


TEMPORAL_PATTERNS: list[tuple[str, str]] = [
    (
        r"\b(?:today|tomorrow|yesterday|tonight)\b",
        "relative_date",
    ),
    (
        r"\b(?:next|last|this)\s+"
        r"(?:morning|afternoon|evening|night|day|week|month|year)\b",
        "relative_date",
    ),
    (
        r"\b(?:before|after|at)\s+"
        r"(?:sunrise|sunset|dawn|dusk|midnight|noon)\b",
        "relative_time",
    ),
    (
        r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+"
        r"(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)\s+later\b",
        "relative_time",
    ),
    (
        r"\b(?:for|after|before)\s+"
        r"(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+"
        r"(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b",
        "duration",
    ),
    (
        r"\b\d{1,2}:\d{2}(?:\s*(?:am|pm))?\b",
        "clock_time",
    ),
    (
        r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        "weekday",
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


def extract_entities(
    text: str,
) -> tuple[list[ExtractedEntity], list[ExtractedEntity]]:
    temporal_entities = _extract_regex_entities(
        text,
        TEMPORAL_PATTERNS,
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
        _remove_duplicates(temporal_entities),
        _remove_duplicates(location_entities),
    )

