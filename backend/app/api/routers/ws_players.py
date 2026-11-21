"""WebSocket endpoint for live player presence updates."""

from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.api.mappers.player_mapper import player_to_out
from app.base_models.schemas import PlayerStatus
from app.core.bus import bus
from app.domain.store import store

router = APIRouter()


@router.websocket('/players')
async def ws_players(
    websocket: WebSocket,
    player_id: UUID = Query(...),
    name: str = Query(...),
    role: str = Query(...),
):
    """WebSocket endpoint for live player presence updates.

    Registers the connection with the PresenceBus and keeps it open
    for broadcasting events. Disconnects are handled automatically.

    Args:
        websocket: The WebSocket connection.
        player_id: Query parameter with the player's UUID.
        name: Query parameter with the player's display name.
        role: Query parameter with the player's role.
    """
    await websocket.accept()
    try:
        player = await store.get_player(player_id)
        print(f'WS connect: {player.id} status={player.status} role={player.role}')
    except ValueError:
        await websocket.close(code=4004, reason='invalid player_id')
        return
    except KeyError:
        await websocket.close(code=4004, reason='unknown player')
        return

    reactivated = False
    if player.status != PlayerStatus.active:
        player = store.group.reactivate(player_id)
        await store.save_player(player)
        reactivated = True

    await bus.register(websocket, str(player_id), name, role)

    if reactivated:
        out = player_to_out(player)
        await bus.publish({'type': 'join', 'player': out.model_dump()})

    try:
        while True:
            # blockiert bis client etwas sendet oder disconnect passiert
            await websocket.receive_text()
    except WebSocketDisconnect:
        await bus.unregister(websocket)
    except Exception:
        await bus.unregister(websocket)
