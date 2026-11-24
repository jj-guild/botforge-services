"""The pong mod's Discord cog (§7 cogs): the mod's only Discord layer.

Owner direction 2026-11-24 (D-PONG-037): the mod ships NO slash command —
the Discord surface is the core commands (``/home`` + ``/admin``) plus the
platform's auto-generated menus (``menu:mod:pong`` / ``menu:mod:pong:admin``,
botforge-services#377). The mod's one declared action — ``register``
(config/mods/pong.views.yaml: the consent-gated registration front door,
SC-PONG-001/002, RG-REG-1) — is wired here at boot through ``wire_action``;
every player-facing string renders from the mod's own i18n catalog (no raw
UI strings). The service is reached the §7 way only: ``mod_service("pong")``
(the contract, never the domain internals).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import discord

from botforge.core.services.i18n import MessageCatalog
from botforge.core.services.mod_entrypoint import mod_service
from botforge.core.services.mod_layout import default_repo_root
from botforge.discord.ui import ConfirmationView
from botforge.discord.views_routing import wire_action

_CATALOG: MessageCatalog | None = None


def _catalog() -> MessageCatalog:
    """Load the mod's locale catalog once (i18n-first: no raw UI strings)."""
    global _CATALOG
    if _CATALOG is None:
        repo_root = default_repo_root()
        conf_dir = (repo_root if repo_root is not None else Path.cwd()) / "modules" / "mods" / "pong" / "conf"
        _CATALOG = MessageCatalog(conf_dir)
    return _CATALOG


def _tr(key: str, locale: str = "en", **kwargs: Any) -> str:
    """Render an i18n key (the catalog falls back to en and never raises)."""
    return _catalog().render(key, locale, **kwargs)


def _locale(interaction: discord.Interaction) -> str:
    """The guild's locale, mapped onto the mod's catalog (fr | en fallback)."""
    code = str(getattr(interaction, "guild_locale", None) or getattr(interaction, "locale", None) or "en")
    return "fr" if code.lower().startswith("fr") else "en"


def _register_handler(service: Any) -> Any:
    """Build the register action handler over the mod's callable surface."""

    async def handler(interaction: discord.Interaction) -> None:
        """The consent-gated registration front door (one ephemeral flow)."""
        locale = _locale(interaction)
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        discord_id = str(interaction.user.id)

        async def _finish(click: discord.Interaction, consent: bool) -> None:
            result = await service.register_player(guild_id, discord_id, consent)
            if not result["registered"]:
                content = _tr("pong.register.refused", locale)
            elif result.get("already_registered"):
                content = _tr("pong.register.already", locale)
            else:
                content = f"{_tr('pong.register.done', locale)}\n{_tr('pong.register.no_season', locale)}"
            await click.response.edit_message(content=content, view=None)

        async def on_confirm(click: discord.Interaction) -> None:
            await _finish(click, consent=True)

        async def on_cancel(click: discord.Interaction) -> None:
            await _finish(click, consent=False)

        view = ConfirmationView(
            mod="pong",
            confirm_label=_tr("pong.register.accept", locale),
            cancel_label=_tr("pong.register.refuse", locale),
            on_confirm=on_confirm,
            on_cancel=on_cancel,
        )
        await interaction.response.send_message(content=_tr("pong.register.consent", locale), view=view, ephemeral=True)

    return handler


def register(bot: Any, config: Any) -> None:
    """Wire the cog onto the bot: the declared register action, nothing else.

    No ``bot.tree.add_command`` (D-PONG-037): the surface rides the
    auto-generated menus. The service instance is held by the wiring so the
    slice's in-process store survives across clicks (a restart loses it —
    the persistent ModStorage-backed store lands with the engine, step 3,
    tracked in #439).
    """
    service = mod_service("pong").PongServiceImpl()
    wire_action("menu:mod:pong", "register", _register_handler(service))


def setup_hook(bot: Any) -> None:
    """Re-register persistent UI after a restart (the action re-wires at register)."""


def close(bot: Any) -> None:
    """Stop the mod's background tasks (none at slice v1)."""
