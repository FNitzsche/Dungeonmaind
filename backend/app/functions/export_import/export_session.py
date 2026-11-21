"""Functions for exporting game session data (group, settings, ChromaDB)."""

import json
import os
import shutil
from uuid import UUID

from fastapi import HTTPException, status

from app.core.chat_store import chat_store
from app.core.config import settings
from app.domain.models import Group
from app.domain.store import store

BASE_DIR = os.path.join(settings.backend_root_path, 'data', 'SavedSessions')


def export_group_to_json(folder_path: str) -> None:
    """Save the current group and its players to a JSON file.

    Args:
        folder_path: Directory path where group.json will be written.
    """

    if len(store.group.players) == 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail='Can not save session, because currently no active'
            'player is still in the session',
        )

    def serialize_group(group: Group) -> dict:
        return {
            'id': str(group.id),
            'max_size': group.max_size,
            'players': [p.to_dict() for p in group.players.values()],
        }

    data = serialize_group(store.group)

    try:
        file_path = os.path.join(folder_path, 'group.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except PermissionError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='Could not save group.json')


def export_settings_to_json(folder_path: str) -> None:
    """Export all settings fields to a JSON file.

    Args:
        folder_path: Directory path where settings.json will be written.
    """
    data = {}

    # Include all Pydantic fields
    data.update(settings.model_dump())  # model_dump() returns a dict of all fields

    try:
        file_path = os.path.join(folder_path, 'settings.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print(f'Settings exported to {file_path}')
    except PermissionError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='Could not save settings.json')


def copy_chroma_db(folder_path: str) -> None:
    """Copy the ChromaDB folder to a destination path.

    Args:
        folder_path: Destination directory for the ChromaDB copy.
    """
    source_path = settings.chroma_db_path

    if not os.path.exists(source_path):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f'Source folder for DB does not exist: {source_path}'
        )

    os.makedirs(folder_path, exist_ok=True)

    dest_folder_path = os.path.join(folder_path, 'chroma_db')

    if os.path.exists(dest_folder_path):
        shutil.rmtree(dest_folder_path)

    try:
        shutil.copytree(source_path, dest_folder_path)
        print(f"Copied 'chroma_db' to {dest_folder_path}")
    except PermissionError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f'Could not copy chroma_db folder: {source_path}'
        )


# Not sure if this is wanted for all players, if they are kept seperately for each player. Would also e necessary to save the player uuid in the file or filename
# to know in the read in, which one belongs to which
async def export_chat_history_of_player(player_id: UUID, folder_path: str) -> None:
    """Export the chat history of a given player to a TXT file.

    Args:
        player_id: The UUID of the player.
        folder_path: Directory where the chat file will be saved.

    Raises:
        ValueError: If no chat history is found for the player.
    """

    history = await chat_store.history(player_id)

    if not history:
        raise ValueError(f'No chat history found for player {player_id}')

    file_path = os.path.join(folder_path, f'chat_history_{player_id}.txt')
    with open(file_path, 'w', encoding='utf-8') as f:
        for msg in history:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            f.write(f'[{role}] {content}\n')


def get_folder_name(campaign_name: str, session_name: str) -> str:
    """Get or create the folder path for a campaign/session combination.

    Args:
        campaign_name: Name of the campaign.
        session_name: Name of the session.

    Returns:
        Absolute path to the session folder.
    """
    folder_path = os.path.join(BASE_DIR, os.path.join(campaign_name, session_name))
    os.makedirs(folder_path, exist_ok=True)

    return folder_path


def rename_folder(campaign_name: str, old_session_name: str, new_session_name: str) -> None:
    """Rename a session folder within a campaign.

    Args:
        campaign_name: Name of the campaign.
        old_session_name: Current name of the session.
        new_session_name: New name for the session.
    """
    old_folder_path = os.path.join(BASE_DIR, os.path.join(campaign_name, old_session_name))
    new_folder_path = os.path.join(BASE_DIR, os.path.join(campaign_name, new_session_name))
    os.rename(old_folder_path, new_folder_path)
