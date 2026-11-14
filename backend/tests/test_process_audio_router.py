"""HTTP-level tests for the audio upload/transcription endpoint."""

import unittest
from unittest import mock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routers import process_audio_data as audio_router_module
from app.domain.session_state import session_registry

SEGMENTS = [
    {'start': 0.5, 'end': 3.0, 'text': 'We leave Neverwinter.', 'speaker': 'Ana'},
    {'start': 3.0, 'end': 6.5, 'text': 'We reach Phandalin.', 'speaker': 'DM'},
]
AUDIO = {'audio': ('chunk_1.webm', b'fake-audio-bytes', 'audio/webm')}


def _app() -> FastAPI:
    application = FastAPI()
    application.include_router(audio_router_module.router, prefix='/processAudioData')
    return application


class TranscribeAudioFileRouterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.transcribe = mock.AsyncMock(return_value=SEGMENTS)
        patch = mock.patch.object(audio_router_module, 'transcribe_audio', self.transcribe)
        patch.start()
        self.addCleanup(patch.stop)
        self.client = AsyncClient(transport=ASGITransport(app=_app()), base_url='http://test')
        self.addAsyncCleanup(self.client.aclose)

    async def test_returns_transcribed_segments(self) -> None:
        res = await self.client.post('/processAudioData/transcribeAudioFile', files=AUDIO)

        self.assertEqual(res.status_code, 200)
        output = res.json()['output']
        self.assertEqual([segment['text'] for segment in output], [s['text'] for s in SEGMENTS])
        self.assertEqual(output[0]['start'], 0.5)
        self.assertEqual(output[1]['end'], 6.5)

    async def test_session_id_is_passed_to_transcription(self) -> None:
        res = await self.client.post(
            '/processAudioData/transcribeAudioFile',
            files=AUDIO,
            data={'session_id': 'Lost Mine/Session_1'},
        )

        self.assertEqual(res.status_code, 200)
        self.transcribe.assert_awaited_once_with(
            b'fake-audio-bytes', content_type='audio/webm', session_id='Lost Mine/Session_1'
        )

    async def test_session_id_defaults_to_the_active_session(self) -> None:
        active = session_registry.start_new()

        await self.client.post('/processAudioData/transcribeAudioFile', files=AUDIO)

        self.assertEqual(self.transcribe.await_args.kwargs['session_id'], active)

    async def test_legacy_unsaved_key_means_the_active_session(self) -> None:
        active = session_registry.start_new()

        await self.client.post(
            '/processAudioData/transcribeAudioFile', files=AUDIO, data={'session_id': 'unsaved'}
        )

        self.assertEqual(self.transcribe.await_args.kwargs['session_id'], active)
        self.assertNotIn(active, ('unsaved', 'default'))

    async def test_transcription_error_returns_500_with_reason(self) -> None:
        self.transcribe.side_effect = RuntimeError('ffmpeg not found')

        res = await self.client.post('/processAudioData/transcribeAudioFile', files=AUDIO)

        self.assertEqual(res.status_code, 500)
        self.assertEqual(res.json()['detail'], 'ffmpeg not found')

    async def test_missing_audio_file_is_rejected(self) -> None:
        res = await self.client.post(
            '/processAudioData/transcribeAudioFile', data={'session_id': 'unsaved'}
        )

        self.assertEqual(res.status_code, 422)
        self.transcribe.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
