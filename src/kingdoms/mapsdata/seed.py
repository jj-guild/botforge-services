"""Create-or-enrich helpers for map entries (kingdoms-services#247).

``create_map_from_name`` implements the game-designer flow: given a map
name, try the Liquipedia provider first (public data + image); when the
page doesn't exist (or its image licence is incompatible), fall back to a
guild-local entry with admin-entered fields. The created entry is stored
in the catalog through the regular service, so forums and pools pick it
up like any other map.
"""

from __future__ import annotations

import logging
import os

# Transition re-exports: the PUBLIC util (kingdoms.core.wiki_names) is
# the home now — the private names stay importable while the callers
# migrate (removed with the in-process path's death).
from kingdoms.core.wiki_names import (  # noqa: F401
    DEFAULT_USER_AGENT_TEMPLATE,
)
from kingdoms.core.wiki_names import (
    extract_page_name as _extract_page_name,
)
from kingdoms.core.wiki_names import (
    title_variants as _title_variants,
)
from kingdoms.core.wiki_names import (
    wiki_user_agent as _user_agent,
)

logger = logging.getLogger("kingdoms.mapsdata")

class MapSeed:
    """The fields a provider resolves for one map name."""

    name: str
    description: str
    resource_url: str
    image_url: str
    icon_url: str = ""
    terrain: str = ""
    size: str = ""
    map_type: str = ""
    nomad: str = ""
    walls: str = ""
    tc: str = ""
    public: bool = True
    game_versions: tuple[str, ...] = ()
    versions: tuple[dict[str, object], ...] = ()
    tags: tuple[str, ...] = ()


class LiquipediaUnconfiguredError(RuntimeError):
    """Liquipedia access is not configured on this environment.

    Raised instead of returning None so the UI can tell the
    game designer "Liquipedia is disabled here" (missing
    PROVIDER_CONTACT) from "Liquipedia has no such page".
    """


async def fetch_map_seed(name: str) -> MapSeed | None:
    """Resolve one map name into a seed (the ext-liquipedia provider first).

    The provider process (ADR-0020) owns the Liquipedia access and its
    tables; when it is configured (``EXT_LIQUIPEDIA_URI``) the seed
    comes over the Content contract. Without it the legacy in-process
    path serves (transition): the UI behavior is identical.
    Returns None when Liquipedia doesn't know the page. Raises
    :class:`LiquipediaUnconfiguredError` on a configuration gap.
    """
    provider_uri = os.environ.get("EXT_LIQUIPEDIA_URI", "")
    if provider_uri:
        from kingdoms.core.rpc.content_client import ContentProviderClient

        client = ContentProviderClient(provider_uri)
        try:
            descriptor = await client.get_map_seed("aoe2", name)
        except Exception as exc:
            # The provider surfaces the open circuit in the gRPC details:
            # map it back so the callers see LIQUIPEDIA IS RATE-LIMITED,
            # not a generic failure (nor "map not found"). The DETAILS
            # carry the provider's clean message — str(exc) is the whole
            # AioRpcError dump and buried the message (the merlin import).
            details = getattr(exc, "details", None)
            message = str(details()) if callable(details) else str(exc)
            if "circuit" in message.lower():
                from kingdoms.mapsdata.liquipedia import LiquipediaCircuitOpenError

                raise LiquipediaCircuitOpenError(message) from exc
            raise
        if descriptor is None:
            return None
        return MapSeed(
            name=str(descriptor.get("name", name)),
            description=str(descriptor.get("description", "")),
            resource_url=str(descriptor.get("resource_url", "")),
            image_url=str(descriptor.get("image_url", "")),
            icon_url=str(descriptor.get("icon_url", "")),
            terrain=str(descriptor.get("terrain", "")),
            size=str(descriptor.get("size", "")),
            map_type=str(descriptor.get("map_type", "")),
            public=True,
        )
    user_agent = _user_agent()
    if not user_agent:
        logger.debug("liquipedia seed skipped: PROVIDER_CONTACT unset")
        raise LiquipediaUnconfiguredError("PROVIDER_CONTACT is not set")
    name = _extract_page_name(name)
    # The legacy path is a SYNCHRONOUS client: blocking HTTP plus the
    # API-terms rate-limit sleeps (a 30 s parse interval). Running it on
    # the event loop froze the bot's heartbeat during bulk imports —
    # it rides a worker thread instead.
    import asyncio

    return await asyncio.to_thread(_fetch_map_seed_liquipedia, user_agent, name)


def _fetch_map_seed_liquipedia(user_agent: str, name: str) -> MapSeed | None:
    """Resolve the seed in-process over the sync Liquipedia client (thread)."""
    from kingdoms.mapsdata.liquipedia import (
        LIQUIPEDIA_ATTRIBUTION,
        LiquipediaMapsProvider,
        MapLicenseError,
        query_tags,
    )

    provider = LiquipediaMapsProvider(user_agent)
    try:
        data = None
        for variant in _title_variants(name):
            try:
                data = provider.map_data(variant)
                break
            except RuntimeError:
                continue
        if data is None:
            return None
        return MapSeed(
            name=data.info.name,
            description=data.info.description,
            resource_url=data.info.source_url,
            image_url=data.image_url,
            icon_url=data.icon_url,
            terrain=data.info.terrain,
            nomad=data.info.nomad,
            walls=data.info.walls,
            tc=data.info.tc,
            size=data.info.size,
            map_type=data.info.map_type,
            public=True,
            game_versions=data.info.game_versions,
            versions=tuple(
                {"name": v.name, "description": v.description, "details": list(v.details)} for v in data.info.versions
            ),
            tags=query_tags(data.info),
        )
    except MapLicenseError:
        logger.info("liquipedia seed: image licence refused for %s", name)
        seed = MapSeed(
            name=name,
            description="",
            resource_url=LIQUIPEDIA_ATTRIBUTION + name.replace(" ", "_"),
            image_url="",
            public=True,
        )
        return seed
    except Exception:
        logger.info("liquipedia seed: no page for %s", name, exc_info=True)
        return None
    finally:
        provider.close()
