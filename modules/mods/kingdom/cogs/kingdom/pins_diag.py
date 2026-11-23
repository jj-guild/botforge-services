"""The admin pin diagnosis (epic #412 T1, the kingdom-tests regression).

The platform's pin-ensure cycle is best-effort by design — when a
panel silently misses its salon (the ⚙️ Paramètres regression), the
WHY lives in the runner logs, unreachable for the mod's owner. This
module reads the SAME signals the ensure cycle itself reads (the
stored salon resolution, the guild channel cache, the pin message
registry) through the platform's PUBLIC seams only, and renders one
French line per pinned surface. The delivery is the /kingdom slash:
an ephemeral followup for admins (the silent ``is_admin`` guard —
never the deny-messaging one, the status card stays untouched for
players). #221 discipline: the whole feature lives in the mod, the
platform contracts stay untouched.
"""

from __future__ import annotations

import logging
from typing import Any

import discord

logger = logging.getLogger("kingdom.pins_diag")

_MOD_SCOPE = "mod/kingdom"


async def pins_report(client: discord.Client, guild_id: str) -> list[tuple[str, str]]:
    """(view key, human status) for every kingdom pinned surface, sorted.

    The status names the failing step in plain French — the moderator
    reads a diagnosis, not a stack trace. The diagnosis reports, never
    raises: a broken seam becomes its own line.
    """
    from botforge.discord.static_pins import registered_static_pins

    if not guild_id or not str(guild_id).isdigit():
        return []
    out: list[tuple[str, str]] = []
    for spec in registered_static_pins():
        scope = getattr(spec, "scope", "") or ""
        if not scope.startswith(_MOD_SCOPE):
            continue
        try:
            out.append((spec.key, await _spec_status(spec, client, guild_id)))
        except Exception as exc:  # noqa: BLE001 — the report never raises
            logger.warning("kingdom: pin diagnosis failed for %s", spec.key, exc_info=True)
            out.append((spec.key, f"erreur : {type(exc).__name__}"))
    return sorted(out)


async def _spec_status(spec: Any, client: discord.Client, guild_id: str) -> str:
    """Name the failing step of one pin, best-effort at every level."""
    channel_id = await spec.resolve_channel(guild_id)
    if not channel_id or not str(channel_id).isdigit():
        return "salon non provisionné (résolution absente — refaire un Repair)"
    guild = client.get_guild(int(guild_id))
    if guild is None:
        return f"serveur {guild_id} hors cache du bot"
    channel = guild.get_channel(int(channel_id))
    if channel is None:
        return f"salon <#{channel_id}> hors cache du bot (droits salon cassés ?)"
    message_id = await spec.resolve_message_id(guild_id)
    if not message_id:
        return f"jamais épinglé (salon <#{channel_id}> trouvé — l'épinglage n'y est jamais passé)"
    try:
        message = await channel.fetch_message(int(message_id))
    except discord.NotFound:
        return f"message {message_id} supprimé — le prochain passage doit le recréer"
    except discord.HTTPException as exc:
        return f"message {message_id} illisible (HTTP {exc.status} — droits lecture du bot ?)"
    if message.pinned:
        return f"épinglé dans <#{channel_id}>"
    return f"présent dans <#{channel_id}> mais NON épinglé ({message.id})"


async def admin_pin_lines(client: discord.Client, guild_id: str) -> list[str]:
    """The /kingdom followup's admin section: one line per pinned surface."""
    report = await pins_report(client, guild_id)
    if not report:
        return []
    lines = ["**Panneaux du mod — diagnostic**"]
    lines.extend(f"• `{key}` — {status}" for key, status in report)
    return lines
