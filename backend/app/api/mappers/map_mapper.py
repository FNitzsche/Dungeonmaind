"""Mappers for converting domain map models to their response schemas."""

from app.base_models.map_base_models import MapEdgeOut, MapLocationOut
from app.domain.map_edge import MapEdge
from app.domain.map_location import MapLocation


def map_location_to_out(location: MapLocation) -> MapLocationOut:
    """Map a domain MapLocation to a MapLocationOut Pydantic schema.

    Args:
        location: The domain MapLocation instance.

    Returns:
        A MapLocationOut schema instance.
    """
    return MapLocationOut(
        id=location.id,
        session_id=location.session_id,
        canonical_name=location.canonical_name,
        aliases=list(location.aliases),
        event_ids=list(location.event_ids),
        mention_count=location.mention_count,
        first_order=location.first_order,
    )


def map_edge_to_out(edge: MapEdge) -> MapEdgeOut:
    """Map a domain MapEdge to a MapEdgeOut Pydantic schema.

    Args:
        edge: The domain MapEdge instance.

    Returns:
        A MapEdgeOut schema instance.
    """
    return MapEdgeOut(
        id=edge.id,
        session_id=edge.session_id,
        from_location_id=edge.from_location_id,
        to_location_id=edge.to_location_id,
        relationship=edge.relationship.value,
        evidence_event_ids=list(edge.evidence_event_ids),
        order=edge.order,
    )
