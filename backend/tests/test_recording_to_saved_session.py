"""End-to-end tests of the backend flow: audio upload -> timeline -> map -> save -> load.

The speech models and the LLM are replaced by small fakes so the whole chain
runs in milliseconds without WhisperX, Ollama or ChromaDB:

- ``FakeWhisper`` returns scripted segments for each uploaded audio chunk.
- ``fake_extract_events`` turns every segment that names a known place into
  one timeline event.

Everything between those two ends is the real code: the HTTP routers, the
transcription pipeline glue, the stores, place resolution, link building and
the session files on disk.
"""

import itertools
import json
import os
import tempfile
import unittest
from unittest import mock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routers import export_import_session as export_import_router
from app.api.routers.map import router as map_router
from app.api.routers.process_audio_data import router as audio_router
from app.api.routers.timeline import router as timeline_router
from app.core.config import settings
from app.domain.map_store import map_store
from app.domain.models import Group, Role, TimelineEvent, TimelineEventType
from app.domain.session_state import session_registry
from app.domain.store import store
from app.domain.timeline_store import timeline_store
from app.domain.transcript_store import transcript_store
from app.functions.process_audio_data import transcribe_audio as pipeline

CAMPAIGN = 'Lost Mine'
SESSION = 'Session_1'
SAVED_ID = f'{CAMPAIGN}/{SESSION}'
UNSAVED = 'unsaved'
KNOWN_PLACES = ('Neverwinter', 'Phandalin', 'Cragmaw Castle')

CHUNK_1 = [
    {'start': 0.4, 'end': 3.1, 'text': ' We gather our gear in Neverwinter. ', 'speaker': 'Ana'},
    {'start': 3.1, 'end': 4.0, 'text': '   ', 'speaker': 'Ben'},
    {'start': 4.0, 'end': 8.2, 'text': 'Pass me the snacks.', 'speaker': 'Ben'},
]
CHUNK_2 = [
    {'start': 0.2, 'end': 5.0, 'text': 'After two days we arrive in Phandalin.', 'speaker': 'DM'},
    {'start': 5.0, 'end': 9.5, 'text': 'Goblins took him to Cragmaw Castle.', 'speaker': 'DM'},
]


class FakeWhisper:
    """Stands in for the ``whisperx`` module and its transcription model."""

    def __init__(self, chunks: tuple[list[dict], ...]) -> None:
        self._chunks = iter(chunks)
        self.loaded_paths: list[str] = []

    def load_audio(self, path: str) -> str:
        self.loaded_paths.append(path)
        assert os.path.exists(path), 'the uploaded audio must be on disk while it is transcribed'
        return 'audio-array'

    def transcribe(self, audio, batch_size: int = 16) -> dict:
        return {'language': 'en', 'segments': [dict(seg) for seg in next(self._chunks)]}

    def load_align_model(self, language_code: str, device: str):
        return 'align-model', {'language': language_code}

    def align(self, segments, model, metadata, audio, device, return_char_alignments=False):
        return {'segments': segments}


def make_fake_extractor():
    """Build an event extractor that emits one event per segment naming a known place."""
    counter = itertools.count()

    def fake_extract_events(texts, speakers=None, timestamps=None, session_id='default'):
        events = []
        for index, text in enumerate(texts):
            places = [place for place in KNOWN_PLACES if place in text]
            if not places:
                continue
            events.append(
                TimelineEvent(
                    id='',
                    session_id=session_id,
                    title=f'Scene in {places[0]}',
                    description=text,
                    event_type=TimelineEventType.travel,
                    order=next(counter),
                    timestamp=float(timestamps[index]) if timestamps else 0.0,
                    speaker_name=speakers[index] if speakers else None,
                    location_entities=places,
                )
            )
        return events

    return fake_extract_events


async def _clear(*session_ids: str) -> None:
    for session_id in session_ids:
        await transcript_store.clear_session(session_id)
        await timeline_store.clear_session(session_id)
        await map_store.clear_session(session_id)


class PipelineTestCase(unittest.IsolatedAsyncioTestCase):
    """Wires the fakes into the transcription module and isolates all state."""

    chunks: tuple[list[dict], ...] = (CHUNK_1, CHUNK_2)

    async def asyncSetUp(self) -> None:
        # Every test starts in a fresh, unsaved game, like a newly joined leader.
        self.draft_id = session_registry.start_new()
        await _clear(UNSAVED, SAVED_ID)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.whisper = FakeWhisper(self.chunks)
        self.embedded: list[dict] = []

        def fake_embed(
            embedding_text, speakers, timestamps=None, persist_directory=None, session_id=None
        ):
            self.embedded.append(
                {
                    'texts': embedding_text,
                    'speakers': speakers,
                    'timestamps': timestamps,
                    'session_id': session_id,
                }
            )

        patches = [
            mock.patch.object(pipeline, 'ensure_transcription_models_loaded', lambda: None),
            mock.patch.object(pipeline, 'whisperx', self.whisper),
            mock.patch.object(pipeline, 'transcription_model', self.whisper),
            mock.patch.object(pipeline, 'alignment_models_cache', {}),
            mock.patch.object(pipeline, 'embedd_transcriptions', fake_embed),
            mock.patch.object(
                pipeline, 'extract_events_from_transcriptions', make_fake_extractor()
            ),
            mock.patch.object(settings, 'enable_diarization', False),
            mock.patch.object(settings, 'backend_root_path', self._tmp.name),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    async def asyncTearDown(self) -> None:
        await _clear(UNSAVED, SAVED_ID, self.draft_id)


class TranscriptionPipelineTests(PipelineTestCase):
    async def test_chunk_becomes_transcript_timeline_and_map(self) -> None:
        segments = await pipeline.transcribe_audio(b'audio', 'audio/webm', session_id=SAVED_ID)

        self.assertEqual(len(segments), 3)
        transcript = await transcript_store.get_segments(SAVED_ID)
        self.assertEqual(
            [segment.to_dict() for segment in transcript],
            [
                {
                    'start': 0.4,
                    'end': 3.1,
                    'text': 'We gather our gear in Neverwinter.',
                    'speaker': 'Ana',
                },
                {'start': 4.0, 'end': 8.2, 'text': 'Pass me the snacks.', 'speaker': 'Ben'},
            ],
        )
        events = await timeline_store.get_session_events(SAVED_ID)
        self.assertEqual([event.location_entities for event in events], [['Neverwinter']])
        self.assertTrue(events[0].id)
        self.assertEqual(events[0].timestamp, 0.4)
        locations = await map_store.get_locations(SAVED_ID)
        self.assertEqual([location.canonical_name for location in locations], ['Neverwinter'])
        self.assertEqual(locations[0].event_ids, [events[0].id])

    async def test_blank_segments_are_not_embedded(self) -> None:
        await pipeline.transcribe_audio(b'audio', 'audio/webm', session_id=SAVED_ID)

        self.assertEqual(len(self.embedded), 1)
        self.assertEqual(
            self.embedded[0]['texts'], ['We gather our gear in Neverwinter.', 'Pass me the snacks.']
        )
        self.assertEqual(self.embedded[0]['speakers'], ['Ana', 'Ben'])
        self.assertEqual(self.embedded[0]['timestamps'], [0.4, 4.0])

    async def test_uploaded_audio_is_removed_after_transcription(self) -> None:
        await pipeline.transcribe_audio(b'audio', 'audio/ogg; codecs=opus', session_id=SAVED_ID)

        self.assertEqual(len(self.whisper.loaded_paths), 1)
        self.assertTrue(self.whisper.loaded_paths[0].endswith('.ogg'))
        self.assertFalse(os.path.exists(self.whisper.loaded_paths[0]))

    async def test_session_id_defaults_to_unsaved(self) -> None:
        await pipeline.transcribe_audio(b'audio', 'audio/webm')

        self.assertEqual(len(await timeline_store.get_session_events(UNSAVED)), 1)
        self.assertEqual(await timeline_store.get_session_events('default'), [])

    async def test_later_chunks_extend_the_same_session(self) -> None:
        await pipeline.transcribe_audio(b'chunk-1', 'audio/webm', session_id=SAVED_ID)
        await pipeline.transcribe_audio(b'chunk-2', 'audio/webm', session_id=SAVED_ID)

        self.assertEqual(len(await transcript_store.get_segments(SAVED_ID)), 4)
        events = await timeline_store.get_session_events(SAVED_ID)
        self.assertEqual(len(events), 3)
        locations = await map_store.get_locations(SAVED_ID)
        self.assertEqual(
            [location.canonical_name for location in locations],
            ['Neverwinter', 'Phandalin', 'Cragmaw Castle'],
        )
        edges = await map_store.get_edges(SAVED_ID)
        travel = [
            (edge.from_location_id, edge.to_location_id)
            for edge in edges
            if edge.relationship.value == 'travel'
        ]
        self.assertEqual(travel, [('loc_1', 'loc_2'), ('loc_2', 'loc_3')])

    async def test_chunk_without_places_adds_transcript_but_no_events(self) -> None:
        self.whisper._chunks = iter([[CHUNK_1[2]]])

        await pipeline.transcribe_audio(b'audio', 'audio/webm', session_id=SAVED_ID)

        self.assertEqual(len(await transcript_store.get_segments(SAVED_ID)), 1)
        self.assertEqual(await timeline_store.get_session_events(SAVED_ID), [])
        self.assertFalse(await map_store.has_map(SAVED_ID))

    async def test_silent_chunk_stores_nothing(self) -> None:
        self.whisper._chunks = iter([[CHUNK_1[1]]])

        await pipeline.transcribe_audio(b'audio', 'audio/webm', session_id=SAVED_ID)

        self.assertEqual(await transcript_store.get_segments(SAVED_ID), [])
        self.assertEqual(self.embedded, [])

    async def test_map_failure_does_not_fail_transcription(self) -> None:
        async def broken_generate_map(session_id: str):
            raise RuntimeError('map exploded')

        with mock.patch.object(pipeline, 'generate_map', broken_generate_map):
            segments = await pipeline.transcribe_audio(b'audio', 'audio/webm', session_id=SAVED_ID)

        self.assertEqual(len(segments), 3)
        self.assertEqual(len(await timeline_store.get_session_events(SAVED_ID)), 1)


class RecordingToSavedSessionFlowTests(PipelineTestCase):
    """Drives the whole user journey through HTTP, as the frontend does."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.saved_dir = os.path.join(self._tmp.name, 'SavedSessions')
        os.makedirs(self.saved_dir)
        self._original_group = store.group
        store.group = Group()
        store.group.add_player('Ana', Role.leader)

        def fake_copy_chroma_db(folder_path: str) -> None:
            os.makedirs(os.path.join(folder_path, 'chroma_db'))

        patches = [
            mock.patch.object(export_import_router, 'SAVED_SESSIONS_DIR', self.saved_dir),
            mock.patch.object(export_import_router, 'DATA_DIR', self._tmp.name),
            mock.patch.object(export_import_router, 'copy_chroma_db', fake_copy_chroma_db),
            mock.patch.object(export_import_router, 'replace_chroma_db', mock.Mock()),
            mock.patch.object(
                export_import_router, 'adopt_legacy_transcriptions', mock.Mock(return_value=0)
            ),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

        application = FastAPI()
        application.include_router(audio_router, prefix='/processAudioData')
        application.include_router(timeline_router, prefix='/timeline')
        application.include_router(map_router, prefix='/map')
        application.include_router(export_import_router.router, prefix='/exportImport')
        self.client = AsyncClient(transport=ASGITransport(app=application), base_url='http://test')
        self.addAsyncCleanup(self.client.aclose)

    async def asyncTearDown(self) -> None:
        store.group = self._original_group
        await super().asyncTearDown()

    async def _upload(self, session_id: str | None = None) -> None:
        data = {'session_id': session_id} if session_id else None
        res = await self.client.post(
            '/processAudioData/transcribeAudioFile',
            files={'audio': ('chunk.webm', b'audio', 'audio/webm')},
            data=data,
        )
        self.assertEqual(res.status_code, 200, res.text)

    async def _get(self, path: str, session_id: str) -> dict:
        res = await self.client.get(path, params={'session_id': session_id})
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    async def test_record_view_save_restart_load(self) -> None:
        # 1. The table records two audio chunks before the session has a name.
        await self._upload(self.draft_id)
        await self._upload(self.draft_id)

        # 2. Timeline and map are available straight away.
        timeline = await self._get('/timeline/events', self.draft_id)
        self.assertEqual(
            [event['location_entities'] for event in timeline['events']],
            [['Neverwinter'], ['Phandalin'], ['Cragmaw Castle']],
        )
        graph = await self._get('/map', self.draft_id)
        places = {location['id']: location['canonical_name'] for location in graph['locations']}
        self.assertEqual(list(places.values()), ['Neverwinter', 'Phandalin', 'Cragmaw Castle'])
        journey = [
            (places[edge['from_location_id']], places[edge['to_location_id']])
            for edge in graph['edges']
            if edge['relationship'] == 'travel'
        ]
        self.assertEqual(journey, [('Neverwinter', 'Phandalin'), ('Phandalin', 'Cragmaw Castle')])

        # 3. Map and timeline are linked in both directions.
        phandalin_id = next(key for key, name in places.items() if name == 'Phandalin')
        place_events = await self._get(f'/map/locations/{phandalin_id}/events', self.draft_id)
        self.assertEqual(len(place_events['events']), 1)
        event_id = place_events['events'][0]['id']
        self.assertEqual(event_id, timeline['events'][1]['id'])
        event_place = await self._get(f'/map/events/{event_id}/location', self.draft_id)
        self.assertEqual(event_place['canonical_name'], 'Phandalin')

        # 4. The leader saves the session under a campaign.
        res = await self.client.post(
            '/exportImport/export',
            json={
                'campaign_name': CAMPAIGN,
                'session_name': SESSION,
                'source_session_id': self.draft_id,
            },
        )
        self.assertEqual(res.status_code, 200, res.text)
        session_dir = os.path.join(self.saved_dir, CAMPAIGN, SESSION)
        with open(os.path.join(session_dir, 'transcript.json'), encoding='utf-8') as f:
            transcript = json.load(f)
        self.assertEqual(len(transcript['segments']), 4)
        self.assertEqual(set(transcript['segments'][0]), {'start', 'end', 'text', 'speaker'})

        # 5. The same timeline and map now answer under the saved key.
        saved_timeline = await self._get('/timeline/events', SAVED_ID)
        saved_graph = await self._get('/map', SAVED_ID)
        self.assertEqual(
            [event['id'] for event in saved_timeline['events']],
            [event['id'] for event in timeline['events']],
        )
        self.assertEqual(len(saved_graph['edges']), len(graph['edges']))
        self.assertEqual((await self._get('/timeline/events', self.draft_id))['events'], [])

        # 6. The backend restarts: everything held in memory is gone.
        await _clear(self.draft_id, SAVED_ID)
        store.group = Group()
        self.assertEqual((await self._get('/timeline/events', SAVED_ID))['events'], [])

        # 7. Loading the saved session brings players, timeline and map back.
        res = await self.client.post(
            '/exportImport/import', json={'campaign_name': CAMPAIGN, 'session_name': SESSION}
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()['name'], 'Ana')
        self.assertEqual(await self._get('/timeline/events', SAVED_ID), saved_timeline)
        self.assertEqual(await self._get('/map', SAVED_ID), saved_graph)
        restored = await self._get(f'/map/locations/{phandalin_id}/events', SAVED_ID)
        self.assertEqual([event['id'] for event in restored['events']], [event_id])

    async def test_recording_continues_after_loading_a_saved_session(self) -> None:
        self.whisper._chunks = iter([CHUNK_1, CHUNK_2])
        await self._upload(self.draft_id)
        await self.client.post(
            '/exportImport/export', json={'campaign_name': CAMPAIGN, 'session_name': SESSION}
        )
        await _clear(self.draft_id, SAVED_ID)
        await self.client.post(
            '/exportImport/import', json={'campaign_name': CAMPAIGN, 'session_name': SESSION}
        )

        await self._upload(SAVED_ID)

        timeline = await self._get('/timeline/events', SAVED_ID)
        self.assertEqual(len(timeline['events']), 3)
        self.assertEqual(len({event['id'] for event in timeline['events']}), 3)
        graph = await self._get('/map', SAVED_ID)
        self.assertEqual(
            [location['canonical_name'] for location in graph['locations']],
            ['Neverwinter', 'Phandalin', 'Cragmaw Castle'],
        )
        self.assertEqual(len(await transcript_store.get_segments(SAVED_ID)), 4)

    async def test_two_sessions_do_not_share_timeline_or_map(self) -> None:
        await self._upload('Lost Mine/Session_A')
        await self._upload('Lost Mine/Session_B')
        self.addAsyncCleanup(_clear, 'Lost Mine/Session_A', 'Lost Mine/Session_B')

        first = await self._get('/map', 'Lost Mine/Session_A')
        second = await self._get('/map', 'Lost Mine/Session_B')

        self.assertEqual(
            [location['canonical_name'] for location in first['locations']], ['Neverwinter']
        )
        self.assertEqual(
            [location['canonical_name'] for location in second['locations']],
            ['Phandalin', 'Cragmaw Castle'],
        )

    async def test_deleting_the_map_falls_back_to_live_resolution(self) -> None:
        await self._upload(self.draft_id)

        res = await self.client.delete('/map', params={'session_id': self.draft_id})

        self.assertEqual(res.json(), {'deleted': True, 'session_id': self.draft_id})
        graph = await self._get('/map', self.draft_id)
        self.assertEqual(
            [location['canonical_name'] for location in graph['locations']], ['Neverwinter']
        )

    async def test_regenerating_the_map_picks_up_timeline_changes(self) -> None:
        await self._upload(self.draft_id)
        await self._upload(self.draft_id)
        timeline = await self._get('/timeline/events', self.draft_id)
        await self.client.delete(f'/timeline/events/{timeline["events"][2]["id"]}')

        res = await self.client.post('/map/generate', json={'session_id': self.draft_id})

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['locations_generated'], 2)
        self.assertEqual(body['edges_generated'], 1)
        self.assertEqual(
            [location['canonical_name'] for location in body['locations']],
            ['Neverwinter', 'Phandalin'],
        )


if __name__ == '__main__':
    unittest.main()
