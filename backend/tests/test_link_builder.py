import unittest
from types import SimpleNamespace

from app.domain.map_edge import MapEdgeRelationship
from app.domain.map_location import MapLocation
from app.functions.geo.link_builder import build_edges


def _event(event_id: str, places: list[str], order: int, session_id: str = 'sess-1'):
    return SimpleNamespace(
        id=event_id, session_id=session_id, order=order, location_entities=places
    )


def _location(
    location_id: str,
    event_ids: list[str],
    session_id: str = 'sess-1',
    canonical_name: str = '',
    aliases: list[str] | None = None,
) -> MapLocation:
    return MapLocation(
        id=location_id,
        session_id=session_id,
        canonical_name=canonical_name or location_id,
        aliases=aliases or [],
        event_ids=event_ids,
    )


class BuildEdgesWorkedExampleTests(unittest.TestCase):
    """The exact evt_1..evt_4 example from the Part 1 backend plan."""

    def setUp(self) -> None:
        self.events = [
            _event('evt_1', ['Velmora Crossing'], 0),
            _event('evt_2', ['Silver Lake'], 1),
            _event('evt_3', ['Ye Olde Tavern'], 2),
            _event('evt_4', ['the tavern'], 3),
        ]
        self.locations = [
            _location('loc_1', ['evt_1'], canonical_name='Velmora Crossing'),
            _location('loc_2', ['evt_2'], canonical_name='Silver Lake'),
            _location(
                'loc_3', ['evt_3', 'evt_4'], canonical_name='Ye Olde Tavern', aliases=['the tavern']
            ),
        ]

    def test_yields_exactly_two_edges(self) -> None:
        edges = build_edges(self.locations, self.events)
        self.assertEqual(len(edges), 2)

    def test_first_edge_matches_edge_1(self) -> None:
        edge = build_edges(self.locations, self.events)[0]
        self.assertEqual(edge.id, 'edge_1')
        self.assertEqual(edge.from_location_id, 'loc_1')
        self.assertEqual(edge.to_location_id, 'loc_2')
        self.assertEqual(edge.relationship, MapEdgeRelationship.travel)
        self.assertEqual(edge.evidence_event_ids, ['evt_1', 'evt_2'])
        self.assertEqual(edge.order, 0)

    def test_second_edge_matches_edge_2(self) -> None:
        edge = build_edges(self.locations, self.events)[1]
        self.assertEqual(edge.id, 'edge_2')
        self.assertEqual(edge.from_location_id, 'loc_2')
        self.assertEqual(edge.to_location_id, 'loc_3')
        self.assertEqual(edge.relationship, MapEdgeRelationship.travel)
        self.assertEqual(edge.evidence_event_ids, ['evt_2', 'evt_3'])
        self.assertEqual(edge.order, 1)

    def test_no_edge_when_location_does_not_change(self) -> None:
        # evt_3 -> evt_4 both resolve to loc_3, so no third edge is emitted.
        edges = build_edges(self.locations, self.events)
        self.assertNotIn(
            ('loc_3', 'loc_3'), [(e.from_location_id, e.to_location_id) for e in edges]
        )

    def test_edges_carry_the_session_id(self) -> None:
        edges = build_edges(self.locations, self.events)
        self.assertTrue(all(edge.session_id == 'sess-1' for edge in edges))


class BuildEdgesBehaviourTests(unittest.TestCase):
    def test_empty_inputs_yield_no_edges(self) -> None:
        self.assertEqual(build_edges([], []), [])

    def test_single_location_yields_no_edges(self) -> None:
        events = [_event('evt_1', ['Velmora Crossing'], 0)]
        locations = [_location('loc_1', ['evt_1'])]
        self.assertEqual(build_edges(locations, events), [])

    def test_events_are_sorted_by_order_before_linking(self) -> None:
        # Supplied out of order; result must follow the ordinal sequence.
        events = [_event('evt_2', ['Silver Lake'], 1), _event('evt_1', ['Velmora Crossing'], 0)]
        locations = [_location('loc_1', ['evt_1']), _location('loc_2', ['evt_2'])]
        edges = build_edges(locations, events)
        self.assertEqual(len(edges), 1)
        self.assertEqual((edges[0].from_location_id, edges[0].to_location_id), ('loc_1', 'loc_2'))

    def test_repeat_transition_collapses_into_one_edge(self) -> None:
        # A -> B -> A -> B should produce two edges (A->B, B->A), not four,
        # with the repeated legs accumulating their evidence events.
        events = [
            _event('evt_1', ['A'], 0),
            _event('evt_2', ['B'], 1),
            _event('evt_3', ['A'], 2),
            _event('evt_4', ['B'], 3),
        ]
        locations = [
            _location('loc_a', ['evt_1', 'evt_3'], canonical_name='A'),
            _location('loc_b', ['evt_2', 'evt_4'], canonical_name='B'),
        ]
        edges = build_edges(locations, events)
        pairs = [(e.from_location_id, e.to_location_id) for e in edges]
        self.assertEqual(pairs, [('loc_a', 'loc_b'), ('loc_b', 'loc_a')])
        forward = next(e for e in edges if e.from_location_id == 'loc_a')
        # Both A->B legs (evt_1->evt_2 and evt_3->evt_4) fold onto one edge,
        # so their evidence events accumulate without duplication.
        self.assertEqual(forward.evidence_event_ids, ['evt_1', 'evt_2', 'evt_3', 'evt_4'])

    def test_cooccurring_places_produce_a_proximity_edge(self) -> None:
        events = [_event('evt_1', ['Market Square', 'Old Well'], 0)]
        locations = [
            _location('loc_1', ['evt_1'], canonical_name='Market Square'),
            _location('loc_2', ['evt_1'], canonical_name='Old Well'),
        ]
        edges = build_edges(locations, events)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].relationship, MapEdgeRelationship.proximity)
        self.assertEqual((edges[0].from_location_id, edges[0].to_location_id), ('loc_1', 'loc_2'))

    def test_events_without_resolved_places_do_not_break_the_journey(self) -> None:
        # evt_2 mentions no resolved place; the leg loc_1 -> loc_2 should still
        # connect loc_1 (evt_1) to loc_2 (evt_3) across the gap.
        events = [
            _event('evt_1', ['Velmora Crossing'], 0),
            _event('evt_2', [], 1),
            _event('evt_3', ['Silver Lake'], 2),
        ]
        locations = [_location('loc_1', ['evt_1']), _location('loc_2', ['evt_3'])]
        edges = build_edges(locations, events)
        self.assertEqual(len(edges), 1)
        self.assertEqual((edges[0].from_location_id, edges[0].to_location_id), ('loc_1', 'loc_2'))
        self.assertEqual(edges[0].evidence_event_ids, ['evt_1', 'evt_3'])


if __name__ == '__main__':
    unittest.main()
