import re
from collections import Counter
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings


from langchain_core.documents import Document

from app.base_models.timeline_models import (
    TimelineCategory,
    TimelineEvent,
    TimelineSourceSegment,
)
from app.functions.embedding.embedding_model import (
    get_all_transcription_documents,
)
from app.functions.entity_extraction.entity_extractor import (
    extract_entities,
)


MAX_SEGMENT_GAP_SECONDS = 30.0
MAX_EVENT_DURATION_SECONDS = 120.0
MAX_SEGMENTS_PER_EVENT = 6
MIN_EVENT_TEXT_LENGTH = 20
MIN_EVENT_DURATION_SECONDS = 2.0

EVENT_TRANSITION_PATTERN = re.compile(
    r"""
    (?=
        \b
        (?:
            suddenly
            | meanwhile
            | afterwards
            | afterward
            | eventually
            | later
            | then
            | after\s+(?:the|a|an)\s+\w+
            | before\s+(?:the|a|an)?\s*\w+
            | when
            | while
            | once
        )
        \b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

CLAUSE_CONNECTOR_PATTERN = re.compile(
    r"\s+\b(?:and|but|then|while)\b\s+",
    re.IGNORECASE,
)

MEANINGFUL_EVENT_CATEGORIES = {
    TimelineCategory.travel,
    TimelineCategory.combat,
    TimelineCategory.discovery,
    TimelineCategory.rest,
    TimelineCategory.quest,
    TimelineCategory.item,
}

CATEGORY_KEYWORDS: dict[
    TimelineCategory,
    dict[str, int],
] = {
    TimelineCategory.combat: {
        "attack": 3,
        "attacked": 3,
        "battle": 3,
        "combat": 3,
        "fight": 3,
        "fighting": 3,
        "initiative": 4,
        "roll for initiative": 5,
        "damage": 2,
        "hit": 1,
        "critical hit": 3,
        "weapon": 1,
        "sword": 2,
        "arrow": 2,
        "spell": 2,
        "enemy": 2,
        "goblin": 2,
        "orc": 2,
        "dragon": 2,
        "monster": 2,
        "armor class": 3,
        "saving throw": 2,
        "defeated": 3,
        "killed": 3,
    },
    TimelineCategory.travel: {
        "travel": 3,
        "travelled": 3,
        "traveled": 3,
        "journey": 3,
        "road": 2,
        "path": 1,
        "walked": 2,
        "rode": 2,
        "sailed": 2,
        "arrived": 4,
        "reached": 3,
        "entered": 2,
        "left": 2,
        "departed": 3,
        "crossed": 2,
        "headed": 2,
        "north": 1,
        "south": 1,
        "east": 1,
        "west": 1,
    },
    TimelineCategory.discovery: {
        "discover": 3,
        "discovered": 4,
        "found": 3,
        "hidden": 3,
        "secret": 3,
        "clue": 3,
        "investigate": 2,
        "investigated": 2,
        "noticed": 2,
        "revealed": 3,
        "uncovered": 3,
        "opened": 1,
        "passage": 2,
        "door": 1,
        "tracks": 2,
        "evidence": 3,
    },
    TimelineCategory.rest: {
        "rest": 4,
        "rested": 4,
        "long rest": 5,
        "short rest": 5,
        "sleep": 3,
        "slept": 3,
        "camp": 3,
        "camped": 3,
        "recover": 2,
        "recovered": 2,
        "healed": 2,
    },
    TimelineCategory.quest: {
        "quest": 4,
        "mission": 4,
        "objective": 3,
        "contract": 3,
        "reward": 2,
        "rescue": 3,
        "must find": 3,
        "need to find": 3,
        "asked us to": 3,
        "promised": 2,
        "accepted the task": 4,
    },
    TimelineCategory.item: {
        "treasure": 4,
        "gold": 2,
        "potion": 3,
        "scroll": 3,
        "key": 3,
        "artifact": 4,
        "weapon": 2,
        "armor": 2,
        "inventory": 2,
        "picked up": 3,
        "received": 2,
        "obtained": 3,
        "loot": 3,
    },
    TimelineCategory.dialogue: {
        "said": 1,
        "asked": 2,
        "answered": 2,
        "told": 2,
        "warned": 3,
        "explained": 2,
        "agreed": 2,
        "conversation": 3,
        "spoke": 2,
        "talked": 2,
        "negotiated": 3,
    },
}


CATEGORY_PRIORITY = [
    TimelineCategory.combat,
    TimelineCategory.quest,
    TimelineCategory.discovery,
    TimelineCategory.item,
    TimelineCategory.travel,
    TimelineCategory.rest,
    TimelineCategory.dialogue,
]

CATEGORY_DESCRIPTIONS: dict[
    TimelineCategory,
    list[str],
] = {
    TimelineCategory.combat: [
        "Characters fight, attack, defend themselves or enter combat.",
        "A battle begins against enemies, monsters or hostile creatures.",
        "Weapons, spells, damage or initiative are used during a fight.",
    ],
    TimelineCategory.travel: [
        "The party moves or journeys from one location to another.",
        "Characters arrive, leave, cross, enter or travel through a place.",
        "The group follows a road, path, river or route toward a destination.",
    ],
    TimelineCategory.discovery: [
        "The party finds a clue, secret, hidden place or important information.",
        "Characters discover something previously unknown.",
        "A hidden door, passage, object or mystery is revealed.",
    ],
    TimelineCategory.rest: [
        "The party rests, sleeps, camps or recovers.",
        "Characters stop travelling to regain strength.",
        "The group takes a short rest or long rest.",
    ],
    TimelineCategory.quest: [
        "The party receives, accepts or completes a quest or mission.",
        "Someone gives the characters an objective or important task.",
        "The group agrees to rescue, retrieve or investigate something.",
    ],
    TimelineCategory.item: [
        "The party obtains, receives or collects an important item.",
        "Characters find treasure, gold, a key, weapon, potion or artifact.",
        "An object is added to the party's inventory.",
    ],
    TimelineCategory.dialogue: [
        "Characters have a conversation or exchange information.",
        "Someone asks, answers, explains, warns or negotiates.",
        "The event mainly consists of spoken discussion.",
    ],
}

@lru_cache(maxsize=1)
def _get_category_embedding_data(
) -> tuple[
    SentenceTransformer,
    list[TimelineCategory],
    np.ndarray,
]:
    """
    Load the embedding model once and precompute category-description
    embeddings.

    The result is cached, so timeline generation does not reload the
    model for every transcription segment.
    """

    model = SentenceTransformer(
        settings.embedding_model
    )

    categories: list[TimelineCategory] = []
    descriptions: list[str] = []

    for category, examples in CATEGORY_DESCRIPTIONS.items():
        for example in examples:
            categories.append(category)
            descriptions.append(example)

    description_embeddings = model.encode(
        descriptions,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return (
        model,
        categories,
        description_embeddings,
    )


EVENT_BOUNDARY_KEYWORDS = {
    "suddenly",
    "after the battle",
    "afterwards",
    "later",
    "the next morning",
    "the next day",
    "meanwhile",
    "before sunset",
    "at dawn",
    "at night",
    "then the party",
    "the group arrived",
    "the group entered",
    "the party discovered",
}


LOCATION_STOP_WORDS = {
    "The Party",
    "The Group",
    "The Adventurers",
    "Two Days Later",
    "After The Battle",
    "Before Sunset",
    "Suddenly",
    "Everyone",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Today",
    "Tomorrow",
    "Yesterday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
}

GENERIC_LOCATION_WORDS = {
    "area",
    "bridge",
    "building",
    "camp",
    "castle",
    "cave",
    "chamber",
    "city",
    "cliff",
    "dungeon",
    "farm",
    "field",
    "forest",
    "fort",
    "fortress",
    "gate",
    "harbor",
    "harbour",
    "hill",
    "house",
    "inn",
    "island",
    "keep",
    "lake",
    "landmark",
    "market",
    "mountain",
    "palace",
    "path",
    "river",
    "road",
    "room",
    "ruins",
    "sea",
    "shop",
    "shore",
    "street",
    "swamp",
    "tavern",
    "temple",
    "tower",
    "town",
    "valley",
    "village",
    "woods",
}

LOCATION_PREPOSITIONS = {
    "above",
    "across",
    "around",
    "at",
    "behind",
    "beneath",
    "beside",
    "beyond",
    "by",
    "from",
    "in",
    "inside",
    "into",
    "near",
    "outside",
    "through",
    "to",
    "toward",
    "towards",
    "under",
    "within",
}

LOCATION_ACTION_PHRASES = {
    "arrived at",
    "arrived in",
    "camped at",
    "crossed",
    "entered",
    "headed to",
    "left",
    "moved to",
    "reached",
    "rested at",
    "returned to",
    "travelled from",
    "travelled to",
    "traveled from",
    "traveled to",
    "walked across",
    "walked through",
    "walked to",
    "went to",
}

LOCATION_DESCRIPTORS = {
    "abandoned",
    "ancient",
    "broken",
    "dark",
    "hidden",
    "large",
    "nearby",
    "new",
    "old",
    "small",
    "wooden",
}

GENERIC_NON_LOCATIONS = {
    # Game roles
    "dungeon master",
    "game master",
    "dm",
    "gm",
    "narrator",

    # Groups and people
    "party",
    "the party",
    "group",
    "the group",
    "team",
    "the team",
    "adventurers",
    "the adventurers",
    "heroes",
    "the heroes",
    "players",
    "everyone",
    "someone",
    "somebody",
    "anyone",
    "nobody",
    "person",
    "people",
    "friend",
    "friends",
    "leader",
    "captain",
    "guard",
    "merchant",
    "villager",
    "traveler",
    "traveller",

    # Pronouns and determiners
    "this",
    "that",
    "these",
    "those",
    "he",
    "she",
    "they",
    "them",
    "him",
    "her",
    "we",
    "us",
    "you",
    "i",

    # Time words
    "today",
    "tomorrow",
    "yesterday",
    "morning",
    "afternoon",
    "evening",
    "night",
    "sunrise",
    "sunset",
    "later",
    "earlier",
    "before",
    "after",
    "now",
    "then",

    # Story connectors
    "suddenly",
    "finally",
    "meanwhile",
    "afterwards",
    "eventually",
    "first",
    "second",
    "next",
    "last",

    # Fillers and number words
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "thing",
    "something",
    "anything",
    "everything",
}


def _safe_float(
    value: object,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = _normalize_text(value)

        if not cleaned:
            continue

        key = cleaned.casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append(cleaned)

    return result


def _document_to_segment(
    document: Document,
) -> TimelineSourceSegment:
    metadata = document.metadata or {}

    start_time = max(
        0.0,
        _safe_float(metadata.get("start_time")),
    )

    end_time = max(
        start_time,
        _safe_float(
            metadata.get("end_time"),
            start_time,
        ),
    )

    return TimelineSourceSegment(
        text=_normalize_text(document.page_content),
        speaker=str(
            metadata.get("player_id", "unknown")
        ),
        start_time=start_time,
        end_time=end_time,
    )


def _contains_boundary_phrase(text: str) -> bool:
    normalized = text.casefold()

    return any(
        phrase in normalized
        for phrase in EVENT_BOUNDARY_KEYWORDS
    )


def _group_duration(
    group: list[TimelineSourceSegment],
) -> float:
    if not group:
        return 0.0

    return max(
        0.0,
        group[-1].end_time - group[0].start_time,
    )


def _group_segments(
    segments: list[TimelineSourceSegment],
) -> list[list[TimelineSourceSegment]]:
    """
    Group event units that belong to the same meaningful event.
    """

    if not segments:
        return []

    groups: list[list[TimelineSourceSegment]] = []
    current_group: list[TimelineSourceSegment] = []
    current_category: TimelineCategory | None = None

    for segment in segments:
        segment_category = _detect_segment_category(
            segment.text
        )

        if not current_group:
            current_group = [segment]
            current_category = segment_category
            continue

        previous = current_group[-1]

        gap = max(
            0.0,
            segment.start_time - previous.end_time,
        )

        duration = _group_duration(
            current_group
        )

        category_changed = (
            current_category is not None
            and segment_category != current_category
        )

        meaningful_category_change = (
            category_changed
            and (
                segment_category
                in MEANINGFUL_EVENT_CATEGORIES
                or current_category
                in MEANINGFUL_EVENT_CATEGORIES
            )
        )

        should_split = (
            gap > MAX_SEGMENT_GAP_SECONDS
            or duration >= MAX_EVENT_DURATION_SECONDS
            or len(current_group) >= MAX_SEGMENTS_PER_EVENT
            or meaningful_category_change
            or _contains_boundary_phrase(segment.text)
        )

        if should_split:
            groups.append(current_group)
            current_group = [segment]
            current_category = segment_category
        else:
            current_group.append(segment)

            if (
                current_category
                in {
                    TimelineCategory.dialogue,
                    TimelineCategory.other,
                }
                and segment_category
                in MEANINGFUL_EVENT_CATEGORIES
            ):
                current_category = segment_category

    if current_group:
        groups.append(current_group)

    return groups


def _keyword_score(
    text: str,
    keyword: str,
    weight: int,
) -> int:
    normalized_text = text.casefold()
    normalized_keyword = keyword.casefold()

    if " " in normalized_keyword:
        return (
            normalized_text.count(normalized_keyword)
            * weight
        )

    pattern = rf"\b{re.escape(normalized_keyword)}\b"

    return (
        len(re.findall(pattern, normalized_text))
        * weight
    )


def _semantic_category_scores(
    text: str,
) -> dict[TimelineCategory, float]:
    """
    Compare a transcription segment with semantic descriptions of all
    timeline categories.
    """

    model, categories, description_embeddings = (
        _get_category_embedding_data()
    )

    text_embedding = model.encode(
        [text],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0]

    similarities = description_embeddings @ text_embedding

    scores: dict[TimelineCategory, float] = {
        category: 0.0
        for category in CATEGORY_DESCRIPTIONS
    }

    for category, similarity in zip(
        categories,
        similarities,
    ):
        scores[category] = max(
            scores[category],
            float(similarity),
        )

    return scores


def _keyword_category_scores(
    text: str,
) -> dict[TimelineCategory, float]:
    """
    Calculate normalized keyword scores between zero and one.
    """

    raw_scores: dict[TimelineCategory, int] = {}

    for category, keywords in CATEGORY_KEYWORDS.items():
        raw_scores[category] = sum(
            _keyword_score(
                text,
                keyword,
                weight,
            )
            for keyword, weight in keywords.items()
        )

    maximum_score = max(
        raw_scores.values(),
        default=0,
    )

    if maximum_score == 0:
        return {
            category: 0.0
            for category in CATEGORY_DESCRIPTIONS
        }

    return {
        category: raw_scores.get(category, 0)
        / maximum_score
        for category in CATEGORY_DESCRIPTIONS
    }




def _detect_category(
    text: str,
) -> TimelineCategory:
    """
    Classify an event using semantic similarity and weighted keywords.

    Semantic similarity handles paraphrases and unseen wording.
    Keywords strengthen clear D&D-specific expressions such as
    'roll for initiative' or 'long rest'.
    """

    cleaned_text = _normalize_text(text)

    if not cleaned_text:
        return TimelineCategory.other

    semantic_scores = _semantic_category_scores(
        cleaned_text
    )

    keyword_scores = _keyword_category_scores(
        cleaned_text
    )

    combined_scores: dict[
        TimelineCategory,
        float,
    ] = {}

    for category in CATEGORY_DESCRIPTIONS:
        combined_scores[category] = (
            semantic_scores.get(category, 0.0) * 0.70
            + keyword_scores.get(category, 0.0) * 0.30
        )

    best_score = max(
        combined_scores.values(),
        default=0.0,
    )

    # Very uncertain text is treated as general dialogue.
    if best_score < 0.28:
        return TimelineCategory.dialogue

    for category in CATEGORY_PRIORITY:
        if combined_scores.get(category, 0.0) == best_score:
            return category

    return max(
        combined_scores,
        key=combined_scores.get,
    )


def _detect_segment_category(
    text: str,
) -> TimelineCategory:
    """
    Classify one transcription segment using the same hybrid semantic
    classifier used for complete events.
    """

    return _detect_category(text)




def _word_count(text: str) -> int:
    return len(
        re.findall(
            r"\b[\w'-]+\b",
            text,
        )
    )


def _is_useful_event_text(text: str) -> bool:
    cleaned = _normalize_text(text)

    return (
        len(cleaned) >= 8
        and _word_count(cleaned) >= 2
    )


def _split_on_category_change(
    text: str,
) -> list[str]:
    """
    Split a clause around connectors such as 'and' only when the two
    resulting parts describe different meaningful event categories.

    Example:
    'Tom defeated the wolf and found a silver key'
        -> combat part
        -> discovery/item part
    """

    cleaned = _normalize_text(text)

    if not cleaned:
        return []

    connector_matches = list(
        CLAUSE_CONNECTOR_PATTERN.finditer(cleaned)
    )

    for match in connector_matches:
        left = _normalize_text(
            cleaned[:match.start()]
        )

        right = _normalize_text(
            cleaned[match.end():]
        )

        if not (
            _is_useful_event_text(left)
            and _is_useful_event_text(right)
        ):
            continue

        left_category = _detect_segment_category(left)
        right_category = _detect_segment_category(right)

        categories_differ = (
            left_category != right_category
        )

        both_meaningful = (
            left_category in MEANINGFUL_EVENT_CATEGORIES
            and right_category in MEANINGFUL_EVENT_CATEGORIES
        )

        if categories_differ and both_meaningful:
            return [
                *_split_on_category_change(left),
                *_split_on_category_change(right),
            ]

    return [cleaned]


def _split_text_into_event_units(
    text: str,
) -> list[str]:
    """
    Split one WhisperX transcription segment into smaller event units.

    Processing:
    1. Split normal sentences.
    2. Split comma/semicolon clauses.
    3. Split at temporal and narrative transitions.
    4. Split conjunctions only when semantic categories change.
    """

    cleaned = _normalize_text(text)

    if not cleaned:
        return []

    sentence_parts = re.split(
        r"(?<=[.!?])\s+",
        cleaned,
    )

    rough_parts: list[str] = []

    for sentence in sentence_parts:
        sentence = _normalize_text(sentence)

        if not sentence:
            continue

        punctuation_parts = re.split(
            r"\s*[;,]\s*",
            sentence,
        )

        for punctuation_part in punctuation_parts:
            punctuation_part = _normalize_text(
                punctuation_part
            )

            if not punctuation_part:
                continue

            transition_parts = EVENT_TRANSITION_PATTERN.split(
                punctuation_part
            )

            rough_parts.extend(
                _normalize_text(part)
                for part in transition_parts
                if _normalize_text(part)
            )

    event_units: list[str] = []

    for part in rough_parts:
        event_units.extend(
            _split_on_category_change(part)
        )

    # Attach very small fragments to the following or previous unit.
    merged_units: list[str] = []

    for unit in event_units:
        unit = _normalize_text(unit)

        if not unit:
            continue

        if _word_count(unit) < 3:
            if merged_units:
                merged_units[-1] = _normalize_text(
                    f"{merged_units[-1]} {unit}"
                )
            continue

        merged_units.append(unit)

    return merged_units or [cleaned]


def _split_segment_with_timestamps(
    segment: TimelineSourceSegment,
) -> list[TimelineSourceSegment]:
    """
    Split a source segment and distribute its timestamps proportionally
    according to the number of words in each event unit.
    """

    units = _split_text_into_event_units(
        segment.text
    )

    if len(units) <= 1:
        return [segment]

    total_words = sum(
        max(1, _word_count(unit))
        for unit in units
    )

    total_duration = max(
        0.0,
        segment.end_time - segment.start_time,
    )

    result: list[TimelineSourceSegment] = []
    current_time = segment.start_time

    for index, unit in enumerate(units):
        word_count = max(
            1,
            _word_count(unit),
        )

        if index == len(units) - 1:
            unit_end = segment.end_time
        else:
            proportional_duration = (
                total_duration
                * word_count
                / total_words
            )

            unit_end = min(
                segment.end_time,
                current_time + proportional_duration,
            )

        result.append(
            TimelineSourceSegment(
                text=unit,
                speaker=segment.speaker,
                start_time=current_time,
                end_time=max(
                    current_time,
                    unit_end,
                ),
            )
        )

        current_time = unit_end

    return result


def _expand_documents_into_segments(
    documents: list[Document],
) -> list[TimelineSourceSegment]:
    """
    Convert stored transcription documents into semantic event segments.
    """

    expanded_segments: list[
        TimelineSourceSegment
    ] = []

    for document in documents:
        if not document.page_content.strip():
            continue

        original_segment = _document_to_segment(
            document
        )

        expanded_segments.extend(
            _split_segment_with_timestamps(
                original_segment
            )
        )

    return expanded_segments






def _clean_location_value(
    value: str,
    known_speakers: set[str] | None = None,
    temporal_values: set[str] | None = None,
) -> str | None:
    """Normalize a location candidate and remove obvious non-locations."""

    cleaned = _normalize_text(value).strip(
        ".,;:!?\\\"'()[]{}"
    )

    if not cleaned or len(cleaned) < 3:
        return None

    cleaned_casefold = cleaned.casefold()

    if cleaned_casefold in GENERIC_NON_LOCATIONS:
        return None

    if cleaned in LOCATION_STOP_WORDS:
        return None

    if known_speakers:
        speaker_names = {
            speaker.casefold()
            for speaker in known_speakers
            if speaker
        }
        if cleaned_casefold in speaker_names:
            return None

    if temporal_values:
        temporal_names = {
            temporal.casefold()
            for temporal in temporal_values
            if temporal
        }

        if cleaned_casefold in temporal_names:
            return None

        # Remove fragments such as "This" from "This morning".
        if any(
            temporal.startswith(f"{cleaned_casefold} ")
            for temporal in temporal_names
        ):
            return None

    return cleaned


def _extract_dialogue_character_names(
    text: str,
) -> set[str]:
    """
    Detect likely character or role names from common dialogue and
    narrative patterns. Returned values are case-folded.
    """

    names: set[str] = set()

    patterns = [
        # "Dungeon Master:" or "Tom:"
        re.compile(
            r"\\b([A-Z][a-z]+(?:\\s+[A-Z][a-z]+)?)\\s*:"
        ),

        # "Tom, look over there."
        re.compile(
            r"\\b([A-Z][a-z]+),\\s+"
        ),

        # "Tom said", "Anna shouted"
        re.compile(
            r"\\b([A-Z][a-z]+)\\s+"
            r"(?:said|asked|answered|shouted|whispered|warned|replied)\\b"
        ),

        # "Tom and Anna walked..."
        re.compile(
            r"\\b([A-Z][a-z]+)\\s+and\\s+([A-Z][a-z]+)\\s+"
            r"(?:walked|travelled|traveled|left|entered|reached|found|"
            r"attacked|defeated|returned|rested|opened|noticed)\\b"
        ),

        # "Tom defeated...", "Anna found..."
        re.compile(
            r"\\b([A-Z][a-z]+)\\s+"
            r"(?:walked|travelled|traveled|left|entered|reached|found|"
            r"attacked|defeated|returned|rested|opened|noticed|crossed)\\b"
        ),
    ]

    for pattern in patterns:
        for match in pattern.finditer(text):
            for group in match.groups():
                if group:
                    names.add(group.casefold())

    return names


def _candidate_has_location_noun(candidate: str) -> bool:
    words = set(
        re.findall(r"[a-zA-Z]+", candidate.casefold())
    )
    return bool(words & GENERIC_LOCATION_WORDS)


def _is_likely_location_in_context(
    candidate: str,
    text: str,
    entity_type: str,
) -> bool:
    """
    Keep a candidate only when it behaves like a place in the sentence.

    Generic place nouns are accepted directly. Proper names such as
    Neverwinter are accepted only when they appear after a location
    preposition or movement/action phrase.
    """

    cleaned_candidate = _normalize_text(candidate).strip(
        ".,;:!?\"'()[]{}"
    )

    if not cleaned_candidate:
        return False

    candidate_lower = cleaned_candidate.casefold()
    normalized_text = _normalize_text(text).casefold()
    escaped_candidate = re.escape(candidate_lower)

    if _candidate_has_location_noun(cleaned_candidate):
        return True

    descriptor_pattern = (
        r"(?:the\s+)?"
        r"(?:(?:"
        + "|".join(
            re.escape(value)
            for value in sorted(LOCATION_DESCRIPTORS)
        )
        + r")\s+)*"
    )

    for preposition in LOCATION_PREPOSITIONS:
        pattern = (
            rf"\b{re.escape(preposition)}\s+"
            rf"{descriptor_pattern}"
            rf"{escaped_candidate}\b"
        )

        if re.search(pattern, normalized_text):
            return True

    for action in LOCATION_ACTION_PHRASES:
        pattern = (
            rf"\b{re.escape(action)}\s+"
            rf"{descriptor_pattern}"
            rf"{escaped_candidate}\b"
        )

        if re.search(pattern, normalized_text):
            return True

    return False


def _extract_event_entities(
    combined_text: str,
    speakers: list[str],
) -> tuple[list[str], list[str]]:
    """
    Extract temporal expressions and reliable location entities.

    A candidate is removed when it is a speaker, likely character name,
    temporal phrase/fragment, generic non-location, or lacks geographic
    context.
    """

    temporal_entities, location_entities = extract_entities(
        combined_text
    )

    temporal_values = _unique_strings(
        [
            entity.text
            for entity in temporal_entities
        ]
    )

    known_speakers = {
        speaker.casefold()
        for speaker in speakers
        if speaker and speaker.casefold() != "unknown"
    }

    character_names = _extract_dialogue_character_names(
        combined_text
    )

    temporal_value_set = {
        value.casefold()
        for value in temporal_values
    }

    cleaned_locations: list[str] = []

    for entity in location_entities:
        if entity.entity_type not in {
            "place_candidate",
            "generic_location",
        }:
            continue

        cleaned = _clean_location_value(
            entity.text,
            known_speakers=set(speakers),
            temporal_values=set(temporal_values),
        )

        if cleaned is None:
            continue

        cleaned_lower = cleaned.casefold()

        if cleaned_lower in known_speakers:
            continue

        if cleaned_lower in character_names:
            continue

        if cleaned_lower in temporal_value_set:
            continue

        if any(
            temporal.startswith(f"{cleaned_lower} ")
            for temporal in temporal_value_set
        ):
            continue

        if not _is_likely_location_in_context(
            candidate=cleaned,
            text=combined_text,
            entity_type=entity.entity_type,
        ):
            continue

        cleaned_locations.append(cleaned)

    return (
        temporal_values,
        _unique_strings(cleaned_locations),
    )


def _main_location(
    locations: list[str],
    combined_text: str,
) -> str | None:
    if not locations:
        return None

    named_locations = [
        location
        for location in locations
        if location.casefold() not in GENERIC_LOCATION_WORDS
    ]

    candidates = (
        named_locations
        if named_locations
        else locations
    )

    counts = Counter(
        location.casefold()
        for location in candidates
    )

    return max(
        candidates,
        key=lambda location: (
            counts[location.casefold()],
            combined_text.casefold().count(
                location.casefold()
            ),
            len(location),
        ),
    )


def _shorten_text(
    text: str,
    maximum_length: int,
) -> str:
    cleaned = _normalize_text(text).strip(
        " \t\n\r.,;:!?-"
    )

    if len(cleaned) <= maximum_length:
        return cleaned

    shortened = cleaned[:maximum_length].rsplit(
        " ",
        1,
    )[0]

    return f"{shortened}…"


def _build_title(
    category: TimelineCategory,
    combined_text: str,
    locations: list[str],
) -> str:
    location = _main_location(
        locations,
        combined_text,
    )

    if category == TimelineCategory.combat:
        return (
            f"Battle near {location}"
            if location
            else "A Battle Begins"
        )

    if category == TimelineCategory.travel:
        if "arrived" in combined_text.casefold():
            return (
                f"Arrival at {location}"
                if location
                else "The Party Arrives"
            )

        return (
            f"Journey through {location}"
            if location
            else "The Party Continues Its Journey"
        )

    if category == TimelineCategory.discovery:
        return (
            f"Discovery at {location}"
            if location
            else "An Important Discovery"
        )

    if category == TimelineCategory.rest:
        return (
            f"Rest near {location}"
            if location
            else "The Party Takes a Rest"
        )

    if category == TimelineCategory.quest:
        return "A New Quest Is Accepted"

    if category == TimelineCategory.item:
        return "An Important Item Is Obtained"

    if category == TimelineCategory.dialogue:
        return (
            f"Conversation at {location}"
            if location
            else "An Important Conversation"
        )

    first_sentence = re.split(
        r"[.!?]",
        combined_text,
        maxsplit=1,
    )[0]

    return _shorten_text(
        first_sentence or combined_text,
        80,
    )


def _is_meaningful_group(
    group: list[TimelineSourceSegment],
) -> bool:
    combined_text = _normalize_text(
        " ".join(
            segment.text
            for segment in group
        )
    )

    if len(combined_text) < MIN_EVENT_TEXT_LENGTH:
        return False

    duration = max(
        segment.end_time
        for segment in group
    ) - min(
        segment.start_time
        for segment in group
    )

    if duration < MIN_EVENT_DURATION_SECONDS:
        return False

    words = re.findall(
        r"\b[a-zA-Z]{2,}\b",
        combined_text,
    )

    if len(words) < 4:
        return False

    return True


def _create_event_from_group(
    group: list[TimelineSourceSegment],
) -> TimelineEvent:
    combined_text = _normalize_text(
        " ".join(
            segment.text
            for segment in group
            if segment.text.strip()
        )
    )

    category = _detect_category(combined_text)
    
    speakers = _unique_strings(
        [
            segment.speaker
            for segment in group
            if segment.speaker.casefold()
            != "unknown"
        ]
    )
    
    temporal_entities, locations = (
        _extract_event_entities(
            combined_text,
            speakers,
        )
    )

    start_time = min(
        segment.start_time
        for segment in group
    )

    end_time = max(
        segment.end_time
        for segment in group
    )

    title = _build_title(
        category,
        combined_text,
        locations,
    )

    description = _shorten_text(
        combined_text,
        600,
    )

    stable_event_key = (
        f"{start_time:.3f}|"
        f"{end_time:.3f}|"
        f"{combined_text}"
    )

    now = datetime.now(timezone.utc).isoformat()

    return TimelineEvent(
        id=str(
            uuid5(
                NAMESPACE_URL,
                stable_event_key,
            )
        ),
        title=title,
        description=description,
        category=category,
        start_time=start_time,
        end_time=end_time,
        speakers=speakers,
        locations=locations,
        temporal_entities=temporal_entities,
        source_segments=group,
        created_automatically=True,
        created_at=now,
        updated_at=now,
    )


def _events_are_similar(
    first: TimelineEvent,
    second: TimelineEvent,
) -> bool:
    gap = max(
        0.0,
        second.start_time - first.end_time,
    )

    same_category = (
        first.category == second.category
    )

    shared_locations = bool(
        {
            location.casefold()
            for location in first.locations
        }
        & {
            location.casefold()
            for location in second.locations
        }
    )

    # Never merge two events with different meaningful categories.
    if first.category != second.category:
        return False

    return (
        gap <= 8.0
        and (
            same_category
            or shared_locations
        )
    )


def _merge_two_events(
    first: TimelineEvent,
    second: TimelineEvent,
) -> TimelineEvent:
    merged_segments = (
        first.source_segments
        + second.source_segments
    )

    return _create_event_from_group(
        merged_segments
    )


def _merge_similar_events(
    events: list[TimelineEvent],
) -> list[TimelineEvent]:
    if not events:
        return []

    merged: list[TimelineEvent] = [
        events[0]
    ]

    for event in events[1:]:
        previous = merged[-1]

        if _events_are_similar(
            previous,
            event,
        ):
            merged[-1] = _merge_two_events(
                previous,
                event,
            )
        else:
            merged.append(event)

    return merged


def generate_timeline_from_embeddings(
) -> tuple[list[TimelineEvent], int]:
    """
    Generate a chronological timeline from transcription documents.

    Processing stages:
    1. Read every transcription document from ChromaDB.
    2. Convert documents into timestamped segments.
    3. Group related nearby segments.
    4. Ignore weak or meaningless groups.
    5. Extract entities and detect event categories.
    6. Merge similar adjacent events.
    """

    documents = get_all_transcription_documents()

    segments = _expand_documents_into_segments(
        documents
    )

    segments.sort(
        key=lambda segment: (
            segment.start_time,
            segment.end_time,
        )
    )

    groups = _group_segments(segments)

    events = [
        _create_event_from_group(group)
        for group in groups
        if group and _is_meaningful_group(group)
    ]

    events.sort(
        key=lambda event: (
            event.start_time,
            event.end_time,
        )
    )

    merged_events = _merge_similar_events(
        events
    )

    return merged_events, len(segments)