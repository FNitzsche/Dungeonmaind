"""Deterministic contextual travel through the existing map generator."""
import pytest

from test_map_generator import document
from test_map_regressions import named_relationships
from app.base_models.map_models import MapRelation
from app.functions.geographic_mapping.map_generator import generate_map_from_documents
from app.functions.geographic_mapping.spatial_relation_extractor import extract_spatial_relations


def documents(*sentences):
    return [document(text, index * 2, index * 2 + 1)
            for index, text in enumerate(sentences)]


@pytest.mark.parametrize("sentences, source, target", [
    (("We left Rivertown.", "We headed north.", "We reached Stonebridge."),
     "Rivertown", "Stonebridge"),
    (("We left Rivertown.", "We followed the northern road.",
      "We eventually reached Stonebridge."), "Rivertown", "Stonebridge"),
    (("We left Rivertown.", "We headed north.", "We arrived at Stonebridge."),
     "Rivertown", "Stonebridge"),
    (("We departed Pine Forest.", "We followed the eastern road.",
      "We arrived at Old Tower."), "Pine Forest", "Old Tower"),
    (("We departed Pine Forest.", "After following the eastern road, we reached Old Tower."),
     "Pine Forest", "Old Tower"),
    (("We departed from Pine Forest.", "We entered Old Tower."),
     "Pine Forest", "Old Tower"),
])
def test_contextual_journey(sentences, source, target):
    graph = generate_map_from_documents(documents(*sentences))

    assert named_relationships(graph) == [(source, target, MapRelation.travelled_to)]
    assert {node.name for node in graph.nodes} == {source, target}
    assert len(graph.nodes) == 2
    assert graph.edges[0].evidence == " ".join(sentences)
    assert graph.edges[0].timestamp == (len(sentences) - 1) * 2
    nodes = {node.name: node for node in graph.nodes}
    assert nodes[source].mentions == nodes[target].mentions == 1
    assert (nodes[source].first_seen, nodes[source].last_seen) == (0, 1)


@pytest.mark.parametrize("statement", [
    "We planned to leave Rivertown and go to Stonebridge.",
    "Maybe Stonebridge is north of Rivertown.",
    "We might have left Rivertown.",
    "We did not leave Rivertown.",
    "Did we leave Rivertown?",
])
def test_non_factual_statements_do_not_start_journeys(statement):
    graph = generate_map_from_documents(documents(
        statement, "We headed north.", "We reached Stonebridge.",
    ))
    assert graph.edges == []


@pytest.mark.parametrize("interruption", [
    "We searched the abandoned rooms.",
    "We rested for the night.",
    "We did not reach Stonebridge.",
    "We didn't reach Stonebridge.",
    "We might reach Stonebridge.",
    "Have we reached Stonebridge?",
    "Maybe Stonebridge is north of Rivertown.",
    "We planned to travel to Stonebridge.",
    "We reached Stonebridge and searched the rooms.",
    "Hill Village is north of Old Tower.",
])
def test_pending_context_is_cleared_by_unrelated_or_non_factual_sentences(interruption):
    graph = generate_map_from_documents(documents(
        "We left Rivertown.", "We headed north.", interruption,
        "We followed the eastern road.", "We arrived at Old Tower.",
    ))
    assert all(edge.relation != MapRelation.travelled_to for edge in graph.edges)


def test_arrival_establishes_current_location_and_completion_clears_pending_state():
    graph = generate_map_from_documents(documents(
        "We arrived at Rivertown.", "We headed north.", "We reached Stonebridge.",
        "We arrived at Pine Forest.",
    ))
    assert named_relationships(graph) == [
        ("Rivertown", "Stonebridge", MapRelation.travelled_to),
    ]
    assert graph.edges[0].evidence == (
        "We arrived at Rivertown. We headed north. We reached Stonebridge."
    )


def test_journey_within_one_segment_keeps_sentence_order():
    graph = generate_map_from_documents(documents(
        "We left Rivertown. We followed the northern road. We eventually reached Stonebridge.",
    ))
    assert named_relationships(graph) == [
        ("Rivertown", "Stonebridge", MapRelation.travelled_to),
    ]
    assert graph.edges[0].timestamp == 0


def test_direction_and_arrival_without_a_known_origin_do_not_create_travel():
    graph = generate_map_from_documents(documents(
        "We headed north.", "We arrived at Stonebridge.",
    ))
    assert graph.edges == []


def test_new_departure_replaces_previous_origin_and_direction():
    graph = generate_map_from_documents(documents(
        "We left Rivertown.", "We headed north.", "We departed Pine Forest.",
        "We followed the eastern road.", "We reached Old Tower.",
    ))
    assert named_relationships(graph) == [
        ("Pine Forest", "Old Tower", MapRelation.travelled_to),
    ]
    assert graph.edges[0].evidence == (
        "We departed Pine Forest. We followed the eastern road. We reached Old Tower."
    )


def test_contextual_normalization_and_repeat_generation():
    transcript = documents(
        "We left the Old Tower.", "We headed east.", "We reached Pine Forest.",
        "We departed pine forest.", "We entered old tower.",
    )
    first = generate_map_from_documents(transcript)
    assert first == generate_map_from_documents(transcript)
    assert first == generate_map_from_documents(reversed(transcript))
    assert {node.name for node in first.nodes} == {"Old Tower", "Pine Forest"}
    assert len(first.nodes) == 2
    assert named_relationships(first) == [
        ("Old Tower", "Pine Forest", MapRelation.travelled_to),
        ("Pine Forest", "Old Tower", MapRelation.travelled_to),
    ]
    assert all(node.mentions == 2 for node in first.nodes)


def test_context_does_not_leak_between_generations():
    assert generate_map_from_documents(documents(
        "We left Rivertown.", "We headed north.",
    )).edges == []
    assert generate_map_from_documents(documents("We reached Stonebridge.")).edges == []


@pytest.mark.parametrize("destination", ["the tower", "the gate", "abandoned rooms", "Rivertown"])
def test_generic_destinations_and_self_travel_do_not_create_edges(destination):
    graph = generate_map_from_documents(documents(
        "We left Rivertown.", "We headed north.", f"We entered {destination}.",
    ))
    assert graph.edges == []
    assert {node.name for node in graph.nodes} == {"Rivertown"}


def test_explicit_path_preserves_relations_evidence_timestamps_and_mentions():
    sentences = (
        "Stonebridge is north of Rivertown.",
        "We travelled from Rivertown to Stonebridge.",
        "Pine Forest is east of Stonebridge.",
    )
    graph = generate_map_from_documents(documents(*sentences))
    names = {node.id: node.name for node in graph.nodes}
    expected = [relation for sentence in sentences for relation in extract_spatial_relations(sentence)]
    assert [(names[edge.source], names[edge.target], edge.relation, edge.evidence, edge.timestamp)
            for edge in graph.edges] == [
        (relation.source, relation.target, relation.relation, relation.evidence, index * 2)
        for index, relation in enumerate(expected)
    ]
    assert {node.name: node.mentions for node in graph.nodes} == {
        "Stonebridge": 3, "Rivertown": 2, "Pine Forest": 1,
    }


def test_explicit_travel_takes_precedence_and_establishes_new_current_location():
    graph = generate_map_from_documents(documents(
        "We left Old Tower.", "We headed north.",
        "We travelled from Rivertown to Stonebridge.",
        "We headed east.", "We reached Pine Forest.",
    ))
    assert named_relationships(graph) == [
        ("Rivertown", "Stonebridge", MapRelation.travelled_to),
        ("Stonebridge", "Pine Forest", MapRelation.travelled_to),
    ]
