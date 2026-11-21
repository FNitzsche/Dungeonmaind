import json
import os
import tempfile
import unittest
from unittest import mock

from app.domain.map_edge import MapEdge, MapEdgeRelationship
from app.domain.map_location import MapLocation
from app.domain.map_store import map_store
from app.domain.models import TimelineEvent, TimelineEventType
from app.domain.timeline_store import timeline_store
from app.domain.transcript_store import TranscriptSegment, transcript_store
from app.functions.export_import import session_files
from app.functions.export_import.session_files import (
    MAP_FILE,
    SESSION_FILES,
    TIMELINE_FILE,
    TRANSCRIPT_FILE,
    UNSAVED_SESSION_ID,
    SessionFileError,
    build_session_id,
    load_session_files,
    read_session_files,
    save_session_folder,
    write_session_files,
)

SAVED_ID = 'Lost Mine/Session_1'


def _segments() -> list[TranscriptSegment]:
    return [
        TranscriptSegment(start=0.5, end=4.2, text='We leave Neverwinter at dawn.', speaker='Ana'),
        TranscriptSegment(start=4.2, end=9.0, text='Phandalin is two days east.', speaker='DM'),
    ]


def _events(session_id: str) -> list[TimelineEvent]:
    return [
        TimelineEvent(
            id='evt_1',
            session_id=session_id,
            title='Explorers Depart',
            description='The party leaves Neverwinter.',
            event_type=TimelineEventType.travel,
            order=0,
            timestamp=0.5,
            speaker_name='Ana',
            temporal_entities=['dawn'],
            location_entities=['Neverwinter'],
            characters=['Ana'],
            display_time='00:00:00',
        ),
        TimelineEvent(
            id='evt_2',
            session_id=session_id,
            title='Arrival',
            description='The party reaches Phandalin.',
            event_type=TimelineEventType.travel,
            order=1,
            timestamp=4.2,
            location_entities=['Phandalin'],
        ),
    ]


def _locations(session_id: str) -> list[MapLocation]:
    return [
        MapLocation(
            id='loc_1',
            session_id=session_id,
            canonical_name='Neverwinter',
            aliases=['the city'],
            event_ids=['evt_1'],
            mention_count=1,
            first_order=0,
        ),
        MapLocation(
            id='loc_2',
            session_id=session_id,
            canonical_name='Phandalin',
            event_ids=['evt_2'],
            mention_count=1,
            first_order=1,
        ),
    ]


def _edges(session_id: str) -> list[MapEdge]:
    return [
        MapEdge(
            id='edge_1',
            session_id=session_id,
            from_location_id='loc_1',
            to_location_id='loc_2',
            relationship=MapEdgeRelationship.travel,
            evidence_event_ids=['evt_1', 'evt_2'],
            order=0,
        )
    ]


async def _clear(*session_ids: str) -> None:
    for session_id in session_ids:
        await transcript_store.clear_session(session_id)
        await timeline_store.clear_session(session_id)
        await map_store.clear_session(session_id)


async def _seed(session_id: str, with_map: bool = True) -> None:
    await transcript_store.replace_session(session_id, _segments())
    await timeline_store.replace_session(session_id, _events(session_id))
    if with_map:
        await map_store.save_map(session_id, _locations(session_id), _edges(session_id))


async def _snapshot(session_id: str) -> dict:
    locations = await map_store.get_locations(session_id)
    edges = await map_store.get_edges(session_id)
    return {
        'segments': [item.to_dict() for item in await transcript_store.get_segments(session_id)],
        'events': [item.to_dict() for item in await timeline_store.get_session_events(session_id)],
        'locations': None if locations is None else [item.to_dict() for item in locations],
        'edges': None if edges is None else [item.to_dict() for item in edges],
    }


def _retarget(snapshot: dict, session_id: str) -> dict:
    """Return the snapshot as it should look once stored under another session ID."""
    result = {'segments': snapshot['segments']}
    for key in ('events', 'locations', 'edges'):
        items = snapshot[key]
        result[key] = (
            None if items is None else [{**item, 'session_id': session_id} for item in items]
        )
    return result


class SessionFilesTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await _clear(UNSAVED_SESSION_ID, SAVED_ID)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.campaign_dir = os.path.join(self._tmp.name, 'Lost Mine')
        os.makedirs(self.campaign_dir)

    async def asyncTearDown(self) -> None:
        await _clear(UNSAVED_SESSION_ID, SAVED_ID)

    def _read(self, folder: str, file_name: str) -> dict:
        with open(os.path.join(folder, file_name), encoding='utf-8') as f:
            return json.load(f)


class WriteAndLoadTests(SessionFilesTestCase):
    async def test_writes_three_files_with_expected_content(self) -> None:
        await _seed(UNSAVED_SESSION_ID)

        await write_session_files(self.campaign_dir, UNSAVED_SESSION_ID, stored_session_id=SAVED_ID)

        self.assertEqual(sorted(os.listdir(self.campaign_dir)), sorted(SESSION_FILES))
        transcript = self._read(self.campaign_dir, TRANSCRIPT_FILE)
        self.assertEqual(transcript['session_id'], SAVED_ID)
        self.assertEqual(
            transcript['segments'][0],
            {'start': 0.5, 'end': 4.2, 'text': 'We leave Neverwinter at dawn.', 'speaker': 'Ana'},
        )
        for segment in transcript['segments']:
            self.assertEqual(set(segment), {'start', 'end', 'text', 'speaker'})

        timeline = self._read(self.campaign_dir, TIMELINE_FILE)
        self.assertEqual([event['id'] for event in timeline['events']], ['evt_1', 'evt_2'])
        self.assertTrue(all(event['session_id'] == SAVED_ID for event in timeline['events']))

        map_data = self._read(self.campaign_dir, MAP_FILE)
        self.assertTrue(map_data['generated'])
        self.assertEqual([loc['id'] for loc in map_data['locations']], ['loc_1', 'loc_2'])
        self.assertEqual(map_data['edges'][0]['relationship'], 'travel')

    async def test_round_trip_restores_identical_data_under_saved_id(self) -> None:
        await _seed(UNSAVED_SESSION_ID)
        expected = _retarget(await _snapshot(UNSAVED_SESSION_ID), SAVED_ID)
        await write_session_files(self.campaign_dir, UNSAVED_SESSION_ID, stored_session_id=SAVED_ID)
        await _clear(UNSAVED_SESSION_ID)

        await load_session_files(self.campaign_dir, SAVED_ID)

        self.assertEqual(await _snapshot(SAVED_ID), expected)

    async def test_load_uses_requested_id_even_if_files_name_another(self) -> None:
        await _seed(UNSAVED_SESSION_ID)
        await write_session_files(self.campaign_dir, UNSAVED_SESSION_ID)
        await _clear(UNSAVED_SESSION_ID)

        await load_session_files(self.campaign_dir, SAVED_ID)

        events = await timeline_store.get_session_events(SAVED_ID)
        locations = await map_store.get_locations(SAVED_ID)
        self.assertEqual({event.session_id for event in events}, {SAVED_ID})
        self.assertEqual({location.session_id for location in locations}, {SAVED_ID})
        self.assertEqual(await timeline_store.get_session_events(UNSAVED_SESSION_ID), [])

    async def test_session_without_generated_map_stays_without_map(self) -> None:
        await _seed(UNSAVED_SESSION_ID, with_map=False)
        await write_session_files(self.campaign_dir, UNSAVED_SESSION_ID)
        await map_store.save_map(SAVED_ID, _locations(SAVED_ID), _edges(SAVED_ID))

        await load_session_files(self.campaign_dir, SAVED_ID)

        self.assertFalse(self._read(self.campaign_dir, MAP_FILE)['generated'])
        self.assertFalse(await map_store.has_map(SAVED_ID))
        self.assertEqual(len(await timeline_store.get_session_events(SAVED_ID)), 2)

    async def test_folder_saved_before_these_files_existed_loads_as_empty(self) -> None:
        await _seed(SAVED_ID)

        files = await load_session_files(self.campaign_dir, SAVED_ID)

        self.assertEqual(files.segments, [])
        self.assertEqual(
            await _snapshot(SAVED_ID),
            {'segments': [], 'events': [], 'locations': None, 'edges': None},
        )

    async def test_malformed_file_raises_and_leaves_stores_untouched(self) -> None:
        await _seed(SAVED_ID)
        before = await _snapshot(SAVED_ID)
        with open(os.path.join(self.campaign_dir, TIMELINE_FILE), 'w', encoding='utf-8') as f:
            f.write('{ not json')

        with self.assertRaises(SessionFileError):
            await load_session_files(self.campaign_dir, SAVED_ID)

        self.assertEqual(await _snapshot(SAVED_ID), before)

    async def test_invalid_entries_are_rejected(self) -> None:
        cases = {
            TRANSCRIPT_FILE: {'segments': [{'start': 0.0, 'text': 'no end'}]},
            TIMELINE_FILE: {'events': [{'id': 'evt_1'}]},
            MAP_FILE: {'locations': [{'id': 'loc_1'}], 'edges': []},
            TIMELINE_FILE + ' ': {'events': 'not-a-list'},
        }
        for file_name, content in cases.items():
            with self.subTest(file=file_name), tempfile.TemporaryDirectory() as folder:
                with open(os.path.join(folder, file_name.strip()), 'w', encoding='utf-8') as f:
                    json.dump(content, f)
                with self.assertRaises(SessionFileError):
                    read_session_files(folder)

    async def test_write_failure_is_reported(self) -> None:
        await _seed(UNSAVED_SESSION_ID)
        missing_folder = os.path.join(self.campaign_dir, 'does-not-exist')

        with self.assertRaises(SessionFileError):
            await write_session_files(missing_folder, UNSAVED_SESSION_ID)


class SaveSessionFolderTests(SessionFilesTestCase):
    def _writers(self):
        def write_group(folder: str) -> None:
            with open(os.path.join(folder, 'group.json'), 'w', encoding='utf-8') as f:
                json.dump({'players': ['Ana']}, f)

        def write_db(folder: str) -> None:
            os.makedirs(os.path.join(folder, 'chroma_db'))

        return write_group, write_db

    def _hidden_entries(self) -> list[str]:
        return [name for name in os.listdir(self.campaign_dir) if name.startswith('.')]

    async def test_save_writes_everything_and_rekeys_stores(self) -> None:
        await _seed(UNSAVED_SESSION_ID)
        expected = _retarget(await _snapshot(UNSAVED_SESSION_ID), SAVED_ID)

        folder = await save_session_folder(
            self.campaign_dir, 'Session_1', UNSAVED_SESSION_ID, SAVED_ID, self._writers()
        )

        self.assertEqual(folder, os.path.join(self.campaign_dir, 'Session_1'))
        self.assertEqual(
            sorted(os.listdir(folder)), sorted(['group.json', 'chroma_db', *SESSION_FILES])
        )
        self.assertEqual(self._hidden_entries(), [])
        # The saved session keeps showing its timeline and map under the new key ...
        self.assertEqual(await _snapshot(SAVED_ID), expected)
        # ... and nothing is left behind for the next unsaved session.
        self.assertEqual(
            await _snapshot(UNSAVED_SESSION_ID),
            {'segments': [], 'events': [], 'locations': None, 'edges': None},
        )

    async def test_saved_folder_can_be_loaded_again(self) -> None:
        await _seed(UNSAVED_SESSION_ID)
        folder = await save_session_folder(
            self.campaign_dir, 'Session_1', UNSAVED_SESSION_ID, SAVED_ID, self._writers()
        )
        expected = await _snapshot(SAVED_ID)
        await _clear(SAVED_ID)

        await load_session_files(folder, SAVED_ID)

        self.assertEqual(await _snapshot(SAVED_ID), expected)

    async def test_failing_writer_fails_whole_save(self) -> None:
        await _seed(UNSAVED_SESSION_ID)
        before = await _snapshot(UNSAVED_SESSION_ID)
        write_group, _ = self._writers()

        def failing_db(folder: str) -> None:
            raise PermissionError('chroma_db is locked')

        with self.assertRaises(PermissionError):
            await save_session_folder(
                self.campaign_dir,
                'Session_1',
                UNSAVED_SESSION_ID,
                SAVED_ID,
                (write_group, failing_db),
            )

        self.assertEqual(os.listdir(self.campaign_dir), [])
        self.assertEqual(await _snapshot(UNSAVED_SESSION_ID), before)
        self.assertEqual(await timeline_store.get_session_events(SAVED_ID), [])

    async def test_failing_session_file_fails_whole_save(self) -> None:
        for failing_file in SESSION_FILES:
            with self.subTest(file=failing_file):
                await _clear(UNSAVED_SESSION_ID, SAVED_ID)
                await _seed(UNSAVED_SESSION_ID)
                before = await _snapshot(UNSAVED_SESSION_ID)
                real_write = session_files._write_json

                def flaky_write(folder, file_name, data, _failing=failing_file, _real=real_write):
                    if file_name == _failing:
                        raise SessionFileError(f'Could not save {file_name}: disk full')
                    _real(folder, file_name, data)

                with (
                    mock.patch.object(session_files, '_write_json', flaky_write),
                    self.assertRaises(SessionFileError),
                ):
                    await save_session_folder(
                        self.campaign_dir,
                        'Session_1',
                        UNSAVED_SESSION_ID,
                        SAVED_ID,
                        self._writers(),
                    )

                self.assertEqual(os.listdir(self.campaign_dir), [])
                self.assertEqual(await _snapshot(UNSAVED_SESSION_ID), before)

    async def test_failed_save_keeps_previous_save_intact(self) -> None:
        await _seed(UNSAVED_SESSION_ID)
        folder = await save_session_folder(
            self.campaign_dir, 'Session_1', UNSAVED_SESSION_ID, SAVED_ID, self._writers()
        )
        previous = {name: self._read(folder, name) for name in SESSION_FILES}

        def failing_writer(folder: str) -> None:
            raise OSError('disk full')

        with self.assertRaises(OSError):
            await save_session_folder(
                self.campaign_dir, 'Session_1', SAVED_ID, SAVED_ID, (failing_writer,)
            )

        self.assertEqual(os.listdir(self.campaign_dir), ['Session_1'])
        self.assertEqual({name: self._read(folder, name) for name in SESSION_FILES}, previous)

    async def test_saving_again_replaces_previous_save(self) -> None:
        await _seed(UNSAVED_SESSION_ID)
        folder = await save_session_folder(
            self.campaign_dir, 'Session_1', UNSAVED_SESSION_ID, SAVED_ID, self._writers()
        )
        await timeline_store.delete_event('evt_2')

        await save_session_folder(
            self.campaign_dir, 'Session_1', SAVED_ID, SAVED_ID, self._writers()
        )

        self.assertEqual(os.listdir(self.campaign_dir), ['Session_1'])
        events = self._read(folder, TIMELINE_FILE)['events']
        self.assertEqual([event['id'] for event in events], ['evt_1'])
        self.assertEqual(len(await timeline_store.get_session_events(SAVED_ID)), 1)


class SessionKeyTests(unittest.IsolatedAsyncioTestCase):
    def test_build_session_id_matches_frontend_key(self) -> None:
        self.assertEqual(build_session_id('Lost Mine', 'Session_1'), 'Lost Mine/Session_1')
        self.assertEqual(build_session_id(' Lost Mine ', ' Session_1 '), 'Lost Mine/Session_1')

    async def test_rename_to_same_id_keeps_data(self) -> None:
        await _clear('same')
        await _seed('same')
        before = await _snapshot('same')

        await session_files.rekey_session('same', 'same')

        self.assertEqual(await _snapshot('same'), before)
        await _clear('same')

    async def test_rename_replaces_data_already_under_new_id(self) -> None:
        await _clear('old', 'new')
        await _seed('old')
        await timeline_store.replace_session(
            'new', [TimelineEvent(id='stale', session_id='new', title='x', description='y')]
        )

        await session_files.rekey_session('old', 'new')

        events = await timeline_store.get_session_events('new')
        self.assertEqual([event.id for event in events], ['evt_1', 'evt_2'])
        self.assertIsNone(await timeline_store.get_event('stale'))
        self.assertEqual(await timeline_store.get_session_events('old'), [])
        await _clear('old', 'new')


if __name__ == '__main__':
    unittest.main()
