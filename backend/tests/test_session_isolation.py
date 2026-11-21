"""Regression tests: two game sessions must never share transcript, timeline or map.

Reproduces the reported bug. A table records a whole script in one game, then
starts a completely new game and records only the first half. Before the fix
the new game showed the events of the whole script, because

- every unsaved game used the same session key (``unsaved``), and
- transcript chunks in the vector database carried no session, so
  "Generate Events" read the recordings of every game ever played.

The speech model, the LLM and the vector database are replaced by fakes. The
fake vector database honours metadata filters, so the tests fail if the code
stops restricting its queries to one session.
"""

import itertools
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routers import export_import_session as export_import_router
from app.api.routers import timeline as timeline_router_module
from app.api.routers.map import router as map_router
from app.api.routers.players import router as players_router
from app.api.routers.process_audio_data import router as audio_router
from app.api.routers.session import router as session_router
from app.core.config import settings
from app.domain.map_store import map_store
from app.domain.models import Group, TimelineEvent, TimelineEventType
from app.domain.session_state import SessionRegistry, session_registry
from app.domain.store import store
from app.domain.timeline_store import timeline_store
from app.domain.transcript_store import transcript_store
from app.functions.embedding import embedding_model
from app.functions.process_audio_data import transcribe_audio as pipeline

PLACES = ('Neverwinter', 'Phandalin', 'Cragmaw Castle', 'Wave Echo Cave', 'Thundertree')

FIRST_HALF = [
    {'start': 0.0, 'end': 3.0, 'text': 'We set out from Neverwinter at dawn.', 'speaker': 'Ana'},
    {'start': 3.0, 'end': 6.0, 'text': 'By nightfall we arrive in Phandalin.', 'speaker': 'DM'},
]
SECOND_HALF = [
    {'start': 0.0, 'end': 3.0, 'text': 'We storm Cragmaw Castle.', 'speaker': 'Ben'},
    {'start': 3.0, 'end': 6.0, 'text': 'We descend into Wave Echo Cave.', 'speaker': 'DM'},
]
WHOLE_SCRIPT = FIRST_HALF + SECOND_HALF
OTHER_STORY = [
    {'start': 0.0, 'end': 4.0, 'text': 'A dragon circles above Thundertree.', 'speaker': 'Cy'}
]


def _texts(segments: list[dict]) -> list[str]:
    return [segment['text'] for segment in segments]


class FakeVectorStore:
    """In-memory stand-in for the Chroma vector store that honours ``where`` filters.

    One list of rows per ``persist_directory``, like one database per folder.
    """

    databases: dict[str, list[dict]] = {}  # noqa: RUF012 - shared on purpose, reset per test

    def __init__(self, persist_directory=None, embedding_function=None) -> None:
        self.rows = self.databases.setdefault(persist_directory, [])
        self._collection = self

    @classmethod
    def from_documents(cls, documents, embedding=None, persist_directory=None):
        vectorstore = cls(persist_directory=persist_directory)
        vectorstore.add_documents(documents)
        return vectorstore

    @staticmethod
    def _matches(metadata: dict, where: dict | None) -> bool:
        if not where:
            return True
        if '$and' in where:
            return all(FakeVectorStore._matches(metadata, part) for part in where['$and'])
        return all(metadata.get(key) == value for key, value in where.items())

    def add_documents(self, documents) -> None:
        for document in documents:
            self.rows.append(
                {
                    'id': f'chunk-{len(self.rows)}',
                    'document': document.page_content,
                    'metadata': dict(document.metadata),
                }
            )

    def get(self, where=None, include=None) -> dict:
        rows = [row for row in self.rows if self._matches(row['metadata'], where)]
        return {
            'ids': [row['id'] for row in rows],
            'documents': [row['document'] for row in rows],
            'metadatas': [dict(row['metadata']) for row in rows],
        }

    def update(self, ids, metadatas) -> None:
        updates = dict(zip(ids, metadatas))
        for row in self.rows:
            if row['id'] in updates:
                row['metadata'] = dict(updates[row['id']])

    def similarity_search(self, query, k=4, filter=None):
        rows = [row for row in self.rows if self._matches(row['metadata'], filter)]
        return [
            SimpleNamespace(page_content=row['document'], metadata=row['metadata'])
            for row in rows[:k]
        ]


class FakeWhisper:
    """Stands in for ``whisperx``; returns the segments queued for the next upload."""

    def __init__(self) -> None:
        self.next_segments: list[dict] = []

    def load_audio(self, path: str) -> str:
        return 'audio-array'

    def transcribe(self, audio, batch_size: int = 16) -> dict:
        return {'language': 'en', 'segments': [dict(segment) for segment in self.next_segments]}

    def load_align_model(self, language_code: str, device: str):
        return 'align-model', {}

    def align(self, segments, model, metadata, audio, device, return_char_alignments=False):
        return {'segments': segments}


def make_fake_extractor():
    """One event per text that names a known place (stands in for the LLM)."""
    counter = itertools.count()

    def fake_extract_events(
        texts, speakers=None, timestamps=None, session_id='default', entities=None
    ):
        events = []
        for text in texts:
            places = [place for place in PLACES if place in text]
            if places:
                events.append(
                    TimelineEvent(
                        id='',
                        session_id=session_id,
                        title=f'Scene in {places[0]}',
                        description=text,
                        event_type=TimelineEventType.travel,
                        order=next(counter),
                        location_entities=places,
                    )
                )
        return events

    return fake_extract_events


def write_saved_chunks(database_folder: str, chunks: list[dict]) -> None:
    """Store the fake database's rows inside a saved session's database folder."""
    with open(os.path.join(database_folder, 'chunks.json'), 'w', encoding='utf-8') as f:
        json.dump(chunks, f)


def read_saved_chunks(database_folder: str) -> list[dict]:
    """Read the fake database rows of a saved session's database folder."""
    with open(os.path.join(database_folder, 'chunks.json'), encoding='utf-8') as f:
        return json.load(f)


class SessionIsolationTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.saved_dir = os.path.join(self._tmp.name, 'SavedSessions')
        self.main_db = os.path.join(self._tmp.name, 'chroma_db')
        os.makedirs(self.saved_dir)
        os.makedirs(self.main_db)

        FakeVectorStore.databases = {}
        self.whisper = FakeWhisper()
        self._known_sessions: set[str] = set()
        self._original_group = store.group
        self._original_db_path = settings.chroma_db_path
        store.group = Group()
        settings.chroma_db_path = self.main_db
        session_registry.start_new()
        extractor = make_fake_extractor()

        def fake_copy_chroma_db(folder_path: str) -> None:
            """Saving copies the whole live database into the session folder."""
            target = os.path.join(folder_path, 'chroma_db')
            os.makedirs(target)
            open(os.path.join(target, 'chroma.sqlite3'), 'w').close()
            write_saved_chunks(target, FakeVectorStore.databases.get(settings.chroma_db_path, []))

        def fake_replace_chroma_db(saved_session_path: str, data_path: str) -> None:
            """Loading switches the backend to a private copy of the saved database."""
            target = os.path.join(self.main_db, f'tmp{len(FakeVectorStore.databases)}')
            os.makedirs(target)
            open(os.path.join(target, 'chroma.sqlite3'), 'w').close()
            FakeVectorStore.databases[target] = read_saved_chunks(
                os.path.join(saved_session_path, 'chroma_db')
            )
            settings.chroma_db_path = target

        patches = [
            mock.patch.object(embedding_model, 'Chroma', FakeVectorStore),
            mock.patch.object(embedding_model, 'SentenceTransformerEmbeddings', mock.Mock()),
            mock.patch.object(settings, 'entity_llm_fallback', False),
            mock.patch.object(settings, 'enable_diarization', False),
            mock.patch.object(settings, 'backend_root_path', self._tmp.name),
            mock.patch.object(pipeline, 'ensure_transcription_models_loaded', lambda: None),
            mock.patch.object(pipeline, 'whisperx', self.whisper),
            mock.patch.object(pipeline, 'transcription_model', self.whisper),
            mock.patch.object(pipeline, 'alignment_models_cache', {}),
            mock.patch.object(pipeline, 'extract_events_from_transcriptions', extractor),
            mock.patch.object(
                timeline_router_module, 'extract_events_from_transcriptions', extractor
            ),
            mock.patch.object(export_import_router, 'SAVED_SESSIONS_DIR', self.saved_dir),
            mock.patch.object(export_import_router, 'DATA_DIR', self._tmp.name),
            mock.patch.object(export_import_router, 'copy_chroma_db', fake_copy_chroma_db),
            mock.patch.object(export_import_router, 'replace_chroma_db', fake_replace_chroma_db),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

        application = FastAPI()
        application.include_router(session_router, prefix='/session')
        application.include_router(players_router, prefix='/players')
        application.include_router(audio_router, prefix='/processAudioData')
        application.include_router(timeline_router_module.router, prefix='/timeline')
        application.include_router(map_router, prefix='/map')
        application.include_router(export_import_router.router, prefix='/exportImport')
        self.client = AsyncClient(transport=ASGITransport(app=application), base_url='http://test')
        self.addAsyncCleanup(self.client.aclose)

    async def asyncTearDown(self) -> None:
        store.group = self._original_group
        settings.chroma_db_path = self._original_db_path
        for session_id in self._known_sessions | {'unsaved'}:
            await transcript_store.clear_session(session_id)
            await timeline_store.clear_session(session_id)
            await map_store.clear_session(session_id)

    # --- helpers that act like the frontend -------------------------------------------

    async def current_session(self) -> str:
        res = await self.client.get('/session/current')
        self.assertEqual(res.status_code, 200, res.text)
        session_id = res.json()['session_id']
        self._known_sessions.add(session_id)
        return session_id

    async def new_game(self, leader_name: str) -> str:
        """A leader joins on the login page, which is how a new game starts."""
        store.group = Group()
        res = await self.client.post('/players', json={'name': leader_name, 'role': 'leader'})
        self.assertEqual(res.status_code, 201, res.text)
        self.leader_id = res.json()['id']
        return await self.current_session()

    async def record(self, session_id: str | None, segments: list[dict]) -> None:
        self.whisper.next_segments = segments
        res = await self.client.post(
            '/processAudioData/transcribeAudioFile',
            files={'audio': ('chunk.webm', b'audio', 'audio/webm')},
            data={'session_id': session_id} if session_id is not None else None,
        )
        self.assertEqual(res.status_code, 200, res.text)

    async def event_texts(self, session_id: str) -> list[str]:
        res = await self.client.get('/timeline/events', params={'session_id': session_id})
        self.assertEqual(res.status_code, 200, res.text)
        return [event['description'] for event in res.json()['events']]

    async def map_places(self, session_id: str) -> list[str]:
        res = await self.client.get('/map', params={'session_id': session_id})
        self.assertEqual(res.status_code, 200, res.text)
        graph = res.json()
        names = {location['id']: location['canonical_name'] for location in graph['locations']}
        for edge in graph['edges']:
            self.assertIn(edge['from_location_id'], names)
            self.assertIn(edge['to_location_id'], names)
        return list(names.values())

    async def transcript_texts(self, session_id: str) -> list[str]:
        return [segment.text for segment in await transcript_store.get_segments(session_id)]

    async def generate_events(self, session_id: str):
        return await self.client.post('/timeline/generate', json={'session_id': session_id})

    async def save(self, campaign: str, session: str, source: str | None = None) -> None:
        body = {'campaign_name': campaign, 'session_name': session}
        if source is not None:
            body['source_session_id'] = source
        res = await self.client.post('/exportImport/export', json=body)
        self.assertEqual(res.status_code, 200, res.text)
        self._known_sessions.add(f'{campaign}/{session}')

    async def load(self, campaign: str, session: str) -> None:
        res = await self.client.post(
            '/exportImport/import', json={'campaign_name': campaign, 'session_name': session}
        )
        self.assertEqual(res.status_code, 200, res.text)
        self._known_sessions.add(f'{campaign}/{session}')

    async def restart_backend(self) -> None:
        """Everything held in memory is lost; files and the vector database remain."""
        for session_id in list(self._known_sessions):
            await transcript_store.clear_session(session_id)
            await timeline_store.clear_session(session_id)
            await map_store.clear_session(session_id)
        fresh = SessionRegistry()
        session_registry._uids = fresh._uids
        session_registry._active_session_id = fresh._active_session_id
        settings.chroma_db_path = self.main_db
        store.group = Group()

    def stored_chunks(self, path: str | None = None) -> list[dict]:
        return FakeVectorStore.databases.get(path or settings.chroma_db_path, [])


class SessionIdentityTests(SessionIsolationTestCase):
    async def test_every_new_game_gets_its_own_session_key(self) -> None:
        first = await self.new_game('Ana')
        second = await self.new_game('Ben')
        third = await self.new_game('Cy')

        self.assertEqual(len({first, second, third}), 3)
        for session_id in (first, second, third):
            self.assertTrue(session_id.startswith('draft-'))
            self.assertNotIn(session_id, ('unsaved', 'default', 'none'))

    async def test_a_joining_member_stays_in_the_leaders_session(self) -> None:
        session_id = await self.new_game('Ana')

        res = await self.client.post('/players', json={'name': 'Ben', 'role': 'member'})

        self.assertEqual(res.status_code, 201)
        self.assertEqual(await self.current_session(), session_id)

    async def test_a_returning_leader_keeps_the_session(self) -> None:
        store.group = Group()
        res = await self.client.post('/players', json={'name': 'Ana', 'role': 'leader'})
        leader_id = res.json()['id']
        session_id = await self.current_session()
        await self.client.delete(f'/players/{leader_id}')

        res = await self.client.post(
            '/players', json={'name': 'Ana', 'role': 'leader', 'reuse_id': leader_id}
        )

        self.assertEqual(res.status_code, 201)
        self.assertEqual(await self.current_session(), session_id)

    async def test_current_session_reports_draft_and_saved_state(self) -> None:
        session_id = await self.new_game('Ana')
        draft = (await self.client.get('/session/current')).json()
        await self.save('Lost Mine', 'Session_1')

        saved = (await self.client.get('/session/current')).json()

        self.assertEqual(
            draft,
            {'session_id': session_id, 'saved': False, 'campaign_name': None, 'session_name': None},
        )
        self.assertEqual(
            saved,
            {
                'session_id': 'Lost Mine/Session_1',
                'saved': True,
                'campaign_name': 'Lost Mine',
                'session_name': 'Session_1',
            },
        )

    async def test_new_session_endpoint_starts_an_empty_session(self) -> None:
        first = await self.new_game('Ana')
        await self.record(first, FIRST_HALF)

        res = await self.client.post('/session/new')

        second = res.json()['session_id']
        self._known_sessions.add(second)
        self.assertNotEqual(second, first)
        self.assertEqual(await self.current_session(), second)
        self.assertEqual(await self.event_texts(second), [])
        self.assertEqual(await self.event_texts(first), _texts(FIRST_HALF))


class TwoSessionsNeverMixTests(SessionIsolationTestCase):
    async def _play_two_games(self) -> tuple[str, str]:
        """Game 1 records the whole script; a completely new game 2 records only half."""
        first = await self.new_game('Ana')
        await self.record(first, WHOLE_SCRIPT)
        second = await self.new_game('Ben')
        await self.record(second, FIRST_HALF)
        return first, second

    async def test_new_game_shows_only_what_was_recorded_in_it(self) -> None:
        _, second = await self._play_two_games()

        self.assertEqual(await self.event_texts(second), _texts(FIRST_HALF))
        self.assertEqual(await self.map_places(second), ['Neverwinter', 'Phandalin'])
        self.assertEqual(await self.transcript_texts(second), _texts(FIRST_HALF))
        for unseen in _texts(SECOND_HALF):
            self.assertNotIn(unseen, await self.event_texts(second))
            self.assertNotIn(unseen, await self.transcript_texts(second))
        self.assertNotIn('Cragmaw Castle', await self.map_places(second))
        self.assertNotIn('Wave Echo Cave', await self.map_places(second))

    async def test_earlier_game_is_untouched_by_the_new_one(self) -> None:
        first, _ = await self._play_two_games()

        self.assertEqual(await self.event_texts(first), _texts(WHOLE_SCRIPT))
        self.assertEqual(
            await self.map_places(first),
            ['Neverwinter', 'Phandalin', 'Cragmaw Castle', 'Wave Echo Cave'],
        )
        self.assertEqual(await self.transcript_texts(first), _texts(WHOLE_SCRIPT))

    async def test_sessions_with_different_stories_share_nothing(self) -> None:
        first = await self.new_game('Ana')
        await self.record(first, FIRST_HALF)
        second = await self.new_game('Cy')
        await self.record(second, OTHER_STORY)
        await self.record(first, SECOND_HALF)  # the first table keeps playing

        self.assertEqual(await self.event_texts(first), _texts(WHOLE_SCRIPT))
        self.assertEqual(await self.event_texts(second), _texts(OTHER_STORY))
        self.assertEqual(await self.map_places(second), ['Thundertree'])
        self.assertNotIn('Thundertree', await self.map_places(first))
        self.assertEqual(await self.transcript_texts(second), _texts(OTHER_STORY))
        event_ids = set()
        for session_id in (first, second):
            res = await self.client.get('/timeline/events', params={'session_id': session_id})
            for event in res.json()['events']:
                self.assertEqual(event['session_id'], session_id)
                self.assertNotIn(event['id'], event_ids)
                event_ids.add(event['id'])

    async def test_generate_events_reads_only_this_sessions_transcript(self) -> None:
        first, second = await self._play_two_games()
        await timeline_store.clear_session(first)
        await timeline_store.clear_session(second)

        generated_second = await self.generate_events(second)
        generated_first = await self.generate_events(first)

        self.assertEqual(generated_second.status_code, 200)
        self.assertEqual(generated_second.json()['events_generated'], 2)
        self.assertEqual(await self.event_texts(second), _texts(FIRST_HALF))
        self.assertEqual(generated_first.json()['events_generated'], 4)
        self.assertEqual(await self.event_texts(first), _texts(WHOLE_SCRIPT))

    async def test_map_generation_uses_only_this_sessions_events(self) -> None:
        _, second = await self._play_two_games()

        res = await self.client.post(
            '/map/generate',
            json={'session_id': second},
            headers={'X-Player-Id': self.leader_id},
        )

        body = res.json()
        self.assertEqual(body['session_id'], second)
        self.assertEqual(
            [location['canonical_name'] for location in body['locations']],
            ['Neverwinter', 'Phandalin'],
        )
        self.assertEqual(body['edges_generated'], 1)
        second_event_ids = {
            event['id']
            for event in (
                await self.client.get('/timeline/events', params={'session_id': second})
            ).json()['events']
        }
        for location in body['locations']:
            self.assertTrue(set(location['event_ids']) <= second_event_ids)

    async def test_regenerating_events_and_map_never_runs_whisper_again(self) -> None:
        first = await self.new_game('Ana')
        await self.record(first, WHOLE_SCRIPT)
        await timeline_store.clear_session(first)
        await map_store.clear_session(first)

        with (
            mock.patch.object(
                self.whisper, 'load_audio', side_effect=AssertionError('audio was loaded again')
            ) as load_audio,
            mock.patch.object(
                self.whisper, 'transcribe', side_effect=AssertionError('Whisper ran again')
            ) as transcribe,
        ):
            events = await self.generate_events(first)
            graph = await self.client.post(
                '/map/generate', json={'session_id': first}, headers={'X-Player-Id': self.leader_id}
            )

        self.assertEqual(events.status_code, 200, events.text)
        self.assertEqual(events.json()['events_generated'], 4)
        self.assertEqual(graph.status_code, 200, graph.text)
        self.assertEqual(
            await self.map_places(first),
            ['Neverwinter', 'Phandalin', 'Cragmaw Castle', 'Wave Echo Cave'],
        )
        load_audio.assert_not_called()
        transcribe.assert_not_called()

    async def test_generate_events_in_a_game_without_recording_finds_nothing(self) -> None:
        first = await self.new_game('Ana')
        await self.record(first, WHOLE_SCRIPT)
        second = await self.new_game('Ben')

        res = await self.generate_events(second)

        self.assertEqual(res.status_code, 404)
        self.assertEqual(await self.event_texts(second), [])
        self.assertEqual(await self.map_places(second), [])

    async def test_every_stored_chunk_is_tagged_with_its_own_session(self) -> None:
        first, second = await self._play_two_games()

        tags = [chunk['metadata']['session_id'] for chunk in self.stored_chunks()]

        self.assertEqual(len(tags), 6)
        self.assertNotIn('none', tags)
        self.assertEqual(tags.count(session_registry.uid_for(first)), 4)
        self.assertEqual(tags.count(session_registry.uid_for(second)), 2)
        self.assertNotEqual(session_registry.uid_for(first), session_registry.uid_for(second))

    async def test_question_search_only_sees_the_asking_session(self) -> None:
        first, second = await self._play_two_games()

        found_second = embedding_model.embedding_search('Where are we?', session_id=second)
        found_first = embedding_model.embedding_search('Where are we?', session_id=first)
        listed_second = embedding_model.get_all_transcription_documents(session_id=second)

        self.assertEqual([doc.page_content for doc in found_second], _texts(FIRST_HALF))
        self.assertEqual([doc.page_content for doc in found_first], _texts(WHOLE_SCRIPT))
        self.assertEqual([doc.page_content for doc in listed_second], _texts(FIRST_HALF))


class LegacyKeyAndOldDataTests(SessionIsolationTestCase):
    async def test_unsaved_key_reaches_only_the_active_game(self) -> None:
        """The key the old frontend sent can no longer address a shared bucket."""
        first = await self.new_game('Ana')
        await self.record('unsaved', WHOLE_SCRIPT)
        self.assertEqual(await self.event_texts(first), _texts(WHOLE_SCRIPT))

        second = await self.new_game('Ben')
        await self.record('unsaved', FIRST_HALF)

        self.assertEqual(await self.event_texts('unsaved'), _texts(FIRST_HALF))
        self.assertEqual(await self.event_texts(second), _texts(FIRST_HALF))
        self.assertEqual(await self.map_places('unsaved'), ['Neverwinter', 'Phandalin'])
        self.assertEqual(await self.event_texts(first), _texts(WHOLE_SCRIPT))

    async def test_upload_without_session_id_goes_to_the_active_game(self) -> None:
        first = await self.new_game('Ana')
        await self.record(None, WHOLE_SCRIPT)
        second = await self.new_game('Ben')

        await self.record(None, FIRST_HALF)

        self.assertEqual(await self.event_texts(first), _texts(WHOLE_SCRIPT))
        self.assertEqual(await self.event_texts(second), _texts(FIRST_HALF))

    async def test_untagged_chunks_from_older_versions_are_ignored_but_kept(self) -> None:
        """Recordings stored before the fix carry session 'none' in the database."""
        embedding_model.embedd_transcriptions(
            embedding_text=_texts(WHOLE_SCRIPT), speakers=['Ana'] * 4, timestamps=[0.0] * 4
        )
        self.assertEqual(
            {chunk['metadata']['session_id'] for chunk in self.stored_chunks()}, {'none'}
        )
        session_id = await self.new_game('Ben')
        await self.record(session_id, OTHER_STORY)
        await timeline_store.clear_session(session_id)

        res = await self.generate_events(session_id)

        self.assertEqual(res.json()['events_generated'], 1)
        self.assertEqual(await self.event_texts(session_id), _texts(OTHER_STORY))
        self.assertEqual(len(self.stored_chunks()), 5)
        untagged = [c for c in self.stored_chunks() if c['metadata']['session_id'] == 'none']
        self.assertEqual([chunk['document'] for chunk in untagged], _texts(WHOLE_SCRIPT))


class SaveAndLoadKeepSessionsApartTests(SessionIsolationTestCase):
    async def _save_two_games(self) -> None:
        first = await self.new_game('Ana')
        await self.record(first, WHOLE_SCRIPT)
        await self.save('Lost Mine', 'Session_1')
        second = await self.new_game('Cy')
        await self.record(second, OTHER_STORY)
        await self.save('Dragon Hunt', 'Session_1')

    async def test_saved_sessions_keep_their_own_data_under_their_own_keys(self) -> None:
        await self._save_two_games()

        self.assertEqual(await self.event_texts('Lost Mine/Session_1'), _texts(WHOLE_SCRIPT))
        self.assertEqual(await self.event_texts('Dragon Hunt/Session_1'), _texts(OTHER_STORY))
        self.assertEqual(await self.map_places('Dragon Hunt/Session_1'), ['Thundertree'])
        self.assertEqual(await self.current_session(), 'Dragon Hunt/Session_1')

    async def test_saved_files_contain_only_their_own_session(self) -> None:
        await self._save_two_games()

        def saved(campaign: str, name: str) -> dict:
            path = os.path.join(self.saved_dir, campaign, 'Session_1', name)
            with open(path, encoding='utf-8') as f:
                return json.load(f)

        self.assertEqual(
            _texts(saved('Dragon Hunt', 'transcript.json')['segments']), _texts(OTHER_STORY)
        )
        self.assertEqual(
            _texts(saved('Lost Mine', 'transcript.json')['segments']), _texts(WHOLE_SCRIPT)
        )
        self.assertEqual(
            [event['description'] for event in saved('Dragon Hunt', 'timeline.json')['events']],
            _texts(OTHER_STORY),
        )
        self.assertEqual(
            [loc['canonical_name'] for loc in saved('Dragon Hunt', 'map.json')['locations']],
            ['Thundertree'],
        )
        self.assertNotEqual(
            saved('Lost Mine', 'transcript.json')['session_uid'],
            saved('Dragon Hunt', 'transcript.json')['session_uid'],
        )

    async def test_loading_after_restart_restores_only_that_session(self) -> None:
        await self._save_two_games()
        await self.restart_backend()

        await self.load('Dragon Hunt', 'Session_1')

        self.assertEqual(await self.current_session(), 'Dragon Hunt/Session_1')
        self.assertEqual(await self.event_texts('Dragon Hunt/Session_1'), _texts(OTHER_STORY))
        self.assertEqual(await self.map_places('Dragon Hunt/Session_1'), ['Thundertree'])
        self.assertEqual(await self.transcript_texts('Dragon Hunt/Session_1'), _texts(OTHER_STORY))
        self.assertEqual(await self.event_texts('Lost Mine/Session_1'), [])

    async def test_generate_after_loading_ignores_other_sessions_in_the_database_copy(self) -> None:
        """The second save's database copy also holds the first game's chunks."""
        await self._save_two_games()
        await self.restart_backend()
        await self.load('Dragon Hunt', 'Session_1')
        self.assertEqual(len(self.stored_chunks()), 5)

        res = await self.generate_events('Dragon Hunt/Session_1')

        self.assertEqual(res.json()['events_generated'], 1)
        self.assertEqual(await self.event_texts('Dragon Hunt/Session_1'), _texts(OTHER_STORY))

    async def test_switching_between_loaded_sessions_shows_only_the_selected_one(self) -> None:
        await self._save_two_games()
        await self.restart_backend()

        await self.load('Lost Mine', 'Session_1')
        first_view = await self.event_texts(await self.current_session())
        await self.load('Dragon Hunt', 'Session_1')
        second_view = await self.event_texts(await self.current_session())

        self.assertEqual(first_view, _texts(WHOLE_SCRIPT))
        self.assertEqual(second_view, _texts(OTHER_STORY))
        self.assertEqual(await self.map_places(await self.current_session()), ['Thundertree'])

    async def test_new_game_after_loading_a_session_starts_empty(self) -> None:
        await self._save_two_games()
        await self.restart_backend()
        await self.load('Lost Mine', 'Session_1')

        session_id = await self.new_game('Ben')
        await self.record(session_id, FIRST_HALF)
        await timeline_store.clear_session(session_id)
        res = await self.generate_events(session_id)

        self.assertEqual(res.json()['events_generated'], 2)
        self.assertEqual(await self.event_texts(session_id), _texts(FIRST_HALF))
        self.assertEqual(await self.map_places(session_id), ['Neverwinter', 'Phandalin'])
        self.assertEqual(await self.event_texts('Lost Mine/Session_1'), _texts(WHOLE_SCRIPT))

    async def test_recording_continues_in_a_loaded_session_only(self) -> None:
        first = await self.new_game('Ana')
        await self.record(first, FIRST_HALF)
        await self.save('Lost Mine', 'Session_1')
        await self.restart_backend()
        await self.load('Lost Mine', 'Session_1')

        await self.record(await self.current_session(), SECOND_HALF)
        await timeline_store.clear_session('Lost Mine/Session_1')
        res = await self.generate_events('Lost Mine/Session_1')

        self.assertEqual(res.json()['events_generated'], 4)
        self.assertEqual(await self.event_texts('Lost Mine/Session_1'), _texts(WHOLE_SCRIPT))

    async def test_saving_keeps_chunks_attached_without_rewriting_them(self) -> None:
        session_id = await self.new_game('Ana')
        await self.record(session_id, FIRST_HALF)
        tags_before = [chunk['metadata']['session_id'] for chunk in self.stored_chunks()]

        await self.save('Lost Mine', 'Session_1')
        await timeline_store.clear_session('Lost Mine/Session_1')
        res = await self.generate_events('Lost Mine/Session_1')

        tags_after = [chunk['metadata']['session_id'] for chunk in self.stored_chunks()]
        self.assertEqual(tags_after, tags_before)
        self.assertEqual(res.json()['events_generated'], 2)

    async def test_session_saved_by_an_older_version_still_loads_its_transcript(self) -> None:
        """Older saves have no session uid and untagged chunks in their database copy."""
        folder = os.path.join(self.saved_dir, 'Old Campaign', 'Session_1')
        first = await self.new_game('Ana')
        await self.record(first, FIRST_HALF)
        await self.save('Old Campaign', 'Session_1')
        for name in ('transcript.json', 'timeline.json', 'map.json'):
            path = os.path.join(folder, name)
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            del data['session_uid']
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        saved_db = os.path.join(folder, 'chroma_db')
        untagged = read_saved_chunks(saved_db)
        for chunk in untagged:
            chunk['metadata']['session_id'] = 'none'
        write_saved_chunks(saved_db, untagged)
        await self.restart_backend()

        await self.load('Old Campaign', 'Session_1')
        await timeline_store.clear_session('Old Campaign/Session_1')
        res = await self.generate_events('Old Campaign/Session_1')

        self.assertEqual(res.json()['events_generated'], 2)
        self.assertEqual(await self.event_texts('Old Campaign/Session_1'), _texts(FIRST_HALF))
        # The saved original is left exactly as it was.
        self.assertEqual(
            {chunk['metadata']['session_id'] for chunk in read_saved_chunks(saved_db)}, {'none'}
        )
        # And a new game started afterwards does not inherit the adopted chunks.
        session_id = await self.new_game('Ben')
        self.assertEqual((await self.generate_events(session_id)).status_code, 404)


if __name__ == '__main__':
    unittest.main()
