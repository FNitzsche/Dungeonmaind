"""Domain model for canonical map locations within a session."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MapLocation:
    """A canonical location referenced across timeline events in a session.

    Attributes:
        id: Unique location identifier.
        session_id: Identifier for the session this location belongs to.
        canonical_name: Primary display name for the location.
        aliases: Alternative names or spellings for the same location.
        event_ids: Timeline event IDs that mention this location.
        mention_count: Total number of mentions across events.
        first_order: Timeline order of the first event that mentions this location.
    """

    id: str
    session_id: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    mention_count: int = 0
    first_order: int = 0
