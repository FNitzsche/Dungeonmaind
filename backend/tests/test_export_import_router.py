"""HTTP-level tests for saving and loading a session (export/import endpoints)."""

import json
import os
import tempfile
import unittest
from unittest import mock

from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.api.routers import export_import_session as export_import_router
from app.api.routers.map import router as map_router
from app.api.routers.timeline import router as timeline_router
from app.domain.map_store import map_store
from app.domain.models import Group, Role, TimelineEvent, TimelineEventType
from app.domain.session_state import session_registry
from app.domain.store import store
from app.domain.timeline_store import timeline_store
from app.domain.transcript_store import TranscriptSegment, transcript_store
from app.functions.export_import.session_files import SESSION_FILES
from app.functions.geo.build_map import generate_map

CAMPAIGN = 'Lost Mine'
SESSION = 'Session_1'
SAVED_ID = f'{CAMPAIGN}/{SESSION}'
EXPORT_BODY = {'campaign_name': CAMPAIGN, 'session_name': SESSION}


def _app() -> FastAPI:
    application = FastAPI()
    application.include_router(export_import_router.router, prefix='/exportImport')
    application.include_router(timeline_router, prefix='/timeline')
    application.include_router(map_router, prefix='/map')
    return application


def _event(event_id: str, place: str, order: int, session_id: str) -> TimelineEvent:
    return TimelineEvent(
        id=event_id,
        session_id=session_id,
        title=f'Arrival at {place}',
        description=f'The party is in {place}.',
        event_type=TimelineEventType.travel,
        order=order,
        timestamp=float(order * 10),
        location_entities=[place],
    )


async def _clear(*session_ids: str) -> None:
    for session_id in session_ids:
        await transcript_store.clear_session(session_id)
        await timeline_store.clear_session(session_id)
        await map_store.clear_session(session_id)


async def _seed(session_id: str) -> None:
    await transcript_store.replace_session(
        session_id,
        [
            TranscriptSegment(start=0.0, end=3.0, text='We are in Neverwinter.', speaker='Ana'),
            TranscriptSegment(start=10.0, end=14.0, text='We reach Phandalin.', speaker='DM'),
        ],
    )
    await timeline_store.replace_session(
        session_id,
        [
            _event('evt_1', 'Neverwinter', 0, session_id),
            _event('evt_2', 'Phandalin', 1, session_id),
        ],
    )
    await generate_map(session_id)


def _fake_copy_chroma_db(folder_path: str) -> None:
    os.makedirs(os.path.join(folder_path, 'chroma_db'))
    with open(os.path.join(folder_path, 'chroma_db', 'chroma.sqlite3'), 'w') as f:
        f.write('db')


class ExportImportRouterTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # Every test starts in a fresh, unsaved game, like a newly joined leader.
        self.draft_id = session_registry.start_new()
        await _clear(SAVED_ID, 'Other/Source')
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.saved_dir = os.path.join(self._tmp.name, 'SavedSessions')
        os.makedirs(self.saved_dir)
        self.session_dir = os.path.join(self.saved_dir, CAMPAIGN, SESSION)

        self._original_group = store.group
        store.group = Group()
        self.leader = store.group.add_player('Ana', Role.leader)
        store.group.add_player('Ben', Role.member)

        self.replace_chroma_db = mock.Mock()
        self.adopt_legacy = mock.Mock(return_value=0)
        patches = [
            mock.patch.object(
                export_import_router, 'adopt_legacy_transcriptions', self.adopt_legacy
            ),
            mock.patch.object(export_import_router, 'SAVED_SESSIONS_DIR', self.saved_dir),
            mock.patch.object(export_import_router, 'DATA_DIR', self._tmp.name),
            mock.patch.object(export_import_router, 'copy_chroma_db', _fake_copy_chroma_db),
            mock.patch.object(export_import_router, 'replace_chroma_db', self.replace_chroma_db),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

        self.client = AsyncClient(transport=ASGITransport(app=_app()), base_url='http://test')
        self.addAsyncCleanup(self.client.aclose)

    async def asyncTearDown(self) -> None:
        store.group = self._original_group
        await _clear(self.draft_id, SAVED_ID, 'Other/Source')

    async def _timeline(self, session_id: str) -> list[dict]:
        res = await self.client.get('/timeline/events', params={'session_id': session_id})
        self.assertEqual(res.status_code, 200)
        return res.json()['events']

    async def _map(self, session_id: str) -> dict:
        res = await self.client.get('/map', params={'session_id': session_id})
        self.assertEqual(res.status_code, 200)
        return res.json()

    def _read(self, file_name: str) -> dict:
        with open(os.path.join(self.session_dir, file_name), encoding='utf-8') as f:
            return json.load(f)


class ExportTests(ExportImportRouterTestCase):
    async def test_export_writes_complete_session_folder(self) -> None:
        await _seed(self.draft_id)

        res = await self.client.post('/exportImport/export', json=EXPORT_BODY)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            sorted(os.listdir(self.session_dir)),
            sorted(['group.json', 'settings.json', 'chroma_db', *SESSION_FILES]),
        )
        self.assertEqual(os.listdir(os.path.join(self.saved_dir, CAMPAIGN)), [SESSION])
        self.assertEqual(
            [player['name'] for player in self._read('group.json')['players']], ['Ana', 'Ben']
        )
        segments = self._read('transcript.json')['segments']
        self.assertEqual(
            segments[0],
            {'start': 0.0, 'end': 3.0, 'text': 'We are in Neverwinter.', 'speaker': 'Ana'},
        )
        self.assertEqual(
            [event['id'] for event in self._read('timeline.json')['events']], ['evt_1', 'evt_2']
        )
        map_data = self._read('map.json')
        self.assertEqual(
            [location['canonical_name'] for location in map_data['locations']],
            ['Neverwinter', 'Phandalin'],
        )
        self.assertEqual(map_data['edges'][0]['relationship'], 'travel')

    async def test_timeline_and_map_follow_the_session_to_its_saved_key(self) -> None:
        await _seed(self.draft_id)
        events_before = await self._timeline(self.draft_id)
        map_before = await self._map(self.draft_id)

        res = await self.client.post('/exportImport/export', json=EXPORT_BODY)

        self.assertEqual(res.status_code, 200)
        events_after = await self._timeline(SAVED_ID)
        self.assertEqual(
            [event['id'] for event in events_after], [event['id'] for event in events_before]
        )
        self.assertTrue(all(event['session_id'] == SAVED_ID for event in events_after))
        map_after = await self._map(SAVED_ID)
        self.assertEqual(len(map_after['locations']), len(map_before['locations']))
        self.assertEqual(len(map_after['edges']), len(map_before['edges']))
        # Nothing is left behind for the next unsaved session.
        self.assertEqual(await self._timeline(self.draft_id), [])
        self.assertEqual((await self._map(self.draft_id))['locations'], [])

    async def test_export_uses_given_source_session_id(self) -> None:
        await _seed('Other/Source')

        res = await self.client.post(
            '/exportImport/export', json={**EXPORT_BODY, 'source_session_id': 'Other/Source'}
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(self._read('timeline.json')['events']), 2)
        self.assertEqual(len(await self._timeline(SAVED_ID)), 2)
        self.assertEqual(await self._timeline('Other/Source'), [])

    async def test_export_of_session_without_recording_still_saves(self) -> None:
        res = await self.client.post('/exportImport/export', json=EXPORT_BODY)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(self._read('transcript.json')['segments'], [])
        self.assertEqual(self._read('timeline.json')['events'], [])
        self.assertFalse(self._read('map.json')['generated'])

    async def test_export_without_players_fails_and_leaves_no_folder(self) -> None:
        await _seed(self.draft_id)
        store.group = Group()

        res = await self.client.post('/exportImport/export', json=EXPORT_BODY)

        self.assertEqual(res.status_code, 400)
        self.assertFalse(os.path.exists(self.session_dir))
        self.assertEqual(os.listdir(os.path.join(self.saved_dir, CAMPAIGN)), [])
        self.assertEqual(len(await self._timeline(self.draft_id)), 2)

    async def test_failing_database_copy_fails_whole_save(self) -> None:
        await _seed(self.draft_id)

        def failing_copy(folder_path: str) -> None:
            raise HTTPException(404, detail='Source folder for DB does not exist')

        with mock.patch.object(export_import_router, 'copy_chroma_db', failing_copy):
            res = await self.client.post('/exportImport/export', json=EXPORT_BODY)

        self.assertEqual(res.status_code, 404)
        self.assertFalse(os.path.exists(self.session_dir))
        self.assertEqual(os.listdir(os.path.join(self.saved_dir, CAMPAIGN)), [])
        self.assertEqual(len(await self._timeline(self.draft_id)), 2)
        self.assertEqual(await self._timeline(SAVED_ID), [])

    async def test_failing_session_file_returns_500_and_leaves_no_folder(self) -> None:
        await _seed(self.draft_id)
        from app.functions.export_import import session_files

        real_write = session_files._write_json

        def flaky_write(folder, file_name, data):
            if file_name == 'map.json':
                raise session_files.SessionFileError('Could not save map.json: disk full')
            real_write(folder, file_name, data)

        with mock.patch.object(session_files, '_write_json', flaky_write):
            res = await self.client.post('/exportImport/export', json=EXPORT_BODY)

        self.assertEqual(res.status_code, 500)
        self.assertIn('map.json', res.json()['detail'])
        self.assertFalse(os.path.exists(self.session_dir))
        self.assertEqual(len(await self._timeline(self.draft_id)), 2)

    async def test_saving_again_under_same_name_replaces_the_save(self) -> None:
        await _seed(self.draft_id)
        await self.client.post('/exportImport/export', json=EXPORT_BODY)
        await self.client.delete('/timeline/events/evt_2')

        res = await self.client.post(
            '/exportImport/export', json={**EXPORT_BODY, 'source_session_id': SAVED_ID}
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(os.listdir(os.path.join(self.saved_dir, CAMPAIGN)), [SESSION])
        self.assertEqual(
            [event['id'] for event in self._read('timeline.json')['events']], ['evt_1']
        )
        self.assertEqual(len(await self._timeline(SAVED_ID)), 1)

    async def test_missing_session_name_is_rejected(self) -> None:
        res = await self.client.post('/exportImport/export', json={'campaign_name': CAMPAIGN})

        self.assertEqual(res.status_code, 422)
        self.assertEqual(os.listdir(self.saved_dir), [])


class ImportTests(ExportImportRouterTestCase):
    async def _export_then_forget(self) -> tuple[list[dict], dict]:
        """Save the seeded session, then drop everything from memory like a restart."""
        await _seed(self.draft_id)
        res = await self.client.post('/exportImport/export', json=EXPORT_BODY)
        self.assertEqual(res.status_code, 200)
        events = await self._timeline(SAVED_ID)
        map_graph = await self._map(SAVED_ID)
        await _clear(self.draft_id, SAVED_ID)
        store.group = Group()
        return events, map_graph

    async def test_import_restores_players_timeline_and_map(self) -> None:
        events, map_graph = await self._export_then_forget()

        res = await self.client.post('/exportImport/import', json=EXPORT_BODY)

        self.assertEqual(res.status_code, 200)
        leader = res.json()
        self.assertEqual(leader['name'], 'Ana')
        self.assertEqual(leader['role'], 'leader')
        self.assertEqual(
            sorted(player.name for player in store.group.players.values()), ['Ana', 'Ben']
        )
        self.replace_chroma_db.assert_called_once_with(self.session_dir, self._tmp.name)
        self.assertEqual(await self._timeline(SAVED_ID), events)
        self.assertEqual(await self._map(SAVED_ID), map_graph)
        segments = await transcript_store.get_segments(SAVED_ID)
        self.assertEqual([segment.speaker for segment in segments], ['Ana', 'DM'])

    async def test_place_and_event_links_work_after_import(self) -> None:
        await self._export_then_forget()
        await self.client.post('/exportImport/import', json=EXPORT_BODY)

        place_events = await self.client.get(
            '/map/locations/loc_2/events', params={'session_id': SAVED_ID}
        )
        event_place = await self.client.get(
            '/map/events/evt_1/location', params={'session_id': SAVED_ID}
        )

        self.assertEqual([event['id'] for event in place_events.json()['events']], ['evt_2'])
        self.assertEqual(event_place.json()['canonical_name'], 'Neverwinter')

    async def test_import_of_unknown_session_returns_404(self) -> None:
        res = await self.client.post(
            '/exportImport/import', json={'campaign_name': CAMPAIGN, 'session_name': 'Nope'}
        )

        self.assertEqual(res.status_code, 404)
        self.replace_chroma_db.assert_not_called()

    async def test_corrupt_session_file_rejects_import_before_changing_anything(self) -> None:
        await self._export_then_forget()
        with open(os.path.join(self.session_dir, 'map.json'), 'w', encoding='utf-8') as f:
            f.write('{ broken')
        current_group = store.group
        await timeline_store.replace_session(SAVED_ID, [_event('live', 'Triboar', 0, SAVED_ID)])

        res = await self.client.post('/exportImport/import', json=EXPORT_BODY)

        self.assertEqual(res.status_code, 400)
        self.assertIn('map.json', res.json()['detail'])
        self.assertIs(store.group, current_group)
        self.replace_chroma_db.assert_not_called()
        self.assertEqual([event['id'] for event in await self._timeline(SAVED_ID)], ['live'])

    async def test_session_saved_before_session_files_existed_still_imports(self) -> None:
        await self._export_then_forget()
        for file_name in SESSION_FILES:
            os.remove(os.path.join(self.session_dir, file_name))

        res = await self.client.post('/exportImport/import', json=EXPORT_BODY)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['name'], 'Ana')
        self.assertEqual(await self._timeline(SAVED_ID), [])
        self.assertEqual((await self._map(SAVED_ID))['locations'], [])

    async def test_import_replaces_stale_data_under_the_same_key(self) -> None:
        events, _ = await self._export_then_forget()
        await timeline_store.replace_session(SAVED_ID, [_event('stale', 'Triboar', 0, SAVED_ID)])

        res = await self.client.post('/exportImport/import', json=EXPORT_BODY)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(await self._timeline(SAVED_ID), events)


class ListingTests(ExportImportRouterTestCase):
    async def test_campaign_listing_shows_saved_sessions_only(self) -> None:
        await _seed(self.draft_id)
        await self.client.post('/exportImport/export', json=EXPORT_BODY)
        os.makedirs(os.path.join(self.saved_dir, CAMPAIGN, '.Session_2.saving-abc12345'))
        os.makedirs(os.path.join(self.saved_dir, 'Empty Campaign'))

        res = await self.client.get('/exportImport/getCampaigns')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json()['campaigns'],
            {CAMPAIGN: {'folders': [SESSION]}, 'Empty Campaign': {'folders': []}},
        )

    async def test_session_listing_hides_hidden_folders(self) -> None:
        os.makedirs(os.path.join(self.saved_dir, CAMPAIGN))
        os.makedirs(os.path.join(self.saved_dir, '.tmp'))

        res = await self.client.get('/exportImport/getSessions')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['folders'], [CAMPAIGN])


if __name__ == '__main__':
    unittest.main()
