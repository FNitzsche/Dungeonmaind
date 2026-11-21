"""Pydantic models for the active-session endpoints."""

from pydantic import BaseModel, Field


class SessionInfo(BaseModel):
    """Identity of the session the backend is currently running.

    Attributes:
        session_id: Key to send with every timeline, map, transcription and
            question request.
        saved: Whether the session has been saved under a campaign.
        campaign_name: Campaign the session is saved in, if it is saved.
        session_name: Name the session is saved under, if it is saved.
    """

    session_id: str = Field(..., description='Key of the active session')
    saved: bool = Field(..., description='Whether the session has been saved')
    campaign_name: str | None = Field(None, description='Campaign name of a saved session')
    session_name: str | None = Field(None, description='Session name of a saved session')
