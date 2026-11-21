import asyncio
import contextlib
import json
import time
from uuid import UUID

from fastapi import WebSocket

from app.domain.models import PlayerStatus
from app.domain.store import store

"""WebSocket-based presence management and event broadcasting."""

GRACE_SEC = 2  # Reload-Toleranz


class PresenceBus:
    """Manages WebSocket connections and broadcasts events to connected clients.

    Each player can have multiple WebSocket connections (e.g., multiple browser
    tabs). When the last connection for a player is closed, a delayed leave
    event is published after a grace period.

    Attributes:
        _lock: Async lock for thread-safe access.
        _sockets: Set of all connected WebSocket connections.
        _ws_meta: Mapping from WebSocket to player metadata dict.
        _player_sockets: Mapping from player_id to set of their WebSockets.
        _pending_leave: Mapping from player_id to delayed leave tasks.
    """

    def __init__(self, timeout_sec: int = 60):
        self._lock = asyncio.Lock()
        self._sockets: set[WebSocket] = set()
        self._ws_meta: dict[WebSocket, dict] = {}  # ws -> {"player_id": "..."}
        self._player_sockets: dict[
            str, set[WebSocket]
        ] = {}  # player_id -> set(ws) | ein Player kann mehrere Tabs/Sockets offen haben, erst beim schließen des letzten einen leave ausführen
        self._pending_leave: dict[str, asyncio.Task] = {}  # player_id -> task

    async def register(self, ws: WebSocket, player_id: str, name: str, role: str):
        """Register a new WebSocket connection for a player.

        Cancels any pending leave task for this player.

        Args:
            ws: The WebSocket connection to register.
            player_id: The player's unique identifier.
            name: The player's display name.
            role: The player's role (leader/member).
        """
        async with self._lock:
            pid = str(player_id)
            self._sockets.add(ws)
            self._ws_meta[ws] = {
                'player_id': pid,
                'name': name,
                'role': role,
                'last_seen': time.time(),
            }
            self._player_sockets.setdefault(pid, set()).add(ws)
            # Falls ein Leave für diesen Spieler geplant war abbrechen
            task = self._pending_leave.pop(pid, None)
            if task and not task.done():
                task.cancel()
                # task.add_done_callback(_silence_task_exception)

    async def unregister(self, ws: WebSocket):
        """Unregister a WebSocket connection and schedule a leave event.

        If this was the last connection for the player, a delayed leave is
        scheduled after a grace period to handle reconnections.

        Args:
            ws: The WebSocket connection to unregister.
        """
        meta = None
        last_socket_for_player = False

        async with self._lock:
            meta = self._ws_meta.pop(ws, None)
            self._sockets.discard(ws)
            if meta:
                pid = meta['player_id']
                s = self._player_sockets.get(pid)
                if s:
                    s.discard(ws)
                    if not s:
                        # Letzter Socket dieses Spielers
                        self._player_sockets.pop(pid, None)
                        last_socket_for_player = True
        with contextlib.suppress(Exception):
            await ws.close()

        if not meta:
            return

        player_id = meta['player_id']

        # Wenn noch andere Tabs dieses Spielers offen sind, nichts tun
        if not last_socket_for_player:
            return

        # letzter Socket weg -> Leave planen
        async def delayed_leave(pid: str):
            try:
                await asyncio.sleep(GRACE_SEC)
                async with self._lock:
                    still_zero = pid not in self._player_sockets or not self._player_sockets.get(
                        pid
                    )
                if still_zero:
                    await self._backend_leave_and_publish(pid)
            except asyncio.CancelledError:
                return
            finally:
                # noinspection PyAsyncCall
                self._pending_leave.pop(
                    pid, None
                )  # durch await wird Exception geworfen, deswegen unterdrückt

        task = asyncio.create_task(delayed_leave(player_id))
        # task.add_done_callback(_silence_task_exception)
        async with self._lock:
            # Falls es schon einen Task gibt, ersetzen
            old = self._pending_leave.get(player_id)
            if old and not old.done():
                old.cancel()
                # old.add_done_callback(_silence_task_exception)
            self._pending_leave[player_id] = task

    async def publish(self, event: dict):
        """Broadcast an event to all connected WebSocket clients.

        Args:
            event: The event dict to serialize and send.
        """
        data = json.dumps(event, default=str)
        dead: list[WebSocket] = []
        async with self._lock:
            targets = list(self._sockets)
        for ws in targets:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.unregister(ws)

    async def _backend_leave_and_publish(self, player_id: str):
        """Deactivate a player in the store and broadcast the leave event.

        Args:
            player_id: The player's unique identifier.
        """
        with contextlib.suppress(Exception):
            await store.group.deactivate(UUID(player_id), status=PlayerStatus.inactive)
        await self.publish({'type': 'leave', 'player_id': str(player_id)})

    async def kick(self, player_id: UUID):
        """Forcefully disconnect all WebSocket connections for a player.

        Args:
            player_id: The UUID of the player to kick.
        """
        pid = str(player_id)
        pid = str(player_id)
        async with self._lock:
            sockets = list(self._player_sockets.get(pid, set()))
        for ws in sockets:
            with contextlib.suppress(Exception):
                await ws.close(code=4001, reason='kicked')


bus = PresenceBus()
