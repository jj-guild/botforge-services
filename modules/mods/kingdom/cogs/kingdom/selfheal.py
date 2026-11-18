"""The mod's boot self-heal (epic #412) — pins land, commands exist.

WHY: the platform's boot routing is best-effort (announce-gated) and
the slash-command sync is scoped to ONE configured guild. On a test
env the pins can miss their salon (a 429 storm at provision time, an
announce-disabled boot) and the ``/kingdom`` slash never registers
outside the sync guild — the mod's owner then sees empty salons and a
command that "doesn't exist", with no logs on his side.

WHAT: once per boot, ~30 s after the gateway is ready, one pass per
guild the bot is a member of rides the PUBLIC seams only:
``ensure_mod_pins`` — the SDK's install/repair path, the SAME one a
Repair click runs — then the command-tree API (fetch, copy, sync) so
every served guild sees the mod's slash commands. Best-effort at
every level: a broken seam becomes its own log line, never a raise.

#221 (the discipline): the CONTRACT (a served guild sees the mod's
pinned surfaces and its slash) lives here, in the mod; the multi-guild
command sync is a platform concern to raise there — this pass is the
mod-side stopgap until the core owns it.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import discord

logger = logging.getLogger("kingdom.selfheal")

# Let the platform's own boot provisioning (routing, first sync) finish
# before this pass reads and writes — a boot 429 storm must not be fed.
_DELAY_S = 30.0


async def ensure_kingdom_surfaces(bot: Any) -> list[tuple[str, str]]:
    """One (guild_id, summary) per guild — the report, never a raise."""
    report: list[tuple[str, str]] = []
    for guild in list(getattr(bot, "guilds", []) or []):
        guild_id = str(getattr(guild, "id", ""))
        pins = "error"
        commands = "error"
        try:
            from botforge.discord.scope_pins import ensure_mod_pins

            landed = await ensure_mod_pins(bot, guild_id, "kingdom")
            pins = str(landed)
        except Exception:  # noqa: BLE001 — the self-heal never breaks the boot
            logger.warning("kingdom: self-heal pins failed (guild %s)", guild_id, exc_info=True)
        try:
            commands = await _ensure_commands(bot, guild_id)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom: self-heal commands failed (guild %s)", guild_id, exc_info=True)
        report.append((guild_id, f"{pins} pins, commands: {commands}"))
        logger.info("kingdom: self-heal pass (guild %s) — %s pins, commands: %s", guild_id, pins, commands)
    return report


async def _ensure_commands(bot: Any, guild_id: str) -> str:
    """The mod's slashes must exist in every served guild.

    The platform syncs ONE configured guild; this reads the guild's
    live commands first and only copies+syncs when ``kingdom`` is
    missing — an already-synced guild costs one cheap fetch.
    """
    tree = getattr(bot, "tree", None)
    if tree is None or not str(guild_id).isdigit():
        return "skipped"
    target = discord.Object(id=int(guild_id))
    try:
        existing = await tree.fetch_commands(guild=target)
    except Exception:
        existing = None
    if existing is not None and any(getattr(cmd, "name", "") == "kingdom" for cmd in existing):
        return "already there"
    tree.copy_global_to(guild=target)
    await tree.sync(guild=target)
    return "synced"


def arm_boot_self_heal(bot: Any) -> None:
    """Schedule the one-shot pass on the next ready (idempotent per bot)."""
    if getattr(bot, "_kingdom_selfheal_armed", False):
        return
    bot._kingdom_selfheal_armed = True  # type: ignore[attr-defined]

    async def _run_once() -> None:
        if getattr(bot, "_kingdom_selfheal_ran", False):
            return
        bot._kingdom_selfheal_ran = True  # type: ignore[attr-defined]
        await asyncio.sleep(_DELAY_S)
        try:
            await ensure_kingdom_surfaces(bot)
        except Exception:  # noqa: BLE001 — never break on_ready
            logger.warning("kingdom: self-heal pass failed — best-effort", exc_info=True)

    bot.add_listener(_run_once, "on_ready")  # type: ignore[attr-defined]
