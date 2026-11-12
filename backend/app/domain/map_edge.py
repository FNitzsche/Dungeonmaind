"""Domain model for inferred spatial links between map locations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MapEdgeRelationship(StrEnum):
    """How two locations are spatially related on the schematic map."""

    travel = 'travel'
    proximity = 'proximity'


@dataclass
class MapEdge:
    """A directed link between two canonical locations in a session.

    Edges are inferred from the party's timeline, not from coordinates:
    a ``travel`` edge records that the party moved from one place to the
    next across consecutive events, while a ``proximity`` edge records
    that two places were mentioned together within a single event.

    Attributes:
        id: Unique edge identifier (edge_1, edge_2, ...).
        session_id: Identifier for the session this edge belongs to.
        from_location_id: Source location id (loc_1, loc_2, ...).
        to_location_id: Destination location id.
        relationship: Kind of link (travel or proximity).
        evidence_event_ids: Timeline event IDs that support this edge.
        order: 0-based position of the edge in the inferred journey.
    """

    id: str
    session_id: str
    from_location_id: str
    to_location_id: str
    relationship: MapEdgeRelationship = field(default_factory=lambda: MapEdgeRelationship.travel)
    evidence_event_ids: list[str] = field(default_factory=list)
    order: int = 0

    def to_dict(self) -> dict:
        """Serialize this edge for timeline/map export."""
        relationship = self.relationship
        return {
            'id': self.id,
            'session_id': self.session_id,
            'from_location_id': self.from_location_id,
            'to_location_id': self.to_location_id,
            'relationship': relationship.value
            if isinstance(relationship, MapEdgeRelationship)
            else str(relationship),
            'evidence_event_ids': list(self.evidence_event_ids),
            'order': self.order,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MapEdge:
        """Deserialize an edge written by export."""
        return cls(
            id=data['id'],
            session_id=data['session_id'],
            from_location_id=data['from_location_id'],
            to_location_id=data['to_location_id'],
            relationship=MapEdgeRelationship(data.get('relationship', 'travel')),
            evidence_event_ids=list(data.get('evidence_event_ids', [])),
            order=int(data.get('order', 0)),
        )
