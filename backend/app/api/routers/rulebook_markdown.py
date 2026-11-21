"""REST API router for browsing and searching the rulebook markdown files."""

import os

from fastapi import APIRouter, HTTPException, status

from app.base_models.embedding_base_model import EmbeddingSearch, EmbeddResponse
from app.base_models.rulebook import FileContentResponse, FolderContent, FolderStructure
from app.core.config import settings
from app.functions.embedding.embedding_model import embedding_search
from app.functions.embedding.markdown_reader import read_markdown_file

router = APIRouter()
BASE_DIR = os.path.join(settings.backend_root_path, 'data', 'markdowns')


@router.get('/folders', response_model=FolderStructure)
async def get_folders() -> FolderStructure:
    """List the folder structure of the rulebook markdown directory.

    Returns:
        FolderStructure: FolderStructure mapping relative paths to their subfolders and .md files.
    """
    folder_dict = {}
    for root, dirs, files in os.walk(BASE_DIR):
        rel_root = os.path.relpath(root, BASE_DIR)
        if rel_root == '.':
            rel_root = ''
        folder_dict[rel_root] = FolderContent(
            folders=dirs, files=[f for f in files if f.endswith('.md')]
        )
    print(folder_dict)
    return folder_dict


@router.get('/file', response_model=FileContentResponse)
async def get_file(path: str) -> FileContentResponse:
    """Get the raw content of a specific markdown file.

    Args:
        path (str): Relative path to the markdown file.

    Returns:
        FileContentResponse: FileContentResponse with the file content.

    Raises:
        HTTPException 404: If the file is not found.
    """
    abs_path = os.path.join(BASE_DIR, path)
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail='Markdown file not found')

    return FileContentResponse(content=read_markdown_file(abs_path))


@router.post('/search', response_model=EmbeddResponse)
async def search_files(req: EmbeddingSearch) -> EmbeddResponse:
    """Search the rulebook using embedding-based similarity search.

    Args:
        req (EmbeddingSearch): EmbeddingSearch with the search query string.

    Returns:
        EmbeddResponse: EmbeddResponse with matching markdown texts.

    Raises:
        HTTPException 404: If no matching markdowns are found.
    """
    retrieved_docs = embedding_search(req.input_string, True)
    md_paths = [doc.metadata.get('path') for doc in retrieved_docs]
    markdown_texts = [read_markdown_file(path) for path in md_paths]
    print('markdown_text:', markdown_texts[0])
    if not markdown_texts:
        print('No markdown_texts found')
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='No Markdowns found')

    return {'markdown_texts': markdown_texts}
