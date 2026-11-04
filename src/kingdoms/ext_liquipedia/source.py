"""ext-liquipedia source: Liquipedia access + the provider's own tables.

The ``LiquipediaMapsProvider`` (moved from ``kingdoms.mapsdata``)
carries the MediaWiki access with its terms-of-use compliance (custom
User-Agent, rate limits, licence guard). This module wraps it with the
provider's persistence: every fetched page is stored raw in Mongo
(``liquipedia_pages``, cache-aside with a TTL) and every resolved map
descriptor in ``liquipedia_maps`` — the raw data lives at the provider,
debuggable and replayable, and a repeated import never re-requests a
fresh page while the cache holds.

The in-memory cache of the underlying provider stays (the process
lifetime); Mongo adds the cross-restart durability the in-process
module never had.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from kingdoms.core.upstream_stats import StatsRegistry
from kingdoms.ext_liquipedia import (
    GAME_WIKIS,
    MAPS_COLLECTION,
    PAGE_CACHE_TTL_S,
    PAGES_COLLECTION,
)
from kingdoms.mapsdata.liquipedia import (
    LiquipediaMapsProvider,
    MapLicenseError,
)

logger = logging.getLogger("kingdoms.ext_liquipedia")


# The process-wide upstream call stats — served over the Status
# contract (GetUpstreamStats); the providers panel reads them on demand.
STATS = StatsRegistry()


class LiquipediaSource:
    """The Content source: Liquipedia access + Mongo-backed cache."""

    def __init__(self, providers: dict[str, LiquipediaMapsProvider], database: Any) -> None:
        """Wire the per-wiki upstream access and the provider's own database.

        The source is game-AGNOSTIC: ``providers`` maps a wiki family
        (one HTTP endpoint each, the pacing clock stays shared process-
        wide); the game_key of the request picks the wiki. It never
        knows who consumes it.
        """
        self._providers = providers
        self._db = database

    def faction_keys(self) -> list[str]:
        """Liquipedia serves maps, not factions — the contract degrades."""
        return []

    def faction_content(self, key: str, locale: str) -> dict[str, Any] | None:
        """No faction content on this source."""
        return None

    def map_content(self, key: str, locale: str, game_key: str = "aoe2") -> dict[str, Any] | None:
        """Serve one map's localized content (name + attribution link)."""
        seed = self.map_seed(game_key, key)
        if seed is None:
            return None
        return {
            "entity_id": f"map:{game_key}:{key}",
            "locale": locale or "en",
            "name": str(seed.get("name", key)),
            "summary": str(seed.get("description", "")),
            "source_url": str(seed.get("resource_url", "")),
            "found": True,
        }

    def map_seed(self, game_key: str, map_key: str) -> dict[str, Any] | None:
        """Resolve one map name into its full descriptor.

        The persisted descriptor serves first (cache-aside); a miss
        fetches the page upstream, persists raw + descriptor, then
        answers. A page absent upstream answers None (the caller
        falls back to admin-entered fields).
        """
        from kingdoms.mapsdata.seed import _extract_page_name, _title_variants

        name = _extract_page_name(map_key)
        cached = self._load_descriptor(game_key, name)
        if cached is not None:
            return cached
        provider = self._providers.get(game_key)
        if provider is None:
            return None  # no wiki declared for this game: nothing to serve
        for variant in _title_variants(name):
            try:
                with STATS.register(f"liquipedia:{game_key}"):
                    data = provider.map_data(variant)
            except MapLicenseError:
                raise
            except RuntimeError:
                continue
            descriptor = _descriptor_of(game_key, variant, data)
            self._persist(game_key, variant, data, descriptor)
            return descriptor
        return None

    def _load_descriptor(self, game_key: str, name: str) -> dict[str, Any] | None:
        """Read the freshest persisted descriptor within the page TTL."""
        try:
            doc = self._db[MAPS_COLLECTION].find_one(
                {"game_key": game_key, "$or": [{"name": name}, {"page": name.replace(" ", "_")}]}
            )
        except Exception:
            return None
        if not doc:
            return None
        if time.time() - float(doc.get("fetched_at", 0)) > PAGE_CACHE_TTL_S:
            return None
        return dict(doc.get("descriptor") or {}) or None

    def _persist(
        self, game_key: str, page: str, data: Any, descriptor: dict[str, Any]
    ) -> None:
        """Store the raw page data and the resolved descriptor."""
        now = time.time()
        try:
            self._db[PAGES_COLLECTION].update_one(
                {"_id": f"{game_key}:{page}"},
                {"$set": {"game_key": game_key, "page": page, "fetched_at": now}},
                upsert=True,
            )
            self._db[MAPS_COLLECTION].update_one(
                {"_id": f"{game_key}:{page}"},
                {
                    "$set": {
                        "game_key": game_key,
                        "page": page,
                        "name": str(data.info.name),
                        "image_url": str(data.image_url),
                        "icon_url": str(data.icon_url),
                        "terrain": str(data.info.terrain),
                        "size": str(data.info.size),
                        "map_type": str(data.info.map_type),
                        "licence_ok": True,
                        "fetched_at": now,
                        "descriptor": descriptor,
                    }
                },
                upsert=True,
            )
        except Exception:
            logger.warning("liquipedia persist failed (page %s) — best-effort", page, exc_info=True)


def _descriptor_of(game_key: str, page: str, data: Any) -> dict[str, Any]:
    """Flatten one MapData into the wire-shaped descriptor dict."""
    return {
        "name": str(data.info.name),
        "description": str(data.info.description),
        "resource_url": str(data.info.source_url),
        "image_url": str(data.image_url),
        "icon_url": str(data.icon_url),
        "terrain": str(data.info.terrain),
        "size": str(data.info.size),
        "map_type": str(data.info.map_type),
        "licence_ok": True,
        "licence_note": "",
    }


def resolve_source(database: Any) -> LiquipediaSource:
    """Build the source from the environment (PROVIDER_CONTACT)."""
    from kingdoms.mapsdata.seed import _user_agent

    user_agent = _user_agent()
    if not user_agent:
        raise RuntimeError(
            "PROVIDER_CONTACT is not set — the Liquipedia terms of use "
            "require an identified User-Agent (https://liquipedia.net/api-terms-of-use)"
        )
    providers = {
        game: LiquipediaMapsProvider(user_agent, api_url=f"https://liquipedia.net/{wiki}/api.php")
        for game, wiki in GAME_WIKIS.items()
    }
    return LiquipediaSource(providers, database)
