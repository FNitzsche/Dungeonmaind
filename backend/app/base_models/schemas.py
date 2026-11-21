"""Pydantic schemas for player, group, and HP request/response models."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# Use the domain enums as the single source of truth
from app.domain.models import PlayerStatus, Role


# Input models
class PlayerIn(BaseModel):
    """Request model for creating or reusing a player.

    Attributes:
        name: Player display name (2-50 characters).
        role: Player role (leader or member).
        reuse_id: Optional UUID for re-joining an existing player.
    """

    name: str = Field(min_length=2, max_length=50)
    role: Role
    reuse_id: UUID | None = None  # used for re-join / reuse flow


# Abilities
class Abilities(BaseModel):
    """Ability scores for a player character.

    Attributes:
        str: Strength score.
        dex: Dexterity score.
        con: Constitution score.
        int_: Intelligence score.
        wis: Wisdom score.
        cha: Charisma score.
    """

    # "int_" kept to match frontend & domain model
    str: int
    dex: int
    con: int
    int_: int
    wis: int
    cha: int


class AbilitiesIn(BaseModel):
    """Partial ability scores input for updating specific fields.

    All fields are optional; only provided fields will be updated.
    """

    str: int | None = None
    dex: int | None = None
    con: int | None = None
    int_: int | None = None
    wis: int | None = None
    cha: int | None = None


# HP (nested)
class Hp(BaseModel):
    """Hit point values for a player character.

    Attributes:
        current: Current hit points.
        max: Maximum hit points.
        temp: Temporary hit points.
    """

    current: int = 0
    max: int = 10
    temp: int = 0


class HpPatch(BaseModel):
    """Partial HP update model; only provided fields will be changed."""

    current: int | None = Field(None, ge=0)
    max: int | None = Field(None, ge=1)
    temp: int | None = Field(None, ge=0)


class MaxHpUpdate(BaseModel):
    """Request model for updating a player's maximum HP."""

    max: int = Field(..., ge=1)


# Output models
class PlayerOut(BaseModel):
    """Response model representing a player.

    Attributes:
        id: Unique player UUID.
        name: Player display name.
        role: Player role.
        status: Current player status.
        hp: Hit point values.
        created_at: Player creation timestamp.
        last_seen_at: Last activity timestamp.
        abilities: Optional ability scores.
        backend_url: Backend URL for resource links.
        has_voiceprint: Whether the player has a voiceprint uploaded.
    """

    id: UUID
    name: str
    role: Role
    status: PlayerStatus
    hp: Hp = Field(default_factory=Hp)
    created_at: datetime
    last_seen_at: datetime
    abilities: Abilities | None = None
    backend_url: str | None = None
    has_voiceprint: bool = False


# Optional: unified patch model (not currently used by routes)
class PlayerPatch(BaseModel):
    """Unified patch model for partial player updates (not currently used by routes)."""

    name: str | None = None
    role: Role | None = None

    hp: HpPatch | None = None
    abilities: AbilitiesIn | None = None

    # flat ability fields
    str: int | None = None
    dex: int | None = None
    con: int | None = None
    int_: int | None = None
    wis: int | None = None
    cha: int | None = None


# Action bodies
class PlayerDamageBody(BaseModel):
    """Request model for applying damage to a player."""

    damage: int = Field(..., ge=0)


class PlayerHealBody(BaseModel):
    """Request model for healing a player."""

    heal: int = Field(..., ge=0)


# Group state
class GroupStateOut(BaseModel):
    """Response model for group state information."""

    group_id: UUID
    size: int
    max_size: int


# For /players/join/check
class JoinCheckOut(BaseModel):
    """Response model for join availability checks.

    Attributes:
        status: Whether the name is 'available', 'inactive_match', or 'active_conflict'.
        candidate: The existing player if an inactive match was found.
    """

    status: Literal['available', 'inactive_match', 'active_conflict']
    candidate: PlayerOut | None = None
