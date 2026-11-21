import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routers.map import router as map_router
from app.base_models.map_base_models import MapEdgeListResponse, MapEdgeOut
from app.domain.models import TimelineEvent
from app.domain.timeline_store import timeline_store

SESSION_ID = 'sess-1'


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


class MapEdgesRouterTests(unittest.IsolatedAsyncioTestCase):
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
        self.client = AsyncClient(transport=ASGITransport(app=_map_app()), base_url='http://test')

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        await timeline_store.clear_all()

    async def test_get_map_edges_matches_worked_example_contract(self) -> None:
        response = await self.client.get('/map/edges', params={'session_id': SESSION_ID})

        self.assertEqual(response.status_code, 200)
        payload = MapEdgeListResponse.model_validate(response.json())
        self.assertEqual(payload.session_id, SESSION_ID)
        self.assertEqual(payload.total, 2)
        self.assertEqual(len(payload.edges), 2)

        self.assertEqual(payload.edges[0].id, 'edge_1')
        self.assertEqual(payload.edges[0].from_location_id, 'loc_1')
        self.assertEqual(payload.edges[0].to_location_id, 'loc_2')
        self.assertEqual(payload.edges[0].relationship, 'travel')
        self.assertEqual(payload.edges[0].evidence_event_ids, ['evt_1', 'evt_2'])
        self.assertEqual(payload.edges[0].order, 0)

        self.assertEqual(payload.edges[1].id, 'edge_2')
        self.assertEqual(payload.edges[1].from_location_id, 'loc_2')
        self.assertEqual(payload.edges[1].to_location_id, 'loc_3')
        self.assertEqual(payload.edges[1].relationship, 'travel')
        self.assertEqual(payload.edges[1].evidence_event_ids, ['evt_2', 'evt_3'])
        self.assertEqual(payload.edges[1].order, 1)

        self._assert_edge_contract(payload.edges)

    async def test_no_third_edge_between_evt_3_and_evt_4(self) -> None:
        response = await self.client.get('/map/edges', params={'session_id': SESSION_ID})

        payload = MapEdgeListResponse.model_validate(response.json())
        pairs = [(edge.from_location_id, edge.to_location_id) for edge in payload.edges]
        self.assertNotIn(('loc_3', 'loc_3'), pairs)

    async def test_get_location_edges_returns_links_touching_a_place(self) -> None:
        response = await self.client.get(
            '/map/locations/loc_2/edges', params={'session_id': SESSION_ID}
        )

        self.assertEqual(response.status_code, 200)
        payload = MapEdgeListResponse.model_validate(response.json())
        # loc_2 is both the destination of edge_1 and the source of edge_2.
        self.assertEqual(payload.total, 2)
        self.assertEqual([edge.id for edge in payload.edges], ['edge_1', 'edge_2'])
        self._assert_edge_contract(payload.edges)

    async def test_get_location_edges_for_endpoint_place_returns_single_link(self) -> None:
        response = await self.client.get(
            '/map/locations/loc_1/edges', params={'session_id': SESSION_ID}
        )

        self.assertEqual(response.status_code, 200)
        payload = MapEdgeListResponse.model_validate(response.json())
        self.assertEqual([edge.id for edge in payload.edges], ['edge_1'])

    async def test_get_location_edges_returns_404_for_unknown_place(self) -> None:
        response = await self.client.get(
            '/map/locations/loc_99/edges', params={'session_id': SESSION_ID}
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['detail'], 'Location not found')

    async def test_get_map_edges_returns_empty_list_for_unknown_session(self) -> None:
        response = await self.client.get('/map/edges', params={'session_id': 'missing'})

        self.assertEqual(response.status_code, 200)
        payload = MapEdgeListResponse.model_validate(response.json())
        self.assertEqual(payload.session_id, 'missing')
        self.assertEqual(payload.edges, [])
        self.assertEqual(payload.total, 0)

    def _assert_edge_contract(self, edges: list[MapEdgeOut]) -> None:
        for edge in edges:
            self.assertTrue(edge.id)
            self.assertEqual(edge.session_id, SESSION_ID)
            self.assertTrue(edge.from_location_id)
            self.assertTrue(edge.to_location_id)
            self.assertIn(edge.relationship, {'travel', 'proximity'})
            self.assertIsInstance(edge.evidence_event_ids, list)
            self.assertGreaterEqual(edge.order, 0)


if __name__ == '__main__':
    unittest.main()
