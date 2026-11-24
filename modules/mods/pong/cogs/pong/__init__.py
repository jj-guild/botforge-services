"""The pong mod's Discord cog (§7): declared actions, nothing else.

There are NO pong slash commands (owner direction 2026-11-24): the
mod's whole surface rides the platform's generated menus — the player
enters through ``/home`` (the standard Mods button, or the mod's own
home button) which opens the generated ``menu:mod:pong``; the
registration is a declared ACTION button on that menu, wired here at
boot through ``wire_action`` — declaration in
``config/mods/pong.views.yaml``, behavior here (never one without the
other).

Everything goes through the contract via ``mod_service("pong")``; all
player-facing copy goes through the i18n catalog (never formatted at
the call site).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import discord

from botforge.core.services.i18n import MessageCatalog
from botforge.core.services.mod_entrypoint import mod_service
from botforge.core.services.mod_layout import default_repo_root
from botforge.discord.ui import ConfirmationView

MOD_NAME = "pong"
MOD_HOME_ID = f"menu:mod:{MOD_NAME}"
MOD_HOME_KEY = f"mod:{MOD_NAME}"  # the /home pin's view key for the mod button
REGISTER_ACTION = "register"

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
    """The interaction's locale, mapped onto the mod's catalog (fr | en fallback)."""
    code = str(getattr(interaction, "guild_locale", None) or getattr(interaction, "locale", None) or "en")
    return "fr" if code.lower().startswith("fr") else "en"


def _service() -> Any:
    """The mod's callable surface, obtained the §7 way (through the contract)."""
    return mod_service(MOD_NAME).PongServiceImpl()


async def _open_registration(interaction: discord.Interaction) -> None:
    """The declared Register action: the consent-gated registration flow (RG-REG-1).

    SC-PONG-001/002: consent accepted persists the player as a candidate;
    consent refused persists NOTHING.
    """
    locale = _locale(interaction)
    guild_id = str(interaction.guild_id)
    discord_id = str(interaction.user.id)
    service = _service()

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
        mod=MOD_NAME,
        confirm_label=_tr("pong.register.accept", locale),
        cancel_label=_tr("pong.register.refuse", locale),
        on_confirm=on_confirm,
        on_cancel=on_cancel,
    )
    await interaction.response.send_message(content=_tr("pong.register.consent", locale), view=view, ephemeral=True)


async def _open_mod_home(interaction: discord.Interaction) -> None:
    """Open the generated pong home menu (the /home button's target)."""
    from botforge.discord.views_routing import open_declared_view

    await open_declared_view(interaction, MOD_HOME_ID)


def register(bot: discord.Client, config: Any = None) -> None:
    """The §7 cog hook: wire the declared actions and the home view (no commands)."""
    from botforge.discord.views_routing import wire_action, wire_view

    # the Register ACTION: declared in config/mods/pong.views.yaml on
    # menu:mod:pong, wired here — one click opens the consent gate.
    wire_action(MOD_HOME_ID, REGISTER_ACTION, _open_registration)
    # the mod's /home button: the pin's "mod:pong" view key and the
    # mod_home_builders bridge both land on the generated menu.
    wire_view(MOD_HOME_KEY, _open_mod_home)
    builders = getattr(bot, "mod_home_builders", None)
    if isinstance(builders, dict):
        builders[MOD_NAME] = _open_mod_home


__all__ = ["MOD_HOME_ID", "MOD_NAME", "REGISTER_ACTION", "register"]
