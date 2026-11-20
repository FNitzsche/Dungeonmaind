import json
import tempfile
import unittest
from pathlib import Path

from app.domain.map_edge import MapEdge, MapEdgeRelationship
from app.domain.map_location import MapLocation
from app.domain.map_overrides import (
    MapConnectionChange,
    MapMerge,
    MapRename,
    MapSplit,
    SessionMapOverrides,
)
from app.functions.geo.map_overrides import (
    apply_map_overrides,
    load_session_overrides,
    record_added_connection,
    record_merge,
    record_removed_connection,
    record_rename,
    record_split,
    save_session_overrides,
)


def _location(
    location_id: str,
    name: str,
    event_ids: list[str],
    aliases: list[str] | None = None,
    session_id: str = 'sess-1',
    first_order: int = 0,
) -> MapLocation:
    return MapLocation(
        id=location_id,
        session_id=session_id,
        canonical_name=name,
        aliases=list(aliases or []),
        event_ids=list(event_ids),
        mention_count=len(event_ids),
        first_order=first_order,
    )


def _edge(from_id: str, to_id: str, edge_id: str = 'edge_1', order: int = 0) -> MapEdge:
    return MapEdge(
        id=edge_id,
        session_id='sess-1',
        from_location_id=from_id,
        to_location_id=to_id,
        relationship=MapEdgeRelationship.travel,
        order=order,
    )


class MapOverridesJsonStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / 'map_overrides.json'

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_missing_file_loads_as_empty_overrides(self) -> None:
        overrides = load_session_overrides('sess-1', self.path)
        self.assertEqual(overrides, SessionMapOverrides())

    def test_round_trips_renames_merges_splits_and_connections(self) -> None:
        record_rename('sess-1', 'loc_1', 'The Rusty Anchor', path=self.path)
        record_merge('sess-1', ['loc_2'], 'loc_1', path=self.path)
        record_split('sess-1', 'loc_3', 'loc_4', 'The Cellar', event_ids=['evt_4'], path=self.path)
        record_added_connection('sess-1', 'loc_1', 'loc_3', 'travel', path=self.path)
        record_removed_connection('sess-1', 'loc_2', 'loc_3', path=self.path)

        loaded = load_session_overrides('sess-1', self.path)
        self.assertEqual(loaded.renames[0].canonical_name, 'The Rusty Anchor')
        self.assertEqual(loaded.merges[0].source_location_ids, ['loc_2'])
        self.assertEqual(loaded.splits[0].new_location_id, 'loc_4')
        self.assertEqual(loaded.added_connections[0].from_location_id, 'loc_1')
        self.assertEqual(loaded.removed_connections[0].to_location_id, 'loc_3')

        document = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertIn('renames', document['sessions']['sess-1'])
        self.assertIn('merges', document['sessions']['sess-1'])
        self.assertIn('splits', document['sessions']['sess-1'])
        self.assertIn('added', document['sessions']['sess-1']['connections'])
        self.assertIn('removed', document['sessions']['sess-1']['connections'])

    def test_sessions_are_isolated_in_the_same_file(self) -> None:
        record_rename('sess-1', 'loc_1', 'Alpha', path=self.path)
        record_rename('sess-2', 'loc_1', 'Beta', path=self.path)

        self.assertEqual(
            load_session_overrides('sess-1', self.path).renames[0].canonical_name, 'Alpha'
        )
        self.assertEqual(
            load_session_overrides('sess-2', self.path).renames[0].canonical_name, 'Beta'
        )

    def test_adding_a_connection_cancels_a_matching_removal(self) -> None:
        record_removed_connection('sess-1', 'loc_1', 'loc_2', 'travel', path=self.path)
        record_added_connection('sess-1', 'loc_1', 'loc_2', 'travel', path=self.path)

        loaded = load_session_overrides('sess-1', self.path)
        self.assertEqual(len(loaded.removed_connections), 0)
        self.assertEqual(len(loaded.added_connections), 1)

    def test_empty_overrides_are_dropped_from_the_file(self) -> None:
        record_rename('sess-1', 'loc_1', 'Alpha', path=self.path)
        save_session_overrides('sess-1', SessionMapOverrides(), path=self.path)

        document = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertNotIn('sess-1', document['sessions'])


class ApplyMapOverridesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.locations = [
            _location('loc_1', 'Velmora Crossing', ['evt_1'], first_order=0),
            _location('loc_2', 'Silver Lake', ['evt_2'], first_order=1),
            _location(
                'loc_3', 'Ye Olde Tavern', ['evt_3', 'evt_4'], aliases=['the tavern'], first_order=2
            ),
        ]
        self.edges = [_edge('loc_1', 'loc_2', 'edge_1', 0), _edge('loc_2', 'loc_3', 'edge_2', 1)]

    def test_rename_replaces_the_canonical_name_and_keeps_the_old_name_as_an_alias(self) -> None:
        overrides = SessionMapOverrides(
            renames=[MapRename(location_id='loc_3', canonical_name='The Rusty Anchor')]
        )
        locations, _ = apply_map_overrides(self.locations, self.edges, overrides)

        tavern = next(item for item in locations if item.id == 'loc_3')
        self.assertEqual(tavern.canonical_name, 'The Rusty Anchor')
        self.assertIn('Ye Olde Tavern', tavern.aliases)
        self.assertEqual(self.locations[2].canonical_name, 'Ye Olde Tavern')

    def test_merge_folds_source_into_target_and_retargets_edges(self) -> None:
        overrides = SessionMapOverrides(
            merges=[MapMerge(source_location_ids=['loc_2'], target_location_id='loc_1')]
        )
        locations, edges = apply_map_overrides(self.locations, self.edges, overrides)

        self.assertEqual([item.id for item in locations], ['loc_1', 'loc_3'])
        self.assertEqual(locations[0].aliases, ['Silver Lake'])
        self.assertEqual(locations[0].event_ids, ['evt_1', 'evt_2'])
        self.assertEqual(
            [(edge.from_location_id, edge.to_location_id) for edge in edges], [('loc_1', 'loc_3')]
        )

    def test_split_carves_a_new_place_and_moves_selected_events(self) -> None:
        overrides = SessionMapOverrides(
            splits=[
                MapSplit(
                    source_location_id='loc_3',
                    new_location_id='loc_4',
                    canonical_name='The Cellar',
                    event_ids=['evt_4'],
                )
            ]
        )
        locations, _ = apply_map_overrides(self.locations, self.edges, overrides)

        tavern = next(item for item in locations if item.id == 'loc_3')
        cellar = next(item for item in locations if item.id == 'loc_4')
        self.assertEqual(tavern.event_ids, ['evt_3'])
        self.assertEqual(cellar.canonical_name, 'The Cellar')
        self.assertEqual(cellar.event_ids, ['evt_4'])

    def test_removed_connection_drops_the_matching_edge(self) -> None:
        overrides = SessionMapOverrides(
            removed_connections=[
                MapConnectionChange(from_location_id='loc_1', to_location_id='loc_2')
            ]
        )
        _, edges = apply_map_overrides(self.locations, self.edges, overrides)

        self.assertEqual(
            [(edge.from_location_id, edge.to_location_id) for edge in edges], [('loc_2', 'loc_3')]
        )
        self.assertEqual(edges[0].id, 'edge_1')

    def test_added_connection_inserts_a_new_edge(self) -> None:
        overrides = SessionMapOverrides(
            added_connections=[
                MapConnectionChange(
                    from_location_id='loc_3', to_location_id='loc_1', relationship='travel'
                )
            ]
        )
        _, edges = apply_map_overrides(self.locations, self.edges, overrides)

        self.assertEqual(len(edges), 3)
        self.assertEqual(edges[-1].from_location_id, 'loc_3')
        self.assertEqual(edges[-1].to_location_id, 'loc_1')
        self.assertEqual(edges[-1].relationship, MapEdgeRelationship.travel)

    def test_apply_is_idempotent(self) -> None:
        overrides = SessionMapOverrides(
            renames=[MapRename(location_id='loc_1', canonical_name='Crossing')],
            merges=[MapMerge(source_location_ids=['loc_2'], target_location_id='loc_1')],
        )
        once_locations, once_edges = apply_map_overrides(self.locations, self.edges, overrides)
        twice_locations, twice_edges = apply_map_overrides(once_locations, once_edges, overrides)

        self.assertEqual(
            [item.id for item in twice_locations], [item.id for item in once_locations]
        )
        self.assertEqual(twice_locations[0].canonical_name, 'Crossing')
        self.assertEqual(len(twice_edges), len(once_edges))


class MapOverridesRouterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from unittest.mock import patch

        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from app.api.routers.map import router as map_router
        from app.domain.map_store import map_store
        from app.domain.models import TimelineEvent
        from app.domain.timeline_store import timeline_store

        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / 'map_overrides.json'
        self.patcher = patch(
            'app.functions.geo.map_overrides.default_overrides_path', return_value=self.path
        )
        self.patcher.start()

        await timeline_store.clear_all()
        await timeline_store.add_events(
            [
                TimelineEvent(
                    id='evt_1',
                    session_id='sess-overrides',
                    title='evt_1',
                    description='',
                    order=1,
                    timestamp=1.0,
                    location_entities=['Velmora Crossing'],
                ),
                TimelineEvent(
                    id='evt_2',
                    session_id='sess-overrides',
                    title='evt_2',
                    description='',
                    order=2,
                    timestamp=2.0,
                    location_entities=['Silver Lake'],
                ),
            ]
        )
        await map_store.clear_session('sess-overrides')
        application = FastAPI()
        application.include_router(map_router, prefix='/map')
        self.client = AsyncClient(transport=ASGITransport(app=application), base_url='http://test')

    async def asyncTearDown(self) -> None:
        from app.domain.map_store import map_store
        from app.domain.timeline_store import timeline_store

        await self.client.aclose()
        await timeline_store.clear_all()
        await map_store.clear_session('sess-overrides')
        self.patcher.stop()
        self.tmpdir.cleanup()

    async def test_get_map_applies_stored_rename_and_removed_connection(self) -> None:
        record_rename('sess-overrides', 'loc_1', 'The Crossing', path=self.path)
        record_removed_connection('sess-overrides', 'loc_1', 'loc_2', path=self.path)

        response = await self.client.get('/map', params={'session_id': 'sess-overrides'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['locations'][0]['canonical_name'], 'The Crossing')
        self.assertEqual(payload['edges'], [])


if __name__ == '__main__':
    unittest.main()
