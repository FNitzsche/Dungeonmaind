"""HTTP-level tests for the timeline endpoints."""

import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routers import timeline as timeline_router_module
from app.domain.map_store import map_store
from app.domain.models import TimelineEvent, TimelineEventType
from app.domain.timeline_store import timeline_store
from app.functions.geo.build_map import generate_map

SESSION_ID = 'Lost Mine/Session_1'
OTHER_SESSION_ID = 'Lost Mine/Session_2'


def _app() -> FastAPI:
    application = FastAPI()
    application.include_router(timeline_router_module.router, prefix='/timeline')
    return application


def _event(event_id: str, order: int, session_id: str = SESSION_ID, **kwargs) -> TimelineEvent:
    return TimelineEvent(
        id=event_id,
        session_id=session_id,
        title=kwargs.pop('title', f'Event {event_id}'),
        description=kwargs.pop('description', 'Something happened.'),
        order=order,
        **kwargs,
    )


def _doc(text: str, **metadata) -> SimpleNamespace:
    return SimpleNamespace(page_content=text, metadata=metadata)


class TimelineRouterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await timeline_store.clear_session(SESSION_ID)
        await timeline_store.clear_session(OTHER_SESSION_ID)
        await map_store.clear_session(SESSION_ID)
        self.client = AsyncClient(transport=ASGITransport(app=_app()), base_url='http://test')
        self.addAsyncCleanup(self.client.aclose)

    async def asyncTearDown(self) -> None:
        await timeline_store.clear_session(SESSION_ID)
        await timeline_store.clear_session(OTHER_SESSION_ID)
        await map_store.clear_session(SESSION_ID)

    async def _list(self, session_id: str = SESSION_ID) -> dict:
        res = await self.client.get('/timeline/events', params={'session_id': session_id})
        self.assertEqual(res.status_code, 200)
        return res.json()

    async def test_list_is_empty_for_unknown_session(self) -> None:
        body = await self._list('never-used')

        self.assertEqual(body, {'session_id': 'never-used', 'events': [], 'total': 0})

    async def test_list_returns_session_events_sorted_by_order(self) -> None:
        await timeline_store.add_events(
            [_event('b', 2), _event('a', 0), _event('c', 1), _event('x', 0, OTHER_SESSION_ID)]
        )

        body = await self._list()

        self.assertEqual([event['id'] for event in body['events']], ['a', 'c', 'b'])
        self.assertEqual(body['total'], 3)
        self.assertEqual(body['session_id'], SESSION_ID)

    async def test_event_fields_are_serialized(self) -> None:
        await timeline_store.add_events(
            [
                _event(
                    'a',
                    0,
                    title='Explorers Depart',
                    event_type=TimelineEventType.travel,
                    timestamp=125.5,
                    speaker_name='Ana',
                    temporal_entities=['dawn'],
                    location_entities=['Neverwinter'],
                    characters=['Ana'],
                    display_time='00:02:05',
                )
            ]
        )

        event = (await self._list())['events'][0]

        self.assertEqual(event['title'], 'Explorers Depart')
        self.assertEqual(event['event_type'], 'travel')
        self.assertEqual(event['timestamp'], 125.5)
        self.assertEqual(event['speaker_name'], 'Ana')
        self.assertEqual(event['temporal_entities'], ['dawn'])
        self.assertEqual(event['location_entities'], ['Neverwinter'])
        self.assertEqual(event['characters'], ['Ana'])
        self.assertEqual(event['display_time'], '00:02:05')
        self.assertIn('created_at', event)

    async def test_get_single_event(self) -> None:
        await timeline_store.add_events([_event('a', 0)])

        res = await self.client.get('/timeline/events/a')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['id'], 'a')

    async def test_get_unknown_event_returns_404(self) -> None:
        res = await self.client.get('/timeline/events/missing')

        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()['detail'], 'Event not found')

    async def test_delete_event_removes_only_that_event(self) -> None:
        await timeline_store.add_events([_event('a', 0), _event('b', 1)])

        res = await self.client.delete('/timeline/events/a')

        self.assertEqual(res.json(), {'deleted': True, 'event_id': 'a'})
        self.assertEqual([event['id'] for event in (await self._list())['events']], ['b'])

    async def test_delete_unknown_event_reports_not_deleted(self) -> None:
        res = await self.client.delete('/timeline/events/missing')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {'deleted': False, 'event_id': 'missing'})

    async def test_clear_removes_only_the_requested_session(self) -> None:
        await timeline_store.add_events([_event('a', 0), _event('x', 0, OTHER_SESSION_ID)])

        res = await self.client.delete('/timeline/events', params={'session_id': SESSION_ID})

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['deleted'])
        self.assertEqual((await self._list())['events'], [])
        self.assertEqual(len((await self._list(OTHER_SESSION_ID))['events']), 1)

    async def test_generate_without_transcriptions_returns_404(self) -> None:
        with mock.patch.object(
            timeline_router_module, 'get_all_transcription_documents', return_value=[]
        ):
            res = await self.client.post('/timeline/generate', json={'session_id': SESSION_ID})

        self.assertEqual(res.status_code, 404)
        self.assertIn('No transcription documents', res.json()['detail'])

    async def test_generate_stores_events_from_the_extractor(self) -> None:
        docs = [
            _doc('We leave Neverwinter.', player_id='Ana', start_time=1.5),
            _doc('We reach Phandalin.', player_id='DM', start_time=9.0),
        ]
        extracted = [_event('', 0, title='Explorers Depart'), _event('', 1, title='Arrival')]
        with (
            mock.patch.object(
                timeline_router_module, 'get_all_transcription_documents', return_value=docs
            ),
            mock.patch.object(
                timeline_router_module, 'extract_events_from_transcriptions', return_value=extracted
            ) as extractor,
        ):
            res = await self.client.post('/timeline/generate', json={'session_id': SESSION_ID})

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['events_generated'], 2)
        self.assertEqual(
            [event['title'] for event in body['events']], ['Explorers Depart', 'Arrival']
        )
        self.assertTrue(all(event['id'] for event in body['events']))
        extractor.assert_called_once_with(
            texts=['We leave Neverwinter.', 'We reach Phandalin.'],
            speakers=['Ana', 'DM'],
            timestamps=[1.5, 9.0],
            session_id=SESSION_ID,
        )
        self.assertEqual(len((await self._list())['events']), 2)

    async def test_generate_falls_back_to_transcript_metadata_without_llm(self) -> None:
        docs = [
            _doc(
                'They departed from Velmora Crossing at dawn.',
                player_id='Ana',
                start_time=125.5,
                temporal_entities='dawn',
                location_entities='Velmora Crossing',
            ),
            _doc('Just some table talk.', player_id='Ben', start_time=140.0),
        ]
        with (
            mock.patch.object(
                timeline_router_module, 'get_all_transcription_documents', return_value=docs
            ),
            mock.patch.object(
                timeline_router_module, 'extract_events_from_transcriptions', return_value=[]
            ),
        ):
            res = await self.client.post('/timeline/generate', json={'session_id': SESSION_ID})

        self.assertEqual(res.status_code, 200)
        events = res.json()['events']
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['location_entities'], ['Velmora Crossing'])
        self.assertEqual(events[0]['timestamp'], 125.5)
        self.assertEqual(events[0]['display_time'], '00:02:05')
        self.assertEqual(events[0]['session_id'], SESSION_ID)

    async def test_generate_replaces_previous_events_of_the_session(self) -> None:
        await timeline_store.add_events([_event('old', 0), _event('x', 0, OTHER_SESSION_ID)])
        with (
            mock.patch.object(
                timeline_router_module,
                'get_all_transcription_documents',
                return_value=[_doc('We reach Phandalin.', player_id='DM')],
            ),
            mock.patch.object(
                timeline_router_module,
                'extract_events_from_transcriptions',
                return_value=[_event('', 0, title='Arrival')],
            ),
        ):
            res = await self.client.post('/timeline/generate', json={'session_id': SESSION_ID})

        self.assertEqual(res.status_code, 200)
        self.assertEqual([event['title'] for event in (await self._list())['events']], ['Arrival'])
        self.assertEqual(len((await self._list(OTHER_SESSION_ID))['events']), 1)

    async def test_generate_rebuilds_a_previously_saved_map(self) -> None:
        # A map was saved earlier, from a timeline that named two places...
        await timeline_store.add_events(
            [
                _event('a', 0, location_entities=['Velmora Crossing']),
                _event('b', 1, location_entities=['Silver Lake']),
            ]
        )
        await generate_map(SESSION_ID)
        # ...then the timeline is regenerated and now also names a third place.
        regenerated = [
            _event('', 0, location_entities=['Velmora Crossing']),
            _event('', 1, location_entities=['Silver Lake']),
            _event('', 2, location_entities=['Kharzul Ridge']),
        ]
        with (
            mock.patch.object(
                timeline_router_module,
                'get_all_transcription_documents',
                return_value=[_doc('We reach Kharzul Ridge.', player_id='DM')],
            ),
            mock.patch.object(
                timeline_router_module,
                'extract_events_from_transcriptions',
                return_value=regenerated,
            ),
        ):
            res = await self.client.post('/timeline/generate', json={'session_id': SESSION_ID})

        self.assertEqual(res.status_code, 200)
        saved = await map_store.get_locations(SESSION_ID)
        self.assertEqual(
            sorted(location.canonical_name for location in saved or []),
            ['Kharzul Ridge', 'Silver Lake', 'Velmora Crossing'],
        )


if __name__ == '__main__':
    unittest.main()
