"""Pydantic models for map location request/response schemas."""

from pydantic import BaseModel, Field


class MapLocationOut(BaseModel):
    """Response model for a single resolved map location.

    Attributes:
        id: Unique location identifier (loc_1, loc_2, ...).
        session_id: Session this location belongs to.
        canonical_name: Primary display name for the location.
        aliases: Alternative names that resolved to this location.
        event_ids: Timeline event IDs that mention this location.
        mention_count: Total mentions across events.
        first_order: 0-based index of the first mentioning event in the session.
    """

    id: str
    session_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    mention_count: int = 0
    first_order: int = 0


class MapLocationListResponse(BaseModel):
    """Response model for the list of resolved places in a session."""

    session_id: str
    locations: list[MapLocationOut]
    total: int


class MapEdgeOut(BaseModel):
    """Response model for a single inferred spatial link.

    Attributes:
        id: Unique edge identifier (edge_1, edge_2, ...).
        session_id: Session this edge belongs to.
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
    relationship: str
    evidence_event_ids: list[str] = Field(default_factory=list)
    order: int = 0


class MapEdgeListResponse(BaseModel):
    """Response model for the list of inferred links in a session."""

    session_id: str
    edges: list[MapEdgeOut]
    total: int


class MapGraphResponse(BaseModel):
    """Response model for a session's full map graph."""

    session_id: str
    locations: list[MapLocationOut]
    edges: list[MapEdgeOut]


class MapGenerateRequest(BaseModel):
    """Request model for generating a session's map from its timeline."""

    session_id: str = 'default'


class MapGenerateResponse(BaseModel):
    """Response model after resolving, linking, and persisting a session's map."""

    session_id: str
    locations_generated: int
    edges_generated: int
    locations: list[MapLocationOut]
    edges: list[MapEdgeOut]


class MapDeleteResponse(BaseModel):
    """Response model for a map deletion result."""

    deleted: bool
    session_id: str | None = None


class MapRenameRequest(BaseModel):
    """Rename a resolved place. Survives regenerate via map_overrides.json."""

    session_id: str = 'default'
    location_id: str
    canonical_name: str


class MapMergeRequest(BaseModel):
    """Fold source places into a surviving target place."""

    session_id: str = 'default'
    source_location_ids: list[str]
    target_location_id: str


class MapSplitRequest(BaseModel):
    """Carve a new place out of an existing one, moving selected events."""

    session_id: str = 'default'
    source_location_id: str
    canonical_name: str
    event_ids: list[str] = Field(default_factory=list)
    new_location_id: str | None = None


class MapConnectionRequest(BaseModel):
    """Add or remove a link between two places."""

    session_id: str = 'default'
    from_location_id: str
    to_location_id: str
    relationship: str | None = None
