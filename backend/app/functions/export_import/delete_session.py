"""Functions for deleting saved session folders."""

import os
import shutil

from fastapi import HTTPException, status

from app.core.config import settings

BASE_DIR = os.path.join(settings.backend_root_path, 'data', 'SavedSessions')


def delete_folder(folder: str) -> None:
    """Delete a folder from SavedSessions directory.

    Args:
        folder: Name of the folder to delete.

    Raises:
        HTTPException 404: If the folder does not exist.
        HTTPException 400: If the path is not a directory.
    """
    folder_path = os.path.join(BASE_DIR, folder)

    if not os.path.exists(folder_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Folder '{folder}' does not exist."
        )

    if not os.path.isdir(folder_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{folder}' is not a directory."
        )

    try:
        shutil.rmtree(folder_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete folder '{folder}': {e!s}",
        )
