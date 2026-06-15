import os
from fastapi import HTTPException, status

def read_markdown_file(file_path: str) -> str:
    """
    Reads the content of a markdown file.
    Raises HTTPException if the file is not found or cannot be read.
    """
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_path}"
        )
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading file {file_path}: {e}"
        )
