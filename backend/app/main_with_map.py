"""Optional entry point that registers the map without editing app/main.py.

Run from backend/: uvicorn app.main_with_map:app --host 0.0.0.0 --port 8000
The existing Docker/start commands continue using the unchanged app.main.
"""
from app.main import create_app
from pathlib import Path
from app.core.config import settings
from app.api.routers.map import router, get_map_store
from app.functions.geographic_mapping.session_integration import install_map_session_integration

app = create_app()
app.include_router(router, prefix="/map", tags=["map"])
install_map_session_integration(
    app, get_map_store, Path(settings.backend_root_path) / "data" / "SavedSessions",
)
