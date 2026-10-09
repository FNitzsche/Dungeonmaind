"""Release 3 map contract. Times are recording offsets in seconds."""
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MapRelation(str, Enum):
    north_of = "north_of"
    south_of = "south_of"
    east_of = "east_of"
    west_of = "west_of"
    near = "near"
    inside = "inside"
    contains = "contains"
    connected_to = "connected_to"
    travelled_to = "travelled_to"


class MapNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    mentions: int = Field(ge=1)
    first_seen: float = Field(ge=0, allow_inf_nan=False)
    last_seen: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def check_times(self):
        if self.last_seen < self.first_seen:
            raise ValueError("last_seen must be >= first_seen")
        return self


class MapEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    relation: MapRelation
    evidence: str = Field(min_length=1)
    timestamp: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def check_endpoints(self):
        if self.source == self.target:
            raise ValueError("An edge must connect different nodes")
        return self


class MapData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: list[MapNode] = Field(default_factory=list)
    edges: list[MapEdge] = Field(default_factory=list)
    source_segment_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def check_graph(self):
        ids = {node.id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("Duplicate node IDs")
        if len({edge.id for edge in self.edges}) != len(self.edges):
            raise ValueError("Duplicate edge IDs")
        for edge in self.edges:
            if edge.source not in ids or edge.target not in ids:
                raise ValueError("Edge references an unknown node")
        return self
