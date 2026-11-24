"""The pong mod's callable surface: the ONLY protocol the cog may use.

R5: the cog depends on this Protocol (and nothing deeper); the domain
stays free of Discord and network concerns (R6). Shapes are plain data
(dict) so the contract can later be served over the wire unchanged.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PongContract(Protocol):
    """The pong mod's callable surface for the Discord layer."""

    async def status(self, guild_id: str) -> dict[str, Any]:
        """Return the mod's status payload (home panel, status probes)."""
        ...

    async def register_player(self, guild_id: str, discord_id: str, consent: bool) -> dict[str, Any]:
        """Register (or refuse) a player, honoring the consent gate (RG-REG-1)."""
        ...
