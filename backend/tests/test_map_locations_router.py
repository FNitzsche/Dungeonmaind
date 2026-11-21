import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routers.map import router as map_router
from app.base_models.map_base_models import MapLocationListResponse, MapLocationOut
from app.base_models.timeline_base_models import TimelineEventListResponse, TimelineEventOut
from app.domain.map_store import map_store
from app.domain.models import TimelineEvent
from app.domain.timeline_store import timeline_store
from app.functions.geo.place_resolver import resolve_locations

SESSION_ID = 'sess-1'


def _event(
    event_id: str, places: list[str], order: int, session_id: str = SESSION_ID
) -> TimelineEvent:
    return TimelineEvent(
        id=event_id,
        session_id=session_id,
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


class MapLocationsRouterTests(unittest.IsolatedAsyncioTestCase):
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
        await map_store.clear_session(SESSION_ID)
        await map_store.clear_session('session_b')

    async def test_get_map_locations_matches_worked_example_contract(self) -> None:
        response = await self.client.get('/map/locations', params={'session_id': SESSION_ID})

        self.assertEqual(response.status_code, 200)
        payload = MapLocationListResponse.model_validate(response.json())
        self.assertEqual(payload.session_id, SESSION_ID)
        self.assertEqual(payload.total, 3)
        self.assertEqual(len(payload.locations), 3)
        self.assertEqual(
            [location.id for location in payload.locations], ['loc_1', 'loc_2', 'loc_3']
        )
        self.assertEqual(payload.locations[0].canonical_name, 'Velmora Crossing')
        self.assertEqual(payload.locations[0].aliases, [])
        self.assertEqual(payload.locations[0].event_ids, ['evt_1'])
        self.assertEqual(payload.locations[0].mention_count, 1)
        self.assertEqual(payload.locations[0].first_order, 0)
        self.assertEqual(payload.locations[1].canonical_name, 'Silver Lake')
        self.assertEqual(payload.locations[1].aliases, [])
        self.assertEqual(payload.locations[1].event_ids, ['evt_2'])
        self.assertEqual(payload.locations[1].mention_count, 1)
        self.assertEqual(payload.locations[1].first_order, 1)
        self.assertEqual(payload.locations[2].canonical_name, 'Ye Olde Tavern')
        self.assertEqual(payload.locations[2].aliases, ['the tavern'])
        self.assertEqual(payload.locations[2].event_ids, ['evt_3', 'evt_4'])
        self.assertEqual(payload.locations[2].mention_count, 2)
        self.assertEqual(payload.locations[2].first_order, 2)
        self._assert_location_contract(payload.locations)

    async def test_get_location_events_matches_worked_example_contract(self) -> None:
        response = await self.client.get(
            '/map/locations/loc_3/events', params={'session_id': SESSION_ID}
        )

        self.assertEqual(response.status_code, 200)
        payload = TimelineEventListResponse.model_validate(response.json())
        self.assertEqual(payload.session_id, SESSION_ID)
        self.assertEqual(payload.total, 2)
        self.assertEqual(len(payload.events), 2)
        self.assertEqual([event.id for event in payload.events], ['evt_3', 'evt_4'])
        self.assertEqual(payload.events[0].location_entities, ['Ye Olde Tavern'])
        self.assertEqual(payload.events[1].location_entities, ['the tavern'])
        self._assert_event_contract(payload.events)

    async def test_get_event_locations_matches_worked_example_contract(self) -> None:
        response = await self.client.get(
            '/map/events/evt_4/locations', params={'session_id': SESSION_ID}
        )

        self.assertEqual(response.status_code, 200)
        payload = MapLocationListResponse.model_validate(response.json())
        self.assertEqual(payload.session_id, SESSION_ID)
        self.assertEqual(payload.total, 1)
        self.assertEqual(len(payload.locations), 1)
        self.assertEqual(payload.locations[0].id, 'loc_3')
        self.assertEqual(payload.locations[0].canonical_name, 'Ye Olde Tavern')
        self.assertEqual(payload.locations[0].aliases, ['the tavern'])
        self.assertEqual(payload.locations[0].event_ids, ['evt_3', 'evt_4'])
        self._assert_location_contract(payload.locations)

    async def test_get_location_events_for_loc_1_returns_only_evt_1(self) -> None:
        response = await self.client.get(
            '/map/locations/loc_1/events', params={'session_id': SESSION_ID}
        )

        self.assertEqual(response.status_code, 200)
        payload = TimelineEventListResponse.model_validate(response.json())
        self.assertEqual([event.id for event in payload.events], ['evt_1'])

    async def test_get_event_locations_for_evt_1_returns_loc_1(self) -> None:
        response = await self.client.get(
            '/map/events/evt_1/locations', params={'session_id': SESSION_ID}
        )

        self.assertEqual(response.status_code, 200)
        payload = MapLocationListResponse.model_validate(response.json())
        self.assertEqual([location.id for location in payload.locations], ['loc_1'])
        self.assertEqual(payload.locations[0].canonical_name, 'Velmora Crossing')

    async def test_get_location_events_returns_404_for_unknown_place(self) -> None:
        response = await self.client.get(
            '/map/locations/loc_99/events', params={'session_id': SESSION_ID}
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['detail'], 'Location not found')

    async def test_get_event_locations_returns_404_when_event_has_no_place(self) -> None:
        response = await self.client.get(
            '/map/events/evt_99/locations', params={'session_id': SESSION_ID}
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['detail'], 'Location not found')

    async def test_campaign_graph_reuses_place_ids_for_a_later_session(self) -> None:
        session_a = [
            _event('evt_1', ['Velmora Crossing'], order=1, session_id='session_a'),
            _event('evt_2', ['Silver Lake'], order=2, session_id='session_a'),
            _event('evt_3', ['Ye Olde Tavern'], order=3, session_id='session_a'),
            _event('evt_4', ['the tavern'], order=4, session_id='session_a'),
        ]
        session_b = [
            _event('evt_5', ['the tavern', 'Old Watchtower'], order=5, session_id='session_b'),
            _event('evt_6', ['Silver Lake', 'Old Watchtower'], order=6, session_id='session_b'),
        ]
        await timeline_store.add_events([*session_a, *session_b])
        campaign = resolve_locations(session_b, existing=resolve_locations(session_a))
        await map_store.save_map('session_b', campaign, [])

        locations_response = await self.client.get(
            '/map/locations', params={'session_id': 'session_b'}
        )
        self.assertEqual(locations_response.status_code, 200)
        places = MapLocationListResponse.model_validate(locations_response.json())
        self.assertEqual(
            [location.id for location in places.locations], ['loc_1', 'loc_2', 'loc_3', 'loc_4']
        )
        tavern = places.locations[2]
        self.assertEqual(tavern.canonical_name, 'Ye Olde Tavern')
        self.assertEqual(tavern.aliases, ['the tavern'])
        self.assertEqual(tavern.event_ids, ['evt_3', 'evt_4', 'evt_5'])

        events_response = await self.client.get(
            '/map/locations/loc_3/events', params={'session_id': 'session_b'}
        )
        self.assertEqual(events_response.status_code, 200)
        linked = TimelineEventListResponse.model_validate(events_response.json())
        self.assertEqual([event.id for event in linked.events], ['evt_3', 'evt_4', 'evt_5'])
        self.assertEqual(linked.events[2].location_entities, ['the tavern', 'Old Watchtower'])

        reverse_response = await self.client.get(
            '/map/events/evt_6/locations', params={'session_id': 'session_b'}
        )
        self.assertEqual(reverse_response.status_code, 200)
        reverse = MapLocationListResponse.model_validate(reverse_response.json())
        self.assertEqual([location.id for location in reverse.locations], ['loc_2', 'loc_4'])

    async def test_get_map_locations_returns_empty_list_for_unknown_session(self) -> None:
        response = await self.client.get('/map/locations', params={'session_id': 'missing'})

        self.assertEqual(response.status_code, 200)
        payload = MapLocationListResponse.model_validate(response.json())
        self.assertEqual(payload.session_id, 'missing')
        self.assertEqual(payload.locations, [])
        self.assertEqual(payload.total, 0)

    def _assert_location_contract(self, locations: list[MapLocationOut]) -> None:
        for location in locations:
            self.assertTrue(location.id)
            self.assertEqual(location.session_id, SESSION_ID)
            self.assertTrue(location.canonical_name)
            self.assertIsInstance(location.aliases, list)
            self.assertIsInstance(location.event_ids, list)
            self.assertGreaterEqual(location.mention_count, 1)
            self.assertGreaterEqual(location.first_order, 0)

    def _assert_event_contract(self, events: list[TimelineEventOut]) -> None:
        for event in events:
            self.assertTrue(event.id)
            self.assertEqual(event.session_id, SESSION_ID)
            self.assertTrue(event.title)
            self.assertIsInstance(event.location_entities, list)
            self.assertIsInstance(event.timestamp, float)
            self.assertIsNotNone(event.created_at)


if __name__ == '__main__':
    unittest.main()
