"""Unit tests for the in-memory timeline and transcript stores."""

import unittest

from app.domain.map_edge import MapEdge
from app.domain.map_location import MapLocation
from app.domain.map_store import MapStore
from app.domain.models import TimelineEvent, TimelineEventType
from app.domain.timeline_store import TimelineStore
from app.domain.transcript_store import TranscriptSegment, TranscriptStore


def _event(event_id: str, order: int = 0, session_id: str = 'sess-1') -> TimelineEvent:
    return TimelineEvent(
        id=event_id, session_id=session_id, title=f'Event {event_id}', description='', order=order
    )


def _segment(text: str, start: float = 0.0) -> TranscriptSegment:
    return TranscriptSegment(start=start, end=start + 1.0, text=text, speaker='Ana')


class TimelineEventModelTests(unittest.TestCase):
    def test_timestamp_defaults_to_zero_seconds(self) -> None:
        self.assertEqual(_event('a').timestamp, 0.0)

    def test_dict_round_trip_keeps_every_field(self) -> None:
        event = TimelineEvent(
            id='a',
            session_id='sess-1',
            title='Explorers Depart',
            description='They leave.',
            event_type=TimelineEventType.travel,
            order=3,
            timestamp=12.5,
            transcription_chunk_id='chunk_3',
            player_id='Ana',
            speaker_name='Ana',
            temporal_entities=['dawn'],
            location_entities=['Neverwinter'],
            characters=['Ana'],
            display_time='00:00:12',
        )

        self.assertEqual(TimelineEvent.from_dict(event.to_dict()), event)

    def test_from_dict_fills_defaults_for_missing_optional_fields(self) -> None:
        event = TimelineEvent.from_dict(
            {'id': 'a', 'session_id': 'sess-1', 'title': 'T', 'description': 'D'}
        )

        self.assertEqual(event.event_type, TimelineEventType.other)
        self.assertEqual(event.order, 0)
        self.assertEqual(event.timestamp, 0.0)
        self.assertEqual(event.location_entities, [])

    def test_from_dict_reads_legacy_empty_timestamp_as_zero(self) -> None:
        event = TimelineEvent.from_dict(
            {'id': 'a', 'session_id': 's', 'title': 'T', 'description': 'D', 'timestamp': ''}
        )

        self.assertEqual(event.timestamp, 0.0)


class TimelineStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = TimelineStore()

    async def test_add_events_assigns_ids_to_events_without_one(self) -> None:
        added = await self.store.add_events([_event(''), _event('')])

        self.assertEqual(len({event.id for event in added}), 2)
        self.assertTrue(all(len(event.id) == 12 for event in added))

    async def test_add_event_keeps_given_id(self) -> None:
        added = await self.store.add_event(_event('evt_1'))

        self.assertEqual(added.id, 'evt_1')
        self.assertIs(await self.store.get_event('evt_1'), added)

    async def test_session_events_are_sorted_by_order_and_scoped(self) -> None:
        await self.store.add_events(
            [_event('b', 2), _event('a', 0), _event('c', 1), _event('x', 0, 'sess-2')]
        )

        events = await self.store.get_session_events('sess-1')

        self.assertEqual([event.id for event in events], ['a', 'c', 'b'])
        self.assertEqual(await self.store.get_session_events('unknown'), [])

    async def test_delete_event(self) -> None:
        await self.store.add_events([_event('a'), _event('b', 1)])

        self.assertTrue(await self.store.delete_event('a'))
        self.assertFalse(await self.store.delete_event('a'))
        self.assertIsNone(await self.store.get_event('a'))
        self.assertEqual([e.id for e in await self.store.get_session_events('sess-1')], ['b'])

    async def test_clear_session_returns_count_and_spares_other_sessions(self) -> None:
        await self.store.add_events([_event('a'), _event('b', 1), _event('x', 0, 'sess-2')])

        self.assertEqual(await self.store.clear_session('sess-1'), 2)
        self.assertEqual(await self.store.clear_session('sess-1'), 0)
        self.assertEqual(len(await self.store.get_session_events('sess-2')), 1)

    async def test_clear_all(self) -> None:
        await self.store.add_events([_event('a'), _event('x', 0, 'sess-2')])

        self.assertEqual(await self.store.clear_all(), 2)
        self.assertEqual(await self.store.get_session_events('sess-1'), [])
        self.assertEqual(await self.store.get_session_events('sess-2'), [])

    async def test_replace_session_swaps_events_and_sets_session_id(self) -> None:
        await self.store.add_events([_event('old')])

        await self.store.replace_session('sess-1', [_event('new', 0, 'somewhere-else')])

        events = await self.store.get_session_events('sess-1')
        self.assertEqual([event.id for event in events], ['new'])
        self.assertEqual(events[0].session_id, 'sess-1')
        self.assertIsNone(await self.store.get_event('old'))

    async def test_replace_session_with_empty_list_clears_it(self) -> None:
        await self.store.add_events([_event('old')])

        self.assertEqual(await self.store.replace_session('sess-1', []), [])
        self.assertEqual(await self.store.get_session_events('sess-1'), [])

    async def test_rename_session_moves_events(self) -> None:
        await self.store.add_events([_event('a', 0, 'unsaved'), _event('b', 1, 'unsaved')])

        moved = await self.store.rename_session('unsaved', 'Camp/Sess')

        self.assertEqual(moved, 2)
        events = await self.store.get_session_events('Camp/Sess')
        self.assertEqual([event.id for event in events], ['a', 'b'])
        self.assertEqual({event.session_id for event in events}, {'Camp/Sess'})
        self.assertEqual(await self.store.get_session_events('unsaved'), [])
        self.assertEqual((await self.store.get_event('a')).session_id, 'Camp/Sess')

    async def test_rename_session_replaces_events_at_the_target(self) -> None:
        await self.store.add_events([_event('a', 0, 'unsaved'), _event('stale', 0, 'Camp/Sess')])

        await self.store.rename_session('unsaved', 'Camp/Sess')

        self.assertEqual([e.id for e in await self.store.get_session_events('Camp/Sess')], ['a'])
        self.assertIsNone(await self.store.get_event('stale'))

    async def test_rename_session_to_itself_changes_nothing(self) -> None:
        await self.store.add_events([_event('a')])

        self.assertEqual(await self.store.rename_session('sess-1', 'sess-1'), 0)
        self.assertEqual(len(await self.store.get_session_events('sess-1')), 1)


class TranscriptStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = TranscriptStore()

    def test_segment_dict_round_trip(self) -> None:
        segment = TranscriptSegment(start=1.5, end=4.0, text='Hello there.', speaker='DM')

        self.assertEqual(
            segment.to_dict(), {'start': 1.5, 'end': 4.0, 'text': 'Hello there.', 'speaker': 'DM'}
        )
        self.assertEqual(TranscriptSegment.from_dict(segment.to_dict()), segment)

    def test_segment_from_dict_defaults_missing_speaker(self) -> None:
        segment = TranscriptSegment.from_dict({'start': '1', 'end': 2, 'text': 'Hi'})

        self.assertEqual((segment.start, segment.end, segment.speaker), (1.0, 2.0, 'unknown'))

    def test_segment_from_dict_requires_times_and_text(self) -> None:
        for incomplete in (
            {'end': 1, 'text': 'x'},
            {'start': 0, 'text': 'x'},
            {'start': 0, 'end': 1},
        ):
            with self.subTest(data=incomplete), self.assertRaises(KeyError):
                TranscriptSegment.from_dict(incomplete)

    async def test_segments_are_appended_in_arrival_order_per_session(self) -> None:
        await self.store.add_segments('sess-1', [_segment('one'), _segment('two', 1.0)])
        await self.store.add_segments('sess-1', [_segment('three', 0.0)])
        await self.store.add_segments('sess-2', [_segment('other')])

        segments = await self.store.get_segments('sess-1')

        self.assertEqual([segment.text for segment in segments], ['one', 'two', 'three'])
        self.assertEqual(len(await self.store.get_segments('sess-2')), 1)
        self.assertEqual(await self.store.get_segments('unknown'), [])

    async def test_get_segments_returns_a_copy(self) -> None:
        await self.store.add_segments('sess-1', [_segment('one')])

        (await self.store.get_segments('sess-1')).clear()

        self.assertEqual(len(await self.store.get_segments('sess-1')), 1)

    async def test_replace_rename_and_clear(self) -> None:
        await self.store.add_segments('unsaved', [_segment('one'), _segment('two')])
        await self.store.replace_session('Camp/Sess', [_segment('stale')])

        await self.store.rename_session('unsaved', 'Camp/Sess')

        texts = [segment.text for segment in await self.store.get_segments('Camp/Sess')]
        self.assertEqual(texts, ['one', 'two'])
        self.assertEqual(await self.store.get_segments('unsaved'), [])
        self.assertEqual(await self.store.clear_session('Camp/Sess'), 2)
        self.assertEqual(await self.store.clear_session('Camp/Sess'), 0)


class MapStoreRenameTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = MapStore()
        self.locations = [MapLocation(id='loc_1', session_id='unsaved', canonical_name='Phandalin')]
        self.edges = [
            MapEdge(
                id='edge_1', session_id='unsaved', from_location_id='loc_1', to_location_id='loc_1'
            )
        ]

    async def test_rename_moves_map_and_updates_session_ids(self) -> None:
        await self.store.save_map('unsaved', self.locations, self.edges)

        self.assertTrue(await self.store.rename_session('unsaved', 'Camp/Sess'))

        self.assertFalse(await self.store.has_map('unsaved'))
        locations = await self.store.get_locations('Camp/Sess')
        edges = await self.store.get_edges('Camp/Sess')
        self.assertEqual([location.session_id for location in locations], ['Camp/Sess'])
        self.assertEqual([edge.session_id for edge in edges], ['Camp/Sess'])

    async def test_rename_without_saved_map_does_nothing(self) -> None:
        self.assertFalse(await self.store.rename_session('unsaved', 'Camp/Sess'))
        self.assertFalse(await self.store.has_map('Camp/Sess'))

    async def test_rename_to_itself_keeps_map(self) -> None:
        await self.store.save_map('unsaved', self.locations, self.edges)

        self.assertFalse(await self.store.rename_session('unsaved', 'unsaved'))
        self.assertTrue(await self.store.has_map('unsaved'))


if __name__ == '__main__':
    unittest.main()
