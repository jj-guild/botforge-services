"""The pong mod's service implementation (its data, its collections).

Implements the contract (contract.py); never imports Discord (R6): the
cog is the mod's only Discord layer. The slice keeps an in-process
store; the persistent collections ride the ModStorage facade (R8) with
the season engine (step 3, tracked in #439).
"""

from __future__ import annotations

from typing import Any

from botforge.mods.pong.grpc.contract import PongContract
from botforge.mods.pong.service import RegistrationService
from botforge.mods.pong.storage import PongStore


class _InProcessPongStore:
    """In-memory PongStore: the slice's ephemeral persistence."""

    def __init__(self) -> None:
        self._players: dict[str, dict[str, Any]] = {}

    async def upsert_player(self, document: dict[str, Any]) -> None:
        self._players[str(document["_id"])] = dict(document)

    async def get_player(self, discord_id: str) -> dict[str, Any] | None:
        document = self._players.get(discord_id)
        return dict(document) if document is not None else None

    async def player_count(self) -> int:
        return len(self._players)


class PongServiceImpl(PongContract):
    """The contract's implementation: a thin shell over the domain service."""

    def __init__(self, store: PongStore | None = None) -> None:
        self._service = RegistrationService(store if store is not None else _InProcessPongStore())

    async def status(self, guild_id: str) -> dict[str, Any]:
        """Return the mod's status payload (home panel, status probes)."""
        return await self._service.status(guild_id)

    async def register_player(self, guild_id: str, discord_id: str, consent: bool) -> dict[str, Any]:
        """Register (or refuse) a player, honoring the consent gate (RG-REG-1)."""
        return await self._service.register_with_consent(guild_id, discord_id, consent)
