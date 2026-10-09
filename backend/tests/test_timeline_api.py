import asyncio
import importlib.util
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Event, get_ident
import types
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.base_models.timeline_models import TimelineEvent, TimelineEventCreate
from app.core.config import settings


class TimelineAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        # Load the real JSON store against temporary data, never session data.
        store_spec = importlib.util.spec_from_file_location(
            '_timeline_store_api_test',
            BACKEND_DIR / 'app/functions/timeline/timeline_store.py',
        )
        store_module = importlib.util.module_from_spec(store_spec)
        with patch.object(settings, 'backend_root_path', temporary.name):
            store_spec.loader.exec_module(store_module)
        self.store = store_module.timeline_store

        # Isolate the heavyweight generator, not FastAPI or the storage layer.
        generator_module = types.ModuleType('app.functions.timeline.timeline_generator')
        self.generate = Mock()
        generator_module.generate_timeline_from_embeddings = self.generate
        spec = importlib.util.spec_from_file_location(
            '_timeline_router_api_test', BACKEND_DIR / 'app/api/routers/timeline.py',
        )
        self.routes = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {
            'app.functions.timeline.timeline_generator': generator_module,
            'app.functions.timeline.timeline_store': store_module,
        }):
            spec.loader.exec_module(self.routes)

        app = FastAPI()
        app.include_router(self.routes.router, prefix='/timeline')
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url='http://test',
        )
        self.addAsyncCleanup(self.client.aclose)
        self.old_events = self.store.replace_events([
            TimelineEventCreate(title='Old event', description='Already stored.'),
        ])
        self.generated = TimelineEvent(
            id='generated-id', created_at='2026-09-20', updated_at='2026-09-20',
            title='The party arrives', description='The party arrives in Waterdeep.',
            category='travel', start_time=10, end_time=20,
            locations=['Waterdeep'], speakers=['DM'], created_automatically=True,
            source_segments=[dict(text='The party arrives in Waterdeep.',
                                  speaker='DM', start_time=10, end_time=20)],
        )
        self.generate.return_value = ([self.generated], 12)

    async def test_repeated_get_returns_stored_events_without_generation_or_writes(self):
        before = Path(self.store.file_path).read_bytes()
        with patch.object(self.store, 'list_events', wraps=self.store.list_events) as read, \
             patch.object(self.store, 'replace_events', wraps=self.store.replace_events) as replace:
            for _ in range(3):
                response = await self.client.get('/timeline/events')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {
                    'events': [event.model_dump(mode='json') for event in self.old_events],
                    'total': 1,
                })
            self.assertEqual(read.call_count, 3)
            replace.assert_not_called()
        self.generate.assert_not_called()
        self.assertEqual(Path(self.store.file_path).read_bytes(), before)

    async def test_post_generates_once_replaces_and_returns_stored_events(self):
        with patch.object(self.store, 'replace_events', wraps=self.store.replace_events) as replace:
            response = await self.client.post('/timeline/generate')
            replace.assert_called_once()
        self.generate.assert_called_once_with()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['generated_count'], 1)
        self.assertEqual(body['source_segment_count'], 12)
        stored = self.store.list_events()
        self.assertEqual(body['events'], [event.model_dump(mode='json') for event in stored])
        self.assertEqual(
            TimelineEventCreate.model_validate(stored[0].model_dump()),
            TimelineEventCreate.model_validate(self.generated.model_dump()),
        )
        self.assertNotEqual(stored[0].id, self.old_events[0].id)
        for _ in range(3):
            read = await self.client.get('/timeline/events')
            self.assertEqual(read.json()['events'], body['events'])
        self.generate.assert_called_once_with()

    async def test_empty_generation_replaces_previous_events(self):
        self.generate.return_value = ([], 0)
        response = await self.client.post('/timeline/generate')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'events': [], 'generated_count': 0, 'source_segment_count': 0,
        })
        self.assertEqual(self.store.list_events(), [])

    async def test_generation_failure_preserves_stored_events(self):
        self.generate.side_effect = RuntimeError('Generation failed')
        response = await self.client.post('/timeline/generate')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.store.list_events(), self.old_events)

    async def test_generation_runs_off_event_loop_and_get_remains_responsive(self):
        started, release = Event(), Event()
        loop_thread = get_ident()
        worker_threads = []

        def blocking_generate():
            worker_threads.append(get_ident())
            started.set()
            if not release.wait(timeout=5):
                raise RuntimeError('Worker was not released while GET completed')
            return [self.generated], 12

        self.generate.side_effect = blocking_generate
        task = asyncio.create_task(self.client.post('/timeline/generate'))
        try:
            self.assertTrue(await asyncio.to_thread(started.wait, 2))
            response = await asyncio.wait_for(self.client.get('/timeline/events'), timeout=2)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['events'][0]['id'], self.old_events[0].id)
            self.assertFalse(task.done())
            self.assertNotEqual(worker_threads, [loop_thread])
        finally:
            release.set()
            generated = await task
        self.assertEqual(generated.status_code, 200)
        self.generate.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
