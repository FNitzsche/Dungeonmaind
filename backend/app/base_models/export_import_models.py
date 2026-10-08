"""Pydantic models for session export/import request/response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.base_models.schemas import PlayerOut


class ExportRequest(BaseModel):
    """Request model for exporting a session to a file.

    Attributes:
        campaign_name: Name of the campaign under which to save.
        session_name: Name of the session to save.
    """

    campaign_name: str = Field(
        ..., description='Name of the campaign where the session has to be saved'
    )
    session_name: str = Field(..., description='Name of the session to be saved')


class ImportRequest(BaseModel):
    """Request model for importing a session from a file."""

    campaign_name: str = Field(
        ..., description='Name of the campaign where the session has to be saved'
    )
    session_name: str = Field(..., description='Name of the session to be loaded')


class RenameRequest(BaseModel):
    """Request model for renaming a saved session."""

    campaign_name: str = Field(..., description='Name of the campaign where the session is saved')
    old_session_name: str = Field(..., description='Name of the saved session')
    new_session_name: str = Field(..., description='New name of the saved session')


class DeleteRequest(BaseModel):
    """Request model for deleting a campaign or session."""

    campaign_or_session_name: str = Field(
        ..., description='Name of the campaign or session to be deleted'
    )


class Sessions(BaseModel):
    """List of session folder names within a campaign."""

    folders: list[str]


class Campaigns(BaseModel):
    """Mapping of campaign names to their sessions."""

    campaigns: dict[str, Sessions]


# If needed later
class GroupOut(BaseModel):
    """Response model for group data including players."""

    id: UUID
    max_size: int
    players: list[PlayerOut]
