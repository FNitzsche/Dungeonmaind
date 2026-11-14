"""REST API router for the identity of the active game session."""

from fastapi import APIRouter

from app.base_models.session_base_models import SessionInfo
from app.core.bus import bus
from app.domain.session_state import session_registry

router = APIRouter()


def session_info(session_id: str | None = None) -> SessionInfo:
    """Describe a session key (the active session by default)."""
    key = session_id or session_registry.active_session_id
    saved = not session_registry.is_draft(key) and '/' in key
    campaign_name, session_name = key.split('/', 1) if saved else (None, None)
    return SessionInfo(
        session_id=key, saved=saved, campaign_name=campaign_name, session_name=session_name
    )


async def announce_session_change() -> None:
    """Tell every connected client that the active session changed."""
    await bus.publish({'type': 'session_changed', 'session_id': session_registry.active_session_id})


@router.get('/current', response_model=SessionInfo)
async def get_current_session() -> SessionInfo:
    """Return the session the backend is currently running.

    Clients use the returned ``session_id`` for every timeline, map,
    transcription and question request, so all devices at the table address
    the same session.

    Returns:
        SessionInfo: Key and save state of the active session.
    """
    return session_info()


@router.post('/new', response_model=SessionInfo)
async def start_new_session() -> SessionInfo:
    """Start a new, empty session and make it the active one.

    Nothing is deleted: the previous session keeps its data under its own
    key. The new session starts with an empty transcript, timeline and map.

    Returns:
        SessionInfo: Key of the new session.
    """
    session_registry.start_new()
    await announce_session_change()
    return session_info()
