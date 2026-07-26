"""REST API router for exporting, importing, and managing saved sessions."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status

from app.api.mappers.player_mapper import player_to_out
from app.base_models.export_import_models import (
    Campaigns,
    DeleteRequest,
    ExportRequest,
    ImportRequest,
    RenameRequest,
    Sessions,
)
from app.base_models.schemas import PlayerOut
from app.core.bus import bus
from app.core.config import settings
from app.domain.store import store
from app.functions.export_import.delete_session import delete_folder
from app.functions.export_import.export_session import (
    copy_chroma_db,
    export_group_to_json,
    export_settings_to_json,
    get_folder_name,
    rename_folder,
)
from app.functions.export_import.import_session import (
    load_groups_from_json,
    load_settings_from_json,
    replace_chroma_db,
)

router = APIRouter()

# Have to add error handling and finish the import stuff

SAVED_SESSIONS_DIR = os.path.join(settings.backend_root_path, 'data', 'SavedSessions')
DATA_DIR = os.path.join(settings.backend_root_path, 'data')


@router.post('/export')
def export_session(req: ExportRequest) -> None:
    """Export the current session (group, settings, ChromaDB) to a folder.

    Args:
        req: ExportRequest with campaign and session names.
    """
    campaign_folder_path = os.path.join(SAVED_SESSIONS_DIR, req.campaign_name)
    try:
        if not os.path.exists(campaign_folder_path):
            os.makedirs(campaign_folder_path, exist_ok=True)
            print(f'Created campaign folder: {campaign_folder_path}')
    except PermissionError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f'Can not create campaign folder at {campaign_folder_path}',
        )
    folder_path = get_folder_name(req.campaign_name, req.session_name)
    export_group_to_json(folder_path)
    export_settings_to_json(folder_path)
    copy_chroma_db(folder_path)  # What is if at this point not all transcriptions are calculated?


@router.post('/import')
async def import_session(req: ImportRequest, request: Request) -> PlayerOut:
    """Import a saved session (group, settings, ChromaDB) from a folder.

    Args:
        req: ImportRequest with campaign and session names.
        request: The incoming HTTP request.

    Returns:
        PlayerOut for the leader of the imported session.
    """
    folder_path = os.path.join(SAVED_SESSIONS_DIR, req.campaign_name, req.session_name)
    if not os.path.isdir(folder_path):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Session folder '{req.session_name}' does not exist."
        )
    file_path_settings = os.path.join(folder_path, 'settings.json')
    load_settings_from_json(file_path_settings)
    file_path_groups = os.path.join(folder_path, 'group.json')
    leader = load_groups_from_json(file_path_groups)

    replace_chroma_db(folder_path, DATA_DIR)

    # Maybe the publishing has to be player by player, so that actually only those players are shown, which actually
    # newly logged in the loaded session
    await bus.publish(
        {'type': 'session_imported', 'players': [p.name for p in store.group.players.values()]}
    )

    return player_to_out(leader, request)


@router.get('/getSessions', response_model=Sessions)
def get_sessions() -> None:
    """List all saved session folders under SavedSessions directory.

    Returns:
        Sessions model with folder names.
    """
    base_path = Path(SAVED_SESSIONS_DIR)

    if not base_path.exists() or not base_path.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f'Invalid path: {SAVED_SESSIONS_DIR}')

    folder_names = [item.name for item in base_path.iterdir() if item.is_dir()]

    return Sessions(folders=folder_names)


@router.get('/getCampaigns', response_model=Campaigns)
def get_campaigns() -> Campaigns:
    """List all campaigns and their sessions.

    Returns:
        Campaigns: Campaigns model mapping campaign names to their sessions.
    """
    base_path = Path(SAVED_SESSIONS_DIR)

    if not base_path.exists() or not base_path.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f'Invalid path: {SAVED_SESSIONS_DIR}')

    campaigns: dict[str, Sessions] = {}

    for campaign_dir in base_path.iterdir():
        if campaign_dir.is_dir():
            # List session subfolders inside each campaign
            session_names = [s.name for s in campaign_dir.iterdir() if s.is_dir()]

            campaigns[campaign_dir.name] = Sessions(folders=session_names)

    return Campaigns(campaigns=campaigns)


@router.post('/deleteCampaignsOrSessions')
def delete_campaigns_or_sessions(req: DeleteRequest):
    """Delete a campaign or session folder.

    Args:
        req: DeleteRequest with the name of the campaign or session to delete.
    """
    delete_folder(req.campaign_or_session_name)


@router.post('/renameSession')
def rename_session(req: RenameRequest):
    """Rename a saved session folder.

    Args:
        req: RenameRequest with campaign, old and new session names.
    """
    rename_folder(req.campaign_name, req.old_session_name, req.new_session_name)
