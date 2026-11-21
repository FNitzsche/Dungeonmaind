"""Root endpoint router."""

from fastapi import APIRouter

router = APIRouter()


@router.get('/')
async def read_root() -> dict:
    """Root endpoint returning a simple greeting message.

    Returns:
        dict: Dict with a welcome message.
    """
    return {'message': 'Hello I am the root!'}
