"""Discord-side adapters for the registration stack (botforge-services#133).

Production wiring of the RegistrationService seams: the Mongo adapter
for the game-side profile bindings, and the AoE2 profile-validation
seam — a profile id is valid when the provider (ext-librematch via the
botforge.v1.Game contract) can resolve its stats.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx

from botforge.core.services.registration import (
    PROFILE_BINDINGS_COLLECTION,
)

INSIGHTS_BASE_URL = "https://www.aoe2insights.com"
# The browser-compatible fallback UA (the plain-text relic-id endpoint
# 403s some datacenter requests — the live #402 finding; the retry keeps
# naming the project, never the library default).
_BROWSER_COMPATIBLE_UA = (
    "Mozilla/5.0 (compatible; botforge-bot/1.0; +https://github.com/jj-guild/botforge)"
)
# The relic-keyed insights URL shape: /user/relic/<relic_id>. Every
# OTHER /user/<id> shape carries the site's OWN id — the insights user
# id, which differs from the relic id (#402): it must resolve through
# the relic-id page, never validate as-is.
INSIGHTS_RELIC_URL_RE = re.compile(
    r"^https?://(?:www\.)?aoe2insights\.com/user/relic/(\d{1,15})(?:[/?#].*)?$",
    re.IGNORECASE,
)
INSIGHTS_URL_RE = re.compile(
    r"aoe2insights\.com/user/(?!relic/)(\d{1,15})(?!\d)", re.IGNORECASE
)
_NUMERIC_ID_RE = re.compile(r"^\d{1,15}$")
# Resolve outcomes (resolve_relic_id_outcome): the binding decision needs
# the REASON a resolution failed — a profile the site never heard of and a
# site that REFUSES this server (the Cloudflare bot filter) are different
# failures, and only the blocked one must guide the player elsewhere.
RELIC_RESOLVED = "resolved"
RELIC_BLOCKED = "blocked"
RELIC_UNKNOWN = "unknown"
RELIC_UNREACHABLE = "unreachable"
# The insights id may hide anywhere in a longer pasted URL (a profile
# deep link, a query, a fragment) — the id itself is the only thing we
# keep, and it never leaves the regex's capture group.
_INSIGHTS_HOSTS = ("aoe2insights.com", "www.aoe2insights.com")
def extract_insights_user_id(typed: str) -> str | None:
    """Extract the aoe2insights user id from a pasted URL, resiliently.

    The pasted URL may be LONGER than the canonical profile page (a deep
    link, a trailing path, a query, a fragment) — the insights id is the
    ``/user/<digits>`` segment and that is ALL we keep (#402: store the
    insights id, resolve the relic id). Double gate: the host is checked
    on the parsed URL, the id never leaves the regex's capture group —
    the downstream request URL cannot be tampered with. The relic-keyed
    shape (``/user/relic/<id>``) does NOT match: its id is a relic id.
    """
    from urllib.parse import urlparse

    parsed = urlparse(typed.strip())
    if parsed.scheme not in ("http", "https") or parsed.netloc.lower() not in _INSIGHTS_HOSTS:
        return None
    match = INSIGHTS_URL_RE.search(typed)
    if match is None:
        return None
    return match.group(1)


async def resolve_relic_id_outcome(
    typed_id: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[str | None, str]:
    """Resolve whatever id the user typed into ``(relic_id, outcome)``.

    See :func:`resolve_relic_id` for the resolution contract; this is the
    seam that carries WHY a resolution failed:

    - ``resolved`` — the site answered the relic id in plain text;
    - ``blocked`` — the site refuses this server (its bot filter):
      the id is NOT trusted as a relic id, the binding refuses and the
      player is guided to the relic-keyed URL shape instead;
    - ``unknown`` — the site answered and this id maps to nothing;
    - ``unreachable`` — network-level failure.

    The live 2026-11-17 finding drives the ``blocked`` distinction: the
    relic-id endpoint sits behind a Cloudflare JavaScript challenge
    ("Just a moment...") on datacenter egress — NO User-Agent passes,
    not even a browser-compatible one, and a TLS-impersonating client
    fares no better. The un-distinguishable failure previously fed the
    silent typed-id-as-relic fallback, which bound the WRONG profile
    (an insights id that happens to be someone else's relic id) — the
    binding must fail loudly instead.
    """
    typed = typed_id.strip()
    if not typed or len(typed) > 200:
        return None, RELIC_UNKNOWN
    url_id = extract_insights_user_id(typed)
    if url_id is not None:
        typed = url_id
    elif not _NUMERIC_ID_RE.fullmatch(typed):
        return None, RELIC_UNKNOWN
    return await _relic_id_from_text_endpoint(typed, transport)


async def resolve_relic_id(
    typed_id: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str | None:
    """Resolve whatever id the user typed into the relic profile id.

    Returns the relic id, or None when nothing resolves (unknown id,
    insights down, or the site's bot filter refusing this server —
    :func:`resolve_relic_id_outcome` tells them apart).
    """
    relic_id, _ = await resolve_relic_id_outcome(typed_id, transport)
    return relic_id


async def _relic_id_from_text_endpoint(
    insights_id: str, transport: httpx.AsyncBaseTransport | None
) -> tuple[str | None, str]:
    """Read the relic id from the plain-text ``/relic-id/`` endpoint.

    The identified User-Agent first (repo rule #277); a 403 (the live
    finding: the endpoint's bot filter) retries once with a
    browser-compatible UA. Nothing else is read — the profile pages
    are never scraped.

    Injection safety: the request URL is built ONLY from a
    regex-validated digit string (<= 15 chars); the plain-text reply must
    be a bare numeric id — any HTML, extra text or mismatch is rejected.

    Returns ``(relic_id, outcome)``; a 403 that survives the UA retry is
    the bot filter (``blocked``) — logged at warning so /logs shows why
    a binding guided the player to the relic-keyed URL shape.
    """
    from botforge.core.upstream_identity import project_user_agent

    url = f"{INSIGHTS_BASE_URL}/user/{insights_id}/relic-id/"
    for user_agent in (project_user_agent(), _BROWSER_COMPATIBLE_UA):
        try:
            async with httpx.AsyncClient(
                timeout=10, follow_redirects=True, transport=transport
            ) as client:
                reply = await client.get(url, headers={"User-Agent": user_agent})
        except Exception:
            logging.getLogger("botforge.registration.seam").warning(
                "INSIGHTS relic-id resolve failed (id %s)", insights_id, exc_info=True
            )
            return None, RELIC_UNREACHABLE
        if reply.status_code == 200:
            text = reply.text.strip()
            if _NUMERIC_ID_RE.fullmatch(text) and text != insights_id:
                return text, RELIC_RESOLVED
            return None, RELIC_UNKNOWN
        if reply.status_code != 403:
            return None, RELIC_UNKNOWN
    logging.getLogger("botforge.registration.seam").warning(
        "INSIGHTS relic-id endpoint blocked this server (id %s, 403 on both user agents)",
        insights_id,
    )
    return None, RELIC_BLOCKED


def _blocked_filter_error() -> Exception:
    """Build the player-facing refusal for a bot-filtered resolution."""
    from botforge.core.services.registration import InvalidProfileError

    return InvalidProfileError(
        "aoe2insights blocks this server's requests, so the relic id cannot be "
        "resolved automatically (bot filter, 403). Paste the /user/relic/<id>/ "
        "form of your insights URL or your Relic ID (the 'Relic ID' shown on "
        "your insights profile) (#402)"
    )


class MongoRegistrationDatabase:
    """Async MongoDB adapter for the RegistrationService persistence seam."""

    def __init__(self, database: Any) -> None:
        """Wrap an async MongoDB database (``get_async_database``)."""
        self._database = database

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

        The profile is addressable by EITHER id (#402): the relic id
        the provider validated, or the aoe2insights user id the player
        pasted — the binding stores both.
        """
        doc = await self._database[PROFILE_BINDINGS_COLLECTION].find_one(
            {"game_key": game_key, "profile_id": profile_id}
        )
        if doc is None:
            # the insights user id addresses the same binding (#402)
            doc = await self._database[PROFILE_BINDINGS_COLLECTION].find_one(
                {"game_key": game_key, "profile.site_ids.aoe2insights": profile_id}
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
        bindings = {str(doc.get("profile_id", "")): dict(doc) async for doc in cursor}
        missing = [pid for pid in profile_ids if str(pid) not in bindings]
        if missing:
            # the insights user ids address the same bindings (#402)
            cursor = self._database["profile_bindings"].find(
                {
                    "game_key": game_key,
                    "profile.site_ids.aoe2insights": {"$in": [str(p) for p in missing]},
                }
            )
            async for doc in cursor:
                bindings[str(doc.get("profile_id", ""))] = dict(doc)
        return list(bindings.values())

    async def list_bindings_for_game(self, game_key: str) -> list[dict[str, Any]]:
        """List every profile binding of a game (live dashboard reuse, #147)."""
        cursor = self._database[PROFILE_BINDINGS_COLLECTION].find({"game_key": game_key})
        return [dict(doc) async for doc in cursor]


def _site_of(site_key: str) -> Any:
    """Return one declared site by key (the registry lookup)."""
    from botforge.core.services.profile_sites import profile_sites_registry

    return profile_sites_registry().site("aoe2", site_key)


class ProviderStatsUnavailableError(RuntimeError):
    """The provider declares no player-stats capability (configuration gap)."""


class Aoe2ProfileValidationSeam:
    """AoE2 profile validation through the provider (botforge.v1.Game).

    A profile id is valid when the configured provider can resolve its
    stats. With no provider URI (local runs), every id is rejected —
    validation is the whole point of the binding (reference §0/§6).
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

        The typed id may be either the relic id (what the provider wants)
        or the aoe2insights user id (what the user pastes). The provider
        is tried first; on a miss, the insights resolver maps the typed
        id to the relic id and the validation retries \u2014 the binding
        always stores the relic id.
        """
        from botforge.game_aoe2.client import GameDataClient

        client = GameDataClient(self._provider_uri)
        capabilities = await client.get_capabilities()
        if not capabilities.player_stats:
            raise ProviderStatsUnavailableError(
                "ext-librematch ne sert pas les stats de profil "
                "(provider mal configur\u00e9 ou injoignable \u2014 vois les logs du bot)"
            )
        typed = profile_id.strip()
        # Any known site's URL parses through the profile-sites registry:
        # a relic-keyed site (aoe2.GG, ageofempires.com) carries the relic
        # id directly — no resolution needed. The insights URL is the
        # #402 trap: only /user/relic/<id> carries the relic id; every
        # other /user/<id> carries the site's OWN id — resolve it, then
        # keep BOTH ids on the binding so the player is addressable by
        # either one.
        from botforge.core.services.profile_sites import ID_KIND_RELIC, parse_profile_url

        parsed = parse_profile_url("aoe2", typed)
        if parsed is not None:
            site_key, site_id = parsed
            site = _site_of(site_key)
            if site is not None and site.id_kind == ID_KIND_RELIC:
                if site_key == "aoe2insights" and not INSIGHTS_RELIC_URL_RE.match(typed):
                    # a longer insights URL: the resilient extractor reads
                    # the id wherever it sits (#402)
                    url_id = extract_insights_user_id(typed) or site_id
                    return await self._resolve_insights(client, url_id)
                return await self._validate_with_client(client, site_id)
        if extract_insights_user_id(typed) is not None:
            url_id = extract_insights_user_id(typed) or ""
            return await self._resolve_insights(client, url_id)
        # A plain id: try the provider first (a relic id validates directly),
        # then resolve through insights (the user typed the insights id).
        validated = await self._validate_with_client(client, typed)
        if validated is not None:
            return validated
        relic_id, outcome = await resolve_relic_id_outcome(typed)
        if outcome in (RELIC_BLOCKED, RELIC_UNREACHABLE):
            raise _blocked_filter_error()
        if relic_id is None:
            return None
        validated = await self._validate_with_client(client, relic_id)
        if validated is not None:
            validated["site_ids"] = {"aoe2insights": typed}
        return validated

    async def _resolve_insights(self, client: Any, insights_id: str) -> dict[str, Any] | None:
        """Resolve an insights user id into the relic id, keeping both.

        The insights id is what the player pastes; the relic id is what
        the provider validates (#402). The binding stores both, so a
        lookup by EITHER id resolves to the same player.

        When the site refuses this server (the Cloudflare bot filter on
        datacenter egress — the live 2026-11-17 finding), the binding
        REFUSES with guidance to the relic-keyed URL shape. The old
        fallback (trust the typed id as a relic id) silently bound the
        WRONG player whenever the ids differ — the typed number is
        sometimes someone else's relic id, and nothing distinguishes
        the two cases without the site's answer.
        """
        relic_id, outcome = await resolve_relic_id_outcome(insights_id)
        if relic_id is None:
            if outcome in (RELIC_BLOCKED, RELIC_UNREACHABLE):
                raise _blocked_filter_error()
            return None
        validated = await self._validate_with_client(client, relic_id)
        if validated is None:
            return None
        validated["site_ids"] = {"aoe2insights": insights_id}
        return validated
    async def search_profiles(self, alias: str) -> list[dict[str, Any]]:
        """Search the provider's profiles by in-game alias (#402's name path).

        The Cloudflare finding forced a resolution path that never
        touches aoe2insights: the provider's own upstream (World's
        Edge) answers exact-alias lookups, so the player types their
        in-game name and picks their account among the homonyms. The
        candidates carry their last matches — the player recognizes
        what THEY played, not an id. Degrades to an empty list.
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

    @staticmethod
    async def _validate_with_client(client: Any, profile_id: str) -> dict[str, Any] | None:
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
            "profile_id": profile_id,
            "profile_name": aliases[0] if aliases else "",
            "aliases": aliases[:5],
        }
