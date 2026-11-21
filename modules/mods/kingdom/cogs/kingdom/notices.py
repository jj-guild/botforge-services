"""The mod's parametrable admin notices (demande-inscription-saison,
Drasah 21/11).

The Roi clicks « S'inscrire à la saison » and the staff learns NOTHING:
the Admission drawer counts the pendings, but a counter never PREVIEWS
itself. The designer's fix: a short notice lands in 📬 demandes with a
Kingdom Admin ping attached.

The template rule (#396 annonce-ready): a notice is ONE kind key +
params, everything else is DATA — the salon (declared channel key),
the pinged role (declared role key) and the text (conf/locales, fr/en)
live in the ``NOTICES`` table and the yaml catalog, never in a
hand-rolled send. A future announcement surface (or another request
kind) reuses ``post_notice`` with a new kind + a new strings key; the
day the #396 announcement seam lands, this table migrates to it as
parameters without touching a single caller.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("kingdom.notices")

MOD = "kingdom"
SCOPE = "mod/kingdom"

# One notice kind = one row of data. channel: the declared channel key
# (conf/mod.yaml) ; role: the declared role key to ping (None = no ping).
NOTICES: dict[str, dict[str, str | None]] = {
    "season_entry_request": {"channel": "requests", "role": "kingdom_admin"},
}

# the catalog section that renders every notice's text (fr/en, .format params)
SECTION = "kingdom.notices"


async def _admin_role_id(bot: Any, guild_id: str) -> str:
    """The declared admin role's live id (« » when unresolvable)."""
    roles_service = getattr(bot, "mod_roles_service", None)
    if roles_service is None:
        return ""
    try:
        from .conscription_gate import _role_id

        rid = await _role_id(bot, guild_id, "kingdom_admin")
    except Exception:  # noqa: BLE001 — the ping degrades to no ping, never a raise
        return ""
    return str(rid or "")


async def post_notice(
    bot: Any, guild_id: str, kind: str, params: dict[str, Any], locale: str = "fr"
) -> bool:
    """Post one admin notice in its declared salon (best-effort).

    Returns True when the notice flew. Never raises: a notice is a
    courtesy, a failed one logs loudly instead of breaking the flow
    that triggered it.
    """
    spec = NOTICES.get(kind)
    if spec is None:
        logger.warning("kingdom notices: unknown kind %r", kind)
        return False
    channel_key = str(spec["channel"] or "")
    guild = getattr(bot, "get_guild", lambda _id: None)(
        int(guild_id) if str(guild_id).isdigit() else None
    )
    if guild is None:
        logger.debug("kingdom notices: no guild %s, notice %r skipped", guild_id, kind)
        return False
    try:
        from botforge.discord.ui.panels_provisioning import stored_channel_id

        channel_id = await stored_channel_id(str(guild_id), SCOPE, channel_key)
    except Exception:  # noqa: BLE001 — an unreadable store skips the notice
        channel_id = ""
    channel = (
        getattr(guild, "get_channel", lambda _id: None)(int(channel_id))
        if str(channel_id or "").isdigit()
        else None
    )
    if channel is None or not hasattr(channel, "send"):
        logger.warning(
            "kingdom notices: salon %r not found for %r (guild %s)", channel_key, kind, guild_id
        )
        return False
    try:
        from .common import mod_catalog

        text = str(mod_catalog().section(SECTION, locale)[kind]).format(**params)
    except Exception:  # noqa: BLE001 — the catalog degrades to the key itself
        logger.warning("kingdom notices: no text for %r (%s)", kind, locale, exc_info=True)
        text = str(kind)
    import discord

    role_id = await _admin_role_id(bot, str(guild_id))
    ping = f"<@&{role_id}> " if str(role_id or "").isdigit() else ""
    try:
        await channel.send(
            content=f"{ping}{text}",
            allowed_mentions=discord.AllowedMentions(
                roles=bool(ping), users=False, everyone=False
            ),
            silent=True,
        )
        return True
    except Exception:  # noqa: BLE001 — posted best-effort, never a blocker
        logger.warning("kingdom notices: post failed (%r)", kind, exc_info=True)
        return False


async def announce_season_entry_request(
    bot: Any, guild_id: str, realm: Any, locale: str = "fr"
) -> bool:
    """« un royaume demande » — the staff notice of a season entry ask."""
    from .common import fmt_paris

    return await post_notice(
        bot,
        guild_id,
        "season_entry_request",
        {
            "realm": str(getattr(realm, "name", "?")),
            "king": str(getattr(realm, "king_name", getattr(realm, "king_id", "?"))),
            "when": fmt_paris(time.time()),
        },
        locale,
    )


__all__ = ["NOTICES", "announce_season_entry_request", "post_notice"]
