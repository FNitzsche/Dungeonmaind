"""Domain models for DM corrections stored in map_overrides.json."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MapRename:
    """Rename a resolved place without changing its id.

    Attributes:
        location_id: Existing location id (loc_1, loc_2, ...).
        canonical_name: Replacement display name for the place.
    """

    location_id: str
    canonical_name: str


@dataclass
class MapMerge:
    """Fold one or more places into a surviving target place.

    Attributes:
        source_location_ids: Location ids absorbed into the target.
        target_location_id: Location id that remains after the merge.
    """

    source_location_ids: list[str]
    target_location_id: str


@dataclass
class MapSplit:
    """Carve a new place out of an existing one, moving selected events.

    Attributes:
        source_location_id: Location id being split.
        new_location_id: Id for the carved-out place.
        canonical_name: Display name for the new place.
        event_ids: Timeline event ids moved onto the new place.
        aliases: Optional alternative names for the new place.
    """

    source_location_id: str
    new_location_id: str
    canonical_name: str
    event_ids: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


@dataclass
class MapConnectionChange:
    """An added or removed link between two places.

    Attributes:
        from_location_id: Source location id.
        to_location_id: Destination location id.
        relationship: Kind of link (travel or proximity). None on a
            removal means drop every link between the pair.
    """

    from_location_id: str
    to_location_id: str
    relationship: str | None = None


@dataclass
class SessionMapOverrides:
    """DM corrections for one session's schematic map.

    Stored in ``map_overrides.json`` so auto-generated places and links
    can be renamed, merged, split, or rewired without regenerating.

    Attributes:
        renames: Canonical-name replacements keyed by location id.
        merges: Source places folded into a surviving target.
        splits: New places carved out of an existing place.
        added_connections: Links the DM added.
        removed_connections: Links the DM removed.
    """

    renames: list[MapRename] = field(default_factory=list)
    merges: list[MapMerge] = field(default_factory=list)
    splits: list[MapSplit] = field(default_factory=list)
    added_connections: list[MapConnectionChange] = field(default_factory=list)
    removed_connections: list[MapConnectionChange] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize this session's overrides for map_overrides.json."""
        return {
            'renames': [
                {'location_id': item.location_id, 'canonical_name': item.canonical_name}
                for item in self.renames
            ],
            'merges': [
                {
                    'source_location_ids': list(item.source_location_ids),
                    'target_location_id': item.target_location_id,
                }
                for item in self.merges
            ],
            'splits': [
                {
                    'source_location_id': item.source_location_id,
                    'new_location_id': item.new_location_id,
                    'canonical_name': item.canonical_name,
                    'event_ids': list(item.event_ids),
                    'aliases': list(item.aliases),
                }
                for item in self.splits
            ],
            'connections': {
                'added': [_connection_to_dict(item) for item in self.added_connections],
                'removed': [_connection_to_dict(item) for item in self.removed_connections],
            },
        }

    @classmethod
    def from_dict(cls, raw: dict | None) -> SessionMapOverrides:
        """Parse one session record from map_overrides.json."""
        data = raw or {}
        connections = data.get('connections') or {}
        return cls(
            renames=[
                MapRename(
                    location_id=str(item.get('location_id', '')),
                    canonical_name=str(item.get('canonical_name', '')),
                )
                for item in data.get('renames') or []
                if isinstance(item, dict)
            ],
            merges=[
                MapMerge(
                    source_location_ids=[
                        str(location_id) for location_id in item.get('source_location_ids') or []
                    ],
                    target_location_id=str(item.get('target_location_id', '')),
                )
                for item in data.get('merges') or []
                if isinstance(item, dict)
            ],
            splits=[
                MapSplit(
                    source_location_id=str(item.get('source_location_id', '')),
                    new_location_id=str(item.get('new_location_id', '')),
                    canonical_name=str(item.get('canonical_name', '')),
                    event_ids=[str(event_id) for event_id in item.get('event_ids') or []],
                    aliases=[str(alias) for alias in item.get('aliases') or []],
                )
                for item in data.get('splits') or []
                if isinstance(item, dict)
            ],
            added_connections=[
                _connection_from_dict(item) for item in connections.get('added') or []
            ],
            removed_connections=[
                _connection_from_dict(item) for item in connections.get('removed') or []
            ],
        )


def _connection_to_dict(item: MapConnectionChange) -> dict:
    payload = {'from_location_id': item.from_location_id, 'to_location_id': item.to_location_id}
    if item.relationship is not None:
        payload['relationship'] = item.relationship
    return payload


def _connection_from_dict(item: object) -> MapConnectionChange:
    data = item if isinstance(item, dict) else {}
    relationship = data.get('relationship')
    return MapConnectionChange(
        from_location_id=str(data.get('from_location_id', '')),
        to_location_id=str(data.get('to_location_id', '')),
        relationship=None if relationship is None else str(relationship),
    )
