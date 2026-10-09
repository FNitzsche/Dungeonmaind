import asyncio
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI, HTTPException
import httpx
from pydantic import BaseModel
from app.api.routers import map as routes
from app.base_models.map_models import MapData
from app.functions.geographic_mapping.map_store import MapStore
from app.functions.geographic_mapping.session_integration import install_map_session_integration


class SessionRequest(BaseModel):
    campaign_name: str
    session_name: str


class DeleteRequest(BaseModel):
    campaign_or_session_name: str


class RenameRequest(BaseModel):
    campaign_name: str
    old_session_name: str
    new_session_name: str


class SessionIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.saved = self.root / "SavedSessions"
        self.store = MapStore(self.root / "map.json")
        self.old = self.store.replace_map(MapData(source_segment_count=7))
        self.calls = []
        self.fail = False
        app = FastAPI()
        app.include_router(routes.router, prefix="/map")
        app.dependency_overrides[routes.get_map_store] = lambda: self.store

        def record(name):
            self.calls.append(name)
            if self.fail:
                raise HTTPException(500, "Original operation failed")

        @app.post("/exportImport/export")
        def export(req: SessionRequest):
            record("export")
            (self.saved / req.campaign_name / req.session_name).mkdir(parents=True, exist_ok=True)

        @app.post("/exportImport/import")
        async def import_session(req: SessionRequest):
            record("import")
            return {"original": "import response"}

        @app.post("/processAudioData/transcribeAudioFile")
        async def transcribe(replace_existing: bool = True):
            record("transcribe")
            self.assertEqual(self.store.get_map(), MapData())
            return {"replace_existing": replace_existing}

        @app.post("/exportImport/deleteCampaignsOrSessions")
        def delete(req: DeleteRequest):
            record("delete")

        @app.post("/exportImport/renameSession")
        def rename(req: RenameRequest):
            record("rename")
            (self.saved / req.campaign_name / req.old_session_name).rename(
                self.saved / req.campaign_name / req.new_session_name)

        self.app = app
        install_map_session_integration(app, lambda: self.store, self.saved)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)
        self.body = {"campaign_name": "campaign", "session_name": "session"}

    async def test_export_and_import_round_trip(self):
        response = await self.client.post("/exportImport/export", json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MapStore(self.saved / "campaign/session/geographic_map.json").get_map(), self.old)
        self.store.replace_map(MapData(source_segment_count=2))
        response = await self.client.post("/exportImport/import", json=self.body)
        self.assertEqual(response.json(), {"original": "import response"})
        self.assertEqual(self.store.get_map(), self.old)
        self.assertEqual(self.calls, ["export", "import"])

    async def test_import_legacy_session_clears_previous_map(self):
        (self.saved / "campaign/session").mkdir(parents=True)
        response = await self.client.post("/exportImport/import", json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.store.get_map(), MapData())

    async def test_invalid_saved_map_cancels_before_import(self):
        folder = self.saved / "campaign/session"
        folder.mkdir(parents=True)
        (folder / "geographic_map.json").write_text("broken")
        response = await self.client.post("/exportImport/import", json=self.body)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.store.get_map(), self.old)

    async def test_missing_session_preserves_map(self):
        response = await self.client.post("/exportImport/import", json=self.body)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.store.get_map(), self.old)

    async def test_failed_import_does_not_leave_previous_session_map(self):
        (self.saved / "campaign/session").mkdir(parents=True)
        self.fail = True
        response = await self.client.post("/exportImport/import", json=self.body)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.store.get_map(), MapData())

    async def test_replace_and_append_both_invalidate(self):
        for replacement in ("true", "false"):
            self.store.replace_map(self.old)
            response = await self.client.post("/processAudioData/transcribeAudioFile?replace_existing=" + replacement)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.store.get_map(), MapData())

    async def test_failed_transcription_remains_empty(self):
        self.fail = True
        response = await self.client.post("/processAudioData/transcribeAudioFile")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.store.get_map(), MapData())

    async def test_delete_invalidates_only_after_success(self):
        self.fail = True
        response = await self.client.post("/exportImport/deleteCampaignsOrSessions", json={"campaign_or_session_name": "campaign/session"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.store.get_map(), self.old)
        self.fail = False
        response = await self.client.post("/exportImport/deleteCampaignsOrSessions", json={"campaign_or_session_name": "campaign/session"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.store.get_map(), MapData())

    async def test_rename_preserves_saved_map(self):
        await self.client.post("/exportImport/export", json=self.body)
        response = await self.client.post("/exportImport/renameSession", json={"campaign_name": "campaign", "old_session_name": "session", "new_session_name": "renamed"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MapStore(self.saved / "campaign/renamed/geographic_map.json").get_map(), self.old)
        self.assertEqual(self.store.get_map(), self.old)

    async def test_reject_traversal_before_original_endpoint(self):
        response = await self.client.post("/exportImport/export", json={"campaign_name": "../outside", "session_name": "session"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.calls, [])

    async def test_original_validation_still_applies(self):
        response = await self.client.post("/exportImport/export", json={})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.calls, [])

    async def test_installation_is_idempotent(self):
        install_map_session_integration(self.app, lambda: self.store, self.saved)
        await self.client.post("/exportImport/export", json=self.body)
        self.assertEqual(self.calls, ["export"])

    async def test_generation_cannot_race_transcription(self):
        from threading import Event
        started, release = Event(), Event()
        def slow_generate():
            started.set()
            if not release.wait(5):
                raise RuntimeError("timeout")
            return MapData(source_segment_count=99)
        with patch.object(routes, "generate_map_from_embeddings", side_effect=slow_generate):
            generation = asyncio.create_task(self.client.post("/map/generate"))
            mutation = None
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 2))
                mutation = asyncio.create_task(self.client.post("/processAudioData/transcribeAudioFile"))
                await asyncio.sleep(0.02)
                self.assertNotIn("transcribe", self.calls)
                release.set()
                self.assertEqual((await generation).status_code, 200)
                self.assertEqual((await mutation).status_code, 200)
            finally:
                release.set()
                await generation
                if mutation:
                    await mutation
        self.assertEqual(self.store.get_map(), MapData())
