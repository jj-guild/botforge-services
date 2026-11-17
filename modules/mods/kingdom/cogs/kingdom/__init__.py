"""The kingdom mod's cog package (§7 cogs) — the mod's Discord layer.

Lifecycle hooks (all optional, all idempotent — see
botforge.core.services.mod_entrypoint): the core calls ``register`` at
bot build time, ``setup_hook`` after a restart to re-register persistent
UI, ``close`` on shutdown. Hooks degrade quietly when their stack
(Mongo, Redis, providers) is not configured.
"""

from __future__ import annotations

from typing import Any

import discord

from .cog import status_view


def register(bot: Any, config: Any) -> None:
    """Wire the cog onto the bot: commands, pins, dynamic items."""
    from botforge.discord.static_pins import StaticPinnedView, register_static_pin
    from botforge.discord.ui.panels_provisioning import stored_channel_id

    from .panel import build_attack_panel, remember_bot

    remember_bot(bot)

    async def _resolve_channel(guild_id: str) -> str:
        return await stored_channel_id(guild_id, "mod/kingdom", "attack") or ""

    register_static_pin(
        StaticPinnedView(
            key="view:mod:kingdom:attack",
            mark_suffix="view:mod:kingdom:attack",
            resolve_channel=_resolve_channel,
            build_layout=build_attack_panel,
            registry=getattr(bot, "message_registry", None),
            scope="mod/kingdom",
        )
    )

    @discord.app_commands.command(
        name="kingdom",
        description="Kingdom — statut du service",
    )
    async def _cmd(interaction: discord.Interaction) -> None:
        view = await status_view(str(interaction.guild_id or ""))
        await interaction.response.send_message(view=view, ephemeral=True)

    bot.tree.add_command(_cmd)


def setup_hook(bot: Any) -> None:
    """Re-register persistent UI after a restart (dynamic items)."""
    from .panel import (
        CancelButton,
        DeclareButton,
        DefendButton,
        HistoryButton,
        InfoButton,
        JoinButton,
    )

    for item in (DeclareButton, HistoryButton, InfoButton, DefendButton, JoinButton, CancelButton):
        try:
            bot.add_dynamic_items(item)
        except Exception:  # noqa: S110 — idempotent across restarts
            pass


def close(bot: Any) -> None:
    """Stop the mod's background tasks (best-effort)."""
