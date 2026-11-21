"""Regression tests for bugs that are known but not fixed yet.

Each test describes the behaviour the app SHOULD have and is marked as an
expected failure, so the suite stays green while the bug is open. When a bug
is fixed its test starts passing, the runner reports an "unexpected success",
and the ``expectedFailure`` marker must then be removed so the test guards the
fix from then on.

IDs (B1, B3, B9) refer to the Release 4 roadmap.
"""

import json
import unittest
from types import SimpleNamespace
from unittest import mock

from app.domain.models import TimelineEvent
from app.domain.timeline_store import TimelineStore
from app.functions.embedding.entity_extractor import ExtractedEntities
from app.functions.geo.link_builder import build_edges
from app.functions.geo.place_resolver import resolve_locations
from app.functions.llm import event_extractor


class _FakeResponse:
    def __init__(self, events: list[dict]) -> None:
        self._body = json.dumps({'message': {'content': json.dumps(events)}}).encode('utf-8')

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False


def _travel_edges(events: list) -> list[tuple[str, str]]:
    locations = resolve_locations(events, session_id='sess-1')
    names = {location.id: location.canonical_name for location in locations}
    return [
        (names[edge.from_location_id], names[edge.to_location_id])
        for edge in build_edges(locations, events, session_id='sess-1')
        if edge.relationship.value == 'travel'
    ]


class KnownBugTests(unittest.IsolatedAsyncioTestCase):
    @unittest.expectedFailure
    def test_b1_events_from_consecutive_segments_get_unique_increasing_order(self) -> None:
        """B1: ``order = chunk_index + i`` gives events of different segments the same order."""
        three_events = [
            {'title': f'Event {n}', 'description': f'Thing {n} happens.', 'event_type': 'other'}
            for n in range(3)
        ]
        with (
            mock.patch.object(
                event_extractor,
                'extract_entities_hybrid',
                return_value=ExtractedEntities(temporal_entities=[], location_entities=[]),
            ),
            mock.patch.object(
                event_extractor, 'urlopen', side_effect=lambda *a, **kw: _FakeResponse(three_events)
            ),
        ):
            events = event_extractor.extract_events_from_transcriptions(
                texts=['First segment.', 'Second segment.'], session_id='sess-1'
            )

        orders = [event.order for event in events]
        self.assertEqual(len(orders), 6)
        self.assertEqual(orders, sorted(set(orders)))

    @unittest.expectedFailure
    def test_b3_event_place_is_the_first_one_mentioned(self) -> None:
        """B3: the link builder uses the lowest-numbered location as an event's place."""
        events = [
            SimpleNamespace(id='e1', order=0, location_entities=['Neverwinter']),
            SimpleNamespace(id='e2', order=1, location_entities=['Phandalin']),
            # Still in Phandalin; Neverwinter is only mentioned in passing.
            SimpleNamespace(id='e3', order=2, location_entities=['Phandalin', 'Neverwinter']),
            SimpleNamespace(id='e4', order=3, location_entities=['Phandalin']),
        ]

        self.assertEqual(_travel_edges(events), [('Neverwinter', 'Phandalin')])

    @unittest.expectedFailure
    async def test_b9_adding_the_same_event_twice_lists_it_once(self) -> None:
        """B9: ``add_event`` checks the session id instead of the event id before appending."""
        store = TimelineStore()
        event = TimelineEvent(id='evt_1', session_id='sess-1', title='T', description='D')

        await store.add_event(event)
        await store.add_event(event)

        self.assertEqual(len(await store.get_session_events('sess-1')), 1)


if __name__ == '__main__':
    unittest.main()
