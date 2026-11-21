import unittest

from app.domain.map_edge import MapEdge, MapEdgeRelationship
from app.domain.map_location import MapLocation
from app.domain.map_store import MapStore


def _location(loc_id: str, session_id: str) -> MapLocation:
    return MapLocation(id=loc_id, session_id=session_id, canonical_name=loc_id)


def _edge(edge_id: str, session_id: str, from_id: str, to_id: str) -> MapEdge:
    return MapEdge(
        id=edge_id,
        session_id=session_id,
        from_location_id=from_id,
        to_location_id=to_id,
        relationship=MapEdgeRelationship.travel,
    )


class MapStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = MapStore()

    async def test_get_locations_returns_none_before_any_save(self) -> None:
        self.assertIsNone(await self.store.get_locations('sess-1'))

    async def test_get_edges_returns_none_before_any_save(self) -> None:
        self.assertIsNone(await self.store.get_edges('sess-1'))

    async def test_has_map_is_false_before_any_save(self) -> None:
        self.assertFalse(await self.store.has_map('sess-1'))

    async def test_save_map_round_trips_locations_and_edges(self) -> None:
        locations = [_location('loc_1', 'sess-1'), _location('loc_2', 'sess-1')]
        edges = [_edge('edge_1', 'sess-1', 'loc_1', 'loc_2')]

        await self.store.save_map('sess-1', locations, edges)

        self.assertEqual(await self.store.get_locations('sess-1'), locations)
        self.assertEqual(await self.store.get_edges('sess-1'), edges)
        self.assertTrue(await self.store.has_map('sess-1'))

    async def test_save_map_with_empty_lists_is_distinguishable_from_ungenerated(self) -> None:
        await self.store.save_map('sess-1', [], [])

        self.assertEqual(await self.store.get_locations('sess-1'), [])
        self.assertEqual(await self.store.get_edges('sess-1'), [])
        self.assertTrue(await self.store.has_map('sess-1'))

    async def test_get_locations_returns_a_copy_not_the_stored_list(self) -> None:
        locations = [_location('loc_1', 'sess-1')]
        await self.store.save_map('sess-1', locations, [])

        fetched = await self.store.get_locations('sess-1')
        fetched.append(_location('loc_2', 'sess-1'))

        self.assertEqual(await self.store.get_locations('sess-1'), locations)

    async def test_sessions_are_isolated(self) -> None:
        await self.store.save_map('sess-1', [_location('loc_1', 'sess-1')], [])
        await self.store.save_map('sess-2', [_location('loc_9', 'sess-2')], [])

        sess_1_locations = await self.store.get_locations('sess-1')
        sess_2_locations = await self.store.get_locations('sess-2')
        self.assertEqual([location.id for location in sess_1_locations], ['loc_1'])
        self.assertEqual([location.id for location in sess_2_locations], ['loc_9'])

    async def test_save_map_overwrites_a_previous_save_for_the_same_session(self) -> None:
        await self.store.save_map('sess-1', [_location('loc_1', 'sess-1')], [])
        await self.store.save_map('sess-1', [_location('loc_2', 'sess-1')], [])

        locations = await self.store.get_locations('sess-1')
        self.assertEqual([location.id for location in locations], ['loc_2'])

    async def test_clear_session_removes_a_saved_map_and_reports_true(self) -> None:
        await self.store.save_map('sess-1', [_location('loc_1', 'sess-1')], [])

        removed = await self.store.clear_session('sess-1')

        self.assertTrue(removed)
        self.assertIsNone(await self.store.get_locations('sess-1'))
        self.assertIsNone(await self.store.get_edges('sess-1'))
        self.assertFalse(await self.store.has_map('sess-1'))

    async def test_clear_session_reports_false_when_nothing_was_saved(self) -> None:
        removed = await self.store.clear_session('missing')
        self.assertFalse(removed)

    async def test_clear_session_does_not_affect_other_sessions(self) -> None:
        await self.store.save_map('sess-1', [_location('loc_1', 'sess-1')], [])
        await self.store.save_map('sess-2', [_location('loc_9', 'sess-2')], [])

        await self.store.clear_session('sess-1')

        self.assertIsNone(await self.store.get_locations('sess-1'))
        self.assertIsNotNone(await self.store.get_locations('sess-2'))


if __name__ == '__main__':
    unittest.main()
