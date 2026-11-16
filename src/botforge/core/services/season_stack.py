"""The per-mod, per-guild season stack accessor — the panels' door (P3).

``build_mod_season_stack`` wires the generic stack (SeasonService +
EnrollmentService + SeasonRolesService) for one mod on ONE guild; the
pinned panels need it resolved lazily (a guild's stack builds on
first use and caches on the bot). The seasons ride the mod's
ModStorage (the namespaced collections — R8); the enrollment's
criteria come from the mod's declaration (``settings.enrollment``).
"""

from __future__ import annotations

import logging
from typing import Any

from botforge.core.services.mod_seasons import build_mod_season_stack
from botforge.core.services.season_roles import SeasonRolesService

logger = logging.getLogger("botforge.core.services.season_stack")

SEASONS_COLLECTION = "seasons"
APPLICATIONS_COLLECTION = "applications"


class ModStorageSeasonDatabase:
    """The SeasonDatabase protocol over the mod's season SCOPE (R8).

    The seasons and the applications live under the SCOPE's own
    namespace — ``mod:<mod>:season:<guild>:seasons`` and
    ``...:applications`` — NEVER the bare ``<mod>:`` prefix (the
    owner's rule: one namespace per scope, the wipe is surgical).
    """

    def __init__(self, database: Any, scope: str) -> None:
        self._db = database
        self._scope = scope

    @property
    def _database(self) -> Any:
        """The inner Mongo database (the enrollment's seam expects it)."""
        return self._db

    def _seasons(self) -> Any:
        """Return the scope's seasons collection."""
        return self._db[f"{self._scope}:{SEASONS_COLLECTION}"]

    async def upsert_season(self, document: dict[str, Any]) -> None:
        """Insert or replace one season document by ``_id``."""
        await self._seasons().replace_one({"_id": document["_id"]}, document, upsert=True)

    async def find_season(self, season_id: str) -> dict[str, Any] | None:
        """Return one season document."""
        doc = await self._seasons().find_one({"_id": season_id})
        return dict(doc) if doc is not None else None

    async def find_ladder_seasons(self, ladder_id: str) -> list[dict[str, Any]]:
        """Return every season document of one ladder (ascending)."""
        cursor = self._seasons().find({"ladder_id": ladder_id})
        return [dict(doc) async for doc in cursor.sort("index", 1)]

    async def find_active_season(self, ladder_id: str) -> dict[str, Any] | None:
        """Return the ladder's live season (scheduled or active)."""
        cursor = self._seasons().find({"ladder_id": ladder_id, "state": {"$in": ["scheduled", "active"]}})
        async for doc in cursor.sort("index", -1).limit(1):
            return dict(doc)
        return None

    async def delete_season(self, season_id: str) -> None:
        """Drop one season document."""
        await self._seasons().delete_one({"_id": season_id})

    async def upsert_application(self, document: dict[str, Any]) -> None:
        """Insert or replace one application document."""
        self._db[f"{self._scope}:{APPLICATIONS_COLLECTION}"].replace_one(
            {"_id": document["_id"]}, document, upsert=True
        )

    def _applications(self) -> Any:
        """Return the scope's applications collection."""
        return self._db[f"{self._scope}:{APPLICATIONS_COLLECTION}"]

    async def find_active_application(self, guild_id: str, user_id: str) -> dict[str, Any] | None:
        """Return one user's pending application."""
        doc = await self._applications().find_one(
            {"guild_id": guild_id, "user_id": user_id, "state": "pending"}
        )
        return dict(doc) if doc is not None else None

    async def list_applications(self, guild_id: str, state: str | None = None) -> list[dict[str, Any]]:
        """List the guild's applications (optionally by state)."""
        query: dict[str, Any] = {"guild_id": guild_id}
        if state is not None:
            query["state"] = state
        cursor = self._applications().find(query)
        return [dict(doc) async for doc in cursor.sort("applied_at", 1)]


def season_stack_for(bot: Any, mod: str, guild_id: str) -> Any:
    """Resolve (or lazily build) one mod's season stack on one guild.

    The stacks cache on the bot (``season_stacks`` keyed by
    ``(mod, guild_id)``); a seasonal mod without its storage wired
    returns None — the panels degrade quietly, never crash.
    """
    cache = getattr(bot, "season_stacks", None)
    if cache is None:
        cache = {}
        bot.season_stacks = cache
    key = (mod, guild_id)
    if key in cache:
        return cache[key]
    from botforge.core.models.db import get_async_database

    mod_roles = getattr(bot, "mod_roles_service", None)
    registry = getattr(bot, "registry", None)
    definition = registry.get(mod) if registry is not None else None
    if definition is None:
        return None
    from botforge.core.services.mod_storage import ModStorage

    storage = ModStorage(get_async_database(), mod)
    from botforge.discord.wiring import build_games_service

    game_data = build_games_service()
    game_key = (getattr(definition, "required_games", ()) or ("",))[0]
    from botforge.core.ids import mod_scope

    scope = mod_scope(mod, game_key, guild_id)
    stack = build_mod_season_stack(
        mod=mod,
        guild_id=guild_id,
        game_key=game_key,
        database=ModStorageSeasonDatabase(storage._db, scope),
        game_data=game_data,
        season_roles=SeasonRolesService(mod_roles, mod) if mod_roles is not None else None,
        # the enrollment ALWAYS wires: no declared criteria = the queue
        # decides (the manual mode) — never "not wired" (the merlin
        # finding: Postuler refused because the declaration carries no
        # settings.enrollment)
        enrollment_criteria=(getattr(definition, "settings", None) or {}).get("enrollment") or {},
    )
    cache[key] = stack
    return stack


__all__ = ["ModStorageSeasonDatabase", "season_stack_for"]
