"""The mods' Mongo adapters: members, mod states, seasons (kingdoms-services#267).

Generic platform persistence for any mod: the membership store (the
enrolled players), the per-guild mod lifecycle states and the seasons
of a mod's scope. A mod never writes its own Mongo layer for these —
it wires these adapters against the shared database and stays
declarative.
"""

from __future__ import annotations

import time
from typing import Any

MEMBERS_COLLECTION = "mod_members"
MOD_STATES_COLLECTION = "mod_states"
SEASONS_COLLECTION = "seasons"


def _now() -> int:
    """Return the current epoch second."""
    return int(time.time())


class ModMembershipMongo:
    """The membership hooks over Mongo — one collection, every mod.

    Document id: ``<mod>:<guild_id>:<user_id>``; the season label rides
    the document (a seasonal mod re-registers per season, a permanent
    mod keeps one row per player).
    """

    def __init__(self, database: Any, mod: str) -> None:
        """Bind the shared database and the mod's namespace."""
        self._db = database
        self._mod = mod

    async def _collection(self) -> Any:
        """Resolve the Mongo collection (async database seam)."""
        return self._db[MEMBERS_COLLECTION]

    async def register_member(self, guild_id: str, user_id: str, display_name: str) -> Any:
        """Upsert one member row (idempotent, last display name wins)."""
        from kingdoms.core.services.membership import MembershipResult

        doc = {
            "_id": f"{self._mod}:{guild_id}:{user_id}",
            "mod": self._mod,
            "guild_id": guild_id,
            "user_id": user_id,
            "display_name": display_name,
            "registered_at": _now(),
        }
        await (await self._collection()).update_one(
            {"_id": doc["_id"]}, {"$set": doc}, upsert=True
        )
        return MembershipResult(ok=True, summary=f"{display_name} inscrit")

    async def unregister_member(self, guild_id: str, user_id: str) -> Any:
        """Delete one member row; unknown members are a no-op success."""
        from kingdoms.core.services.membership import MembershipResult

        await (await self._collection()).delete_one(
            {"_id": f"{self._mod}:{guild_id}:{user_id}"}
        )
        return MembershipResult(ok=True, summary="désinscrit")

    async def is_member(self, guild_id: str, user_id: str) -> bool:
        """Whether one player is enrolled."""
        doc = await (await self._collection()).find_one(
            {"_id": f"{self._mod}:{guild_id}:{user_id}"}
        )
        return bool(doc)

    async def list_members(self, guild_id: str) -> list[dict[str, Any]]:
        """List the guild's enrolled players (ascending by display name)."""
        cursor = (await self._collection()).find({"mod": self._mod, "guild_id": guild_id})
        docs = [doc async for doc in cursor]
        return sorted(docs, key=lambda d: str(d.get("display_name") or ""))


class ModLifecycleMongo:
    """The ModLifecycleDatabase protocol over Mongo."""

    def __init__(self, database: Any) -> None:
        """Bind the shared database."""
        self._db = database

    async def upsert_mod_state(self, document: dict[str, Any]) -> None:
        """Insert or replace one mod state document by ``_id``."""
        await self._db[MOD_STATES_COLLECTION].update_one(
            {"_id": document["_id"]}, {"$set": document}, upsert=True
        )

    async def find_mod_state(self, guild_id: str, mod: str) -> dict[str, Any] | None:
        """Return one mod state document; None when absent."""
        doc = await self._db[MOD_STATES_COLLECTION].find_one({"_id": f"{guild_id}:{mod}"})
        return dict(doc) if doc else None


class ModSeasonMongo:
    """The SeasonDatabase protocol over Mongo, for a mod's scope.

    The seasons collection is shared; every query narrows on the
    mod's ladder id (its ``<mod>:<game>:<guild>`` scope).
    """

    def __init__(self, database: Any, ladder_id: str) -> None:
        """Bind the shared database and the mod's season scope."""
        self._db = database
        self._ladder = ladder_id

    async def upsert_season(self, document: dict[str, Any]) -> None:
        """Insert or replace one season document by ``_id``."""
        await self._db[SEASONS_COLLECTION].update_one(
            {"_id": document["_id"]}, {"$set": document}, upsert=True
        )

    async def find_season(self, season_id: str) -> dict[str, Any] | None:
        """Return one season document; None when absent."""
        doc = await self._db[SEASONS_COLLECTION].find_one({"_id": season_id})
        return dict(doc) if doc else None

    async def find_ladder_seasons(self, ladder_id: str) -> list[dict[str, Any]]:
        """List the seasons of the scope (ascending by start)."""
        cursor = self._db[SEASONS_COLLECTION].find({"ladder_id": ladder_id or self._ladder})
        docs = [doc async for doc in cursor]
        return sorted(docs, key=lambda d: int(d.get("start_at") or 0))

    async def find_active_season(self, ladder_id: str) -> dict[str, Any] | None:
        """Return the scope's active season; None when none."""
        doc = await self._db[SEASONS_COLLECTION].find_one(
            {"ladder_id": ladder_id or self._ladder, "state": "active"}
        )
        return dict(doc) if doc else None

    async def delete_season(self, season_id: str) -> None:
        """Delete one season document (never-started seasons only)."""
        await self._db[SEASONS_COLLECTION].delete_one({"_id": season_id})
