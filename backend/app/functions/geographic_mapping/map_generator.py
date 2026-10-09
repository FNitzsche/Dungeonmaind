"""Build a repeatable graph from all transcription documents, not summaries."""
import math
import re
from uuid import NAMESPACE_URL, uuid5

from app.base_models.map_models import MapData, MapEdge, MapNode
from app.functions.entity_extraction.entity_extractor import (
    extract_entities, GENERIC_LOCATION_WORDS, LOCATION_DESCRIPTORS,
)
from app.functions.geographic_mapping.spatial_relation_extractor import (
    extract_spatial_relations, normalize_location,
)
from app.functions.geographic_mapping.contextual_travel_extractor import ContextualTravelExtractor


def _time(value, default=0.0):
    try:
        result = float(value)
        return max(0.0, result) if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _stable_id(kind, key):
    return str(uuid5(NAMESPACE_URL, "dungeonmaind/map/" + kind + "/" + key))


def generate_map_from_documents(documents) -> MapData:
    """Document objects must expose page_content and metadata.

    Bare generic names are scoped to their segment to avoid merging unrelated caves.
    Capitalized compound place names share one identity across segments.
    Repeated relation assertions retain separate evidence across segments.
    Consecutive confirmed travel sentences can supply contextual travel edges;
    their timestamp is the destination segment's start and evidence spans the journey.
    """
    segments = []
    for document in documents:
        text = str(document.page_content or "").strip()
        if not text:
            continue
        metadata = document.metadata or {}
        start = _time(metadata.get("start_time"))
        end = max(start, _time(metadata.get("end_time"), start))
        segments.append((start, end, text))
    segments.sort()
    # Recognize a named location consistently when later mentions use lowercase.
    known_names = set()
    vocabulary = GENERIC_LOCATION_WORDS | LOCATION_DESCRIPTORS
    for _, _, text in segments:
        _, entities = extract_entities(text)
        candidates = [normalize_location(entity.text) for entity in entities]
        for relation in extract_spatial_relations(text):
            candidates.extend((relation.source, relation.target))
        for name in candidates:
            words = name.split()
            if words and any(word[0].isupper() for word in words) and (len(words) > 1 or not all(word.casefold() in vocabulary for word in words)):
                known_names.add(name.casefold())
    context = ContextualTravelExtractor(known_names)
    contextual_segments = []
    for _, _, text in segments:
        contextual = context.extract(text)
        contextual_segments.append(contextual)
        known_names.update(name.casefold() for name in contextual[1])
    nodes, edges = {}, {}
    for index, (start, end, text) in enumerate(segments):
        contextual_relations, contextual_locations = contextual_segments[index]
        relations = extract_spatial_relations(text) + contextual_relations
        names = {name.casefold(): name for name in contextual_locations}
        # Sentence-level calls retain repeated mentions that the existing
        # entity extractor deduplicates within a single input.
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
            _, locations = extract_entities(sentence)
            for entity in locations:
                name = normalize_location(entity.text)
                if name:
                    names.setdefault(name.casefold(), name)
        for relation in relations:
            for name in (relation.source, relation.target):
                names.setdefault(name.casefold(), name)

        # Preserve every explicit relation endpoint. For isolated entities,
        # retain named places, not incidental generic rooms/roads or fragments
        # of a longer known place name ("tower" inside "Old Tower").
        endpoints = {name.casefold() for relation in relations
                     for name in (relation.source, relation.target)}
        names = {key: name for key, name in names.items()
                 if key in endpoints or (key in known_names and not any(
                     key != longer and re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", longer)
                     for longer in known_names))}

        local_ids = {}
        for normalized, name in names.items():
            # Only clearly capitalized names are treated as global identities.
            # Bare generic descriptors such as "cave" remain segment-local.
            generic = normalized not in known_names
            key = normalized + (f"|segment:{index}" if generic else "")
            node_id = _stable_id("node", key)
            local_ids[normalized] = node_id
            occurrences = len(re.findall(r"(?<!\w)" + re.escape(name).replace(r"\ ", r"\s+") + r"(?!\w)", text, re.I))
            # A contextual origin is referenced by the new edge but was actually
            # mentioned in an earlier segment; do not count a fabricated mention.
            if not occurrences and node_id in nodes:
                continue
            count = max(1, occurrences)
            if node_id in nodes:
                old = nodes[node_id]
                nodes[node_id] = old.model_copy(update={
                    "mentions": old.mentions + count, "last_seen": max(old.last_seen, end),
                })
            else:
                nodes[node_id] = MapNode(id=node_id, name=name, mentions=count, first_seen=start, last_seen=end)
        for relation in relations:
            source, target = local_ids[relation.source.casefold()], local_ids[relation.target.casefold()]
            if source == target:
                continue
            key = f"{index}|{source}|{target}|{relation.relation.value}|{relation.evidence}"
            edge_id = _stable_id("edge", key)
            edges[edge_id] = MapEdge(id=edge_id, source=source, target=target,
                relation=relation.relation, evidence=relation.evidence, timestamp=start)
    return MapData(nodes=list(nodes.values()), edges=list(edges.values()), source_segment_count=len(segments))


def generate_map_from_embeddings() -> MapData:
    # Lazy import avoids initializing the heavyweight embedding stack on GET.
    from app.functions.embedding.embedding_model import get_all_transcription_documents
    return generate_map_from_documents(get_all_transcription_documents())
