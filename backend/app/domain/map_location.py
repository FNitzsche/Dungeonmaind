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
        first_order: 0-based index of the first mentioning event in the
            ordered session timeline.
    """

    id: str
    session_id: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    mention_count: int = 0
    first_order: int = 0

    def to_dict(self) -> dict:
        """Serialize this location for timeline/map export."""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'canonical_name': self.canonical_name,
            'aliases': list(self.aliases),
            'event_ids': list(self.event_ids),
            'mention_count': self.mention_count,
            'first_order': self.first_order,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MapLocation:
        """Deserialize a location written by export."""
        return cls(
            id=data['id'],
            session_id=data['session_id'],
            canonical_name=data['canonical_name'],
            aliases=list(data.get('aliases', [])),
            event_ids=list(data.get('event_ids', [])),
            mention_count=int(data.get('mention_count', 0)),
            first_order=int(data.get('first_order', 0)),
        )
