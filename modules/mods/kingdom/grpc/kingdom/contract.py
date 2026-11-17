"""The kingdom mod's service contract (§7).

The ONLY surface the cog may call: the service implements it, the cog
consumes it. Everything else in the service package is private — the
cog never touches the mod's collections or internals directly.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

__all__ = ["KingdomStack", "KingdomService"]


class KingdomStack(Protocol):
    """The wired engine stack (P4.1a): kingdoms, territories, attacks."""

    @property
    def kingdoms(self) -> Any:
        """The enrollment/season service (KingdomService)."""
        ...

    @property
    def territories(self) -> Any:
        """The territory/cadastre service (TerritoryService)."""
        ...

    @property
    def attacks(self) -> Any:
        """The attack/defense state machine (AttackService)."""
        ...

    @property
    def diplomacy(self) -> Any:
        """The civilization-conditions & marriage service (DiplomacyService)."""
        ...

    @property
    def events(self) -> Any:
        """The weekly event orchestrator (EventService)."""
        ...

    @property
    def config(self) -> Any:
        """The validated season configuration (KingdomSeasonConfig)."""
        ...


@runtime_checkable
class KingdomService(Protocol):
    """What the kingdom mod's service exposes to its cog."""

    async def status(self, guild_id: str) -> dict[str, Any]:
        """Return the mod's status for the guild (the cog renders it)."""
        ...

    def stack(self) -> KingdomStack | None:
        """Return the wired engine stack, or None when the data layer
        is unavailable (Mongo down, CI smoke) — the cog degrades
        quietly, never crashes."""
        ...
