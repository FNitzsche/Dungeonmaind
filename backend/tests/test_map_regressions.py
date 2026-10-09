"""Offline regressions for the public document-to-map interface."""
import pytest

from test_map_generator import document
from app.base_models.map_models import MapRelation
from app.functions.geographic_mapping.map_generator import generate_map_from_documents


ROUTE_TRANSCRIPT = (
    "Stonebridge is north of Rivertown.",
    "We travelled from Rivertown to Stonebridge.",
    "Stonebridge is connected to Pine Forest.",
    "Pine Forest is east of Stonebridge.",
    "We travelled from Stonebridge to Pine Forest.",
    "Old Tower is inside Pine Forest.",
    "We travelled from Pine Forest to Old Tower.",
    "Hill Village is north of Old Tower.",
    "We travelled from Old Tower to Hill Village.",
    "Castle Gate is east of Hill Village.",
    "We travelled from Hill Village to Castle Gate.",
    "We travelled from Castle Gate to Rivertown.",
)
ROUTE_LOCATIONS = {
    "Rivertown", "Stonebridge", "Pine Forest", "Old Tower",
    "Hill Village", "Castle Gate",
}


@pytest.fixture
def route_documents():
    return [document(text, index * 2, index * 2 + 1)
            for index, text in enumerate(ROUTE_TRANSCRIPT)]


def named_relationships(graph):
    """Resolve the model's edge endpoint IDs to readable location names."""
    names = {node.id: node.name for node in graph.nodes}
    return [(names[edge.source], names[edge.target], edge.relation)
            for edge in graph.edges]


def test_duplicate_location_normalization():
    graph = generate_map_from_documents([
        document("Old Tower is inside Pine Forest.", 0, 1),
        document("We travelled from Pine Forest to the Old Tower.", 2, 3),
        document("Hill Village is north of old tower.", 4, 5),
        document("We travelled from OLD TOWER to Hill Village.", 6, 7),
        document("Old Tower is inside Pine Forest.", 8, 9),
    ])

    towers = [node for node in graph.nodes if node.name.casefold() == "old tower"]
    assert len(towers) == 1
    assert towers[0].name == "Old Tower"
    assert {node.name for node in graph.nodes} == {
        "Old Tower", "Pine Forest", "Hill Village",
    }
    assert len(graph.nodes) == 3
    assert towers[0].mentions == 5
    # Repeated assertions keep their separate evidence; only nodes are merged.
    assert len(graph.edges) == 5
    assert all(towers[0].id in (edge.source, edge.target) for edge in graph.edges)


def test_generic_node_filtering():
    transcript = (
        "Old Tower is inside Pine Forest.",
        "We entered the tower and searched the abandoned rooms.",
        "Castle Gate is east of Hill Village.",
        "We opened the gate.",
    )
    graph = generate_map_from_documents([
        document(text, index, index + 1) for index, text in enumerate(transcript)
    ])

    names = {node.name for node in graph.nodes}
    assert names == {"Old Tower", "Pine Forest", "Castle Gate", "Hill Village"}
    assert names.isdisjoint({"tower", "gate", "abandoned rooms"})
    assert len(graph.nodes) == 4


def test_realistic_route_relationships(route_documents):
    graph = generate_map_from_documents(route_documents)

    assert {node.name for node in graph.nodes} == ROUTE_LOCATIONS
    assert len(graph.nodes) == 6
    expected = {
        ("Stonebridge", "Rivertown", MapRelation.north_of),
        ("Rivertown", "Stonebridge", MapRelation.travelled_to),
        ("Stonebridge", "Pine Forest", MapRelation.connected_to),
        ("Pine Forest", "Stonebridge", MapRelation.east_of),
        ("Stonebridge", "Pine Forest", MapRelation.travelled_to),
        ("Old Tower", "Pine Forest", MapRelation.inside),
        ("Pine Forest", "Old Tower", MapRelation.travelled_to),
        ("Hill Village", "Old Tower", MapRelation.north_of),
        ("Old Tower", "Hill Village", MapRelation.travelled_to),
        ("Castle Gate", "Hill Village", MapRelation.east_of),
        ("Hill Village", "Castle Gate", MapRelation.travelled_to),
        ("Castle Gate", "Rivertown", MapRelation.travelled_to),
    }
    assert set(named_relationships(graph)) == expected
    assert len(graph.edges) == len(expected)


def test_repeated_generation_is_idempotent(route_documents):
    first = generate_map_from_documents(route_documents)
    second = generate_map_from_documents(route_documents)

    assert first == second
    for graph in (first, second):
        assert {node.name for node in graph.nodes} == ROUTE_LOCATIONS
        assert len(graph.nodes) == len({node.name.casefold() for node in graph.nodes}) == 6
        assert len({node.id for node in graph.nodes}) == 6
        relationships = named_relationships(graph)
        assert len(relationships) == len(set(relationships)) == 12
        assert len({edge.id for edge in graph.edges}) == 12


@pytest.mark.parametrize("statement", [
    "Stonebridge might be north of Rivertown.",
    "Is Stonebridge north of Rivertown?",
    "We planned to travel from Rivertown to Stonebridge.",
])
def test_non_factual_statements_do_not_create_confirmed_relations(statement):
    assert generate_map_from_documents([document(statement)]).edges == []

    # Ensure filtering still works when the same locations already exist.
    graph = generate_map_from_documents([
        document("Stonebridge is near Rivertown.", 0, 1),
        document(statement, 2, 3),
    ])
    assert named_relationships(graph) == [
        ("Stonebridge", "Rivertown", MapRelation.near),
    ]
