"""Discord-side adapters for the registration stack (botforge-services#133).

Production wiring of the RegistrationService seams: the Mongo adapter
for the game-side profile bindings, and the AoE2 profile-validation
seam \u2014 a profile id is valid when the provider (ext-librematch via the
botforge.v1.Game contract) can resolve its stats.

Account identification (owner direction 2026-11-20): the player binds
by their IN-GAME NAME (the alias search answers homonym candidates
with clan/country/Elo to pick from) or their RELIC ID. The aoe2insights
user-id resolution is GONE \u2014 the site blocks this server's egress with
a Cloudflare filter, no id-resolution path survives; the player-facing
doc explains how to copy the Relic ID from under their avatar
(docs/DEVELOPMENT/PLAYER-FLOWS \u2192 aoe2 Relic ID).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from botforge.core.services.registration import (
    PROFILE_BINDINGS_COLLECTION,
)

_NUMERIC_ID_RE = re.compile(r"^\d{1,15}$")

#: the legacy aoe2insights user ids the #402 resolution used to store;
#: no read path depends on them anymore, the field is scrubbed from
#: the stored bindings (the owner's 2026-11-20 purge).
LEGACY_INSIGHTS_FIELD = "profile.site_ids.aoe2insights"


def _insights_guidance_error() -> Exception:
    """Build the player-facing note for an aoe2insights paste."""
    from botforge.core.services.registration import InvalidProfileError

    return InvalidProfileError(
        "aoe2insights urls are not accepted anymore (the site blocks us): paste your "
        "in-game name, or your Relic ID \u2014 on aoe2insights it sits under your avatar, "
        "click it once and copy (#402)"
    )


class MongoRegistrationDatabase:
    """Async MongoDB adapter for the RegistrationService persistence seam."""

    def __init__(self, database: Any) -> None:
        """Wrap an async MongoDB database (``get_async_database``)."""
        self._database = database

    async def scrub_legacy_insights_ids(self) -> int:
        """Remove the legacy insights id field from every binding.

        One sweep at boot (best-effort): the #402 resolution used to
        store ``profile.site_ids.aoe2insights`` on every binding \u2014 the
        resolution path is gone, the field must not survive it. Returns
        the number of modified documents.
        """
        try:
            result = await self._database[PROFILE_BINDINGS_COLLECTION].update_many(
                {LEGACY_INSIGHTS_FIELD: {"$exists": True}},
                {"$unset": {LEGACY_INSIGHTS_FIELD: ""}},
            )
        except Exception:
            logging.getLogger("botforge.registration.seam").warning(
                "the legacy insights id scrub failed", exc_info=True
            )
            return 0
        if result.modified_count:
            logging.getLogger("botforge.registration.seam").info(
                "scrubbed the legacy insights id from %s binding(s)",
                result.modified_count,
            )
        return int(result.modified_count)

    async def upsert_entry(self, collection: str, document: dict[str, Any]) -> None:
        """Insert or replace one document by ``_id``."""
        await self._database[collection].replace_one({"_id": document["_id"]}, document, upsert=True)

    async def find_entry(self, collection: str, entry_id: str) -> dict[str, Any] | None:
        """Return one document by ``_id``; None when absent."""
        doc = await self._database[collection].find_one({"_id": entry_id})
        return dict(doc) if doc is not None else None

    async def find_user_bindings(self, user_id: str) -> list[dict[str, Any]]:
        """List the game-profile bindings of a user (all games)."""
        cursor = self._database[PROFILE_BINDINGS_COLLECTION].find({"user_id": user_id})
        return [dict(doc) async for doc in cursor]

    async def find_binding_by_profile(self, game_key: str, profile_id: str) -> dict[str, Any] | None:
        """Return the binding owning a profile; None when unbound.

        The profile is addressed by its relic id \u2014 the canonical id the
        provider validated at binding time.
        """
        doc = await self._database[PROFILE_BINDINGS_COLLECTION].find_one(
            {"game_key": game_key, "profile_id": profile_id}
        )
        return dict(doc) if doc is not None else None

    async def delete_binding(self, game_key: str, user_id: str, profile_id: str) -> bool:
        """Drop one profile binding; True when one existed."""
        result = await self._database[PROFILE_BINDINGS_COLLECTION].delete_one(
            {"_id": f"binding:{game_key}:{user_id}:{profile_id}"}
        )
        return bool(result.deleted_count > 0)

    async def find_bindings_by_profiles(
        self, game_key: str, profile_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Read many profiles' bindings in ONE batched find($in)."""
        if not profile_ids:
            return []
        cursor = self._database["profile_bindings"].find(
            {"game_key": game_key, "profile_id": {"$in": list(profile_ids)}}
        )
        return [dict(doc) async for doc in cursor]

    async def list_bindings_for_game(self, game_key: str) -> list[dict[str, Any]]:
        """List every profile binding of a game (live dashboard reuse, #147)."""
        cursor = self._database[PROFILE_BINDINGS_COLLECTION].find({"game_key": game_key})
        return [dict(doc) async for doc in cursor]


class ProviderStatsUnavailableError(RuntimeError):
    """The provider declares no player-stats capability (configuration gap)."""


class Aoe2ProfileValidationSeam:
    """AoE2 profile validation through the provider (botforge.v1.Game).

    A profile id is valid when the configured provider can resolve its
    stats. With no provider URI (local runs), every id is rejected \u2014
    validation is the whole point of the binding (reference \u00a70/\u00a76).
    """

    DEFAULT_PROVIDER_URI = "botforge-game-aoe2:50071"

    def __init__(self, provider_uri: str | None = None) -> None:
        """Read the provider address from the environment by default.

        The docker-network default (botforge-ext-librematch:50061) stands
        in when the environment declares no URI: the compose network
        always carries the provider, and an empty URI made the seam
        reject every profile silently (the 2026-10-16 test findings).
        """
        self._provider_uri = (
            provider_uri or os.environ.get("GAME_AOE2_URI", "") or self.DEFAULT_PROVIDER_URI
        )
        logging.getLogger("botforge.registration.seam").info(
            "AOE2 PROFILE SEAM provider_uri=%s", self._provider_uri
        )

    async def validate_profile(self, profile_id: str) -> dict[str, Any] | None:
        """Return the profile's public data when the provider knows it.

        Two inputs identify a player (owner direction 2026-11-20): a
        bare RELIC ID, or a relic-keyed URL of any known site whose ids
        ARE relic ids (aoe2.gg, ageofempires.com \u2014 no resolution
        needed, the site path's id validates as-is). The in-game NAME
        never reaches this seam (the alias search and its candidate
        picker run before, in the add-account flow); an aoe2insights
        url is refused with the copy-your-Relic-ID guidance.
        """
        from botforge.core.services.profile_sites import ID_KIND_RELIC, parse_profile_url
        from botforge.game_aoe2.client import GameDataClient

        client = GameDataClient(self._provider_uri)
        capabilities = await client.get_capabilities()
        if not capabilities.player_stats:
            raise ProviderStatsUnavailableError(
                "ext-librematch ne sert pas les stats de profil "
                "(provider mal configur\u00e9 ou injoignable \u2014 vois les logs du bot)"
            )
        typed = profile_id.strip()
        if "aoe2insights.com" in typed.lower():
            raise _insights_guidance_error()
        parsed = parse_profile_url("aoe2", typed)
        if parsed is not None:
            site_key, site_id = parsed
            from botforge.core.services.profile_sites import profile_sites_registry

            site = profile_sites_registry().site("aoe2", site_key)
            if site is not None and site.id_kind == ID_KIND_RELIC:
                return await self._validate_with_client(client, site_id)
            raise _insights_guidance_error()
        if not _NUMERIC_ID_RE.fullmatch(typed):
            return None
        return await self._validate_with_client(client, typed)

    async def search_profiles(self, alias: str) -> list[dict[str, Any]]:
        """Search the provider's profiles by in-game alias (#402's name path).

        The player types their in-game name and picks their account
        among the homonyms — the candidates carry their last matches,
        so the player recognizes what THEY played. Degrades to [].
        """
        from botforge.game_aoe2.client import GameDataClient

        typed = alias.strip()
        if not typed or len(typed) > 64:
            return []
        try:
            client = GameDataClient(self._provider_uri)
            return await client.search_profiles(typed)
        except Exception:
            logging.getLogger("botforge.registration.seam").warning(
                "PROFILE SEARCH failed (alias %s)", typed, exc_info=True
            )
            return []

    async def _validate_with_client(self, client: Any, profile_id: str) -> dict[str, Any] | None:
        """Validate one relic id against the running provider."""
        stats = await client.get_player_stats(profile_id)
        if stats is None:
            return None
        entries = [e for b in stats.blocks for e in b.entries]
        aliases = [e.value for e in entries if e.key == "alias"]
        if not aliases:
            aliases = [e.value for e in entries][:5]
        # the profile name rides the binding (owner direction): the stored
        # name of each profile id, so every link renders it without a
        # provider round-trip
        return {
            "profile_id": str(profile_id),
            "profile_name": aliases[0] if aliases else "",
            "aliases": aliases[:5],
        }
