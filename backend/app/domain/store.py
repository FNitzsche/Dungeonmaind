"""Thread-safe in-memory store for the single game group."""

import asyncio
from collections.abc import Mapping
from uuid import UUID

from app.domain.models import Group, Player, PlayerStatus, Role


class SingleGroupStore:
    """Async-safe store for the single group and its players.

    Provides thread-safe read/write access to the group and player data.

    Attributes:
        group: The single Group instance.
        _lock: Async lock for thread-safe access.
    """

    def __init__(self) -> None:
        self.group = Group()
        self._lock = asyncio.Lock()

    async def join(self, name: str, role: Role) -> Player:
        """Add a new player to the group.

        Args:
            name: The player's name.
            role: The player's role (leader or member).

        Returns:
            The newly created Player instance.
        """
        async with self._lock:
            return self.group.add_player(name, role)

    async def leave(self, player_id: UUID) -> None:
        """Mark a player as inactive (leave the group).

        Args:
            player_id: The UUID of the player leaving.
        """
        async with self._lock:
            self.group.deactivate(player_id, status=PlayerStatus.inactive)

    async def list_players(self) -> list[Player]:
        """Return all players in the group.

        Returns:
            List of all Player instances.
        """
        # bewusst kein lock auf die list, da vermutlich nicht so viele Anfragen
        return list(self.group.players.values())

    async def get_player(self, player_id: UUID) -> Player:
        """Get a player by UUID.

        Args:
            player_id: The UUID of the player.

        Returns:
            The Player instance.

        Raises:
            KeyError: If the player is not found.
        """
        async with self._lock:
            return self.group.get_player(player_id)

    async def update_player_abilities(
        self, player_id: UUID, changes: Mapping[str, int | None]
    ) -> Player:
        """Update ability scores for a player.

        Args:
            player_id: The UUID of the player.
            changes: Mapping of ability field names to new values.

        Returns:
            The updated Player instance.
        """
        async with self._lock:
            p = self.group.get_player(player_id)  # KeyError falls unbekannt
            for k, v in changes.items():
                if v is None:
                    continue
                # nur bekannte Ability-Felder setzen
                if hasattr(p.abilities, k):
                    setattr(p.abilities, k, int(v))
            p.touch()
            return p

    async def save_player(self, player: Player) -> None:
        """Save a player to the group store.

        Args:
            player: The Player instance to save.
        """
        async with self._lock:
            self.group.players[player.id] = player

    async def update_player_max_hp(self, pid: UUID, max_hp: int) -> Player:
        """Update a player's maximum HP.

        Args:
            pid: The UUID of the player.
            max_hp: The new maximum HP value.

        Returns:
            The updated Player instance.
        """
        async with self._lock:
            p = self.group.get_player(pid)
            p.set_max_hp(max_hp)
            p.touch()
            self.group.players[p.id] = p
            return p


store = SingleGroupStore()
