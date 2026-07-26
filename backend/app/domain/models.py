"""Domain models for players, groups, timeline events, and related value objects."""

from __future__ import annotations

import base64
import secrets
import string
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class Role(StrEnum):
    """Player role within a group."""

    leader = 'leader'
    member = 'member'


class PlayerStatus(StrEnum):
    """Player online/offline status."""

    active = 'active'
    inactive = 'inactive'
    kicked = 'kicked'


def now_utc() -> datetime:
    """Return the current UTC datetime.

    Returns:
        Current datetime in UTC.
    """
    return datetime.now(UTC)


def make_join_code(length: int = 6) -> str:
    """Generate a short, human-readable join code.

    Args:
        length: Length of the generated code (default 6).

    Returns:
        A random alphanumeric join code string.
    """
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@dataclass
class Abilities:
    """Character ability scores with stable numeric defaults.

    Attributes:
        str: Strength score (default 10).
        dex: Dexterity score (default 10).
        con: Constitution score (default 10).
        int_: Intelligence score (default 10).
        wis: Wisdom score (default 10).
        cha: Charisma score (default 10).
    """

    # stabile numerische Defaults, damit das Frontend keine "—" zeigt
    str: int = 10
    dex: int = 10
    con: int = 10
    int_: int = 10
    wis: int = 10
    cha: int = 10


@dataclass
class Hp:
    """Hit point values for a player character.

    Attributes:
        current: Current hit points (default 10).
        max: Maximum hit points (default 10).
        temp: Temporary hit points (default 0).
    """

    current: int = 10
    max: int = 10
    temp: int = 0


@dataclass
class Voiceprint:
    """Stored audio data for a player's voice sample.

    Attributes:
        audio_bytes: Raw audio byte data.
        content_type: MIME type of the audio data.
    """

    audio_bytes: bytes
    content_type: str


@dataclass
class Player:
    """Represents a player character in the game session.

    Attributes:
        id: Unique UUID for the player.
        name: Display name of the player.
        role: Player role (leader or member).
        status: Current online status (active/inactive/kicked).
        hp: Hit point values (current, max, temp).
        created_at: Timestamp when the player was created.
        last_seen_at: Timestamp of the player's last activity.
        abilities: Character ability scores.
        voiceprint: Optional stored voice sample.
    """

    id: UUID
    name: str
    role: Role
    status: PlayerStatus = PlayerStatus.active
    hp: Hp = field(default_factory=Hp)  # nested HP object
    created_at: datetime = field(default_factory=now_utc)
    last_seen_at: datetime = field(default_factory=now_utc)
    abilities: Abilities = field(default_factory=Abilities)
    voiceprint: Voiceprint | None = None

    def touch(self) -> None:
        """Update the last_seen_at timestamp to now."""
        self.last_seen_at = now_utc()

    # HP helpers

    def clamp(self) -> None:
        """Clamp HP values to valid ranges.

        Ensures max_hp >= 1, current_hp is between 0 and max_hp,
        and temp_hp >= 0.
        """
        if self.hp.max < 1:
            self.hp.max = 1
        if self.hp.current > self.hp.max:
            self.hp.current = self.hp.max
        if self.hp.current < 0:
            self.hp.current = 0
        if self.hp.temp < 0:
            self.hp.temp = 0

    def set_hp(self, hp: int, max_hp: int | None = None, temp_hp: int | None = None) -> None:
        """Set HP values with backward-compatible signature.

        Args:
            hp: New current HP value.
            max_hp: Optional new max HP value.
            temp_hp: Optional new temp HP value.
        """
        if max_hp is not None:
            self.hp.max = int(max_hp)
        if temp_hp is not None:
            self.hp.temp = int(temp_hp)
        self.hp.current = int(hp)
        self.clamp()

    def heal(self, amount: int) -> int:
        """Heal the player by a given amount, capped at max_hp.

        Args:
            amount: Amount of HP to restore.

        Returns:
            The actual amount of HP restored.
        """
        before = self.hp.current
        self.hp.current = min(self.hp.max, self.hp.current + max(0, int(amount)))
        return self.hp.current - before

    def apply_damage(self, dmg: int) -> dict[str, int]:
        """Apply damage to the player, absorbing with temp HP first.

        Args:
            dmg: Amount of damage to apply.

        Returns:
            Dict with 'temp_absorbed' and 'hp_loss' values.
        """
        dmg = max(0, int(dmg))
        from_temp = min(self.hp.temp, dmg)
        self.hp.temp -= from_temp
        remaining = dmg - from_temp
        before = self.hp.current
        self.hp.current = max(0, self.hp.current - remaining)
        return {'temp_absorbed': from_temp, 'hp_loss': before - self.hp.current}

    def set_max_hp(self, max_hp: int) -> None:
        """Set max HP and clamp all HP values to valid ranges.

        Args:
            max_hp: New maximum HP (must be at least 1).

        Raises:
            ValueError: If max_hp is less than 1.
        """
        max_hp_int = int(max_hp)
        if max_hp_int < 1:
            raise ValueError('max_hp must be at least 1')
        self.hp.max = max_hp_int
        self.clamp()

    # Serialization helpers (tolerate legacy formats)

    def to_dict(self) -> dict:
        """Serialize the player to a dictionary.

        Returns:
            Dict representation of the player.
        """
        voice_dict = None
        if getattr(self, 'voiceprint', None) is not None:
            voice_dict = {
                'content_type': self.voiceprint.content_type,
                'audio_b64': base64.b64encode(self.voiceprint.audio_bytes).decode('ascii'),
            }

        return {
            'id': str(self.id),
            'name': self.name,
            'role': self.role.value,
            'status': self.status.value,
            'hp': {'current': self.hp.current, 'max': self.hp.max, 'temp': self.hp.temp},
            'abilities': {
                'str': self.abilities.str,
                'dex': self.abilities.dex,
                'con': self.abilities.con,
                'int_': self.abilities.int_,
                'wis': self.abilities.wis,
                'cha': self.abilities.cha,
            }
            if self.abilities
            else None,
            'voiceprint': voice_dict,
            'created_at': self.created_at.isoformat(),
            'last_seen_at': self.last_seen_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Player:
        """Deserialize a player from a dictionary.

        Handles legacy formats and sets leader status to active.

        Args:
            data: Dict representation of a player.

        Returns:
            A new Player instance.
        """
        role = Role(data['role'])

        if role == Role.leader:  # alle leader werden active gesetzt
            status = PlayerStatus.active
        elif (
            PlayerStatus(data['status']) == PlayerStatus.active
        ):  # alle (noch) aktiven Player werden inactive, um rejoinen zu können
            status = PlayerStatus.inactive
        else:
            status = PlayerStatus(
                data['status']
            )  # Player die bereits inactive oder kicked sind behalten ihren Status

        hp_field = data.get('hp') or {}
        hp = Hp(
            current=int(hp_field.get('current', 10)),
            max=int(hp_field.get('max', 10)),
            temp=int(hp_field.get('temp', 0)),
        )

        abilities_data = data.get('abilities') or {}
        abilities = Abilities(
            str=int(abilities_data.get('str', 10)),
            dex=int(abilities_data.get('dex', 10)),
            con=int(abilities_data.get('con', 10)),
            int_=int(abilities_data.get('int_', 10)),
            wis=int(abilities_data.get('wis', 10)),
            cha=int(abilities_data.get('cha', 10)),
        )

        voiceprint = None
        voice_data = data.get('voiceprint')
        if voice_data and voice_data.get('audio_b64'):
            try:
                audio_bytes = base64.b64decode(voice_data['audio_b64'])
                content_type = voice_data.get('content_type', 'application/octet-stream')
                voiceprint = Voiceprint(audio_bytes=audio_bytes, content_type=content_type)
            except Exception:
                voiceprint = None

        created_at = (
            datetime.fromisoformat(data['created_at']) if 'created_at' in data else now_utc()
        )
        last_seen_at = (
            datetime.fromisoformat(data['last_seen_at']) if 'last_seen_at' in data else created_at
        )

        return cls(
            id=UUID(str(data['id'])),
            name=data['name'],
            role=role,
            status=status,
            hp=hp,
            abilities=abilities,
            voiceprint=voiceprint,
            created_at=created_at,
            last_seen_at=last_seen_at,
        )


class TimelineEventType(StrEnum):
    """Categorization of timeline events in a session."""

    combat = 'combat'
    discovery = 'discovery'
    dialogue = 'dialogue'
    travel = 'travel'
    rest = 'rest'
    quest = 'quest'
    other = 'other'


@dataclass
class TimelineEvent:
    """A notable event that occurred during a game session.

    Attributes:
        id: Unique event identifier.
        session_id: Identifier for the session this event belongs to.
        title: Short title for the event.
        description: Detailed description of the event.
        event_type: Categorization of the event (combat, discovery, etc.).
        order: Ordinal position within the session.
        timestamp: Float timestamp of when the event occurred.
        transcription_chunk_id: ID of the transcription chunk this event was extracted from.
        player_id: ID of the player associated with the event.
        speaker_name: Name of the speaker associated with the event.
        temporal_entities: List of time-related entities extracted from the event.
        location_entities: List of location entities extracted from the event.
        created_at: Timestamp when the event was created.
    """

    id: str
    session_id: str
    title: str
    description: str
    event_type: TimelineEventType = field(default_factory=lambda: TimelineEventType.other)
    order: int = 0
    timestamp: float = 0.0
    transcription_chunk_id: str | None = None
    player_id: str | None = None
    speaker_name: str | None = None
    temporal_entities: list[str] = field(default_factory=list)
    location_entities: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=now_utc)

    def to_dict(self) -> dict:
        """Serialize the timeline event to a dictionary.

        Returns:
            Dict representation of the event.
        """
        return {
            'id': self.id,
            'session_id': self.session_id,
            'title': self.title,
            'description': self.description,
            'event_type': self.event_type.value,
            'order': self.order,
            'timestamp': self.timestamp,
            'transcription_chunk_id': self.transcription_chunk_id,
            'player_id': self.player_id,
            'speaker_name': self.speaker_name,
            'temporal_entities': self.temporal_entities,
            'location_entities': self.location_entities,
            'created_at': self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> TimelineEvent:
        """Deserialize a timeline event from a dictionary.

        Args:
            data: Dict representation of a timeline event.

        Returns:
            A new TimelineEvent instance.
        """
        return cls(
            id=data['id'],
            session_id=data['session_id'],
            title=data['title'],
            description=data['description'],
            event_type=TimelineEventType(data.get('event_type', 'other')),
            order=data.get('order', 0),
            timestamp=data.get('timestamp', 0.0),
            transcription_chunk_id=data.get('transcription_chunk_id'),
            player_id=data.get('player_id'),
            speaker_name=data.get('speaker_name'),
            temporal_entities=data.get('temporal_entities', []),
            location_entities=data.get('location_entities', []),
            created_at=datetime.fromisoformat(data['created_at'])
            if 'created_at' in data
            else now_utc(),
        )


@dataclass
class Group:
    """Represents a group (party) of players in a game session.

    Attributes:
        id: Unique UUID for the group.
        max_size: Maximum number of active players allowed.
        players: Dict mapping player UUID to Player objects.
    """

    id: UUID = field(default_factory=uuid4)
    max_size: int = 6
    # Spieler werden per ID gehalten
    players: dict[UUID, Player] = field(default_factory=dict)

    # Views

    def active(self) -> dict[UUID, Player]:
        """Return only active players.

        Returns:
            Dict of active players keyed by UUID.
        """
        return {pid: p for pid, p in self.players.items() if p.status == PlayerStatus.active}

    def inactive(self) -> dict[UUID, Player]:
        """Return only inactive players.

        Returns:
            Dict of inactive players keyed by UUID.
        """
        return {pid: p for pid, p in self.players.items() if p.status == PlayerStatus.inactive}

    def size(self) -> int:
        """Return the number of active players.

        Returns:
            Active player count.
        """
        return len(self.active())

    def leader_id(self, is_inactive_ok: bool = False) -> UUID | None:
        """Return the UUID of the group leader.

        Args:
            is_inactive_ok: If True, also consider inactive leaders as fallback.

        Returns:
            The leader's UUID, or None if no leader exists.
        """
        leader_pid: UUID = None
        for pid, p in self.active().items():  # zuerst versuchen einen aktiven leader zu finden
            if p.role == Role.leader:
                leader_pid = pid
        if is_inactive_ok and leader_pid is None:
            for pid, p in self.inactive().items():  # wenn keinen gefunden, dann inaktiven
                if p.role == Role.leader:
                    leader_pid = pid
        return leader_pid

    def has_active_name(self, name: str) -> bool:
        """Check if an active player with the given name exists.

        Args:
            name: The name to check.

        Returns:
            True if an active player with that name exists.
        """
        n = name.strip().lower()
        return any(p.name.strip().lower() == n for p in self.active().values())

    # Mutations

    def add_player(self, name: str, role: Role) -> Player:
        """Add a new player to the group.

        Rules:
        - max_size applies to active players only.
        - Only one active leader is allowed.
        - Player names must be unique among active players.

        Args:
            name: The player's display name.
            role: The player's role (leader or member).

        Returns:
            The newly created Player instance.

        Raises:
            ValueError: If the group is full, a leader already exists,
                or the name is already taken.
        """
        if self.size() >= self.max_size:
            raise ValueError(f'Group size {self.size()} >= {self.max_size}')
        if role is Role.leader and self.leader_id() is not None:
            raise ValueError("Group role 'leader' already exists")
        if self.has_active_name(name):
            raise ValueError(f"Player name '{name}' already exists")

        player = Player(id=uuid4(), name=name, role=role, status=PlayerStatus.active)
        self.players[player.id] = player
        return player

    def deactivate(self, pid: UUID, status: PlayerStatus = PlayerStatus.inactive) -> None:
        """Soft-deactivate a player by updating their status.

        If the new status is inactive, removes any duplicate inactive/kicked
        players with the same name.

        Args:
            pid: The UUID of the player to deactivate.
            status: The new status (default PlayerStatus.inactive).
        """
        p = self.players.get(pid)
        if not p:
            return

        p.status = status
        p.touch()

        if status == PlayerStatus.inactive:
            n = p.name.strip().lower()
            to_remove = [
                other_id
                for other_id, other in self.players.items()
                if other_id != pid
                and other.status in (PlayerStatus.inactive, PlayerStatus.kicked)
                and other.name.strip().lower() == n
            ]
            for other_id in to_remove:
                self.players.pop(other_id, None)

    def reactivate(self, pid: UUID) -> Player:
        """Reactivate a player by setting status to active.

        Args:
            pid: The UUID of the player to reactivate.

        Returns:
            The reactivated Player instance.

        Raises:
            KeyError: If the player does not exist.
        """
        p = self.players.get(pid)
        if not p:
            raise KeyError(f"Player '{pid}' does not exist")
        p.status = PlayerStatus.active
        p.touch()
        return p

    def get_player(self, pid: UUID) -> Player:
        """Get a player by UUID.

        Args:
            pid: The UUID of the player.

        Returns:
            The Player instance.

        Raises:
            KeyError: If the player is not found.
        """
        p = self.players.get(pid)
        if not p:
            raise KeyError('Player not found.')
        return p

    def remove_player(self, pid: UUID) -> None:
        """Remove a player by marking them as inactive (soft delete).

        Args:
            pid: The UUID of the player to remove.
        """
        self.deactivate(pid, status=PlayerStatus.inactive)
