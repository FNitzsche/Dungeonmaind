"""Load, save, and apply DM map corrections from map_overrides.json.

``map_overrides.json`` is the durable store for DM edits: place renames,
merges, splits, and added or removed connections. Auto-generated maps stay
untouched; these overrides are reapplied on regenerate and on read so
corrections survive a from-scratch rebuild.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from app.core.config import settings
from app.domain.map_edge import MapEdge, MapEdgeRelationship
from app.domain.map_location import MapLocation
from app.domain.map_overrides import (
    MapConnectionChange,
    MapMerge,
    MapRename,
    MapSplit,
    SessionMapOverrides,
)

_EMPTY_DOCUMENT = {'sessions': {}}


def default_overrides_path() -> Path:
    """Return the path of the shared map_overrides.json store."""
    return Path(settings.backend_root_path) / 'data' / 'map_overrides.json'


def load_overrides_document(path: Path | None = None) -> dict:
    """Read the full map_overrides.json document.

    Args:
        path: Optional override path. Defaults to backend/data/map_overrides.json.

    Returns:
        The parsed document. Missing or invalid files yield an empty store.
    """
    store_path = path or default_overrides_path()
    try:
        raw = json.loads(store_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {'sessions': {}}
    if not isinstance(raw, dict):
        return {'sessions': {}}
    sessions = raw.get('sessions')
    if not isinstance(sessions, dict):
        return {'sessions': {}}
    return {'sessions': sessions}


def load_session_overrides(session_id: str, path: Path | None = None) -> SessionMapOverrides:
    """Load DM corrections for one session.

    Args:
        session_id: Session identifier.
        path: Optional override path.

    Returns:
        The session's overrides, or an empty set if none are stored.
    """
    document = load_overrides_document(path)
    return SessionMapOverrides.from_dict(document['sessions'].get(session_id))


def save_session_overrides(
    session_id: str, overrides: SessionMapOverrides, path: Path | None = None
) -> None:
    """Write one session's DM corrections into map_overrides.json.

    Args:
        session_id: Session identifier.
        overrides: Corrections to persist for the session.
        path: Optional override path.
    """
    store_path = path or default_overrides_path()
    document = load_overrides_document(store_path)
    payload = overrides.to_dict()
    connections = payload['connections']
    empty = not (
        payload['renames']
        or payload['merges']
        or payload['splits']
        or connections['added']
        or connections['removed']
    )
    if empty:
        document['sessions'].pop(session_id, None)
    else:
        document['sessions'][session_id] = payload
    _write_document(store_path, document)


def record_rename(
    session_id: str, location_id: str, canonical_name: str, path: Path | None = None
) -> SessionMapOverrides:
    """Store a place rename, replacing any earlier rename of the same id."""
    overrides = load_session_overrides(session_id, path)
    overrides.renames = [item for item in overrides.renames if item.location_id != location_id]
    overrides.renames.append(MapRename(location_id=location_id, canonical_name=canonical_name))
    save_session_overrides(session_id, overrides, path)
    return overrides


def record_merge(
    session_id: str,
    source_location_ids: list[str],
    target_location_id: str,
    path: Path | None = None,
) -> SessionMapOverrides:
    """Store a merge of source places into a surviving target."""
    overrides = load_session_overrides(session_id, path)
    overrides.merges.append(
        MapMerge(
            source_location_ids=list(source_location_ids), target_location_id=target_location_id
        )
    )
    save_session_overrides(session_id, overrides, path)
    return overrides


def record_split(
    session_id: str,
    source_location_id: str,
    new_location_id: str,
    canonical_name: str,
    event_ids: list[str] | None = None,
    aliases: list[str] | None = None,
    path: Path | None = None,
) -> SessionMapOverrides:
    """Store a split that carves a new place out of an existing one."""
    overrides = load_session_overrides(session_id, path)
    overrides.splits.append(
        MapSplit(
            source_location_id=source_location_id,
            new_location_id=new_location_id,
            canonical_name=canonical_name,
            event_ids=list(event_ids or []),
            aliases=list(aliases or []),
        )
    )
    save_session_overrides(session_id, overrides, path)
    return overrides


def record_added_connection(
    session_id: str,
    from_location_id: str,
    to_location_id: str,
    relationship: str = 'travel',
    path: Path | None = None,
) -> SessionMapOverrides:
    """Store an added connection, cancelling a matching removal if present."""
    overrides = load_session_overrides(session_id, path)
    overrides.removed_connections = [
        item
        for item in overrides.removed_connections
        if not _same_connection(item, from_location_id, to_location_id, relationship)
    ]
    if not any(
        _same_connection(item, from_location_id, to_location_id, relationship)
        for item in overrides.added_connections
    ):
        overrides.added_connections.append(
            MapConnectionChange(
                from_location_id=from_location_id,
                to_location_id=to_location_id,
                relationship=relationship,
            )
        )
    save_session_overrides(session_id, overrides, path)
    return overrides


def record_removed_connection(
    session_id: str,
    from_location_id: str,
    to_location_id: str,
    relationship: str | None = None,
    path: Path | None = None,
) -> SessionMapOverrides:
    """Store a removed connection, cancelling a matching addition if present."""
    overrides = load_session_overrides(session_id, path)
    overrides.added_connections = [
        item
        for item in overrides.added_connections
        if not _same_connection(item, from_location_id, to_location_id, relationship)
    ]
    if not any(
        _same_connection(item, from_location_id, to_location_id, relationship)
        for item in overrides.removed_connections
    ):
        overrides.removed_connections.append(
            MapConnectionChange(
                from_location_id=from_location_id,
                to_location_id=to_location_id,
                relationship=relationship,
            )
        )
    save_session_overrides(session_id, overrides, path)
    return overrides


def apply_map_overrides(
    locations: list[MapLocation], edges: list[MapEdge], overrides: SessionMapOverrides
) -> tuple[list[MapLocation], list[MapEdge]]:
    """Apply stored DM corrections onto an auto-generated map graph.

    Order: renames, then splits, then merges, then removed connections,
    then added connections. Splits run before merges so a place that was
    carved out and later absorbed stays gone. Operations that no longer
    match the graph (already-merged sources, existing split ids) are
    skipped so applying twice is safe.

    Args:
        locations: Auto-generated map locations.
        edges: Auto-generated map edges.
        overrides: DM corrections for the same session.

    Returns:
        A new (locations, edges) pair with corrections applied.
    """
    next_locations = [_copy_location(location) for location in locations]
    next_edges = [_copy_edge(edge) for edge in edges]

    for rename in overrides.renames:
        _apply_rename(next_locations, rename)
    for split in overrides.splits:
        next_locations = _apply_split(next_locations, split)
    for merge in overrides.merges:
        next_locations, next_edges = _apply_merge(next_locations, next_edges, merge)
    next_edges = _apply_removed_connections(next_edges, overrides.removed_connections)
    next_edges = _apply_added_connections(next_locations, next_edges, overrides.added_connections)
    return next_locations, next_edges


def _write_document(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document or _EMPTY_DOCUMENT, indent=4, ensure_ascii=False) + '\n'
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    tmp_path.write_text(payload, encoding='utf-8')
    tmp_path.replace(path)


def _copy_location(location: MapLocation) -> MapLocation:
    return replace(location, aliases=list(location.aliases), event_ids=list(location.event_ids))


def _copy_edge(edge: MapEdge) -> MapEdge:
    return replace(edge, evidence_event_ids=list(edge.evidence_event_ids))


def _same_connection(
    item: MapConnectionChange, from_id: str, to_id: str, relationship: str | None
) -> bool:
    if item.from_location_id != from_id or item.to_location_id != to_id:
        return False
    if relationship is None or item.relationship is None:
        return True
    return _normalize_relationship(item.relationship) == _normalize_relationship(relationship)


def _normalize_relationship(value: str | None) -> MapEdgeRelationship:
    token = (value or '').strip().lower()
    if token in {'travel', 'traveled'}:
        return MapEdgeRelationship.travel
    return MapEdgeRelationship.proximity


def _apply_rename(locations: list[MapLocation], rename: MapRename) -> None:
    name = rename.canonical_name.strip()
    if not rename.location_id or not name:
        return
    for location in locations:
        if location.id != rename.location_id:
            continue
        if location.canonical_name != name and name not in location.aliases:
            location.aliases = [location.canonical_name, *location.aliases]
        location.canonical_name = name
        location.aliases = [alias for alias in location.aliases if alias != name]
        return


def _apply_merge(
    locations: list[MapLocation], edges: list[MapEdge], merge: MapMerge
) -> tuple[list[MapLocation], list[MapEdge]]:
    target_id = merge.target_location_id
    source_ids = [item for item in merge.source_location_ids if item and item != target_id]
    if not target_id or not source_ids:
        return locations, edges

    by_id = {location.id: location for location in locations}
    target = by_id.get(target_id)
    if target is None:
        return locations, edges

    remap = {source_id: target_id for source_id in source_ids if source_id in by_id}
    if not remap:
        return locations, edges

    for source_id in remap:
        source = by_id[source_id]
        for alias in [source.canonical_name, *source.aliases]:
            if alias and alias != target.canonical_name and alias not in target.aliases:
                target.aliases.append(alias)
        for event_id in source.event_ids:
            if event_id not in target.event_ids:
                target.event_ids.append(event_id)
        target.mention_count = len(target.event_ids)
        target.first_order = min(target.first_order, source.first_order)

    kept_locations = [location for location in locations if location.id not in remap]
    return kept_locations, _retarget_edges(
        edges, remap, {location.id for location in kept_locations}
    )


def _apply_split(locations: list[MapLocation], split: MapSplit) -> list[MapLocation]:
    source = next((item for item in locations if item.id == split.source_location_id), None)
    if source is None:
        return locations
    new_id = split.new_location_id.strip() or _next_location_id(locations)
    if new_id == source.id:
        return locations
    if any(item.id == new_id for item in locations):
        return locations

    moved = [event_id for event_id in split.event_ids if event_id in source.event_ids]
    source.event_ids = [event_id for event_id in source.event_ids if event_id not in moved]
    source.mention_count = len(source.event_ids)

    locations.append(
        MapLocation(
            id=new_id,
            session_id=source.session_id,
            canonical_name=split.canonical_name.strip() or new_id,
            aliases=list(split.aliases),
            event_ids=moved,
            mention_count=len(moved),
            first_order=source.first_order,
        )
    )
    return locations


def _apply_removed_connections(
    edges: list[MapEdge], removals: list[MapConnectionChange]
) -> list[MapEdge]:
    kept: list[MapEdge] = []
    for edge in edges:
        if any(_matches_edge(edge, item) for item in removals):
            continue
        kept.append(edge)
    return _resequence_edges(kept)


def _apply_added_connections(
    locations: list[MapLocation], edges: list[MapEdge], additions: list[MapConnectionChange]
) -> list[MapEdge]:
    known_ids = {location.id for location in locations}
    session_id = (
        locations[0].session_id if locations else (edges[0].session_id if edges else 'default')
    )
    next_edges = list(edges)
    for addition in additions:
        from_id = addition.from_location_id
        to_id = addition.to_location_id
        if not from_id or not to_id or from_id == to_id:
            continue
        if from_id not in known_ids or to_id not in known_ids:
            continue
        relationship = _normalize_relationship(addition.relationship or 'travel')
        if any(
            edge.from_location_id == from_id
            and edge.to_location_id == to_id
            and edge.relationship == relationship
            for edge in next_edges
        ):
            continue
        next_edges.append(
            MapEdge(
                id=f'edge_{len(next_edges) + 1}',
                session_id=session_id,
                from_location_id=from_id,
                to_location_id=to_id,
                relationship=relationship,
                order=len(next_edges),
            )
        )
    return _resequence_edges(next_edges)


def _matches_edge(edge: MapEdge, change: MapConnectionChange) -> bool:
    if edge.from_location_id != change.from_location_id:
        return False
    if edge.to_location_id != change.to_location_id:
        return False
    if change.relationship is None:
        return True
    return edge.relationship == _normalize_relationship(change.relationship)


def _retarget_edges(
    edges: list[MapEdge], remap: dict[str, str], known_ids: set[str]
) -> list[MapEdge]:
    collapsed: list[MapEdge] = []
    seen: dict[tuple[str, str, MapEdgeRelationship], MapEdge] = {}
    for edge in edges:
        from_id = remap.get(edge.from_location_id, edge.from_location_id)
        to_id = remap.get(edge.to_location_id, edge.to_location_id)
        if from_id == to_id or from_id not in known_ids or to_id not in known_ids:
            continue
        key = (from_id, to_id, edge.relationship)
        existing = seen.get(key)
        if existing is None:
            updated = replace(
                edge,
                from_location_id=from_id,
                to_location_id=to_id,
                evidence_event_ids=list(edge.evidence_event_ids),
            )
            seen[key] = updated
            collapsed.append(updated)
            continue
        for event_id in edge.evidence_event_ids:
            if event_id not in existing.evidence_event_ids:
                existing.evidence_event_ids.append(event_id)
    return _resequence_edges(collapsed)


def _resequence_edges(edges: list[MapEdge]) -> list[MapEdge]:
    sequenced: list[MapEdge] = []
    for index, edge in enumerate(edges):
        sequenced.append(replace(edge, id=f'edge_{index + 1}', order=index))
    return sequenced


def next_location_id(
    locations: list[MapLocation],
    overrides: SessionMapOverrides | None = None,
) -> str:
    """Return a loc_N id not used by the graph or stored DM corrections.

    New splits must not reuse an id that a later merge still names, or the
    new pin is created and then immediately absorbed.
    """
    highest = 0
    for location_id in _known_location_ids(locations, overrides):
        if not location_id.startswith('loc_'):
            continue
        suffix = location_id.removeprefix('loc_')
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f'loc_{highest + 1}'


def _next_location_id(
    locations: list[MapLocation],
    overrides: SessionMapOverrides | None = None,
) -> str:
    return next_location_id(locations, overrides)


def _known_location_ids(
    locations: list[MapLocation],
    overrides: SessionMapOverrides | None = None,
) -> set[str]:
    ids = {location.id for location in locations if location.id}
    if overrides is None:
        return ids
    for rename in overrides.renames:
        ids.add(rename.location_id)
    for merge in overrides.merges:
        ids.add(merge.target_location_id)
        ids.update(merge.source_location_ids)
    for split in overrides.splits:
        ids.add(split.source_location_id)
        ids.add(split.new_location_id)
    for change in (*overrides.added_connections, *overrides.removed_connections):
        ids.add(change.from_location_id)
        ids.add(change.to_location_id)
    return {item for item in ids if item}
