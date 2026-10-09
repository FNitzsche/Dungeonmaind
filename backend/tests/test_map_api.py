import asyncio
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI
import httpx
from app.api.routers import map as routes
from app.base_models.map_models import MapData
from app.functions.geographic_mapping.map_store import MapStore


class MapAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = MapStore(Path(temporary.name) / "map.json")
        app = FastAPI()
        app.include_router(routes.router, prefix="/map")
        app.dependency_overrides[routes.get_map_store] = lambda: self.store
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def test_get_empty_does_not_write_or_generate(self):
        with patch.object(routes, "generate_map_from_embeddings") as generate:
            response = await self.client.get("/map")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), MapData().model_dump())
        self.assertFalse(self.store.file_path.exists())
        generate.assert_not_called()

    async def test_generate_persists_and_get_does_not_regenerate(self):
        graph = MapData(source_segment_count=3)
        with patch.object(routes, "generate_map_from_embeddings", return_value=graph) as generate:
            response = await self.client.post("/map/generate")
            read = await self.client.get("/map")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(read.json(), response.json())
        self.assertEqual(MapStore(self.store.file_path).get_map(), graph)
        generate.assert_called_once_with()

    async def test_failure_preserves_previous_map(self):
        graph = self.store.replace_map(MapData(source_segment_count=5))
        with patch.object(routes, "generate_map_from_embeddings", side_effect=RuntimeError("offline")):
            response = await self.client.post("/map/generate")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.store.get_map(), graph)

    async def test_corrupt_storage_returns_error_without_overwriting(self):
        self.store.file_path.write_text("invalid json")
        response = await self.client.get("/map")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.store.file_path.read_text(), "invalid json")

    async def test_get_responsive_during_generation(self):
        started, release = Event(), Event()
        def slow_generate():
            started.set()
            if not release.wait(5):
                raise RuntimeError("timeout")
            return MapData(source_segment_count=1)
        with patch.object(routes, "generate_map_from_embeddings", side_effect=slow_generate):
            task = asyncio.create_task(self.client.post("/map/generate"))
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 2))
                read = await asyncio.wait_for(self.client.get("/map"), 2)
                self.assertEqual(read.status_code, 200)
                self.assertFalse(task.done())
            finally:
                release.set()
                response = await task
        self.assertEqual(response.status_code, 200)


class MapStoreTests(unittest.TestCase):
    def test_atomic_write_failure_preserves_map_and_cleans_temporary_file(self):
        with TemporaryDirectory() as directory:
            store = MapStore(Path(directory) / "map.json")
            old = store.replace_map(MapData(source_segment_count=2))
            with patch("app.functions.geographic_mapping.map_store.os.replace", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    store.replace_map(MapData(source_segment_count=3))
            self.assertEqual(store.get_map(), old)
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])
