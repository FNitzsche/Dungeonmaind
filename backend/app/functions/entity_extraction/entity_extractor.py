import re

from app.base_models.entity_extraction_models import ExtractedEntity


# ============================================================
# TEMPORAL CONFIGURATION
# ============================================================

NUMBER_WORDS = (
    r"one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|\d+"
)

TIME_UNITS = (
    r"seconds?|minutes?|hours?|days?|weeks?|months?|years?"
)

DAY_PARTS = (
    r"morning|afternoon|evening|night"
)

SUN_TIMES = (
    r"sunrise|sunset|dawn|dusk|midnight|noon"
)


TEMPORAL_PATTERNS: list[tuple[str, str]] = [

    # today / tomorrow / yesterday / tonight
    (
        r"\b(?:today|tomorrow|yesterday|tonight)\b",
        "relative_date",
    ),

    # the following morning / the next day / previous week
    (
        rf"\b(?:the\s+)?(?:next|following|previous)\s+"
        rf"(?:{DAY_PARTS}|day|week|month|year)\b",
        "relative_date",
    ),

    # this morning / last night
    (
        rf"\b(?:this|last|next)\s+"
        rf"(?:{DAY_PARTS}|day|week|month|year)\b",
        "relative_date",
    ),

    # later that evening / earlier that morning
    (
        rf"\b(?:later|earlier)\s+that\s+"
        rf"(?:{DAY_PARTS})\b",
        "relative_time",
    ),

    # before sunrise / after sunset / at midnight
    (
        rf"\b(?:before|after|at)\s+"
        rf"(?:{SUN_TIMES})\b",
        "relative_time",
    ),

    # three days later / two hours later / a week later
    (
        rf"\b(?:a|an|{NUMBER_WORDS})\s+"
        rf"(?:{TIME_UNITS})\s+later\b",
        "relative_time",
    ),

    # three days earlier
    (
        rf"\b(?:a|an|{NUMBER_WORDS})\s+"
        rf"(?:{TIME_UNITS})\s+earlier\b",
        "relative_time",
    ),

    # for two hours / after three days
    (
        rf"\b(?:for|after|before)\s+"
        rf"(?:a|an|{NUMBER_WORDS})\s+"
        rf"(?:{TIME_UNITS})\b",
        "duration",
    ),

    # in two hours / within three days
    (
        rf"\b(?:in|within)\s+"
        rf"(?:a|an|{NUMBER_WORDS})\s+"
        rf"(?:{TIME_UNITS})\b",
        "duration",
    ),

    # 12:30 / 12:30 PM
    (
        r"\b\d{1,2}:\d{2}(?:\s*(?:am|pm))?\b",
        "clock_time",
    ),

    # 8 PM
    (
        r"\b\d{1,2}\s*(?:am|pm)\b",
        "clock_time",
    ),

    # weekdays
    (
        r"\b(?:monday|tuesday|wednesday|thursday|"
        r"friday|saturday|sunday)\b",
        "weekday",
    ),
]


# ============================================================
# LOCATION NOUNS
# ============================================================

GENERIC_LOCATION_WORDS = {
    # Settlements
    "village",
    "town",
    "city",
    "settlement",
    "hamlet",
    "capital",

    # Buildings
    "building",
    "house",
    "home",
    "hut",
    "cottage",
    "inn",
    "tavern",
    "shop",
    "market",
    "warehouse",
    "stable",

    # Fortifications
    "castle",
    "keep",
    "fort",
    "fortress",
    "tower",
    "palace",
    "citadel",
    "stronghold",
    "outpost",
    "gate",

    # Religious / magical
    "temple",
    "shrine",
    "chapel",
    "monastery",
    "sanctuary",

    # Underground / dungeon
    "dungeon",
    "cave",
    "caves",
    "cavern",
    "caverns",
    "crypt",
    "tomb",
    "tombs",
    "catacomb",
    "catacombs",
    "chamber",
    "chambers",
    "room",
    "rooms",
    "corridor",
    "corridors",
    "hall",
    "hallway",
    "passage",
    "tunnel",
    "tunnels",
    "cellar",
    "basement",
    "vault",

    # Nature
    "forest",
    "woods",
    "jungle",
    "swamp",
    "marsh",
    "mountain",
    "mountains",
    "hill",
    "hills",
    "valley",
    "cliff",
    "canyon",
    "desert",
    "field",
    "meadow",
    "plain",
    "plains",
    "grove",

    # Water
    "river",
    "lake",
    "sea",
    "ocean",
    "pond",
    "stream",
    "waterfall",
    "shore",
    "coast",
    "harbor",
    "harbour",
    "dock",
    "docks",
    "port",

    # Travel
    "road",
    "path",
    "trail",
    "bridge",
    "crossroad",
    "crossroads",

    # General
    "area",
    "place",
    "location",
    "camp",
    "campsite",
    "ruins",
    "landmark",
    "island",
}


# ============================================================
# LOCATION DESCRIPTORS
# ============================================================

LOCATION_DESCRIPTORS = {
    # Relative / positional
    "current",
    "nearby",
    "nearest",
    "distant",
    "remote",

    # Direction
    "northern",
    "southern",
    "eastern",
    "western",
    "north",
    "south",
    "east",
    "west",

    # Position
    "upper",
    "lower",
    "inner",
    "outer",
    "central",

    # Size / shape
    "small",
    "large",
    "huge",
    "tiny",
    "narrow",
    "wide",
    "long",
    "deep",

    # Age / condition
    "old",
    "ancient",
    "new",
    "abandoned",
    "ruined",
    "broken",
    "destroyed",
    "collapsed",
    "damaged",
    "forgotten",
    "lost",
    "hidden",
    "secret",

    # Environment
    "dark",
    "underground",
    "subterranean",
    "flooded",
    "frozen",
    "snowy",
    "icy",
    "rocky",
    "misty",
    "foggy",
    "swampy",
    "wooded",
    "overgrown",

    # Material
    "stone",
    "wooden",

    # Fantasy
    "cursed",
    "haunted",
    "enchanted",
    "magical",
    "sacred",
    "holy",
    "unholy",
    "forbidden",
    "mysterious",

    # Common fantasy name adjectives
    "ashen",
    "black",
    "white",
    "red",
    "green",
    "blue",
    "silver",
    "golden",
}


# ============================================================
# LOCATION CONTEXT
# ============================================================

LOCATION_ACTIONS = [
    "travelled to",
    "traveled to",
    "travelled from",
    "traveled from",
    "went back to",
    "went back into",
    "went back inside",
    "returned to",
    "returned from",
    "descended into",
    "walked through",
    "walked across",
    "walked into",
    "walked to",
    "arrived at",
    "arrived in",
    "headed to",
    "headed toward",
    "headed towards",
    "moved to",
    "moved into",
    "camped at",
    "rested at",
    "went to",
    "entered",
    "reached",
    "crossed",
    "left",
    "approached",
    "visited",
    "explored",
    "discovered",
    "found",
    "noticed",
    "searched",
]


LOCATION_PREPOSITIONS = [
    "inside",
    "outside",
    "beneath",
    "behind",
    "beside",
    "beyond",
    "within",
    "through",
    "towards",
    "toward",
    "under",
    "above",
    "below",
    "across",
    "near",
    "around",
    "from",
    "into",
    "at",
    "in",
    "to",
]


CAPITALIZED_STOP_WORDS = {
    "A",
    "An",
    "The",
    "At",
    "After",
    "Before",
    "Later",
    "Earlier",
    "Then",
    "Next",
    "Following",
    "Previous",
    "This",
    "That",
    "These",
    "Those",
    "Today",
    "Tomorrow",
    "Yesterday",
    "Tonight",
    "Everyone",
    "Someone",
    "Somebody",
    "Anyone",
    "Nobody",
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
    "Eleven",
    "Twelve",
}


# ============================================================
# GENERAL HELPERS
# ============================================================

def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _make_entity(
    text: str,
    entity_type: str,
    start: int,
    end: int,
) -> ExtractedEntity:
    return ExtractedEntity(
        text=text,
        entity_type=entity_type,
        start_character=start,
        end_character=end,
    )


def _span_overlaps(
    start: int,
    end: int,
    entities: list[ExtractedEntity],
) -> bool:

    for entity in entities:

        if (
            entity.start_character is None
            or entity.end_character is None
        ):
            continue

        if (
            start < entity.end_character
            and end > entity.start_character
        ):
            return True

    return False


# ============================================================
# TEMPORAL EXTRACTION
# ============================================================

def _extract_temporal_entities(
    text: str,
) -> list[ExtractedEntity]:

    entities: list[ExtractedEntity] = []

    for pattern, entity_type in TEMPORAL_PATTERNS:

        for match in re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):

            entities.append(
                _make_entity(
                    match.group(0),
                    entity_type,
                    match.start(),
                    match.end(),
                )
            )

    return entities


# ============================================================
# PROPER NAMED LOCATION AFTER ACTION
# ============================================================

def _extract_named_locations_after_actions(
    text: str,
    temporal_entities: list[ExtractedEntity],
) -> list[ExtractedEntity]:

    entities: list[ExtractedEntity] = []

    actions = "|".join(
        re.escape(action)
        for action in sorted(
            LOCATION_ACTIONS,
            key=len,
            reverse=True,
        )
    )

    capital_word = r"[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'-]*"

    connector = (
        r"(?:of|the|and|de|del|la|le|von|van)"
    )

    proper_name = (
        rf"{capital_word}"
        rf"(?:"
        rf"\s+{capital_word}"
        rf"|"
        rf"\s+{connector}\s+{capital_word}"
        rf"){{0,5}}"
    )

    pattern = re.compile(
        rf"""
        \b(?:{actions})\b
        \s+
        (?:a\s+|an\s+|the\s+)?
        (?P<location>{proper_name})
        """,
        re.VERBOSE,
    )

    for match in pattern.finditer(text):

        value = _normalize_text(
            match.group("location")
        )

        if value in CAPITALIZED_STOP_WORDS:
            continue

        start = match.start("location")
        end = match.end("location")

        if _span_overlaps(
            start,
            end,
            temporal_entities,
        ):
            continue

        entities.append(
            _make_entity(
                value,
                "place_candidate",
                start,
                end,
            )
        )

    return entities


# ============================================================
# PROPER LOCATION COMPOUNDS
# ============================================================

def _extract_named_location_compounds(
    text: str,
    temporal_entities: list[ExtractedEntity],
) -> list[ExtractedEntity]:

    entities: list[ExtractedEntity] = []

    location_words = "|".join(
        re.escape(word)
        for word in sorted(
            GENERIC_LOCATION_WORDS,
            key=len,
            reverse=True,
        )
    )

    #
    # Examples:
    #
    # Whispering Crypt
    # Blackstone Keep
    # Ashen Forest
    # Silver Tower
    #
    pattern = re.compile(
        rf"""
        \b
        (?P<location>
            [A-Z][A-Za-zÀ-ÖØ-öø-ÿ'-]*
            \s+
            (?i:{location_words})
        )
        \b
        """,
        re.VERBOSE,
    )

    for match in pattern.finditer(text):

        value = _normalize_text(
            match.group("location")
        )

        start = match.start("location")
        end = match.end("location")

        if _span_overlaps(
            start,
            end,
            temporal_entities,
        ):
            continue

        entities.append(
            _make_entity(
                value,
                "place_candidate",
                start,
                end,
            )
        )

    return entities


# ============================================================
# GENERIC LOCATIONS
# ============================================================

def _extract_generic_locations(
    text: str,
    temporal_entities: list[ExtractedEntity],
) -> list[ExtractedEntity]:

    entities: list[ExtractedEntity] = []

    location_words = "|".join(
        re.escape(word)
        for word in sorted(
            GENERIC_LOCATION_WORDS,
            key=len,
            reverse=True,
        )
    )

    descriptors = "|".join(
        re.escape(word)
        for word in sorted(
            LOCATION_DESCRIPTORS,
            key=len,
            reverse=True,
        )
    )

    #
    # Example captures:
    #
    # village
    # current cave
    # hidden chamber
    # northern corridor
    # abandoned village
    # dark forest
    #
    generic_phrase = (
        rf"(?:(?:{descriptors})\s+)*"
        rf"(?:{location_words})"
    )

    #
    # We only require location context.
    # The context itself is NOT captured.
    #
    contexts = (
        LOCATION_ACTIONS
        + LOCATION_PREPOSITIONS
    )

    context_pattern = "|".join(
        re.escape(value)
        for value in sorted(
            contexts,
            key=len,
            reverse=True,
        )
    )

    pattern = re.compile(
        rf"""
        \b(?:{context_pattern})\b
        \s+
        (?:a\s+|an\s+|the\s+)?
        (?P<location>{generic_phrase})
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    for match in pattern.finditer(text):

        value = _normalize_text(
            match.group("location")
        )

        start = match.start("location")
        end = match.end("location")

        if _span_overlaps(
            start,
            end,
            temporal_entities,
        ):
            continue

        entities.append(
            _make_entity(
                value,
                "generic_location",
                start,
                end,
            )
        )

    return entities


# ============================================================
# SECONDARY LOCATION CONTEXT
# ============================================================

def _extract_secondary_locations(
    text: str,
    temporal_entities: list[ExtractedEntity],
) -> list[ExtractedEntity]:
    """
    Finds additional locations later in the same sentence.

    Example:

        he went back to the village after sunrise
        from the current cave

    Returns:
        village
        current cave
    """

    entities: list[ExtractedEntity] = []

    location_words = "|".join(
        re.escape(word)
        for word in sorted(
            GENERIC_LOCATION_WORDS,
            key=len,
            reverse=True,
        )
    )

    descriptors = "|".join(
        re.escape(word)
        for word in sorted(
            LOCATION_DESCRIPTORS,
            key=len,
            reverse=True,
        )
    )

    prepositions = "|".join(
        re.escape(value)
        for value in sorted(
            LOCATION_PREPOSITIONS,
            key=len,
            reverse=True,
        )
    )

    generic_phrase = (
        rf"(?:(?:{descriptors})\s+)*"
        rf"(?:{location_words})"
    )

    pattern = re.compile(
        rf"""
        \b(?:{prepositions})\b
        \s+
        (?:a\s+|an\s+|the\s+)?
        (?P<location>{generic_phrase})
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    for match in pattern.finditer(text):

        value = _normalize_text(
            match.group("location")
        )

        start = match.start("location")
        end = match.end("location")

        if _span_overlaps(
            start,
            end,
            temporal_entities,
        ):
            continue

        entities.append(
            _make_entity(
                value,
                "generic_location",
                start,
                end,
            )
        )

    return entities


# ============================================================
# DEDUPLICATION
# ============================================================

def _remove_duplicates(
    entities: list[ExtractedEntity],
) -> list[ExtractedEntity]:

    if not entities:
        return []

    #
    # Prefer longer entities.
    #
    ordered = sorted(
        entities,
        key=lambda entity: (
            -len(entity.text),
            entity.start_character
            if entity.start_character is not None
            else 0,
        ),
    )

    selected: list[ExtractedEntity] = []

    for entity in ordered:

        if (
            entity.start_character is None
            or entity.end_character is None
        ):
            continue

        duplicate = False

        for existing in selected:

            if (
                existing.start_character is None
                or existing.end_character is None
            ):
                continue

            same_text = (
                entity.text.casefold()
                == existing.text.casefold()
            )

            contained = (
                entity.start_character
                >= existing.start_character
                and entity.end_character
                <= existing.end_character
            )

            overlaps = (
                entity.start_character
                < existing.end_character
                and entity.end_character
                > existing.start_character
            )

            if same_text or contained or overlaps:
                duplicate = True
                break

        if not duplicate:
            selected.append(entity)

    return sorted(
        selected,
        key=lambda entity: (
            entity.start_character
            if entity.start_character is not None
            else 0
        ),
    )


# ============================================================
# PUBLIC API
# ============================================================

def extract_entities(
    text: str,
) -> tuple[
    list[ExtractedEntity],
    list[ExtractedEntity],
]:

    text = _normalize_text(text)

    # --------------------------------------------------------
    # Temporal entities
    # --------------------------------------------------------

    temporal_entities = (
        _extract_temporal_entities(text)
    )

    temporal_entities = _remove_duplicates(
        temporal_entities
    )

    # --------------------------------------------------------
    # Location entities
    # --------------------------------------------------------

    location_entities: list[ExtractedEntity] = []

    #
    # Named locations after movement/actions:
    #
    # travelled to Neverwinter
    # entered Temple of the Moon
    #
    location_entities.extend(
        _extract_named_locations_after_actions(
            text,
            temporal_entities,
        )
    )

    #
    # Named compounds:
    #
    # Blackstone Keep
    # Ashen Forest
    #
    location_entities.extend(
        _extract_named_location_compounds(
            text,
            temporal_entities,
        )
    )

    #
    # Generic places:
    #
    # hidden chamber
    # northern corridor
    #
    location_entities.extend(
        _extract_generic_locations(
            text,
            temporal_entities,
        )
    )

    #
    # Additional locations appearing later:
    #
    # from the current cave
    #
    location_entities.extend(
        _extract_secondary_locations(
            text,
            temporal_entities,
        )
    )

    location_entities = _remove_duplicates(
        location_entities
    )

    return (
        temporal_entities,
        location_entities,
    )