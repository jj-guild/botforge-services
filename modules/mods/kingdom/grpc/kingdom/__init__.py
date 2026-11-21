"""The kingdom mod's gRPC service package (§7 grpc).

Its data, its collections, its contract. The cog calls this package
through the contract — never the other way around.

The package exposes ONE service singleton (``service()``) and its lazy
engine stack (``stack()``) at module level — the cogs' accessor
(``mod_service("kingdom").stack()``) rides them, so the stack is built
once per process, never rebuilt per click.
"""

from __future__ import annotations

from .contract import KingdomService, KingdomStack
from .service import KingdomServiceImpl

_SERVICE: KingdomService = KingdomServiceImpl()


def service() -> KingdomService:
    """Return the mod's service singleton."""
    return _SERVICE


def stack() -> KingdomStack | None:
    """Return the engine stack (built lazily on the singleton; None without Mongo)."""
    return _SERVICE.stack()


__all__ = ["KingdomService", "KingdomServiceImpl", "KingdomStack", "service", "stack"]
