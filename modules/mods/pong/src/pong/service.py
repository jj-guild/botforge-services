"""Pong registration service: the consent-gated player registration.

SC-PONG-001/002: consent accepted persists the player as a candidate;
consent refused persists NOTHING. Re-registering an existing player is
idempotent (today: until an admin removes them).
"""

from __future__ import annotations

from typing import Any

from botforge.mods.pong.errors import ErrorContext, RegistrationError
from botforge.mods.pong.models import ConsentDecision, PlayerModel, PlayerState
from botforge.mods.pong.storage import PongStore


class RegistrationService:
    """Domain service over an injected PongStore (no Discord, no I/O assumptions)."""

    def __init__(self, store: PongStore) -> None:
        self._store = store

    async def register_with_consent(self, guild_id: str, discord_id: str, consent: bool) -> dict[str, Any]:
        """Register (or refuse) a player, honoring the consent gate (RG-REG-1)."""
        if not consent:
            # SC-PONG-002: a refusal stores nothing, ever.
            return {"registered": False, "consent": ConsentDecision.REFUSED.value}
        try:
            existing = await self._store.get_player(discord_id)
            if existing is not None:
                # Idempotent: the earliest registration wins; the consent trace is kept.
                return {
                    "registered": True,
                    "already_registered": True,
                    "consent": ConsentDecision.ACCEPTED.value,
                    "player": existing,
                }
            player = PlayerModel(
                _id=discord_id,
                guild_id=guild_id,
                state=PlayerState.REGISTERED,
                consent=ConsentDecision.ACCEPTED,
            )
            await self._store.upsert_player(player.to_mongo())
        except Exception as exc:  # noqa: BLE001 - typed boundary (R5 rule)
            raise RegistrationError("player registration failed", ErrorContext({"discord_id": discord_id})) from exc
        return {
            "registered": True,
            "already_registered": False,
            "consent": ConsentDecision.ACCEPTED.value,
            "player": player.to_mongo(),
        }

    async def status(self, guild_id: str) -> dict[str, Any]:
        """The mod's status payload for its home panel and /status probes."""
        return {
            "mod": "pong",
            "guild": guild_id,
            "state": "slice",
            "players": await self._store.player_count(),
        }
