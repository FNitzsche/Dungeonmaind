"""REST API router for player management (join, leave, kick, health, voiceprint)."""

import contextlib
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)

from app.api.mappers.player_mapper import player_to_out
from app.base_models.schemas import (
    AbilitiesIn,
    GroupStateOut,
    HpPatch,
    JoinCheckOut,
    MaxHpUpdate,
    PlayerDamageBody,
    PlayerHealBody,
    PlayerIn,
    PlayerOut,
    PlayerStatus,
    Role,
)
from app.core.bus import bus
from app.domain.models import Player as DomainPlayer
from app.domain.models import Voiceprint
from app.domain.store import store

router = APIRouter()


# Helpers


async def _get_all_players() -> list[DomainPlayer]:
    """
    Single source to load all players from the domain store.
    Adjust if your store API differs.
    """
    return await store.list_players()


# Group state


@router.get('/state', response_model=GroupStateOut)
async def group_state() -> GroupStateOut:
    """Return the current group state (ID, size, max_size).

    Returns:
        GroupStateOut: GroupStateOut with group metadata.
    """
    g = store.group
    return GroupStateOut(group_id=g.id, size=g.size(), max_size=g.max_size())


# List players (with include_inactive)


@router.get('', response_model=list[PlayerOut])
async def list_players(request: Request, include_inactive: bool = False) -> list[PlayerOut]:
    """List all players, optionally including inactive ones.

    Args:
        request (Request): The incoming HTTP request.
        include_inactive (bool): If True, include inactive and kicked players.

    Returns:
        list[PlayerOut]: List of PlayerOut schemas.
    """
    players = await _get_all_players()

    if not include_inactive:
        players = [p for p in players if p.status == PlayerStatus.active]

    return [player_to_out(p, request) for p in players]


# Join check (used by LoginView)


@router.get('/join/check', response_model=JoinCheckOut)
async def join_check(name: str, request: Request) -> JoinCheckOut:
    """Check if a player name is available for joining.

    Args:
        name (str): The player name to check.
        request (Request): The incoming HTTP request.

    Returns:
        JoinCheckOut: JoinCheckOut with status and optional candidate.
    """
    players = await _get_all_players()
    target = name.strip().lower()

    # active_conflict
    for p in players:
        if p.name.strip().lower() == target and p.status == PlayerStatus.active:
            return JoinCheckOut(status='active_conflict')

    # inactive_match
    for p in players:
        if p.name.strip().lower() == target and p.status != PlayerStatus.active:
            candidate = player_to_out(p, request)
            return JoinCheckOut(status='inactive_match', candidate=candidate)

    return JoinCheckOut(status='available')


# Join (new + reuse)
@router.post('', response_model=PlayerOut, status_code=status.HTTP_201_CREATED)
async def join(payload: PlayerIn, request: Request) -> PlayerOut:
    """Join a new player or reuse an existing inactive player.

    Args:
        payload (PlayerIn): PlayerIn data (name, role, optional reuse_id).
        request (Request): The incoming HTTP request.

    Returns:
        PlayerOut: The created or reactivated PlayerOut.
    """
    # Reuse existing inactive/kicked player
    if payload.reuse_id:
        try:
            p = await store.get_player(payload.reuse_id)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail='Player to reuse not found'
            )

        # Leader collision: only one active leader
        if payload.role == Role.leader:
            players = await _get_all_players()
            for other in players:
                if other.id == p.id:
                    continue
                if other.status == PlayerStatus.active and other.role == Role.leader:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT, detail='Leader role already taken'
                    )

        # Reactivate, update role; keep HP/abilities/name
        p.status = PlayerStatus.active
        p.role = payload.role
        p.touch()
        await store.save_player(p)

        out = player_to_out(p, request)
        await bus.publish({'type': 'join', 'player': out.model_dump()})
        return out

    # New player
    try:
        player = await store.join(payload.name, payload.role)
    except ValueError as e:
        detail = str(e)
        lowered = detail.lower()
        conflict = 'group size' in lowered or 'group role' in lowered or 'player name' in lowered
        code = status.HTTP_409_CONFLICT if conflict else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=detail)

    out = player_to_out(player, request)
    await bus.publish({'type': 'join', 'player': out.model_dump()})
    return out


# Leave / Kick / Exists


@router.delete('/{player_id}', status_code=status.HTTP_204_NO_CONTENT)
async def leave(player_id: UUID):
    """Remove a player from the group (mark as inactive).

    Args:
        player_id: The UUID of the player to remove.
    """
    await store.leave(player_id)
    await bus.publish({'type': 'leave', 'player_id': str(player_id)})
    return None


async def _require_leader(
    actor_id: UUID | None = Query(None, alias='actor_id'),
    x_player_id: str | None = Header(default=None, alias='X-Player-Id'),
):
    """Dependency that ensures the requester is an active leader.

    Args:
        actor_id: Optional query parameter for the actor's UUID.
        x_player_id: Optional X-Player-Id header.

    Returns:
        The leader Player object.

    Raises:
        HTTPException 403: If no active leader is found.
    """
    candidate_ids: list[UUID] = []

    if actor_id:
        candidate_ids.append(actor_id)
    if x_player_id:
        with contextlib.suppress(ValueError):
            candidate_ids.append(UUID(x_player_id))

    players = await _get_all_players()

    for cid in candidate_ids:
        for p in players:
            if p.id == cid and p.status == PlayerStatus.active and p.role == Role.leader:
                return p

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Leader permissions required')


@router.post('/{player_id}/kick', status_code=status.HTTP_204_NO_CONTENT)
async def kick(player_id: UUID, _leader: DomainPlayer = Depends(_require_leader)) -> None:
    """Kick a player from the group (leader-only).

    Args:
        player_id (UUID): The UUID of the player to kick.
        _leader (DomainPlayer): The authenticated leader (dependency).
    """
    try:
        p = await store.get_player(player_id)
    except KeyError:
        return None

    p.status = PlayerStatus.kicked
    p.touch()
    await store.save_player(p)

    await bus.kick(player_id)
    await bus.publish({'type': 'leave', 'player_id': str(player_id)})
    return None


@router.get('/{player_id}/exists')
async def player_exists(player_id: UUID) -> dict:
    """Check if a player UUID exists in the store.

    Args:
        player_id (UUID): The UUID to check.

    Returns:
        dict: Dict with 'exists' boolean.
    """
    try:
        await store.get_player(player_id)
        return {'exists': True}
    except Exception:
        return {'exists': False}


# Abilities update (self-only)


@router.patch('/{player_id}', response_model=PlayerOut)
async def update_player(
    player_id: UUID,
    payload: AbilitiesIn,
    request: Request,
    x_player_id: str | None = Header(default=None, alias='X-Player-Id'),
) -> PlayerOut:
    """Update a player's ability scores (self-only via X-Player-Id header).

    Args:
        player_id (UUID): The UUID of the player to update.
        payload (AbilitiesIn): AbilitiesIn with fields to update.
        request (Request): The incoming HTTP request.
        x_player_id (str | None): X-Player-Id header for authorization.

    Returns:
        PlayerOut: The updated PlayerOut.
    """
    if not x_player_id or x_player_id != str(player_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Only the player can update their own abilities.',
        )

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        p = await store.get_player(player_id)
        return player_to_out(p, request)

    try:
        p = await store.update_player_abilities(player_id, changes)
    except KeyError:
        raise HTTPException(status_code=404, detail='Player not found')

    out = player_to_out(p, request)
    await bus.publish({'type': 'update', 'player': out.model_dump()})
    return out


# Health APIs (nested hp)


@router.patch('/{player_id}/health', response_model=PlayerOut)
async def patch_health(player_id: UUID, patch: HpPatch, request: Request) -> PlayerOut:
    """Patch a player's HP values (current, max, temp).

    Args:
        player_id (UUID): The UUID of the player.
        patch (HpPatch): HpPatch with fields to update.
        request (Request): The incoming HTTP request.

    Returns:
        PlayerOut: The updated PlayerOut.
    """
    p = await store.get_player(player_id)

    if patch.current is not None:
        p.hp.current = int(patch.current)
    if patch.max is not None:
        p.hp.max = int(patch.max)
    if patch.temp is not None:
        p.hp.temp = int(patch.temp)

    p.clamp()
    await store.save_player(p)

    await bus.publish(
        {
            'type': 'health/update',
            'player_id': str(p.id),
            'hp': {'current': p.hp.current, 'max': p.hp.max, 'temp': p.hp.temp},
        }
    )

    return player_to_out(p, request)


@router.post('/{player_id}/damage', response_model=PlayerOut)
async def apply_damage(player_id: UUID, body: PlayerDamageBody, request: Request) -> PlayerOut:
    """Apply damage to a player.

    Args:
        player_id (UUID): The UUID of the player.
        body (PlayerDamageBody): PlayerDamageBody with damage amount.
        request (Request): The incoming HTTP request.

    Returns:
        PlayerOut: The updated PlayerOut.
    """
    p = await store.get_player(player_id)
    p.apply_damage(body.damage)
    await store.save_player(p)

    await bus.publish(
        {
            'type': 'health/update',
            'player_id': str(p.id),
            'hp': {'current': p.hp.current, 'max': p.hp.max, 'temp': p.hp.temp},
        }
    )

    return player_to_out(p, request)


@router.post('/{player_id}/heal', response_model=PlayerOut)
async def apply_heal(player_id: UUID, body: PlayerHealBody, request: Request) -> PlayerOut:
    """Heal a player by a given amount.

    Args:
        player_id (UUID): The UUID of the player.
        body (PlayerHealBody): PlayerHealBody with heal amount.
        request (Request): The incoming HTTP request.

    Returns:
        PlayerOut: The updated PlayerOut.
    """
    p = await store.get_player(player_id)
    p.heal(body.heal)
    await store.save_player(p)

    await bus.publish(
        {
            'type': 'health/update',
            'player_id': str(p.id),
            'hp': {'current': p.hp.current, 'max': p.hp.max, 'temp': p.hp.temp},
        }
    )

    return player_to_out(p, request)


@router.post('/{player_id}/health/max', response_model=PlayerOut)
async def update_max_hp(player_id: UUID, body: MaxHpUpdate, request: Request) -> PlayerOut:
    """Update a player's maximum HP.

    Args:
        player_id (UUID): The UUID of the player.
        body (MaxHpUpdate): MaxHpUpdate with the new max HP.
        request (Request): The incoming HTTP request.

    Returns:
        PlayerOut: The updated PlayerOut.
    """
    try:
        p = await store.update_player_max_hp(player_id, body.max)
    except KeyError:
        raise HTTPException(status_code=404, detail='Player not found')
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    await store.save_player(p)

    await bus.publish(
        {
            'type': 'health/update',
            'player_id': str(p.id),
            'hp': {'current': p.hp.current, 'max': p.hp.max, 'temp': p.hp.temp},
        }
    )

    return player_to_out(p, request)


@router.post('/{player_id}/voiceprint', response_model=PlayerOut)
async def upload_player_voiceprint(
    player_id: UUID, request: Request, audio: UploadFile = File(...)
) -> PlayerOut:
    """Upload a voiceprint audio file for a player.

    Args:
        player_id (UUID): The UUID of the player.
        request (Request): The incoming HTTP request.
        audio (UploadFile): The uploaded audio file.

    Returns:
        PlayerOut: The updated PlayerOut with has_voiceprint=True.
    """
    try:
        p = await store.get_player(player_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Player not found')

    audio_bytes = await audio.read()
    content_type = audio.content_type
    p.voiceprint = Voiceprint(audio_bytes=audio_bytes, content_type=content_type)
    await store.save_player(p)

    out = player_to_out(p, request)
    await bus.publish({'type': 'update', 'player': out.model_dump()})

    return out
