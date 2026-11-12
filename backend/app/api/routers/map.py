"""REST API router for a session's map: places, links, and the full graph.

Locations and edges are read from MapStore once POST /map/generate has run
for a session. Until then, the read endpoints fall back to resolving them
live from the in-memory timeline event list, so Places/Links lookups keep
working standalone without requiring generation first.
"""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.mappers.map_mapper import map_edge_to_out, map_location_to_out
from app.api.mappers.timeline_mapper import timeline_event_to_out
from app.base_models.map_base_models import (
    MapDeleteResponse,
    MapEdgeListResponse,
    MapGenerateRequest,
    MapGenerateResponse,
    MapGraphResponse,
    MapLocationListResponse,
    MapLocationOut,
)
from app.base_models.timeline_base_models import TimelineEventListResponse
from app.domain.map_edge import MapEdge
from app.domain.map_location import MapLocation
from app.domain.map_store import map_store
from app.domain.models import TimelineEvent
from app.domain.timeline_store import timeline_store
from app.functions.geo.build_map import generate_map
from app.functions.geo.link_builder import build_edges
from app.functions.geo.place_resolver import resolve_locations

router = APIRouter()


async def _session_events_and_locations(
    session_id: str,
) -> tuple[list[TimelineEvent], list[MapLocation]]:
    """Get a session's events and its resolved map locations.

    Prefers the locations saved by /map/generate; falls back to resolving
    them live from the in-memory timeline event list if nothing has been
    generated yet for this session.
    """
    events = await timeline_store.get_session_events(session_id)
    stored_locations = await map_store.get_locations(session_id)
    if stored_locations is not None:
        return events, stored_locations
    return events, resolve_locations(events, session_id=session_id)


async def _session_edges(session_id: str) -> tuple[list[MapLocation], list[MapEdge]]:
    """Get a session's resolved locations and inferred edges.

    Prefers the edges saved by /map/generate; falls back to inferring them
    live from the resolved locations if nothing has been generated yet.
    """
    events, locations = await _session_events_and_locations(session_id)
    stored_edges = await map_store.get_edges(session_id)
    if stored_edges is not None:
        return locations, stored_edges
    return locations, build_edges(locations, events, session_id=session_id)


@router.get('/locations', response_model=MapLocationListResponse)
async def list_locations(
    session_id: str = Query('default', description='Session identifier'),
) -> MapLocationListResponse:
    """List resolved map places for a session.

    Normalizes, dedupes, and alias-merges location_entities from the
    session's ordered timeline events. Reads MapStore when a map has been
    generated, otherwise resolves places live from the timeline.

    Args:
        session_id: Session identifier (default 'default').

    Returns:
        MapLocationListResponse with one MapLocationOut per resolved place.
    """
    _, locations = await _session_events_and_locations(session_id)
    return MapLocationListResponse(
        session_id=session_id,
        locations=[map_location_to_out(location) for location in locations],
        total=len(locations),
    )


@router.get('/locations/{location_id}/events', response_model=TimelineEventListResponse)
async def list_location_events(
    location_id: str, session_id: str = Query('default', description='Session identifier')
) -> TimelineEventListResponse:
    """List timeline events linked to a resolved map place.

    Reads event_ids already stored on the MapLocation and fetches those
    TimelineEvents. Does not re-scan location names.

    Args:
        location_id: Resolved place id (loc_1, loc_2, ...).
        session_id: Session identifier (default 'default').

    Returns:
        TimelineEventListResponse for the linked events.

    Raises:
        HTTPException 404: If the location is not found in the session.
    """
    events, locations = await _session_events_and_locations(session_id)
    location = next((item for item in locations if item.id == location_id), None)
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Location not found')

    events_by_id = {event.id: event for event in events}
    linked = [events_by_id[event_id] for event_id in location.event_ids if event_id in events_by_id]
    return TimelineEventListResponse(
        session_id=session_id,
        events=[timeline_event_to_out(event) for event in linked],
        total=len(linked),
    )


@router.get('/events/{event_id}/location', response_model=MapLocationOut)
async def get_event_location(
    event_id: str, session_id: str = Query('default', description='Session identifier')
) -> MapLocationOut:
    """Find the resolved map place linked to a timeline event.

    Reverse of GET /locations/{location_id}/events: scans resolved
    locations for the first whose event_ids contains this event.

    Args:
        event_id: Timeline event id (evt_4, ...).
        session_id: Session identifier (default 'default').

    Returns:
        MapLocationOut for the matching place.

    Raises:
        HTTPException 404: If no location lists this event.
    """
    _, locations = await _session_events_and_locations(session_id)
    location = next((item for item in locations if event_id in item.event_ids), None)
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Location not found')
    return map_location_to_out(location)


@router.get('/events/{event_id}/locations', response_model=MapLocationListResponse)
async def list_event_locations(
    event_id: str, session_id: str = Query('default', description='Session identifier')
) -> MapLocationListResponse:
    """List resolved map places linked to a timeline event.

    Reverse of GET /locations/{location_id}/events: returns every location
    whose event_ids contains this event.

    Args:
        event_id: Timeline event id (evt_4, ...).
        session_id: Session identifier (default 'default').

    Returns:
        MapLocationListResponse with the matching places.

    Raises:
        HTTPException 404: If no location lists this event.
    """
    _, locations = await _session_events_and_locations(session_id)
    matched = [item for item in locations if event_id in item.event_ids]
    if not matched:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Location not found')
    return MapLocationListResponse(
        session_id=session_id,
        locations=[map_location_to_out(item) for item in matched],
        total=len(matched),
    )


@router.get('/edges', response_model=MapEdgeListResponse)
async def list_edges(
    session_id: str = Query('default', description='Session identifier'),
) -> MapEdgeListResponse:
    """List inferred spatial links for a session.

    Resolves the session's places, then infers the travel and proximity
    edges between them from the ordered timeline. Reads MapStore when a map
    has been generated, otherwise infers links live from the timeline.

    Args:
        session_id: Session identifier (default 'default').

    Returns:
        MapEdgeListResponse with one MapEdgeOut per inferred link.
    """
    _, edges = await _session_edges(session_id)
    return MapEdgeListResponse(
        session_id=session_id, edges=[map_edge_to_out(edge) for edge in edges], total=len(edges)
    )


@router.get('/locations/{location_id}/edges', response_model=MapEdgeListResponse)
async def list_location_edges(
    location_id: str, session_id: str = Query('default', description='Session identifier')
) -> MapEdgeListResponse:
    """List the inferred links that touch one resolved place.

    Returns every edge whose source or destination is this location, so the
    frontend can highlight the connections into and out of a single pin.

    Args:
        location_id: Resolved place id (loc_1, loc_2, ...).
        session_id: Session identifier (default 'default').

    Returns:
        MapEdgeListResponse with the edges touching this location (possibly
        empty if the place has no inferred links).

    Raises:
        HTTPException 404: If the location is not found in the session.
    """
    locations, edges = await _session_edges(session_id)
    if not any(item.id == location_id for item in locations):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Location not found')

    touching = [
        edge for edge in edges if location_id in (edge.from_location_id, edge.to_location_id)
    ]
    return MapEdgeListResponse(
        session_id=session_id,
        edges=[map_edge_to_out(edge) for edge in touching],
        total=len(touching),
    )


@router.post('/generate', response_model=MapGenerateResponse)
async def generate_session_map(req: MapGenerateRequest) -> MapGenerateResponse:
    """Resolve places, infer links, and persist a session's map.

    Runs the full pipeline: fetches the session's timeline events, resolves
    them into places, infers the links between those places, and saves both
    into MapStore so later reads (including this session's other map
    endpoints) return the same persisted graph.

    Args:
        req: MapGenerateRequest with the session_id to generate.

    Returns:
        MapGenerateResponse with the counts and full contents of the
        generated graph.
    """
    locations, edges = await generate_map(req.session_id)
    return MapGenerateResponse(
        session_id=req.session_id,
        locations_generated=len(locations),
        edges_generated=len(edges),
        locations=[map_location_to_out(location) for location in locations],
        edges=[map_edge_to_out(edge) for edge in edges],
    )


@router.get('', response_model=MapGraphResponse)
async def get_map(
    session_id: str = Query('default', description='Session identifier'),
) -> MapGraphResponse:
    """Get the full map graph for a session.

    Returns the locations and edges saved by POST /map/generate; falls back
    to resolving them live if nothing has been generated yet for this
    session.

    Args:
        session_id: Session identifier (default 'default').

    Returns:
        MapGraphResponse with the session's locations and edges.
    """
    locations, edges = await _session_edges(session_id)
    return MapGraphResponse(
        session_id=session_id,
        locations=[map_location_to_out(location) for location in locations],
        edges=[map_edge_to_out(edge) for edge in edges],
    )


@router.delete('', response_model=MapDeleteResponse)
async def delete_map(
    session_id: str = Query('default', description='Session identifier'),
) -> MapDeleteResponse:
    """Clear a session's saved map.

    Args:
        session_id: Session identifier (default 'default').

    Returns:
        MapDeleteResponse indicating whether a saved map was removed.
    """
    deleted = await map_store.clear_session(session_id)
    return MapDeleteResponse(deleted=deleted, session_id=session_id)
