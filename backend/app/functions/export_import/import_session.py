"""Functions for importing game session data from saved files."""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import settings
from app.domain.models import Group, Player, PlayerStatus, Role
from app.domain.store import store


def load_groups_from_json(file_path: str) -> Player:
    """Load group and player data from a JSON file into the store.

    Args:
        file_path: Path to the JSON file.

    Returns:
        The leader Player instance, or None if no leader found.

    Raises:
        HTTPException: If the file is missing or data is invalid.
    """

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f'No saved group data found at {file_path}'
        )

    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)

        # Deserialize players - only serialize one leader
        players = {}
        found_leader: bool = False
        for p in data.get('players', []):
            player = Player.from_dict(p)
            if (
                player.role == Role.leader and found_leader
            ):  # sobald der erste leader gefunden wurde, werden alle anderen
                player.role = (
                    Role.member
                )  # auf Member und inactive gesetzt - inactive, weil bei from_dict
                player.status = PlayerStatus.inactive  # alle leader auf active gesetzt werden
            if player.role == Role.leader:
                found_leader = True
            players[player.id] = player

        if not players:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f'No saved players found at {file_path} for saved session',
            )

        # Deserialize group
        group = Group(id=UUID(data['id']), max_size=data['max_size'], players=players)

        if len(group.players) == 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f'Something went wrong when trying to load group in file {file_path}',
            )

        if group.max_size < 1 or (len(group.players) > group.max_size):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f'Input file at {file_path} has invalid max_size value for group members',
            )

        # Update global store
        store.group = group

        print(f'Loaded group data from {file_path} with {len(players)} players')

    except Exception as e:
        print(f'Failed to load group data: {e}')
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f'Failed to load group data: {e}')

    leader_id = store.group.leader_id()
    leader = store.group.get_player(leader_id) if leader_id else None

    return leader


def load_settings_from_json(file_path: str) -> None:
    """Read settings from a JSON file and update the global settings object.

    Args:
        file_path: Path to the settings JSON file.
    """
    with open(file_path, encoding='utf-8') as f:
        data = json.load(f)

    try:
        for key, value in data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
            else:
                print(f"Warning: settings has no attribute '{key}', skipping.")
    except KeyError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f'Input file at {file_path} has invalid settings'
        )


def replace_chroma_db(saved_sessions_path: str, data_path: str) -> None:
    """Replace the current ChromaDB with the one from a saved session.

    Copies the saved ChromaDB into a timestamped tmp folder and updates
    the settings path.

    Args:
        saved_sessions_path: Path to the SavedSessions folder containing chroma_db.
        data_path: Path to the data folder where the active ChromaDB lives.
    """
    session_db_path = os.path.join(saved_sessions_path, 'chroma_db')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target_db_path = os.path.join(data_path, 'chroma_db', 'tmp' + timestamp)

    if not os.path.isdir(session_db_path):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f'No chroma_db found in saved session: {session_db_path}',
        )

    if not os.path.isdir(data_path):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f'Data path does not exist: {data_path}'
        )

    # Copy the saved chroma_db into data folder
    try:
        shutil.copytree(session_db_path, target_db_path)
        print(f'Restored chroma_db from {session_db_path} to {target_db_path}')
    except PermissionError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Could not copy database from: {session_db_path} to{target_db_path}',
        )
    settings.chroma_db_path = target_db_path
    print('changed settings.chroma_db_path to ' + settings.chroma_db_path)


# Not used at the moment
def read_chat_history(file_path: str) -> list[dict[str, str]]:
    """Read a chat history TXT file and return a list of messages.

    Args:
        file_path: Path to the chat TXT file.

    Returns:
        List of messages, each a dict with keys 'role' and 'content'.
    """
    messages = []

    with open(file_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('[') and ']' in line:
                role_end = line.index(']')
                role = line[1:role_end].strip()
                content = line[role_end + 1 :].strip()
                messages.append({'role': role, 'content': content})
            else:
                # fallback if line doesn't match expected format
                messages.append({'role': 'unknown', 'content': line})

    return messages
