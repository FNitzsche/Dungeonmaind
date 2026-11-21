"""Pydantic models for rulebook markdown folder/file structures."""

from pydantic import BaseModel


class FolderContent(BaseModel):
    """Content listing for a rulebook folder.

    Attributes:
        folders: List of subfolder names.
        files: List of markdown file names.
    """

    folders: list[str]
    files: list[str]


FolderStructure = dict[str, FolderContent]


class FileContentResponse(BaseModel):
    """Response model containing the raw content of a markdown file."""

    content: str
