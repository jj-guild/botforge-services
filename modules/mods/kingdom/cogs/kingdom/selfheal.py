"""The mod's boot self-heal (epic #412) — pins land, commands exist.

WHY: the platform's boot routing is best-effort (announce-gated) and
the slash-command sync is scoped to ONE configured guild. On a test
env the pins can miss their salon (a 429 storm at provision time, an
announce-disabled boot) and the ``/kingdom`` slash never registers
outside the sync guild — the mod's owner then sees empty salons and a
command that "doesn't exist", with no logs on his side.

WHAT: once per boot, ~30 s after the gateway is ready, one pass per
guild the bot is a member of rides the PUBLIC seams only:
``provision_mod_roles`` + ``provision_mod_channels`` (the SDK's
install/repair path, the SAME one a Repair click runs — the pass
brings the DECLARED salons into existence on a guild that never
received the provisioning, the priority-one admin-category case),
then ``ensure_mod_pins`` — the pins then land in salons that exist —
then the command-tree API (fetch, copy, sync) so every served guild
sees the mod's slash commands. Best-effort at every level: a broken
seam becomes its own log line, never a raise. Kill-switch:
``BOTFORGE_KINGDOM_BOOT_PROVISION=off/0/false`` disables the
channel/role provisioning (the pins/commands passes stay).

#221 (the discipline): the CONTRACT (a served guild sees the mod's
pinned surfaces and its slash) lives here, in the mod; the multi-guild
command sync is a platform concern to raise there — this pass is the
mod-side stopgap until the core owns it.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import discord

logger = logging.getLogger("kingdom.selfheal")

# architecture-salons-v1 : la catégorie retirée (le profil = une commande).
# Écrite en \N escapes : les petites capitales inline déclenchent
# une pluie d'alertes RUF001 (leçon de la fournée).
RETIRED_PROFILES_CATEGORY = (
    "\N{BUST IN SILHOUETTE} "
    "\N{LATIN LETTER SMALL CAPITAL P}"
    "\N{LATIN LETTER SMALL CAPITAL R}"
    "\N{LATIN LETTER SMALL CAPITAL O}"
    "\N{LATIN LETTER SMALL CAPITAL F}"
    "\N{LATIN LETTER SMALL CAPITAL I}"
    "\N{LATIN LETTER SMALL CAPITAL L}"
    "s"
)


# Let the platform's own boot provisioning (routing, first sync) finish
# before this pass reads and writes — a boot 429 storm must not be fed.
_DELAY_S = 30.0


def _boot_provision_enabled() -> bool:
    """Kill-switch: `BOTFORGE_KINGDOM_BOOT_PROVISION=off/0/false`."""
    return os.getenv("BOTFORGE_KINGDOM_BOOT_PROVISION", "on").strip().lower() not in {
        "off",
        "0",
        "false",
        "no",
    }


async def ensure_kingdom_surfaces(bot: Any) -> list[tuple[str, str]]:
    """One (guild_id, summary) per guild — the report, never a raise."""
    report: list[tuple[str, str]] = []
    for guild in list(getattr(bot, "guilds", []) or []):
        guild_id = str(getattr(guild, "id", ""))
        provisioning = "off"
        # the DECLARED salons first (the Repair-click seams, idempotent
        # by stored resolutions — a converged guild is a cheap no-op) :
        # the pins below need salons that exist, the admin category
        # (⚙️ paramètres & co) must be functional without a manual click
        if _boot_provision_enabled():
            try:
                from botforge.discord.mods_forum import (
                    provision_mod_channels,
                    provision_mod_roles,
                )

                roles = await provision_mod_roles(bot, guild_id, "kingdom")
                channels = await provision_mod_channels(bot, guild_id, "kingdom")
                provisioning = f"{channels} channels, {roles} roles"
            except Exception:  # the self-heal never breaks the boot
                logger.warning(
                    "kingdom: self-heal provisioning failed (guild %s)",
                    guild_id,
                    exc_info=True,
                )
                provisioning = "error"
        pins = "error"
        commands = "error"
        try:
            from botforge.discord.scope_pins import ensure_mod_pins

            landed = await ensure_mod_pins(bot, guild_id, "kingdom")
            pins = str(landed)
        except Exception:  # the self-heal never breaks the boot
            logger.warning("kingdom: self-heal pins failed (guild %s)", guild_id, exc_info=True)
        if _boot_provision_enabled():
            await _rattrapage_sidebar(guild, guild_id)
            await _rattrapage_tail(bot)
            await _rattrapage_ranks(bot)
        try:
            commands = await _ensure_commands(bot, guild_id)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom: self-heal commands failed (guild %s)", guild_id, exc_info=True)
        report.append((guild_id, f"provisioning: {provisioning}; {pins} pins, commands: {commands}"))
        logger.info(
            "kingdom: self-heal pass (guild %s) — %s; %s pins, commands: %s",
            guild_id,
            provisioning,
            pins,
            commands,
        )
    return report


async def _rattrapage_sidebar(guild: object, guild_id: str) -> None:
    """architecture-salons-v1 (Drasah 24/11) : le RATTRAPAGE de la sidebar.

    Les catégories des royaumes déjà vivants rejoignent le bandeau
    au-dessus d'admin (règle sine qua non : admin dernier, quoi qu'il
    arrive), et la catégorie vide legacy des PROFILS (le profil devient
    une commande) est balayée. Best-effort, jamais bloquant.
    """
    try:
        from botforge.mods.kingdom.cogs.realms import place_realm_categories

        band = await place_realm_categories(guild)
        if band:
            logger.info(
                "kingdom: self-heal placed %d realm categorie(s) above admin", band
            )
    except Exception:  # the self-heal never breaks the boot
        logger.warning(
            "kingdom: the realm band placement failed (guild %s)",
            guild_id,
            exc_info=True,
        )
    try:
        swept = await _sweep_retired_profiles_category(guild)
        if swept:
            logger.info(
                "kingdom: self-heal swept the retired profiles category (guild %s)",
                guild_id,
            )
    except Exception:
        logger.warning(
            "kingdom: the profiles sweep failed (guild %s)", guild_id, exc_info=True
        )


async def _rattrapage_tail(bot: Any) -> None:
    """sidebar-contract-v2 (Drasah 24/11) : the boot re-asserts the tail.

    The declared bottom folders (the admin group, the reserve home,
    the platform plumbing like the game data folders) sink to their
    DECLARED order at boot — a fresh deploy converges immediately
    instead of waiting for the 5-min refresher. Best-effort.
    """
    try:
        from botforge.discord.ui.panels_provisioning import enforce_bottom_categories

        moved = await enforce_bottom_categories(bot)
        if moved:
            logger.info("kingdom: boot re-asserted %d bottom categorie(s)", moved)
    except Exception:
        logger.warning("kingdom: the boot bottom assert failed", exc_info=True)


async def _rattrapage_ranks(bot: Any) -> None:
    """saisons-roles-v1 (Drasah 24/11) : le boot distribue les rangs.

    Les saisons déjà engagées (l'incident Blanc) reçoivent leurs rôles
    King/Lord dès le boot — la convergence relit la saison, les
    manquants partent poser, les en trop retirer. Best-effort.
    """
    try:
        from .season_roles_sync import sync_season_roles

        moved = await sync_season_roles(bot)
        if moved:
            logger.info("kingdom: boot converged %d season role change(s)", moved)
    except Exception:
        logger.warning("kingdom: the boot rank assert failed", exc_info=True)


async def _sweep_retired_profiles_category(guild: Any) -> int:
    """architecture-salons-v1 : PROFILS n'existe plus (le profil devient une commande).

    La catégorie vide legacy (jamais recréée par le provisionnement,
    le groupe a quitté la déclaration) est supprimée au boot —
    UNIQUEMENT vide : une catégorie habitée reste sur place,
    inchangée, et le coup suivant repassera.
    """
    retired = RETIRED_PROFILES_CATEGORY
    for category in list(getattr(guild, "categories", None) or []):
        if str(getattr(category, "name", "")) != retired:
            continue
        if list(getattr(category, "channels", None) or []):
            continue
        try:
            await category.delete(reason="kingdom: the retired profiles category")
            return 1
        except Exception:
            logger.warning(
                "kingdom: deleting the retired profiles category failed — best-effort",
                exc_info=True,
            )
    return 0


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


async def boot_self_heal(bot: Any) -> None:
    """The one-shot boot pass (launched from the mod's setup_hook task).

    Runs once per bot process (the flag survives reconnects); never
    breaks the boot — best-effort. discord.py 2.7 removed
    ``Client.add_listener`` and ``bot.event`` would override the core's
    ``on_ready``, so the pass rides a task instead of an event listener.
    """
    if getattr(bot, "_kingdom_selfheal_ran", False):
        return
    bot._kingdom_selfheal_ran = True  # type: ignore[attr-defined]
    await asyncio.sleep(_DELAY_S)
    try:
        await ensure_kingdom_surfaces(bot)
    except Exception:  # noqa: BLE001 — never break the boot
        logger.warning("kingdom: self-heal pass failed — best-effort", exc_info=True)
