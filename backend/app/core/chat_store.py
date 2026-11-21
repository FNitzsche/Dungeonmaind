"""In-memory chat history storage per player with async-safe access."""

import asyncio
from collections import defaultdict
from uuid import UUID


class ChatStore:
    """Async-safe in-memory store for per-player chat histories.

    Each message is stored with role, content, and an embedding vector.

    Attributes:
        _lock: Async lock for thread-safe access.
        _by_player: Mapping from player UUID to list of message dicts.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._by_player = defaultdict(list)  # UUID -> List[dict]

    async def append(
        self, player_id: UUID, role: str, content: str, embedded_content: list[float]
    ) -> None:
        """Append a message to a player's chat history.

        Args:
            player_id: The player's UUID.
            role: Message role ('user' or 'assistant').
            content: The message text content.
            embedded_content: The embedding vector for the message content.
        """
        async with self._lock:
            self._by_player[player_id].append(
                {'role': role, 'content': content, 'embedded_content': embedded_content}
            )

    async def history(self, player_id: UUID) -> list[dict]:
        """Return a copy of a player's chat history.

        Args:
            player_id: The player's UUID.

        Returns:
            A list of message dicts (role, content, embedded_content).
        """
        # Nur Kopie rausgeben
        async with self._lock:
            return list(self._by_player[player_id])

    async def clear(self, player_id: UUID) -> None:
        """Clear the chat history for a specific player.

        Args:
            player_id: The player's UUID.
        """
        async with self._lock:
            self._by_player[player_id].clear()

    async def clear_all(self) -> None:
        """Clear all chat histories for all players."""
        async with self._lock:
            self._by_player = defaultdict(list)


chat_store = ChatStore()
