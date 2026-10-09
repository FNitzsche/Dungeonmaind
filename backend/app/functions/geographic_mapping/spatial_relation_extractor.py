"""Conservative English extraction of explicit spatial assertions.

Only supported sentence forms create edges. Negated, hypothetical and
question forms are skipped. No relation is inferred from co-occurrence.
"""
from dataclasses import dataclass
import re

from app.base_models.map_models import MapRelation


@dataclass(frozen=True)
class SpatialRelation:
    source: str
    target: str
    relation: MapRelation
    evidence: str


def normalize_location(name: str) -> str:
    """Remove articles and normalize whitespace; keep readable spelling."""
    return re.sub(r"^(?:the|a|an)\s+", "", " ".join(name.split()), flags=re.I).strip(" ,:;\"'")


_RELATIONS = {
    "north of": MapRelation.north_of, "south of": MapRelation.south_of,
    "east of": MapRelation.east_of, "west of": MapRelation.west_of,
    "near": MapRelation.near, "inside": MapRelation.inside,
    "within": MapRelation.inside, "contains": MapRelation.contains,
    "connected to": MapRelation.connected_to,
}
_PLACE = r"[A-Za-z][A-Za-z0-9'’\-]*(?:\s+[A-Za-z][A-Za-z0-9'’\-]*){0,7}"
_SPATIAL = re.compile(
    rf"^(?P<source>{_PLACE})\s+(?:is|are|was|were|lies|lie|stands|sits)\s+"
    r"(?:located\s+|situated\s+)?(?P<relation>north of|south of|east of|west of|near|inside|within|connected to)\s+"
    rf"(?P<target>{_PLACE})$", re.I,
)
_CONTAINS = re.compile(rf"^(?P<source>{_PLACE})\s+contains\s+(?P<target>{_PLACE})$", re.I)
_TRAVEL = re.compile(
    rf"^(?:we|they|the party|our party|the group)\s+(?:travelled|traveled|walked|journeyed|moved|rode|sailed)\s+"
    rf"from\s+(?P<source>{_PLACE})\s+to\s+(?P<target>{_PLACE})$", re.I,
)
_UNCERTAIN = re.compile(r"\b(?:not|never|no|might|may|could|would|should|perhaps|maybe|if|whether|plan|planned|planning|want|wanted)\b", re.I)
_NON_PLACES = {"we", "they", "he", "she", "it", "you", "i", "there", "here", "party", "group"}


def extract_spatial_relations(text: str) -> list[SpatialRelation]:
    results = []
    for match in re.finditer(r"[^.!?\n]+[.!?]?", text):
        evidence = match.group().strip()
        sentence = evidence.rstrip(".!?").strip()
        if not sentence or evidence.endswith("?") or _UNCERTAIN.search(sentence):
            continue
        relation_match = _TRAVEL.fullmatch(sentence)
        relation = MapRelation.travelled_to
        if relation_match is None:
            relation_match = _SPATIAL.fullmatch(sentence)
            if relation_match:
                relation = _RELATIONS[relation_match["relation"].casefold()]
            else:
                relation_match = _CONTAINS.fullmatch(sentence)
                relation = MapRelation.contains
        if relation_match is None:
            continue
        source = normalize_location(relation_match["source"])
        target = normalize_location(relation_match["target"])
        if source.casefold() == target.casefold() or {source.casefold(), target.casefold()} & _NON_PLACES:
            continue
        # Reject trailing clauses rather than incorporating narrative as a name.
        if re.search(r"\b(?:and|but|because|then|which|that)\b", source + " " + target, re.I):
            continue
        results.append(SpatialRelation(source, target, relation, evidence))
    return results
