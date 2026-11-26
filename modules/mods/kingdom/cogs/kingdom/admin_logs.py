"""The mod's admin action log seam (T4a logs-admin, Drasah 25/11).

Every meaningful admin CLICK on the cockpit mutates the season, yet the
staff had NO trail: the journal idea reborn as 📜 logs — ONE salon, the
requests riding the same surface (the merge of T4a).

The template rule (#396 annonce-ready): a log line is ONE kind key +
an action text, everything else is DATA — the emoji rides the KINDS
table, the salon is the DECLARED channel key (admin_log) resolved by
``stored_channel_id`` (never by display name), the time rides the Paris
clock seam (``fmt_paris``, the players' own clock); the day the #396
announcement seam lands, ``log_admin_action_safe`` migrates to it as a
parameter without touching a single caller.

The trail is a COURTESY: a missing guild, an unresolved salon or a
refused send logs loudly and NEVER breaks the admin flow that fired it.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("kingdom.admin_logs")

MOD = "kingdom"
SCOPE = "mod/kingdom"

# One log kind = one row of data (the emoji is data, NEVER hand-picked at
# the call site — a new surface adds one row, zero code).
KIND_EMOJI: dict[str, str] = {
    "season": "⚙️",
    "regie": "🎚️",
    "time": "⏱️",
    "distributor": "🎁",
    "decision": "⚖️",
    "realm": "👑",
    "console": "🧹",
    # kingdom-report-v1 (Drasah 26/11) : le signalement joueur (Affaire 38)
    "report": "🚩",
}

# kinds the hue of the fallback when a call site forgets its own (never a
# crash, the log's job is to exist).
_FALLBACK_KIND = "decision"


def admin_log_line(kind: str, action: str, admin_id: str, moment: Any = None) -> str:
    """Compose one trail line: « [25/11 19:32] ⚖️ <@123> … ».

    The kind's emoji is DATA (the KINDS table above), the clock rides
    ``fmt_paris`` (the players' own Paris seam), an empty admin degrades
    to no mention, an unknown kind to the fallback emoji — never a raise.
    """
    from .common import fmt_paris

    emoji = KIND_EMOJI.get(str(kind or ""), KIND_EMOJI[_FALLBACK_KIND])
    admin = str(admin_id or "")
    mention = f"<@{admin}>" if admin.isdigit() else ""
    stamp = fmt_paris(float(moment) if moment is not None else time.time())
    parts = (f"[{stamp}]", emoji, mention, str(action or "").strip())
    return " ".join(part for part in parts if part)


async def log_admin_action_safe(
    bot: Any, guild_id: str, kind: str, action: str, admin_id: str
) -> bool:
    """Post one admin action line in 📜 logs (best-effort, never raises).

    Returns True when the line flew. The salon is the DECLARED
    channel key admin_log resolved by its STORED id — the provisioning
    owns the resolution, a miss (virgin guild, unwired Mongo) skips
    quietly instead of guessing a name.
    """
    line = admin_log_line(kind, action, admin_id)
    guild = getattr(bot, "get_guild", lambda _id: None)(
        int(guild_id) if str(guild_id).isdigit() else None
    )
    if guild is None:
        logger.debug("kingdom admin logs: no guild %s, %r skipped", guild_id, kind)
        return False
    try:
        from botforge.discord.ui.panels_provisioning import stored_channel_id

        channel_id = await stored_channel_id(str(guild_id), SCOPE, "admin_log")
    except Exception:  # noqa: BLE001 — an unreadable store skips the line
        channel_id = ""
    channel = (
        getattr(guild, "get_channel", lambda _id: None)(int(str(channel_id)))
        if str(channel_id or "").isdigit()
        else None
    )
    if channel is None or not hasattr(channel, "send"):
        logger.warning(
            "kingdom admin logs: salon admin_log not found (guild %s)", guild_id
        )
        return False
    import discord

    try:
        await channel.send(
            content=line,
            allowed_mentions=discord.AllowedMentions(
                users=False, roles=False, everyone=False
            ),
            silent=True,
        )
        return True
    except Exception:  # noqa: BLE001 — a trail never blocks the admin flow
        logger.warning("kingdom admin logs: post failed (%r)", kind, exc_info=True)
        return False


async def log_admin_action_on_interaction(interaction: Any, kind: str, action: str) -> None:
    """One-liner for the ephemeral windows: the trail of THIS admin.

    Fully defensive: a partial interaction (a test fake, a cold wire)
    degrades to a skipped line — the trail is a courtesy, NEVER a
    raise on the admin flow that fired it.
    """
    try:
        client = getattr(interaction, "client", None)
        user = getattr(getattr(interaction, "user", None), "id", "")
        guild_id = str(getattr(interaction, "guild_id", "") or "")
        await log_admin_action_safe(client, guild_id, kind, action, str(user or ""))
    except Exception:  # noqa: BLE001 — the trail never breaks the click
        logger.warning("kingdom admin logs: interaction trail failed", exc_info=True)


__all__ = ["KIND_EMOJI", "admin_log_line", "log_admin_action_on_interaction", "log_admin_action_safe"]
