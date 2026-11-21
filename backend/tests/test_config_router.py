"""HTTP-level tests for the configuration endpoints.

Covers the failure that made every save return 500: the backend is configured
through ``.env`` with an Ollama model such as ``gemma3:1b``, the config page
sends that value straight back, and the old validation rejected it — then the
catch-all turned the 400 into a 500 with no traceback.
"""

import logging
import unittest
from unittest import mock

from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.api.routers import config_router
from app.core.chat_store import chat_store
from app.core.config import settings
from app.domain.models import Group, Role
from app.domain.store import store

KNOWN_LLM = 'hf.co/bartowski/google_gemma-3-1b-it-qat-GGUF:Q5_K_M'
OTHER_LLM = 'hf.co/bartowski/microsoft_Phi-4-mini-instruct-GGUF:Q5_K_M'
OLLAMA_LLM = 'gemma3:1b'  # what this project's .env actually sets


def _app() -> FastAPI:
    application = FastAPI()
    application.include_router(config_router.router, prefix='/config')
    return application


class ConfigRouterTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._original_group = store.group
        store.group = Group()
        self.player = store.group.add_player('Ana', Role.leader)

        # Keep the real settings object untouched by the tests.
        for field, value in (
            ('llm_model', KNOWN_LLM),
            ('transcription_model', 'base'),
            ('embedding_model', 'all-MiniLM-L6-v2'),
            ('embedding_top_k', 6),
        ):
            patch = mock.patch.object(settings, field, value)
            patch.start()
            self.addCleanup(patch.stop)

        # Nothing here may touch WhisperX or ChromaDB.
        self.reload_model = mock.Mock()
        self.delete_transcriptions = mock.Mock()
        self.reembed = mock.Mock()
        for name, double in (
            ('reload_transcription_model', self.reload_model),
            ('delete_transcription_embeddings', self.delete_transcriptions),
            ('reembed_chroma_entries', self.reembed),
        ):
            patch = mock.patch.object(config_router, name, double)
            patch.start()
            self.addCleanup(patch.stop)

        self.client = AsyncClient(transport=ASGITransport(app=_app()), base_url='http://test')
        self.addAsyncCleanup(self.client.aclose)

    async def asyncTearDown(self) -> None:
        store.group = self._original_group

    def payload(self, **overrides) -> dict:
        """The body the configuration page sends, with overrides applied."""
        body = {
            'player_id': str(self.player.id),
            'selected_LLM': settings.llm_model,
            'transcription_model': settings.transcription_model,
            'embedding_model': settings.embedding_model,
            # The page sends this as a string; the model coerces it.
            'embedding_top_k': str(settings.embedding_top_k),
            'clear_chat': False,
            'delete_transcriptions': False,
        }
        body.update(overrides)
        return body

    async def change(self, **overrides):
        return await self.client.post('/config/changeConfig', json=self.payload(**overrides))

    async def current(self) -> dict:
        res = await self.client.get('/config/getConfig')
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()


class GetConfigTests(ConfigRouterTestCase):
    async def test_returns_the_current_settings(self) -> None:
        self.assertEqual(
            await self.current(),
            {
                'selected_LLM': KNOWN_LLM,
                'transcription_model': 'base',
                'embedding_model': 'all-MiniLM-L6-v2',
                'embedding_top_k': 6,
            },
        )

    async def test_reports_a_model_that_is_not_a_built_in_option(self) -> None:
        with mock.patch.object(settings, 'llm_model', OLLAMA_LLM):
            self.assertEqual((await self.current())['selected_LLM'], OLLAMA_LLM)


class SuccessfulChangeTests(ConfigRouterTestCase):
    async def test_valid_change_is_applied_and_persisted(self) -> None:
        res = await self.change(selected_LLM=OTHER_LLM, embedding_top_k='12')

        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json(), {'status': 'success'})
        self.assertEqual(settings.llm_model, OTHER_LLM)
        self.assertEqual(settings.embedding_top_k, 12)
        # The change survives into the next read, which is what the page reloads.
        self.assertEqual((await self.current())['selected_LLM'], OTHER_LLM)
        self.assertEqual((await self.current())['embedding_top_k'], 12)

    async def test_sending_the_configuration_back_unchanged_succeeds(self) -> None:
        res = await self.change()

        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(await self.current(), {**(await self.current())})

    async def test_model_configured_in_env_round_trips(self) -> None:
        """The reported bug: read the config, send it back, get 500."""
        with mock.patch.object(settings, 'llm_model', OLLAMA_LLM):
            configured = await self.current()

            res = await self.client.post(
                '/config/changeConfig', json=self.payload(selected_LLM=configured['selected_LLM'])
            )

            self.assertEqual(res.status_code, 200, res.text)
            self.assertEqual(settings.llm_model, OLLAMA_LLM)

    async def test_switching_away_from_an_env_model_to_a_known_one_works(self) -> None:
        with mock.patch.object(settings, 'llm_model', OLLAMA_LLM):
            res = await self.change(selected_LLM=KNOWN_LLM)

            self.assertEqual(res.status_code, 200, res.text)
            self.assertEqual(settings.llm_model, KNOWN_LLM)

    async def test_changing_the_transcription_model_reloads_it(self) -> None:
        res = await self.change(transcription_model='medium')

        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(settings.transcription_model, 'medium')
        self.reload_model.assert_called_once_with()

    async def test_changing_the_embedding_model_reembeds_before_storing(self) -> None:
        res = await self.change(embedding_model='all-MiniLM-L12-v2')

        self.assertEqual(res.status_code, 200, res.text)
        self.reembed.assert_called_once_with('all-MiniLM-L12-v2')
        self.assertEqual(settings.embedding_model, 'all-MiniLM-L12-v2')

    async def test_unchanged_fields_do_not_trigger_expensive_work(self) -> None:
        res = await self.change()

        self.assertEqual(res.status_code, 200, res.text)
        self.reload_model.assert_not_called()
        self.reembed.assert_not_called()
        self.delete_transcriptions.assert_not_called()

    async def test_clear_chat_clears_the_history(self) -> None:
        await chat_store.append(self.player.id, 'user', 'Where are we?', [0.1])

        res = await self.change(clear_chat=True)

        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(await chat_store.history(self.player.id), [])

    async def test_delete_transcriptions_is_applied(self) -> None:
        res = await self.change(delete_transcriptions=True)

        self.assertEqual(res.status_code, 200, res.text)
        self.delete_transcriptions.assert_called_once_with()


class InvalidValueTests(ConfigRouterTestCase):
    async def test_each_unknown_value_is_rejected_with_400(self) -> None:
        cases = {
            'selected_LLM': 'definitely-not-a-model',
            'transcription_model': 'turbo',
            'embedding_model': 'some-other-encoder',
            'embedding_top_k': '7',
        }
        for field, bad in cases.items():
            with self.subTest(field=field):
                res = await self.change(**{field: bad})

                self.assertEqual(res.status_code, 400, res.text)
                detail = res.json()['detail']
                self.assertIn(str(bad), detail)
                self.assertIn('Allowed values', detail)

    async def test_nothing_is_applied_when_a_value_is_invalid(self) -> None:
        res = await self.change(selected_LLM=OTHER_LLM, transcription_model='turbo')

        self.assertEqual(res.status_code, 400, res.text)
        # The valid LLM in the same request must not be applied either.
        self.assertEqual(settings.llm_model, KNOWN_LLM)
        self.assertEqual(settings.transcription_model, 'base')
        self.reload_model.assert_not_called()

    async def test_clearing_chat_for_an_unknown_player_returns_404(self) -> None:
        res = await self.change(clear_chat=True, player_id='11111111-1111-4111-8111-111111111111')

        self.assertEqual(res.status_code, 404, res.text)
        self.assertEqual(res.json()['detail'], 'Player not found')


class MalformedRequestTests(ConfigRouterTestCase):
    async def test_missing_required_field_returns_422(self) -> None:
        for field in ('player_id', 'selected_LLM', 'transcription_model', 'embedding_model'):
            with self.subTest(field=field):
                body = self.payload()
                del body[field]

                res = await self.client.post('/config/changeConfig', json=body)

                self.assertEqual(res.status_code, 422, res.text)

    async def test_wrong_type_returns_422(self) -> None:
        for field, bad in (('player_id', 'not-a-uuid'), ('embedding_top_k', 'six')):
            with self.subTest(field=field):
                res = await self.change(**{field: bad})

                self.assertEqual(res.status_code, 422, res.text)

    async def test_top_k_sent_as_a_string_is_accepted(self) -> None:
        res = await self.change(embedding_top_k='9')

        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(settings.embedding_top_k, 9)


class FailureReportingTests(ConfigRouterTestCase):
    async def test_unexpected_failure_returns_500_and_logs_the_traceback(self) -> None:
        self.reembed.side_effect = RuntimeError('ChromaDB is locked')

        with self.assertLogs(config_router.logger, level=logging.ERROR) as captured:
            res = await self.change(embedding_model='all-MiniLM-L12-v2')

        self.assertEqual(res.status_code, 500)
        self.assertIn('ChromaDB is locked', res.json()['detail'])
        logged = '\n'.join(captured.output)
        self.assertIn('Applying the configuration change failed', logged)
        self.assertIn('Traceback (most recent call last)', logged)
        self.assertIn('RuntimeError: ChromaDB is locked', logged)
        # The failed change is not half-applied.
        self.assertEqual(settings.embedding_model, 'all-MiniLM-L6-v2')

    async def test_a_deliberate_http_error_is_not_turned_into_500(self) -> None:
        self.reload_model.side_effect = HTTPException(409, detail='Model busy')

        res = await self.change(transcription_model='medium')

        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()['detail'], 'Model busy')


class TranscriptionReloadGuardTests(unittest.TestCase):
    """The reload must not crash before WhisperX has ever been imported."""

    def test_reload_without_a_loaded_model_does_nothing(self) -> None:
        from app.functions.process_audio_data import transcribe_audio

        with (
            mock.patch.object(transcribe_audio, 'transcription_model', None),
            mock.patch.object(transcribe_audio, 'whisperx', None),
            mock.patch.object(transcribe_audio, 'load_transcription_model') as loader,
        ):
            transcribe_audio.reload_transcription_model()

            loader.assert_not_called()
            self.assertIsNone(transcribe_audio.transcription_model)

    def test_reload_with_a_loaded_model_replaces_it(self) -> None:
        from app.functions.process_audio_data import transcribe_audio

        with (
            mock.patch.object(transcribe_audio, 'transcription_model', object()),
            mock.patch.object(transcribe_audio, 'load_audio_dependencies'),
            mock.patch.object(
                transcribe_audio, 'load_transcription_model', return_value='new-model'
            ) as loader,
        ):
            transcribe_audio.reload_transcription_model()

            loader.assert_called_once_with()
            self.assertEqual(transcribe_audio.transcription_model, 'new-model')


if __name__ == '__main__':
    unittest.main()
