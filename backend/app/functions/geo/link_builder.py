"""Infer directed spatial links between resolved map locations.

Turns a flat list of resolved places plus the ordered session timeline
into an actual journey with direction. Part 1 is schematic, not GPS:
there are no coordinates, only "location A connects to location B",
inferred from the order in which places appear across events.

Two kinds of link are produced:

- ``travel`` — the party's primary location changed from one event to the
  next; the edge points from the earlier place to the later one.
- ``proximity`` — two distinct places were mentioned inside a single
  event, so they are spatially associated without implied direction.

Repeated transitions between the same ordered pair are collapsed onto a
single edge (their evidence events accumulate) rather than duplicated.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.domain.map_edge import MapEdge, MapEdgeRelationship
from app.domain.map_location import MapLocation


def _event_order(event: Any) -> int:
    """Return an event's ordinal position, defaulting to 0."""
    return int(getattr(event, 'order', 0) or 0)


def _build_event_to_location_index(locations: Sequence[MapLocation]) -> dict[str, list[str]]:
    """Invert resolved locations into an event_id -> [location_id] index.

    Reuses the ``event_ids`` list the place resolver already stored on each
    MapLocation, so edges are inferred without re-matching place names.
    Location order is preserved so the primary (first-resolved) place of an
    event is deterministic.

    Args:
        locations: Resolved MapLocations for one session.

    Returns:
        Mapping from event id to the location ids that mention it, in
        resolved-location order.
    """
    index: dict[str, list[str]] = {}
    for location in locations:
        for event_id in location.event_ids:
            index.setdefault(event_id, []).append(location.id)
    return index


def build_edges(
    locations: Sequence[MapLocation], events: Sequence[Any], session_id: str | None = None
) -> list[MapEdge]:
    """Infer travel and proximity edges for one session.

    Walks the timeline in event order. Whenever the primary location
    changes between two consecutive located events, a ``travel`` edge is
    emitted from the earlier place to the later one, with both events kept
    as evidence. Whenever a single event mentions two or more distinct
    places, a ``proximity`` edge is emitted between them.

    Repeated transitions between the same ordered pair of locations are
    collapsed onto the first matching edge (evidence events accumulate),
    so the map shows one line per connection rather than duplicates.

    Args:
        locations: Resolved MapLocations for the session (from the place
            resolver). Only their ``id`` and ``event_ids`` are used.
        events: Ordered TimelineEvent list for the same session. Sorted by
            ``order`` defensively if not already sorted.
        session_id: Optional session id override. Defaults to the first
            location's session id, then the first event's, then 'default'.

    Returns:
        Inferred MapEdges in journey order, each with a sequential id and
        0-based ``order``.
    """
    ordered_events = sorted(events, key=_event_order)
    event_to_locations = _build_event_to_location_index(locations)

    resolved_session = session_id
    if resolved_session is None and locations:
        resolved_session = locations[0].session_id
    if resolved_session is None:
        for event in ordered_events:
            candidate = getattr(event, 'session_id', None)
            if candidate:
                resolved_session = str(candidate)
                break
    resolved_session = resolved_session or 'default'

    edges: list[MapEdge] = []
    # Maps (from_location_id, to_location_id, relationship) -> existing edge
    # so repeat transitions collapse onto one line instead of duplicating.
    edge_by_key: dict[tuple[str, str, MapEdgeRelationship], MapEdge] = {}

    def add_evidence(edge: MapEdge, *event_ids: str) -> None:
        for event_id in event_ids:
            if event_id and event_id not in edge.evidence_event_ids:
                edge.evidence_event_ids.append(event_id)

    def upsert_edge(
        from_id: str, to_id: str, relationship: MapEdgeRelationship, evidence: tuple[str, ...]
    ) -> None:
        key = (from_id, to_id, relationship)
        existing = edge_by_key.get(key)
        if existing is not None:
            add_evidence(existing, *evidence)
            return
        edge = MapEdge(
            id=f'edge_{len(edges) + 1}',
            session_id=resolved_session,
            from_location_id=from_id,
            to_location_id=to_id,
            relationship=relationship,
            order=len(edges),
        )
        add_evidence(edge, *evidence)
        edges.append(edge)
        edge_by_key[key] = edge

    previous_location_id: str | None = None
    previous_event_id: str | None = None

    for event in ordered_events:
        event_id = str(getattr(event, 'id', '') or '')
        location_ids = event_to_locations.get(event_id, [])

        # Proximity: distinct places named together in one event. Ordered by
        # resolved-location order and de-duplicated so A<->B is emitted once.
        distinct_here: list[str] = []
        for location_id in location_ids:
            if location_id not in distinct_here:
                distinct_here.append(location_id)
        for i in range(len(distinct_here)):
            for j in range(i + 1, len(distinct_here)):
                upsert_edge(
                    distinct_here[i], distinct_here[j], MapEdgeRelationship.proximity, (event_id,)
                )

        if not distinct_here:
            # Event mentions no resolved place; it cannot start or continue
            # a journey leg, so leave the running position untouched.
            continue

        current_location_id = distinct_here[0]
        if previous_location_id is not None and current_location_id != previous_location_id:
            upsert_edge(
                previous_location_id,
                current_location_id,
                MapEdgeRelationship.travel,
                (previous_event_id or '', event_id),
            )

        previous_location_id = current_location_id
        previous_event_id = event_id

    return edges
