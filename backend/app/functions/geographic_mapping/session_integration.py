"""Opt-in lifecycle hooks installed on a NEW app instance, not source routers.

The original endpoints and their FastAPI validation are retained. Hooks run
around the resolved endpoint call, not by intercepting request/response bodies.
"""
import asyncio
from functools import wraps
import inspect
from pathlib import Path

from fastapi import HTTPException
from fastapi.routing import APIRoute, request_response

from app.functions.geographic_mapping.map_store import MapStore


def _safe_path(root, *parts):
    root = Path(root).resolve()
    if any(not part or Path(part).is_absolute() or "\\" in part or ".." in Path(part).parts for part in parts):
        raise HTTPException(400, "Invalid campaign/session path")
    result = root.joinpath(*parts).resolve()
    if result == root or not result.is_relative_to(root):
        raise HTTPException(400, "Invalid campaign/session path")
    return result


async def _invoke(endpoint, values):
    if inspect.iscoroutinefunction(endpoint):
        return await endpoint(**values)
    return await asyncio.to_thread(endpoint, **values)


def install_map_session_integration(application, store_provider, saved_sessions_dir):
    """Serialize map generation with HTTP transcript/session mutations.

    Only one worker process is supported, matching the existing server setup.
    No global original router is modified; only routes on this app are wrapped.
    """
    if getattr(application.state, "map_session_hooks_installed", False):
        return
    lock = asyncio.Lock()
    tracked = {"/map/generate", "/processAudioData/transcribeAudioFile",
               "/exportImport/export", "/exportImport/import",
               "/exportImport/deleteCampaignsOrSessions", "/exportImport/renameSession"}
    found = {route.path for route in application.routes if isinstance(route, APIRoute) and "POST" in route.methods}
    missing = tracked - found
    if missing:
        raise RuntimeError("Map integration missing expected routes: " + ", ".join(sorted(missing)))

    def make_wrapper(original, path):
        @wraps(original)
        async def wrapped(**values):
            async with lock:
                store = store_provider()
                req = values.get("req")
                session_path = None
                restored = None
                if path in {"/exportImport/export", "/exportImport/import"}:
                    session_path = _safe_path(saved_sessions_dir, req.campaign_name, req.session_name)
                elif path == "/exportImport/deleteCampaignsOrSessions":
                    _safe_path(saved_sessions_dir, req.campaign_or_session_name)
                elif path == "/exportImport/renameSession":
                    _safe_path(saved_sessions_dir, req.campaign_name, req.old_session_name)
                    _safe_path(saved_sessions_dir, req.campaign_name, req.new_session_name)

                if path == "/exportImport/import":
                    if not session_path.is_dir():
                        raise HTTPException(404, "Saved session does not exist")
                    try:
                        restored = await asyncio.to_thread(MapStore(session_path / "geographic_map.json").get_map)
                    except Exception as error:
                        raise HTTPException(409, "Saved session map is invalid; import cancelled") from error
                    # Import can partially mutate the original backend before
                    # failing. Never leave the previous session's map visible.
                    await asyncio.to_thread(store.clear_map)
                elif path == "/processAudioData/transcribeAudioFile":
                    # Both replacement and append make the old graph stale.
                    await asyncio.to_thread(store.clear_map)

                result = await _invoke(original, values)

                if path == "/exportImport/export":
                    graph = await asyncio.to_thread(store.get_map)
                    await asyncio.to_thread(MapStore(session_path / "geographic_map.json").replace_map, graph)
                elif path == "/exportImport/import":
                    await asyncio.to_thread(store.replace_map, restored)
                elif path == "/exportImport/deleteCampaignsOrSessions":
                    # Existing backend does not track an active saved-session
                    # identity. Conservatively invalidate after any deletion.
                    await asyncio.to_thread(store.clear_map)
                return result
        return wrapped

    for route in application.routes:
        if not isinstance(route, APIRoute) or route.path not in tracked or "POST" not in route.methods:
            continue
        wrapped = make_wrapper(route.dependant.call, route.path)
        route.endpoint = wrapped
        route.dependant.call = wrapped
        # Rebuild handler so formerly synchronous endpoints are awaited.
        route.app = request_response(route.get_route_handler())
    application.state.map_session_hooks_installed = True
