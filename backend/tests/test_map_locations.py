import unittest

from fastapi import HTTPException

from app.api.routers.map import (
    get_event_location,
    list_event_locations,
    list_location_events,
    list_locations,
)
from app.domain.models import TimelineEvent
from app.domain.timeline_store import timeline_store


def _event(
    event_id: str, places: list[str], order: int, session_id: str = 'sess-1'
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


async def _seed_four_event_example() -> None:
    await timeline_store.add_events(
        [
            _event('evt_1', ['Velmora Crossing'], order=1),
            _event('evt_2', ['Silver Lake'], order=2),
            _event('evt_3', ['Ye Olde Tavern'], order=3),
            _event('evt_4', ['the tavern'], order=4),
        ]
    )


class MapLocationsApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await timeline_store.clear_all()

    async def asyncTearDown(self) -> None:
        await timeline_store.clear_all()

    async def test_get_map_locations_returns_resolved_places_for_session(self) -> None:
        await _seed_four_event_example()

        payload = await list_locations(session_id='sess-1')

        self.assertEqual(payload.session_id, 'sess-1')
        self.assertEqual(payload.total, 3)
        self.assertEqual(
            [location.id for location in payload.locations], ['loc_1', 'loc_2', 'loc_3']
        )
        self.assertEqual(payload.locations[0].canonical_name, 'Velmora Crossing')
        self.assertEqual(payload.locations[1].canonical_name, 'Silver Lake')
        self.assertEqual(payload.locations[2].canonical_name, 'Ye Olde Tavern')
        self.assertEqual(payload.locations[2].aliases, ['the tavern'])
        self.assertEqual(payload.locations[2].event_ids, ['evt_3', 'evt_4'])

    async def test_get_map_locations_defaults_to_empty_session(self) -> None:
        payload = await list_locations(session_id='default')

        self.assertEqual(payload.session_id, 'default')
        self.assertEqual(payload.locations, [])
        self.assertEqual(payload.total, 0)

    async def test_get_location_events_returns_linked_timeline_events(self) -> None:
        await _seed_four_event_example()

        payload = await list_location_events(location_id='loc_3', session_id='sess-1')

        self.assertEqual(payload.session_id, 'sess-1')
        self.assertEqual(payload.total, 2)
        self.assertEqual([event.id for event in payload.events], ['evt_3', 'evt_4'])
        self.assertEqual(payload.events[0].location_entities, ['Ye Olde Tavern'])
        self.assertEqual(payload.events[1].location_entities, ['the tavern'])

    async def test_get_location_events_returns_404_for_unknown_place(self) -> None:
        await _seed_four_event_example()

        with self.assertRaises(HTTPException) as raised:
            await list_location_events(location_id='loc_99', session_id='sess-1')

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, 'Location not found')

    async def test_get_event_location_returns_the_place_that_lists_the_event(self) -> None:
        await _seed_four_event_example()

        payload = await get_event_location(event_id='evt_4', session_id='sess-1')

        self.assertEqual(payload.id, 'loc_3')
        self.assertEqual(payload.canonical_name, 'Ye Olde Tavern')
        self.assertEqual(payload.aliases, ['the tavern'])
        self.assertEqual(payload.event_ids, ['evt_3', 'evt_4'])

    async def test_get_event_locations_returns_the_places_that_list_the_event(self) -> None:
        await _seed_four_event_example()

        payload = await list_event_locations(event_id='evt_4', session_id='sess-1')

        self.assertEqual(payload.session_id, 'sess-1')
        self.assertEqual(payload.total, 1)
        self.assertEqual(payload.locations[0].id, 'loc_3')
        self.assertEqual(payload.locations[0].canonical_name, 'Ye Olde Tavern')
        self.assertEqual(payload.locations[0].aliases, ['the tavern'])
        self.assertEqual(payload.locations[0].event_ids, ['evt_3', 'evt_4'])

    async def test_get_event_locations_returns_every_place_mentioned_by_the_event(self) -> None:
        await timeline_store.add_events(
            [
                _event('evt_1', ['Velmora Crossing'], order=1),
                _event('evt_2', ['Silver Lake'], order=2),
                _event('evt_5', ['Velmora Crossing', 'Silver Lake'], order=5),
            ]
        )

        payload = await list_event_locations(event_id='evt_5', session_id='sess-1')

        self.assertEqual(payload.total, 2)
        self.assertEqual([location.id for location in payload.locations], ['loc_1', 'loc_2'])
        self.assertEqual(payload.locations[0].canonical_name, 'Velmora Crossing')
        self.assertEqual(payload.locations[1].canonical_name, 'Silver Lake')

    async def test_get_event_locations_returns_404_when_event_has_no_place(self) -> None:
        await _seed_four_event_example()

        with self.assertRaises(HTTPException) as raised:
            await list_event_locations(event_id='evt_99', session_id='sess-1')

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, 'Location not found')

    async def test_get_event_location_returns_404_when_event_has_no_place(self) -> None:
        await _seed_four_event_example()

        with self.assertRaises(HTTPException) as raised:
            await get_event_location(event_id='evt_99', session_id='sess-1')

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, 'Location not found')


if __name__ == '__main__':
    unittest.main()
