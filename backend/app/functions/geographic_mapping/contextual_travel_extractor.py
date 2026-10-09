"""Conservative travel context for consecutive sentences in transcript order.

An arrival alone establishes a current location. Only a departure or a
directional movement starts a journey. Unsupported or non-factual sentences
clear all context, and explicit relations always take precedence.
"""
import re

from app.base_models.map_models import MapRelation
from app.functions.entity_extraction.entity_extractor import (
    GENERIC_LOCATION_WORDS, LOCATION_DESCRIPTORS,
)
from app.functions.geographic_mapping.spatial_relation_extractor import (
    SpatialRelation, _NON_PLACES, _PLACE, _UNCERTAIN,
    extract_spatial_relations, normalize_location,
)


_PARTY = r"(?:we|they|the party|our party|the group)"
_DIRECTION = r"(?P<direction>north|south|east|west)(?:ern|ward)?"
_ROAD = rf"(?:the\s+)?{_DIRECTION}\s+road"
_DEPARTURE = re.compile(
    rf"^{_PARTY}\s+(?:left|departed(?:\s+from)?)\s+(?P<location>{_PLACE})$", re.I,
)
_MOVEMENT = re.compile(
    rf"^{_PARTY}\s+(?:headed\s+{_DIRECTION}|followed\s+"
    r"(?:the\s+)?(?P<road_direction>north|south|east|west)(?:ern|ward)?\s+road)$",
    re.I,
)
_ARRIVAL = re.compile(
    rf"^(?:after\s+following\s+{_ROAD},\s*)?{_PARTY}\s+"
    rf"(?:eventually\s+)?(?:reached|arrived\s+at|entered)\s+(?P<location>{_PLACE})$",
    re.I,
)
_NON_FACTUAL = re.compile(
    r"\b(?:cannot|can't|didn't|hadn't|haven't|won't|wasn't|weren't|"
    r"possibly|probably|supposedly|apparently|imagine|imagined|dreamed|intend|intended)\b",
    re.I,
)
_CLAUSE = re.compile(r"\b(?:and|but|because|then|which|that)\b", re.I)


class ContextualTravelExtractor:
    """Per-generation state; returns existing relations and confirmed names."""

    def __init__(self, known_names):
        self.known_names = set(known_names)
        self._clear()

    def _clear(self):
        self.current_location = None
        self.current_evidence = None
        self.origin = None
        self.pending_direction = None
        self.evidence = []

    def _location(self, value):
        name = normalize_location(value)
        words = name.split()
        vocabulary = GENERIC_LOCATION_WORDS | LOCATION_DESCRIPTORS
        if not words or name.casefold() in _NON_PLACES or _CLAUSE.search(name):
            return None
        # Reuse global named-place identities, but never resolve bare generic
        # references ("the tower") to an earlier named place ("Old Tower").
        if len(words) == 1 and name.casefold() in vocabulary:
            return None
        if name.casefold() not in self.known_names and not all(
            word[0].isupper() or word in {"of", "the", "de", "del", "von", "van"}
            for word in words
        ):
            return None
        self.known_names.add(name.casefold())
        return name

    def extract(self, text):
        relations, locations = [], []
        for match in re.finditer(r"[^.!?\n]+[.!?]?", text):
            evidence = match.group().strip()
            sentence = evidence.rstrip(".!?").strip()
            if evidence.endswith("?") or _UNCERTAIN.search(sentence) or _NON_FACTUAL.search(sentence):
                self._clear()
                continue

            explicit = extract_spatial_relations(evidence)
            if explicit:
                self._clear()
                if explicit[-1].relation == MapRelation.travelled_to:
                    self.current_location = self._location(explicit[-1].target)
                    self.current_evidence = evidence
                continue

            departure = _DEPARTURE.fullmatch(sentence)
            if departure:
                self._clear()
                self.current_location = self._location(departure["location"])
                self.origin = self.current_location
                if self.origin:
                    locations.append(self.origin)
                    self.evidence = [evidence]
                continue

            movement = _MOVEMENT.fullmatch(sentence)
            if movement and self.current_location:
                if not self.origin:
                    self.evidence = [self.current_evidence]
                self.origin = self.origin or self.current_location
                self.pending_direction = movement["direction"] or movement["road_direction"]
                self.evidence.append(evidence)
                continue

            arrival = _ARRIVAL.fullmatch(sentence)
            if arrival:
                destination = self._location(arrival["location"])
                if destination:
                    locations.append(destination)
                    if arrival["direction"] and self.current_location:
                        if not self.origin:
                            self.evidence = [self.current_evidence]
                        self.origin = self.origin or self.current_location
                        self.pending_direction = arrival["direction"]
                    if self.origin and self.origin.casefold() != destination.casefold():
                        relations.append(SpatialRelation(
                            source=self.origin, target=destination,
                            relation=MapRelation.travelled_to,
                            evidence=" ".join([*self.evidence, evidence]),
                        ))
                    self._clear()
                    self.current_location = destination
                    self.current_evidence = evidence
                    continue
            self._clear()
        return relations, locations
