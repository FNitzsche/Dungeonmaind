import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routers.map import router as map_router
from app.base_models.map_base_models import (
    MapDeleteResponse,
    MapEdgeListResponse,
    MapGenerateResponse,
    MapGraphResponse,
    MapLocationListResponse,
)
from app.domain.map_store import map_store
from app.domain.models import Group, Role, TimelineEvent
from app.domain.store import store
from app.domain.timeline_store import timeline_store

SESSION_ID = 'sess-integration'


def _event(event_id: str, places: list[str], order: int) -> TimelineEvent:
    return TimelineEvent(
        id=event_id,
        session_id=SESSION_ID,
        title=event_id,
        description='',
        order=order,
        timestamp=float(order),
        location_entities=places,
    )


def _map_app() -> FastAPI:
    application = FastAPI()
    application.include_router(map_router, prefix='/map')
    return application


class MapIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """Seeds evt_1..evt_4 (the plan's own worked example) and drives the
    full generate -> query round trip through the real HTTP router.
    """

    async def asyncSetUp(self) -> None:
        await timeline_store.clear_all()
        await timeline_store.add_events(
            [
                _event('evt_1', ['Velmora Crossing'], order=1),
                _event('evt_2', ['Silver Lake'], order=2),
                _event('evt_3', ['Ye Olde Tavern'], order=3),
                _event('evt_4', ['the tavern'], order=4),
            ]
        )
        await map_store.clear_session(SESSION_ID)
        self._original_group = store.group
        store.group = Group()
        self.leader = store.group.add_player('Ana', Role.leader)
        self.leader_headers = {'X-Player-Id': str(self.leader.id)}
        self.client = AsyncClient(transport=ASGITransport(app=_map_app()), base_url='http://test')

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        await timeline_store.clear_all()
        await map_store.clear_session(SESSION_ID)
        store.group = self._original_group

    async def _post(self, path: str, **kwargs):
        kwargs.setdefault('headers', self.leader_headers)
        return await self.client.post(path, **kwargs)

    async def _delete(self, path: str, **kwargs):
        kwargs.setdefault('headers', self.leader_headers)
        return await self.client.delete(path, **kwargs)

    async def test_generate_returns_exactly_the_worked_example_from_the_plan(self) -> None:
        response = await self._post('/map/generate', json={'session_id': SESSION_ID})

        self.assertEqual(response.status_code, 200)
        payload = MapGenerateResponse.model_validate(response.json())
        self.assertEqual(payload.session_id, SESSION_ID)
        self.assertEqual(payload.locations_generated, 3)
        self.assertEqual(payload.edges_generated, 2)

        self.assertEqual(
            [location.id for location in payload.locations], ['loc_1', 'loc_2', 'loc_3']
        )
        self.assertEqual(payload.locations[0].canonical_name, 'Velmora Crossing')
        self.assertEqual(payload.locations[0].event_ids, ['evt_1'])
        self.assertEqual(payload.locations[1].canonical_name, 'Silver Lake')
        self.assertEqual(payload.locations[1].event_ids, ['evt_2'])
        self.assertEqual(payload.locations[2].canonical_name, 'Ye Olde Tavern')
        self.assertEqual(payload.locations[2].aliases, ['the tavern'])
        self.assertEqual(payload.locations[2].event_ids, ['evt_3', 'evt_4'])

        self.assertEqual([edge.id for edge in payload.edges], ['edge_1', 'edge_2'])
        self.assertEqual(
            (payload.edges[0].from_location_id, payload.edges[0].to_location_id), ('loc_1', 'loc_2')
        )
        self.assertEqual(
            (payload.edges[1].from_location_id, payload.edges[1].to_location_id), ('loc_2', 'loc_3')
        )
        pairs = {(edge.from_location_id, edge.to_location_id) for edge in payload.edges}
        self.assertNotIn(('loc_3', 'loc_3'), pairs)

    async def test_get_map_after_generate_returns_the_persisted_graph(self) -> None:
        await self._post('/map/generate', json={'session_id': SESSION_ID})

        response = await self.client.get('/map', params={'session_id': SESSION_ID})

        self.assertEqual(response.status_code, 200)
        payload = MapGraphResponse.model_validate(response.json())
        self.assertEqual(payload.session_id, SESSION_ID)
        self.assertEqual(len(payload.locations), 3)
        self.assertEqual(len(payload.edges), 2)

    async def test_get_map_falls_back_to_live_resolution_before_generate_has_run(self) -> None:
        response = await self.client.get('/map', params={'session_id': SESSION_ID})

        self.assertEqual(response.status_code, 200)
        payload = MapGraphResponse.model_validate(response.json())
        self.assertEqual(len(payload.locations), 3)
        self.assertEqual(len(payload.edges), 2)

    async def test_generated_map_survives_timeline_events_being_cleared(self) -> None:
        await self._post('/map/generate', json={'session_id': SESSION_ID})
        await timeline_store.clear_session(SESSION_ID)

        response = await self.client.get('/map', params={'session_id': SESSION_ID})

        payload = MapGraphResponse.model_validate(response.json())
        self.assertEqual(len(payload.locations), 3)
        self.assertEqual(len(payload.edges), 2)

    async def test_location_events_click_through_resolves_after_generate(self) -> None:
        await self._post('/map/generate', json={'session_id': SESSION_ID})

        response = await self.client.get(
            '/map/locations/loc_3/events', params={'session_id': SESSION_ID}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([event['id'] for event in response.json()['events']], ['evt_3', 'evt_4'])

    async def test_event_locations_click_through_resolves_after_generate(self) -> None:
        await self._post('/map/generate', json={'session_id': SESSION_ID})

        response = await self.client.get(
            '/map/events/evt_1/locations', params={'session_id': SESSION_ID}
        )

        self.assertEqual(response.status_code, 200)
        payload = MapLocationListResponse.model_validate(response.json())
        self.assertEqual([location.id for location in payload.locations], ['loc_1'])

    async def test_locations_and_edges_endpoints_read_the_persisted_graph_after_generate(
        self,
    ) -> None:
        await self._post('/map/generate', json={'session_id': SESSION_ID})

        locations_response = await self.client.get(
            '/map/locations', params={'session_id': SESSION_ID}
        )
        edges_response = await self.client.get('/map/edges', params={'session_id': SESSION_ID})

        locations_payload = MapLocationListResponse.model_validate(locations_response.json())
        edges_payload = MapEdgeListResponse.model_validate(edges_response.json())
        self.assertEqual(locations_payload.total, 3)
        self.assertEqual(edges_payload.total, 2)

    async def test_delete_map_clears_the_persisted_graph(self) -> None:
        await self._post('/map/generate', json={'session_id': SESSION_ID})

        delete_response = await self._delete('/map', params={'session_id': SESSION_ID})

        self.assertEqual(delete_response.status_code, 200)
        delete_payload = MapDeleteResponse.model_validate(delete_response.json())
        self.assertTrue(delete_payload.deleted)

        # Falls back to live resolution again, since timeline events remain.
        response = await self.client.get('/map', params={'session_id': SESSION_ID})
        payload = MapGraphResponse.model_validate(response.json())
        self.assertEqual(len(payload.locations), 3)

    async def test_delete_map_reports_false_when_nothing_was_generated(self) -> None:
        response = await self._delete('/map', params={'session_id': SESSION_ID})

        self.assertEqual(response.status_code, 200)
        payload = MapDeleteResponse.model_validate(response.json())
        self.assertFalse(payload.deleted)

    async def test_regenerate_overwrites_the_previously_saved_map(self) -> None:
        await self._post('/map/generate', json={'session_id': SESSION_ID})
        await timeline_store.add_events([_event('evt_5', ['Dragon Spire'], order=5)])

        response = await self._post('/map/generate', json={'session_id': SESSION_ID})

        payload = MapGenerateResponse.model_validate(response.json())
        self.assertEqual(payload.locations_generated, 4)
        self.assertEqual(
            [location.canonical_name for location in payload.locations][-1], 'Dragon Spire'
        )


if __name__ == '__main__':
    unittest.main()
