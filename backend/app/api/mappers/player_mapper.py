"""Mapper for converting domain Player models to PlayerOut schemas."""

from fastapi import Request

from app.base_models.schemas import Abilities, Hp, PlayerOut
from app.domain.models import Player as DomainPlayer


def player_to_out(player: DomainPlayer, request: Request | None = None) -> PlayerOut:
    """Map a domain Player model to a PlayerOut Pydantic schema.

    Args:
        player: The domain Player instance.
        request: Optional HTTP request for generating the backend URL.

    Returns:
        A PlayerOut schema instance.
    """
    backend_url = str(request.base_url).rstrip('/') if request is not None else ''

    # Abilities
    abilities_model = None
    if getattr(player, 'abilities', None) is not None:
        a = player.abilities
        abilities_model = Abilities(
            str=int(getattr(a, 'str')),
            dex=int(getattr(a, 'dex')),
            con=int(getattr(a, 'con')),
            int_=int(getattr(a, 'int_')),
            wis=int(getattr(a, 'wis')),
            cha=int(getattr(a, 'cha')),
        )

    # HP
    hp_model = Hp(current=int(player.hp.current), max=int(player.hp.max), temp=int(player.hp.temp))

    has_voiceprint = getattr(player, 'voiceprint', None) is not None

    return PlayerOut(
        id=player.id,
        name=player.name,
        role=player.role,
        status=player.status,
        created_at=player.created_at,
        last_seen_at=player.last_seen_at,
        backend_url=backend_url,
        hp=hp_model,
        abilities=abilities_model,
        has_voiceprint=has_voiceprint,
    )
