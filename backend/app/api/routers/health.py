"""Health check endpoint for connection verification."""

from fastapi import APIRouter, Response, status

router = APIRouter()


@router.get('/checkConnection')
async def checkConnection(response: Response):
    """Health check endpoint that returns 204 No Content.

    Used by frontends to verify the backend is reachable.
    Disables caching to prevent stale responses.

    Args:
        response: The HTTP response object.
    """
    print('check_connection: Habe Anfrage erhalten!')
    response.status_code = status.HTTP_204_NO_CONTENT
    response.headers['Cache-Control'] = (
        'no-store'  # Caching unterbinden - wichtig, damit Browser/Proxies nichts "alt" liefern.
    )
