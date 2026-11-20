"""Orchestrates place resolution and link inference into one saved map.

Glues together the place resolver and the link builder: fetch a session's
ordered timeline events, resolve them into places, infer the links between
those places, reapply any saved DM overrides, and persist the result.
This is the /map/generate entry point — no new matching or inference
logic lives here.
"""

from __future__ import annotations

from app.domain.map_edge import MapEdge
from app.domain.map_location import MapLocation
from app.domain.map_store import map_store
from app.domain.timeline_store import timeline_store
from app.functions.geo.link_builder import build_edges
from app.functions.geo.map_overrides import apply_map_overrides, load_session_overrides
from app.functions.geo.place_resolver import resolve_locations


async def generate_map(session_id: str) -> tuple[list[MapLocation], list[MapEdge]]:
    """Rebuild a session's map from scratch, then reapply saved overrides.

    Ignores any previously saved graph. Places and links are inferred
    again from the current timeline, then map_overrides.json corrections
    for this session are applied so DM edits survive regenerate.

    Args:
        session_id: The session identifier.

    Returns:
        A tuple of (MapLocations, MapEdges) after overrides, in the same
        order they were saved to the MapStore.
    """
    events = await timeline_store.get_session_events(session_id)
    locations = resolve_locations(events, existing=[], session_id=session_id)
    edges = build_edges(locations, events, session_id=session_id)
    locations, edges = apply_map_overrides(
        locations, edges, load_session_overrides(session_id)
    )
    await map_store.save_map(session_id, locations, edges)
    return locations, edges
