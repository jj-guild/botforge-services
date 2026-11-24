"""The pong mod's storage seam (R8): a Protocol, storage-agnostic.

The domain never talks to Mongo/caches directly; it speaks plain
dicts to a PongStore. The slice uses an in-process implementation;
the persistent ModStorage-backed one lands with the engine (step 3).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PongStore(Protocol):
    """The storage contract the registration service depends on."""

    async def upsert_player(self, document: dict[str, Any]) -> None:
        """Insert or update a player document keyed by `_id` (discord_id)."""
        ...

    async def get_player(self, discord_id: str) -> dict[str, Any] | None:
        """Return the player document, or None if the player is not registered."""
        ...

    async def player_count(self) -> int:
        """Return the number of registered players (slice status panel)."""
        ...
