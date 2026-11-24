"""The pong mod's Discord cog (§7): commands and views, nothing else.

The cog is intentionally thin: identity (Discord-shaped data) ends at
the boundary, everything goes through the contract via
``mod_service("pong")``. All player-facing copy goes through the i18n
catalog (never formatted at the call site), all latency goes through
``defer`` (the 3-second rule), and the UI rides the SDK only (no raw
``discord.ui`` views).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import discord
from discord import app_commands

from botforge.core.services.i18n import MessageCatalog
from botforge.core.services.mod_entrypoint import mod_service
from botforge.core.services.mod_layout import default_repo_root
from botforge.discord.ui import BLURPLE, ConfirmationView, Container, Text, UILayout

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


def _boot_text(key: str, fallback: str) -> str:
    """Command description at registration time (synced once per boot)."""
    try:
        return _tr(key, "en")
    except Exception:  # noqa: BLE001 - the tree must boot even without locales
        return fallback


def _locale(interaction: discord.Interaction) -> str:
    """The guild's locale, mapped onto the mod's catalog (fr | en fallback)."""
    code = str(getattr(interaction, "guild_locale", None) or getattr(interaction, "locale", None) or "en")
    return "fr" if code.lower().startswith("fr") else "en"


def _service() -> Any:
    """The mod's callable surface, obtained the §7 way (through the contract)."""
    return mod_service("pong").PongServiceImpl()


@app_commands.command(name="pong", description=_boot_text("pong.commands.pong.description", "AOE Pong home panel"))
@app_commands.guild_only()
async def pong_home(interaction: discord.Interaction) -> None:
    """The mod's home panel (status snapshot of the slice)."""
    status = await _service().status(str(interaction.guild_id))
    locale = _locale(interaction)
    layout = (
        UILayout()
        .add(
            Container(accent=BLURPLE)
            .add(Text(f"# {_tr('pong.home.title', locale)}"))
            .add(Text(_tr("pong.home.state", locale, **{"state": status["state"]})))
            .add(Text(_tr("pong.home.players", locale, **{"players": status["players"]})))
        )
        .build()
    )
    await interaction.response.send_message(view=layout, ephemeral=True)


@app_commands.command(
    name="register_to_tournament",
    description=_boot_text("pong.commands.register.description", "Register for the AOE Pong tournament (consent required)"),
)
@app_commands.guild_only()
async def register_to_tournament(interaction: discord.Interaction) -> None:
    """The consent-gated registration flow (RG-REG-1, SC-PONG-001/002)."""
    # The service call crosses the process boundary: defer first (3-second rule).
    await interaction.response.defer(thinking=True, ephemeral=True)
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
        mod="pong",
        confirm_label=_tr("pong.register.accept", locale),
        cancel_label=_tr("pong.register.refuse", locale),
        on_confirm=on_confirm,
        on_cancel=on_cancel,
    )
    await interaction.followup.send(content=_tr("pong.register.consent", locale), view=view, ephemeral=True)


def register(bot: discord.Client, config: Mapping[str, Any] | None = None) -> None:
    """The §7 cog hook: attach the mod's commands to the bot's tree."""
    bot.tree.add_command(pong_home)
    bot.tree.add_command(register_to_tournament)


__all__ = ["pong_home", "register", "register_to_tournament"]
