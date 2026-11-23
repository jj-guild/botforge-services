"""The home surface: /home + the pinned 🏛 menu, one ephemeral view per button.

The home is the guild's front door: a pinned menu in the 🏛-home
channel (provisioned like every managed channel), plus the /home command
showing the same menu. Every button answers with an **ephemeral** view —
the home is public, the answers are personal.

Namespace uniqueness (the §3b rule): the pinned home rides the
``home:`` namespace, served only by the DynamicItems declared here — no
live-closure view is registered for the pinned message, so a click has
exactly one dispatch path, restart-proof.

- ``home:pin:menu``   — the marker identifying the pinned message;
- ``home:open:<view>`` — one button per view (status, profile, games,
  users, admin, mod:<name>).

The standard views render the platform's own data (the /status layout,
the core profile bindings, the provider status); a mod view routes to
the mod's home view builder when the mod provides one.

The pinned message is **never rebuilt while it lives**: its id is
registered in the message registry (``home-menu`` key, per guild) and
the periodic check only verifies the registered message still exists
(re-pinning it if it was unpinned) - the menu is recreated solely when
the registered message is gone (deleted, channel wiped). Without a
registry (local runs), an in-memory store provides the same lifecycle
for the process's lifetime.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
from typing import Any

import discord
from discord import app_commands

from botforge.core.services.home import HomeService
from botforge.core.services.i18n import MessageCatalog
from botforge.discord.commands_i18n import localized, reply, tr
from botforge.discord.ephemeral import EphemeralOrigin

logger = logging.getLogger("botforge.home")

HOME_CHANNEL_NAME = "🏛-home"
HOME_CHANNEL_CATEGORY = "bot_home"
HOME_MARKER = "home:pin:"
HOME_MESSAGE_KEY = "view:home"
HOME_MESSAGE_LEGACY_KEY = "home-menu"
HOME_MESSAGE_PLATFORM = "discord"


# The legacy home:open ids mapped onto the declared view ids — the
# pins deployed before the views registry keep working through it.
_LEGACY_VIEW_KEYS = {
    "profile": "panel:profile",
    "status": "panel:status",
    "games": "menu:games:home",
    "mods": "menu:mods:home",
    "admin": "menu:admin",
    "live": "panel:game:aoe2:live",
    "users": "panel:game:aoe2:players",
}


class HomeButton(discord.ui.DynamicItem[discord.ui.Button[Any]], template=r"home:open:(?P<view>[a-z0-9:_-]+)"):
    """One persistent home button: opens an ephemeral view at click time."""

    def __init__(self, view_key: str, label: str, emoji: str) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"home:open:{view_key}",
                label=label,
                emoji=emoji,
                style=discord.ButtonStyle.secondary,
            )
        )
        self.view_key = view_key

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> HomeButton:
        """Rebuild the button from the custom_id at click time."""
        del interaction
        button = item if isinstance(item, discord.ui.Button) else None
        emoji = ""
        label = "?"
        if button is not None:
            label = button.label or "?"
            emoji = button.emoji.name if isinstance(button.emoji, discord.PartialEmoji) else ""
        return cls(match.group("view"), label, emoji)
        return cls(match.group("view"), item.label or "?", emoji)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the declared view at click time (legacy ids mapped).

        The declared menus carry ``view:open:<view id>`` buttons; the
        legacy ``home:open:<key>`` ids ride the pins deployed before
        the views registry. They map onto the same declared views so
        an un-refreshed pin still opens the right thing.
        """
        from botforge.discord.views_routing import open_declared_view

        await open_declared_view(interaction, _LEGACY_VIEW_KEYS.get(self.view_key, self.view_key))


async def _view_status(interaction: discord.Interaction) -> None:
    """Render the /status layout, ephemeral."""
    await interaction.response.defer(ephemeral=True)
    from pathlib import Path

    from botforge.discord.announce import AnnounceConfig, build_announcement_layout
    from botforge.discord.bot.factory import BotforgeBot

    bot = interaction.client
    if not isinstance(bot, BotforgeBot):
        await interaction.followup.send(await reply(interaction, "profile.status_unavailable"), ephemeral=True)
        return
    status = bot.status_service
    latency_raw: float | None = bot.latency if bot.latency == bot.latency and bot.latency != float("inf") else None
    layout = build_announcement_layout(
        status,
        AnnounceConfig(config_dir=Path(bot.config.config_dir)),
        env=bot.config.deploy_env,
        latency_ms=round(latency_raw * 1000) if latency_raw is not None else None,
    )
    await interaction.followup.send(view=layout, ephemeral=True)


async def _view_profile(interaction: discord.Interaction) -> None:
    """Render the user's games, linked accounts (name + elo) and actions."""
    registration = getattr(interaction.client, "registration_service", None)
    if registration is None:
        await interaction.response.send_message(await reply(interaction, "not_configured"), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=False)
    await _profile_followup(interaction)


async def _resolve_profile_names(
    interaction: discord.Interaction, bindings: list[dict[str, Any]]
) -> dict[str, str]:
    """Resolve each binding's display name: stored first, provider next.

    The binding's stored profile payload (profile_name, aliases) wins —
    a missing one (the pre-merge seed wiped some) resolves through the
    librematch provider's stats (its alias entries), cached for the
    render; the profile id is the last resort, never a bare '?'.
    """
    names: dict[str, str] = {}
    missing: list[str] = []
    for binding in bindings:
        profile = binding.get("profile") or {}
        pid = str(binding.get("profile_id", ""))
        stored = str(profile.get("profile_name") or "")
        aliases = [str(a) for a in (profile.get("aliases") or []) if str(a)]
        if stored:
            names[pid] = stored
        elif aliases:
            names[pid] = aliases[0]
        elif pid:
            missing.append(pid)
    if missing:
        # resolve the missing names through the profile seam's provider
        game = str(bindings[0].get("game_key", "aoe2")) if bindings else "aoe2"
        await _resolve_missing_names_from_provider(game, missing, names)
    return names


async def _resolve_missing_names_from_provider(
    game: str, missing: list[str], names: dict[str, str]
) -> None:
    """Fill the missing profile names through the librematch provider."""
    try:
        # Rule 4: the bot asks the GAME SERVICE, never the ext provider.
        from botforge.game_aoe2.client import GameDataClient

        provider_uri = os.environ.get("GAME_AOE2_URI", "")
        if not provider_uri:
            return
        client = GameDataClient(provider_uri)
        for pid in missing:
            stats = await client.get_player_stats(pid)
            if stats is None:
                continue
            entries = [e for b in stats.blocks for e in b.entries if e.key == "alias"]
            if not entries:
                entries = [e for b in stats.blocks for e in b.entries][:1]
            if entries:
                names[pid] = str(entries[0].value)
    except Exception:
        logger.warning("HOME: provider name resolve failed — best-effort", exc_info=True)


async def _profile_game_blocks(
    interaction: discord.Interaction, bindings: list[dict[str, Any]], user_id: str
) -> list[discord.ui.TextDisplay[discord.ui.LayoutView]]:
    """Render the linked accounts grouped by game (one block per game)."""
    by_game: dict[str, list[dict[str, Any]]] = {}
    for binding in bindings:
        by_game.setdefault(str(binding.get("game_key", "?")), []).append(binding)
    players_by_id: dict[str, dict[str, Any]] = {}
    enrichers: dict[str, Any] = getattr(interaction.client, "mod_profile_enrichers", {}) or {}
    for enricher in enrichers.values():
        try:
            players_by_id.update(await enricher(interaction.client) or {})
        except Exception:
            logger.warning("HOME: profile enricher failed", exc_info=True)
    blocks: list[discord.ui.TextDisplay[discord.ui.LayoutView]] = []
    resolved = await _resolve_profile_names(interaction, bindings)
    # The stats enrichment (#404 T6): the profile view carries each
    # account's current elo and its stored peak — best-effort, the
    # account line stays as it was when the stats are unknown.
    from botforge.discord.stats_views import account_elo_by_profile

    elo_lines: dict[str, str] = {}
    try:
        elo_lines = await account_elo_by_profile(
            interaction.client,
            [str(e.get("profile_id", "")) for e in bindings],
            translate=lambda key, **fmt: reply(interaction, key, **fmt),
        )
    except Exception:
        logger.warning("HOME: the account stats enrichment failed", exc_info=True)
    for game, entries in sorted(by_game.items()):
        lines = [f"## {_game_label(game)}"]
        for entry in entries:
            pid = str(entry.get("profile_id", "?"))
            name = resolved.get(pid) or pid
            player = players_by_id.get(user_id)
            elo = f" — {player.get('rating')} elo" if player else ""
            stored = elo_lines.get(pid)
            if stored:
                elo = f" — {stored}" if not elo else f"{elo} · {stored}"
            url = _game_account_url(game, str(pid))
            account = f"[{name}]({url}) (`{pid}`)" if url else f"{name} (`{pid}`)"
            lines.append(f"• {account}{elo}")
        blocks.append(discord.ui.TextDisplay(chr(10).join(lines)))
    return blocks


async def _profile_followup(
    interaction: discord.Interaction, banner: str = "", origin: Any = None
) -> None:
    """Render the profile view, updating the original ephemeral message.

    The ephemeral contract: the profile view NEVER sends a copy of
    itself — the caller hands the original message (captured at the
    button click) and it is edited in place, banner and all; only the
    very first render sends a message.
    """
    registration = getattr(interaction.client, "registration_service", None)
    if registration is None:
        await interaction.followup.send(await reply(interaction, "not_configured"), ephemeral=True)
        return
    user_id = str(interaction.user.id)
    bindings = await registration.list_bindings(user_id)
    blocks: list[Any] = []
    if not bindings:
        blocks.append(discord.ui.TextDisplay(await reply(interaction, "profile.no_account")))
    blocks.extend(await _profile_game_blocks(interaction, bindings, user_id))
    view = discord.ui.LayoutView(timeout=None)
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row.add_item(
        ProfileAddAccountButton(await tr(interaction, "profile.add_button", "Ajouter un compte"))
    )
    row.add_item(
        ProfileRenameButton(await tr(interaction, "profile.rename_button", "Changer de pseudo"))
    )
    if bindings:
        row.add_item(
            ProfileRemoveAccountButton(await tr(interaction, "profile.remove_button", "Retirer un compte"))
        )
        # the stats layer serves aoe2 today: the matches button rides
        # the profile view whenever the user owns at least one aoe2
        # account (a new game's stats will widen the guard).
        if any(str(b.get("game_key")) == "aoe2" for b in bindings):
            row.add_item(ProfileMatchesButton(await tr(interaction, "profile.matches_button", "Derniers matchs")))
    header = await _profile_header(interaction, user_id)
    if banner:
        header = f"{header}\n\n{banner}"
    view.add_item(discord.ui.Container(discord.ui.TextDisplay(header), *blocks))
    view.add_item(row)
    from botforge.discord.ui.view_footer import add_view_footer

    add_view_footer(view, "panel:profile")
    if origin is not None:
        from botforge.discord.ephemeral import edit_ephemeral

        if await edit_ephemeral(origin, view):
            # the defer(thinking=True) residue goes — the ORIGIN edit
            # refreshed the clicked view, exactly ONE surface stays
            await _delete_deferred_followup(interaction)
            return
        # the origin is gone (an expired token, a superseded view):
        # NEVER send a copy of the profile view — the ephemeral
        # contract forbids it; the action's banner answers as text.
        note = banner or await reply(interaction, "profile.updated")
        await interaction.followup.send(note, ephemeral=True)
        return
    await interaction.followup.send(view=view, ephemeral=True)


async def _delete_deferred_followup(interaction: discord.Interaction) -> None:
    """Delete the deferred thinking message a modal submit leaves behind.

    A defer(thinking=False) creates an ephemeral followup message; when
    the flow ends by editing the ORIGIN in place, that residue must go
    — the user sees exactly one view, not a view + a stale thinking.
    """
    try:
        # the deferred response IS the latest followup message —
        # fetch the interaction's own ephemeral response and delete it
        original = await interaction.original_response()
        if original is not None and original.flags.ephemeral:
            await interaction.delete_original_response()
    except Exception:
        logger.debug("deferred followup cleanup skipped — best-effort", exc_info=True)




PROFILE_PROVIDER = "ext-librematch (aoe2)"

GAME_LABELS = {"aoe2": "Age of Empires II"}


def _live_client_for(bot: Any, game_key: str) -> Any:
    """Resolve the dashboard client of one game (None when unwired).

    The URI convention is ``GAME_<KEY>_URI``; aoe2 is served by the
    game service's GameData client. The live view is ephemeral-only
    (on demand): one client per render, nothing kept warm.
    """
    import os

    uri = os.environ.get(f"GAME_{game_key.upper()}_URI", "")
    if not uri:
        return None
    if game_key == "aoe2":
        from botforge.game_aoe2.client import GameDataClient

        return GameDataClient(uri)
    return None


def _game_label(game_key: str) -> str:
    """Render one game key as its display name."""
    return GAME_LABELS.get(game_key, game_key)


def _profile_sites(game_key: str) -> list[tuple[str, str, str]]:
    """List the game's declared profile sites: (key, label, no-url)."""
    from botforge.core.services.profile_sites import profile_sites_registry

    return [(s.key, s.label, "") for s in profile_sites_registry().sites_for(game_key)]


def _game_account_url(game_key: str, relic_id: str, site_key: str = "") -> str:
    """Build the profile's public page URL on the chosen (or default) site.

    The sites are declared in ``config/games/<game>/profile_sites.yaml``
    — never hard-coded; the user's preferred site rides their settings.
    """
    from botforge.core.services.profile_sites import format_profile_url

    return format_profile_url(game_key, relic_id, site_key)


async def _user_preferred_site(interaction: discord.Interaction, game_key: str) -> str:
    """Read the user's preferred profile site for a game ('' = default)."""
    logs_service = getattr(interaction.client, "logs_service", None)
    if logs_service is None:
        return ""
    try:
        settings = await logs_service._safe(
            logs_service._db.get_user_settings(str(interaction.user.id))
        ) or {}
    except Exception:
        return ""
    return str(settings.get(f"profile_site:{game_key}", ""))


async def _set_user_preferred_site(
    interaction: discord.Interaction, game_key: str, site_key: str
) -> None:
    """Persist the user's preferred profile site for a game."""
    logs_service = getattr(interaction.client, "logs_service", None)
    if logs_service is None:
        return
    import time as _time

    settings = await logs_service._safe(
        logs_service._db.get_user_settings(str(interaction.user.id))
    ) or {}
    settings[f"profile_site:{game_key}"] = site_key
    settings["updated_at"] = int(_time.time())
    await logs_service._db.set_user_settings(str(interaction.user.id), settings)


async def _report_profile_error(
    interaction: discord.Interaction,
    action: str,
    game_key: str,
    exc: BaseException,
) -> None:
    """Log the precise failure and DM the admins (spam-guarded)."""
    import traceback

    logger.warning("PROFILE %s failed (game %s): %s", action, game_key, exc, exc_info=True)
    bot = interaction.client
    admins = tuple(getattr(getattr(bot, "status_service", None), "bot_admins", ()) or ())
    detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__, limit=8))
    content = (
        f"**Erreur profil \u2014 {action}**\n"
        f"Jeu : `{game_key}` \u00b7 Provider : `{PROFILE_PROVIDER}`\n"
        f"Utilisateur : <@{interaction.user.id}>\n"
        f"Erreur : `{type(exc).__name__}: {exc}`\n"
        f"```\n{detail[:1500]}\n```"
    )
    from botforge.discord.error_report import dm_admins

    with contextlib.suppress(Exception):
        if admins:
            await dm_admins(bot, admins, content)


async def _dm_profile_notice(interaction: discord.Interaction, key: str, **kwargs: Any) -> None:
    """DM the user the account-change notice in their own stored language.

    The ephemeral view answers the click (the guild's context); the DM
    is the user's personal record and speaks THEIR language \u2014 the
    stored DM choice, then the observed client locale, then English.
    Best-effort: a closed DM is skipped quietly.
    """
    client = interaction.client
    catalog = getattr(client, "messages", None)
    if catalog is None:
        return
    logs = getattr(client, "logs_service", None)
    locale = "en"
    user_id = str(interaction.user.id)
    if logs is not None:
        try:
            locale = str(await logs.get_user_locale(user_id) or "en")
        except Exception:
            locale = "en"
    rendered = str(catalog.render(f"profile_dm.{key}", locale, **kwargs))
    if rendered == f"profile_dm.{key}":
        rendered = str(catalog.render(f"profile_dm.{key}", "en", **kwargs))
    if rendered == f"profile_dm.{key}":
        return
    try:
        await interaction.user.send(rendered)
    except Exception:
        logger.info("PROFILE DM skipped (user %s \u2014 DMs closed?)", user_id)


class ProfileAddAccountButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"home:profile:add",
):
    """Open the add-account modal (profile id)."""

    def __init__(self, label: str = "Ajouter un compte") -> None:
        super().__init__(
            discord.ui.Button(
                label=label, emoji="\u2795", style=discord.ButtonStyle.success, custom_id="home:profile:add"
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> ProfileAddAccountButton:
        """Rebuild the item from the wire."""
        del interaction, item, match
        return cls()

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the add-account modal (game options, aoe2-only fallback)."""
        import asyncio

        try:
            options = await asyncio.wait_for(_game_select_options(), timeout=2.5)
        except Exception:
            options = None
        await interaction.response.send_modal(
            ProfileAddAccountModal(options, origin=EphemeralOrigin.capture(interaction))
        )


async def _game_select_options() -> list[discord.SelectOption]:
    """Build the game picker's options: the known games, aoe2 first."""
    options = [discord.SelectOption(label="Age of Empires II", value="aoe2", default=True)]
    try:
        from botforge.discord.admin_panel_games import _games_wiring

        service = _games_wiring()
        if service is not None:
            for key in [g for g in await service.list_game_keys() if g != "aoe2"]:
                options.append(discord.SelectOption(label=key, value=key))
    except Exception:
        logger.warning("PROFILE ADD: game list read failed — aoe2 only", exc_info=True)
    return options[:25]



def _is_name_input(typed: str) -> bool:
    """Tell whether the typed input reads as an in-game name, not an id/URL.

    The #402 name path: ids are digits, URLs carry a scheme/host —
    anything else is a name the provider searches by alias.
    """
    stripped = typed.strip()
    if not stripped:
        return False
    if stripped.isdigit():
        return False
    return "http://" not in stripped and "https://" not in stripped and ".com" not in stripped


def _candidate_line(candidate: dict[str, Any]) -> str:
    """One candidate's discriminator line: what the ACCOUNT carries.

    The player picks among homonyms by the account's own identity —
    clan, country and the two elos. The maps ride the MATCHES, never
    the account, so they never headline the candidate (#402).
    """
    alias = str(candidate.get("alias", ""))
    clan = str(candidate.get("clan", ""))
    country = str(candidate.get("country", ""))
    head = alias + (f" [{clan}]" if clan else "")
    if country:
        head = f"{head} ({country.upper()})"
    elo_1v1 = int(candidate.get("elo_1v1", 0))
    elo_tg = int(candidate.get("elo_tg", 0))
    return f"{head} \u2014 1v1 {elo_1v1 or '?'} \u00b7 TG {elo_tg or '?'}"[:100]


async def _bind_error_note(interaction: discord.Interaction, exc: Exception, game: str, typed: str) -> str:
    """Map a binding failure to its player-facing note (the add flow)."""
    await _report_profile_error(interaction, "profile.add", game, exc)
    reason = str(exc).lower()
    if "d\u00e9j\u00e0" in reason or "already" in reason:
        return await reply(interaction, "profile.add_taken")
    if "no profile seam" in reason or "unknown game" in reason:
        return await reply(interaction, "profile.add_game_unconfigured", game=game)
    if "player_stats" in reason or "mal configur" in reason:
        return await reply(interaction, "profile.add_provider_error", provider=PROFILE_PROVIDER)
    if "not accepted anymore" in reason:
        return await reply(interaction, "profile.add_insights_refused")
    if "valid" in reason or "inconnu" in reason:
        return await reply(interaction, "profile.add_unknown", profile=typed)
    return (
        f"Add failed: the provider {PROFILE_PROVIDER} did not answer "
        "\u2014 the exact error went to the admins."
    )


async def _finish_bind(
    interaction: discord.Interaction, game: str, profile_id: str, origin: Any
) -> None:
    """Confirm a successful bind: the DM notice, then the refreshed profile."""
    bound_url = _game_account_url(game, profile_id)
    await _dm_profile_notice(
        interaction,
        "account_added",
        account=f"[{game} {profile_id}]({bound_url})" if bound_url else game,
    )
    await _profile_followup(
        interaction,
        banner=await reply(interaction, "profile.add_success"),
        origin=origin,
    )


class _AccountCandidateSelect(discord.ui.Select[Any]):
    """The homonym picker: each option is one profile's last played preview."""

    def __init__(self, candidates: list[dict[str, Any]], game: str, origin: Any) -> None:
        super().__init__(
            custom_id="home:profile:add:candidate",
            placeholder="Pick your account...",
            options=[
                discord.SelectOption(
                    label=(_candidate_line(c) or str(c.get("profile_id", "")))[:100],
                    description=str(c.get("steam_name", ""))[:100],
                    value=str(c.get("profile_id", "")),
                )
                for c in candidates[:25]
            ],
            min_values=1,
            max_values=1,
        )
        self.game = game
        self.origin = origin

    async def callback(self, interaction: discord.Interaction) -> None:
        """Bind the picked candidate \u2014 selection IS the validation."""
        registration = getattr(interaction.client, "registration_service", None)
        if registration is None:
            await interaction.response.send_message(await reply(interaction, "not_configured"), ephemeral=True)
            return
        profile_id = str((self.values or [""])[0])
        # The candidate list vanishes IMMEDIATELY (owner direction
        # 2026-11-20, the delete-after-bind never fired on ephemerals):
        # editing THIS message \u2014 the component's own primitive, never
        # the flaky ephemeral delete \u2014 replaces it with the pickup note
        # and pulls the picker away in the same ack. The bind then runs
        # in the followup window; a failure reports as a new note.
        note = await reply(interaction, "profile.add_picked")
        await interaction.response.edit_message(content=note, view=None)
        try:
            await registration.bind_profile(str(interaction.user.id), self.game, profile_id)
        except Exception as exc:
            failure = await _bind_error_note(interaction, exc, self.game, profile_id)
            await interaction.followup.send(failure, ephemeral=True)
            return
        await _finish_bind(interaction, self.game, profile_id, self.origin)


class _AccountCandidateView(discord.ui.View):
    """Ephemeral: pick your account among the alias-search candidates."""

    def __init__(self, candidates: list[dict[str, Any]], game: str, origin: Any) -> None:
        super().__init__(timeout=180)
        self.add_item(_AccountCandidateSelect(candidates, game, origin))


class ProfileAddAccountModal(discord.ui.Modal):
    """The add-account form: game select (aoe2 preselected) + profile id."""

    def __init__(
        self, options: list[discord.SelectOption] | None = None, origin: Any = None
    ) -> None:
        super().__init__(title="Ajouter un compte", timeout=None)
        self.origin = origin
        self.game: discord.ui.Select[Any] = discord.ui.Select(
            custom_id="home:profile:add:game",
            options=options or [discord.SelectOption(label="Age of Empires II", value="aoe2", default=True)],
            placeholder="Jeu du compte...",
            min_values=1,
            max_values=1,
        )
        self.profile_id: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="Ton pseudo en jeu ou ton Relic ID",
            placeholder="Ex. JeanJack ou 17190369 — Relic ID : sur aoe2insights, sous l'avatar, clique l'id puis copie",
            max_length=64,
            required=True,
        )
        self.add_item(discord.ui.Label(text="Jeu du compte", component=self.game))
        self.add_item(self.profile_id)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Bind the account, audit, confirm, then refresh the profile view.

        A typed NAME never goes to bind_profile: it searches the
        provider's alias index (#402's name path) and the player picks
        their account among the homonyms in a followup view.
        """
        registration = getattr(interaction.client, "registration_service", None)
        if registration is None:
            await interaction.response.send_message(await reply(interaction, "not_configured"), ephemeral=True)
            return
        chosen = (self.game.values or ["aoe2"])[0]
        typed = str(self.profile_id.value).strip()
        # the ONLY valid ephemeral modal defer (discord.py): thinking=True —
        # the bind takes seconds, the 3s window survives it
        await interaction.response.defer(ephemeral=True, thinking=True)
        if _is_name_input(typed):
            try:
                candidates = await registration.search_candidates(str(chosen), typed)
            except Exception as exc:
                note = await _bind_error_note(interaction, exc, chosen, typed)
                await interaction.followup.send(note, ephemeral=True)
                return
            if not candidates:
                note = await reply(interaction, "profile.add_unknown", profile=typed)
                await interaction.followup.send(note, ephemeral=True)
                return
            await interaction.followup.send(
                await reply(interaction, "profile.add_pick", name=typed),
                view=_AccountCandidateView(candidates, chosen, self.origin),
                ephemeral=True,
            )
            return
        try:
            await registration.bind_profile(str(interaction.user.id), str(chosen), typed)
        except Exception as exc:
            note = await _bind_error_note(interaction, exc, chosen, typed)
            await interaction.followup.send(note, ephemeral=True)
            return
        await _finish_bind(interaction, str(chosen), typed, self.origin)


async def _profile_header(interaction: discord.Interaction, user_id: str) -> str:
    """Build the profile header: the user's chosen name when known.

    The wordage rides the locale (owner 2026-11-22: the hardcoded
    header spoke English whatever the guild's language).
    """
    identity = getattr(interaction.client, "identity_service", None)
    user = None
    if identity is not None:
        try:
            user = await identity.get_user(f"discord:{user_id}")
        except Exception:
            logger.warning("HOME: identity lookup failed", exc_info=True)
    if user is None or not user.display_name:
        # reply() resolves the replies.* catalog (tr() only maps the
        # ui.* component labels \u2014 a replies key through tr() always
        # fell back to the English, owner 2026-11-22)
        return await reply(interaction, "profile.header_no_name")
    header = await reply(interaction, "profile.header_with_name")
    return header.format(name=user.display_name)






INSIGHTS_MATCH_URL = "https://www.aoe2insights.com/match/{match_id}"
REPLAY_URL = (
    "https://api.ageofempires.com/api/GameStats/AgeII/GetMatchReplay/"
    "?matchId={match_id}&profileId={profile_id}"
)
LIBREMATCH_SOURCE_URL = (
    "https://aoe-api.worldsedgelink.com/community/leaderboard/GetRecentMatchHistory"
    "?title=age2&profile_ids=%5B%22{profile_id}%22%5D&count=25"
)  # 25: the provider's REAL quick window (the panel keeps the 10 INTERESTING)

#: the named settings the RAW options blob completes (the
_OUTCOME_COLOURS = {"win": 0x57F287, "loss": 0xED4245, "ongoing": 0xFEE75C, "lobby": 0x5865F2}


async def _entity_post_url(
    bot: Any,
    guild_id: str,
    channel_id: str,
    names: str | list[str],
) -> str:
    """Resolve one entity's forum POST into its jump URL (best-effort).

    The civs/maps forums keep one thread per entity, titled by its
    LOCALIZED display name (which language the guild speaks decides
    the title, owner 2026-11-22: the Italian/Vietnamese posts never
    linked under their English names). The caller hands EVERY known
    name form, localized first; each also matches its plural/singular
    and its ``Name - whatever`` prefix, walking the public AND the
    private archives. A miss renders plain text, never a wrong link.
    """
    if isinstance(names, str):
        names = [names]
    names = [str(n or "").strip() for n in names if str(n or "").strip()]
    if not channel_id or not names:
        return ""
    channel = bot.get_channel(int(channel_id)) if guild_id else None
    if channel is None:
        return ""
    forms: list[str] = []
    for wanted in [n.casefold() for n in names]:
        for form in (wanted, wanted[:-1] if wanted.endswith("s") else wanted + "s"):
            if form and form not in forms:
                forms.append(form)
    return await _thread_named(channel, forms)


async def _thread_named(channel: Any, forms: list[str]) -> str:
    """Find the forum thread whose title matches one of the forms."""
    # the client's channel.threads cache only carries the threads it
    # happened to load (owner 2026-11-23: Magyars linked, Italiens did
    # not - the cache had one and not the other); the guild's ACTIVE
    # thread list is the complete scan
    threads: list[Any] = list(getattr(channel, "threads", []) or [])
    try:
        parent_id = getattr(channel, "id", None)
        active = await channel.guild.fetch_active_threads()
        for thread in getattr(active, "threads", []) or []:
            if getattr(thread, "parent_id", None) == parent_id and all(
                str(getattr(t, "id", "")) != str(getattr(thread, "id", "")) for t in threads
            ):
                threads.append(thread)
    except Exception:
        logger.debug("the active thread walk failed", exc_info=True)
    for private in (False, True):
        try:
            async for thread in channel.archived_threads(limit=100, private=private):
                threads.append(thread)
        except Exception:
            logger.debug("the archived thread walk failed", exc_info=True)
        for thread in threads:
            thread_name = str(getattr(thread, "name", "")).strip().casefold()
            for form in forms:
                if thread_name == form or thread_name.startswith(
                    f"{form} "
                ) or thread_name.startswith(f"{form} \u2014"):
                    # thread.jump_url is Discord's OWN canonical link
                    return str(getattr(thread, "jump_url", "") or "")
    logger.debug("the entity post was not found (forms: %s)", forms)
    return ""


async def _entity_image(entity_id: str, guild_id: str) -> str:
    """Read one entity's stored image url (the content service)."""
    from botforge.discord.content_posts import content_service, guild_locale

    service = content_service()
    if service is None:
        return ""
    locale = await guild_locale(guild_id, None)
    try:
        doc = await service.content_get(entity_id, locale)
        if doc is None and locale != "en":
            doc = await service.content_get(entity_id, "en")
    except Exception:
        logger.debug("the content read failed (%s)", entity_id, exc_info=True)
        return ""
    if not doc:
        return ""
    return str(doc.get("image_url") or "")


def _civ_entity_id(civ_name: str) -> str:
    """Return the stored civ content id - the core's faction convention.

    The catalog's faction ids follow ``faction:<game>:<slug>`` (the
    game service's own builder, game_data.py) - the panel reuses the
    SAME convention, never its own. The KEY is CANONICAL (the
    English reference name's slug): localized display names never
    address the database (owner 2026-11-22).
    """
    from botforge.core.ids import slug_id

    return f"faction:aoe2:{slug_id(civ_name)}"


def _civ_entity_ids(civ_name: str) -> list[str]:
    """Return the civ's content id CANDIDATES, canonical first.

    AoE2 renames its civilizations across patches (Maya/Mayas/Mayans,
    Inca/Incas, Magyar/Magyars) and adds/removes some: when the
    reference table hands a newer (or older) name than the catalog
    stored, the plural/singular alias of the SAME civ stands the
    best chance of addressing the stored doc.
    """
    from botforge.core.ids import slug_id

    slug = slug_id(civ_name).strip().casefold()
    forms: list[str] = [slug]
    if slug.endswith("s"):
        alt = slug[:-1]
    else:
        alt = slug + "s"
    if alt and alt not in forms:
        forms.append(alt)
    return [f"faction:aoe2:{form}" for form in forms if form]


def _map_entity_id(map_name: str) -> str:
    """Return the stored map content id - the core's own builder.

    ``map_entry_id`` is the platform's single map-id convention - the
    panel never re-implements it.
    """
    from botforge.core.ids import map_entry_id

    return map_entry_id("aoe2", map_name, None)


def _fmt_clock(seconds: int) -> str:
    """Render a duration as mm:ss (the old bot's 00:37)."""
    minutes, secs = divmod(max(0, seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


async def _stored_channel(guild_id: str, scope: str, key: str) -> str:
    """Return the stored channel id (empty when unwired)."""
    from botforge.discord.ui.panels_provisioning import stored_channel_id

    channel_id = await stored_channel_id(guild_id, scope, key) if guild_id else None
    return str(channel_id) if channel_id else ""


#: the slot colours ride the locale (profile.matches_colour_N);
#: these stay the fallback when a label never resolves
SLOT_COLOURS = {
    1: "Bleue",
    2: "Rouge",
    3: "Verte",
    4: "Jaune",
    5: "Cyan",
    6: "Violette",
    7: "Grise",
    8: "Orange",
}

#: the settings footer labels ride the locale too (the provider's
#: settings_json carries the canonical label, the panel translates)
SETTING_LABEL_KEYS = {
    "Mode": "profile.matches_setting_mode",
    "Taille": "profile.matches_setting_size",
    "Pop": "profile.matches_setting_pop",
    "Vitesse": "profile.matches_setting_speed",
    "Victoire": "profile.matches_setting_victory",
    "Cheats": "profile.matches_setting_cheats",
    "Ressources": "profile.matches_setting_resources",
    "Vision": "profile.matches_setting_reveal",
    "Âge départ": "profile.matches_setting_start_age",
    "Âge final": "profile.matches_setting_end_age",
    "Difficulté": "profile.matches_setting_difficulty",
    "Traité": "profile.matches_setting_treaty",
}

#: the BOOLEAN settings (the post-RoR option keys): option key
#: \u2192 locale label key. DIRECT 'y'/'n' flags - verified against
#: aoe2insights' own rendering of match 506901691 (owner 2026-11-23):
#: every ticked rule reads 'y' in the blob, every unticked one 'n'
#: (the collector's "!bool" notes sat the values the wrong way).
SETTING_BOOLEANS = {
    "1": "profile.matches_setting_cheats",
    "65": "profile.matches_setting_lock_speed",
    "66": "profile.matches_setting_lock_teams",
    "62": "profile.matches_setting_full_tech",
    "75": "profile.matches_setting_record",
    "76": "profile.matches_setting_shared_expl",
    "77": "profile.matches_setting_team_positions",
    "78": "profile.matches_setting_team_together",
    "79": "profile.matches_setting_turbo",
}


def _seat_teams(card: dict[str, Any]) -> list[tuple[int, list[dict[str, Any]]]]:
    """Group the card's seats per team, SLOT-ordered within each.

    The seats follow the slotinfo positions (the game's slots 1-8);
    a missing slot falls back to the alias order.
    """
    by_team: dict[int, list[dict[str, Any]]] = {}
    for player in card.get("players") or []:
        if not isinstance(player, dict):
            continue
        by_team.setdefault(int(player.get("team", 0) or 0), []).append(player)
    for seats in by_team.values():
        seats.sort(
            key=lambda p: (int((p or {}).get("slot", 0) or 0), str((p or {}).get("alias", "")))
        )
    return [(team, by_team[team]) for team in sorted(by_team)]


def _ordered_teams(card: dict[str, Any], me_ids: set[str]) -> list[tuple[int, list[dict[str, Any]]]]:
    """Order the teams: MY team first (owner 2026-11-22), even team 2."""
    teams = _seat_teams(card)
    my_team = next(
        (
            i
            for i, (_, seats) in enumerate(teams)
            if any(str((p or {}).get("profile_id", "")) in me_ids for p in seats)
        ),
        None,
    )
    if my_team is None or my_team == 0:
        return teams
    return [*teams[my_team : my_team + 1], *teams[:my_team], *teams[my_team + 1 :]]



def _card_footer_text(card: dict[str, Any], labels: dict[str, Any], me_ids: set[str] | None = None) -> str:
    """Render the footer: the source line only.

    The settings LINE is gone (owner 2026-11-23: the footer carries
    the source, the settings live behind the settings button). The
    source link mirrors the provider's fetch of the VIEWER's history
    page: HIS profile among the match seats - not the first seat's
    (owner 2026-11-23: a fantasy profile id rode the link).
    """
    seats = [str((p or {}).get("profile_id") or "") for p in (card.get("players") or [])]
    mine = next((pid for pid in seats if pid in (me_ids or set())), seats[0] if seats else "")
    source_url = LIBREMATCH_SOURCE_URL.format(profile_id=mine) if mine else ""
    source = str(labels.get("source", "Source : libre:match")).format(url=source_url or "libre:match")
    return f"-# {source}"


#: the named settings the RAW options blob completes (the
#: post-Return-of-Rome AoE2 keys); label key \u2192 value table
_SETTINGS_RAW_KEYS: dict[str, tuple[str, dict[str, str] | None]] = {
    "37": ("Ressources", {
        "0": "Standard", "1": "Faible", "2": "Moyen", "3": "\u00c9lev\u00e9", "4": "Tr\u00e8s \u00e9lev\u00e9",
        "5": "Infini", "6": "Al\u00e9atoire",
    }),
    "82": ("Vision", {"0": "Normale", "1": "Explor\u00e9e", "2": "Toute visible"}),
    "0": ("\u00c2ge d\u00e9part", {
        "0": "Standard", "2": "\u00c2ge sombre", "3": "\u00c2ge f\u00e9odal", "4": "\u00c2ge des ch\u00e2teaux",
        "5": "\u00c2ge imp\u00e9rial", "6": "Post-imp\u00e9rial",
    }),
    "4": ("\u00c2ge final", {
        "0": "Standard", "2": "\u00c2ge sombre", "3": "\u00c2ge f\u00e9odal", "4": "\u00c2ge des ch\u00e2teaux",
        "5": "\u00c2ge imp\u00e9rial", "6": "Post-imp\u00e9rial",
    }),
    "61": ("Difficult\u00e9 IA", {
        "-1": "Extr\u00eame", "0": "Tr\u00e8s difficile", "1": "Difficile", "2": "Mod\u00e9r\u00e9e",
        "3": "Normale", "4": "Tr\u00e8s facile",
    }),
    "57": ("Trait\u00e9", None),  # the raw treaty minutes - shown only when > 0
}


def _int_or(value: Any, default: int = 0) -> int:
    """Coerce to int, the default on garbage."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _settings_named_pairs(card: dict[str, Any]) -> list[tuple[str, str]]:
    """Derive the named value lines of the settings view.

    The provider's stored pairs (Mode, Taille, Pop, Vitesse,
    Victoire) stay the canonical summary; the raw options blob
    completes them (Ressources, Vision, ages, difficult\u00e9, trait\u00e9)
    when it rides the card.
    """
    import json as _json

    pairs: list[tuple[str, str]] = [
        (str(label), str(value)) for label, value in (card.get("settings") or [])
        if str(label) != "Cheats"
    ]
    raw = str(card.get("options_json") or "")
    try:
        options: dict[str, Any] = _json.loads(raw) if raw else {}
    except Exception:
        options = {}
    if isinstance(options, dict):
        for key, (label, table) in _SETTINGS_RAW_KEYS.items():
            value = options.get(key)
            if value in (None, ""):
                continue
            if key == "57" and _int_or(value, 0) <= 0:
                continue  # no treaty reads better than "0 min"
            shown = str((table or {}).get(str(value), value)) if table is not None else f"{value} min"
            pairs.append((label, shown))
    return pairs


def _settings_bool_lines(card: dict[str, Any], labels: dict[str, Any]) -> list[str]:
    """Derive the game-rule checkbox lines (✅ enabled, ⬜ off)."""
    import json as _json

    raw = str(card.get("options_json") or "")
    try:
        options: dict[str, Any] = _json.loads(raw) if raw else {}
    except Exception:
        options = {}
    lines: list[str] = []
    if not isinstance(options, dict) or not options:
        return lines
    bool_labels: dict[str, str] = dict(labels.get("setting_bools") or {})
    for key, label_key_path in SETTING_BOOLEANS.items():
        raw_value = options.get(key)
        if raw_value in (None, ""):
            continue
        enabled = str(raw_value).lower() == "y"
        label = bool_labels.get(key) or label_key_path.split(".")[-1]
        mark = "\u2705" if enabled else "\u2b1c"
        lines.append(f"{mark} {label}")
    return lines


class _MatchSettingsButton(discord.ui.Button[Any]):
    """The settings button of ONE match card (owner 2026-11-23).

    An INLINE, non-persistent item: the panels are ephemeral popups,
    the button and its payload (the card) share the popup's own
    lifetime. The click answers the FULL settings view - sober but
    complete: disabled selects for the named values, emoji checkbox
    lines for the game rules.
    """

    def __init__(self, card: dict[str, Any], labels: dict[str, Any]) -> None:
        super().__init__(
            label=str(labels.get("settings_button", "Param\u00e8tres")),
            emoji="\u2699\ufe0f",
            style=discord.ButtonStyle.secondary,
            custom_id="home:match:settings",
        )
        self._card = card
        self._labels = labels

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            view=_settings_view(self._card, self._labels),
            ephemeral=True,
        )


def _settings_view(card: dict[str, Any], labels: dict[str, Any]) -> discord.ui.LayoutView:
    """Build the FULL settings view of one match (an ephemeral popup)."""
    from botforge.discord.ui.view_footer import add_view_footer

    match_id = str(card.get("match_id") or card.get("match_ref") or "?")
    pairs = _settings_named_pairs(card)
    bool_lines = _settings_bool_lines(card, labels)
    named_labels: dict[str, str] = dict(labels.get("settings") or {})
    title = str(labels.get("settings_title", "\u2699\ufe0f Param\u00e8tres \u2014 Match n\u00b0{id}"))
    title = title.format(id=match_id)
    view = discord.ui.LayoutView(timeout=None)
    container_blocks: list[Any] = [discord.ui.TextDisplay(f"## {title}")]
    for label, value in pairs:
        container_blocks.append(
            discord.ui.TextDisplay(f"-# {named_labels.get(label, label)} : {value}")
        )
    if bool_lines:
        container_blocks.append(discord.ui.Separator())
        container_blocks.append(discord.ui.TextDisplay("\n".join(bool_lines)))
    view.add_item(discord.ui.Container(*container_blocks))
    return add_view_footer(view, f"panel:match:settings:aoe2:{match_id}")


def _card_format(card: dict[str, Any]) -> str:
    """Return the match's format tag (1v1 / 2v2 / 4v4 / custom...)."""
    teams = _seat_teams(card)
    if not teams:
        return ""
    sizes = [len(seats) for _, seats in teams]
    if len(teams) == 1:
        return "custom" if sizes[0] > 2 else ("1v1" if sizes[0] == 1 else "custom")
    if len(teams) == 2 and sizes[0] == sizes[1]:
        return f"{sizes[0]}v{sizes[1]}" if sizes[0] > 1 else "1v1"
    return "FFA" if len(teams) > 2 else "custom"


def _is_ranked(card: dict[str, Any]) -> bool:
    """Return True when the match is an AUTOMATCH (the ranked label)."""
    lobby = str(card.get("lobby_title") or card.get("description") or "").strip().upper()
    return lobby == "AUTOMATCH" or (not lobby and card.get("status") == "finished")


def _card_kind(card: dict[str, Any]) -> str:
    """Return Ranked / Custom: a NON-automatch lobby title says custom."""
    return "ranked" if _is_ranked(card) else "custom"



async def _entity_local_names(
    entity_ids: str | list[str], guild_id: str, fallback: str, bot: Any = None
) -> list[str]:
    """Resolve an entity's LOCALIZED display names (guild locale, then en).

    The aoe2techtree content docs carry per-locale names (fr:
    ``Italiens``, ``Vietnamiens``...) while the provider's reference
    tables speak English \u2014 the panels must display and resolve
    the names of the guild's own language (owner 2026-11-22: the
    Italian/Vietnamese posts never linked).
    """
    from botforge.discord.content_posts import content_service, guild_locale

    service = content_service()
    if service is None:
        return [fallback] if fallback else []
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]
    # the REAL guild locale needs the bot (the STORED choice rides the
    # logs service on it): a null bot resolved "en" and the French
    # posts never matched (owner 2026-11-23: Vietnamese/Italians)
    locales_resolved = await guild_locale(guild_id, bot)
    names: list[str] = []
    locales = list(dict.fromkeys([locales_resolved, "en"]))
    for locale in locales:
        for entity_id in entity_ids:
            try:
                doc = await service.content_get(entity_id, locale)
            except Exception:
                logger.debug("the entity content read failed (%s)", entity_id, exc_info=True)
                doc = None
            name = str((doc or {}).get("name", "") or "").strip()
            if name and name not in names:
                names.append(name)
            if doc:
                break  # the first candidate that answers names the entity
    if fallback and fallback not in names:
        names.append(fallback)
    return [n for n in names if n]


async def _posts_enrichment(
    interaction: discord.Interaction,
    cards: list[dict[str, Any]],
    guild_id: str,
) -> tuple[
    dict[str, str], dict[str, str], dict[str, str], dict[str, str], dict[str, str], dict[str, str]
]:
    """Resolve per-batch: (civ posts, civ images, map posts, map images, civ names, map names)."""
    civ_urls: dict[str, str] = {}
    civ_images: dict[str, str] = {}
    map_urls: dict[str, str] = {}
    map_images: dict[str, str] = {}
    if not guild_id:
        return civ_urls, civ_images, map_urls, map_images, civ_urls, map_urls
    civs_channel = await _stored_channel(guild_id, "games/aoe2", "civs")
    maps_channel = await _stored_channel(guild_id, "games/aoe2", "maps")
    civs_needed: set[str] = set()
    maps_needed: set[str] = set()
    for card in cards:
        for player in card.get("players") or []:
            civ = str((player or {}).get("civ") or "").strip()
            if civ:
                civs_needed.add(civ)
        map_name = str(card.get("map_name") or "").strip()
        if map_name:
            maps_needed.add(map_name)
    civ_display: dict[str, str] = {}
    map_display: dict[str, str] = {}
    for civ in civs_needed:
        candidates = _civ_entity_ids(civ)
        names = await _entity_local_names(candidates, guild_id, civ, interaction.client)
        civ_urls[civ] = await _entity_post_url(interaction.client, guild_id, civs_channel, names)
        civ_display[civ] = names[0] if names else civ
        civ_images[civ] = ""
        for candidate in candidates:
            civ_images[civ] = await _entity_image(candidate, guild_id)
            if civ_images[civ]:
                break
    for map_name in maps_needed:
        names = await _entity_local_names(_map_entity_id(map_name), guild_id, map_name, interaction.client)
        map_urls[map_name] = await _entity_post_url(interaction.client, guild_id, maps_channel, names)
        map_display[map_name] = names[0] if names else map_name
        map_images[map_name] = await _entity_image(_map_entity_id(map_name), guild_id)
    return civ_urls, civ_images, map_urls, map_images, civ_display, map_display


async def _match_panels_ctx(
    interaction: discord.Interaction,
    cards: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve the shared context of the whole card batch.

    The civ/map post urls and stored images plus the ladder boards
    (1v1 / TG, current - max) resolve ONCE for every card - a popup
    costs one enrichment per distinct entity, not per card.
    """
    from botforge.discord.stats_views import stats_client

    guild_id = str(interaction.guild_id or "")
    civ_urls, civ_images, map_urls, map_images, civ_display, map_display = await _posts_enrichment(
        interaction, cards, guild_id
    )
    ladder: dict[str, dict[str, tuple[int, int]]] = {}
    seat_ids = sorted({str((p or {}).get("profile_id", "")) for c in cards for p in c.get("players") or []})
    client = stats_client()
    if seat_ids and client is not None:
        try:
            accounts = await client.get_account_stats(seat_ids)
        except Exception:
            logger.debug("the account stats fetch failed", exc_info=True)
            accounts = []
        for account in accounts:
            boards: dict[str, tuple[int, int]] = {}
            for board in account.leaderboards:
                # only the shown boards: unranked/custom (leaderboard 0)
                # never renders on a seat (owner 2026-11-22)
                if str(board.name) in ("rm_1v1", "rm_team"):
                    boards[str(board.name)] = (int(board.current), int(board.max))
            if boards:
                ladder[str(account.profile_id)] = boards
    return {
        "civ_urls": civ_urls,
        "civ_images": civ_images,
        "map_urls": map_urls,
        "map_images": map_images,
        "civ_display": civ_display,
        "map_display": map_display,
        "ladder": ladder,
    }


def _seat_text(
    player: dict[str, Any],
    card: dict[str, Any],
    ctx: dict[str, Any],
    labels: dict[str, str],
    me_ids: set[str] | None = None,
) -> tuple[str, str]:
    me_ids = me_ids or set()
    """Render ONE seat: (text, civ image url).

    The owner's 2026-11-22 grammar:
    ``💀 [ ▸ ] **Merlin Pinpin** avec [Magyars](post)``
    ``1v1 : 1039 - 1120``
    ``TG : **1300** - 1421 (-11)``
    The MATCH's own board renders pre-match Elo in bold with the diff
    (finished only); the other board renders plain current - max. The
    post-match Elo never renders - it is pre-match + diff.
    """
    civ_urls = ctx["civ_urls"]
    ladder = ctx["ladder"]
    pid = str(player.get("profile_id", ""))
    alias = str(player.get("alias") or player.get("name") or pid or "?")
    civ = str(player.get("civ") or "").strip()
    match_id = str(card.get("match_id") or card.get("match_ref") or "")
    finished = card.get("status") == "finished"
    replay = REPLAY_URL.format(match_id=match_id, profile_id=pid) if match_id else ""
    jump = f"[[ \u25b8 ]]({replay})" if replay else ""
    civ_link = f"[{civ}]({civ_urls[civ]})" if civ and civ_urls.get(civ) else civ
    # the alias links to its insights profile (relic id); ONLY the
    # viewed player's alias carries the bold (owner 2026-11-22)
    insights_profile = f"https://www.aoe2insights.com/user/relic/{pid}/" if pid else ""
    alias_link = f"[{alias}]({insights_profile})" if insights_profile else alias
    name = f"**{alias_link}**" if pid in me_ids else alias_link
    slot = int(player.get("slot", 0) or 0)
    # the colour NAMING was speculative (the game's own colour table
    # needs verifying): keep the honest position only (owner 2026-11-22)
    slot_badge = f"P{slot}" if slot else ""
    line = " ".join(bit for bit in [slot_badge, name] if bit)
    if civ_link:
        line += f" {labels.get('with', 'avec')} {civ_link}"
    if jump:
        line += f" {jump}"
    # the ladder lines: 1v1 and TG only (never unranked), one under
    # the other; the match's own board carries the bold elo — even
    # in a custom game — and the elo DIFF renders for RANKED
    # matches only (an unranked diff means nothing, owner 2026-11-22)
    boards = ladder.get(pid) or {}
    boards = dict(boards)
    before = int(player.get("rating_before") or 0)
    after = int(player.get("rating_after") or 0)
    is_team_game = len(_seat_teams(card)) and any(len(seats) > 1 for _, seats in _seat_teams(card))
    match_board = "rm_team" if is_team_game else "rm_1v1"
    ranked = str(card.get("lobby_title") or "").strip().upper() == "AUTOMATCH"
    lines = [line]
    for key, label in (("rm_1v1", "1v1"), ("rm_team", "TG")):
        current, peak = boards.get(key, (0, 0))
        if key == match_board and (before if ranked else current):
            value = before if ranked else current
            highlight = max(value, peak, after if ranked else 0, 0)
            body = f"-# {label} : **{value}** - {highlight}"
            if ranked and finished and after != before:
                body += f" ({after - before:+d})"
            lines.append(body)
        elif current:
            span = f"{current} - {peak}" if peak and peak > current else f"{current}"
            lines.append(f"-# {label} : {span}")
    return "\n".join(lines), ctx["civ_images"].get(civ, "")


def _seat_component(text: str, civ_image: str) -> Any:
    """One seat becomes a Section with the civ icon in accessory."""
    if civ_image:
        return discord.ui.Section(
            discord.ui.TextDisplay(text),
            accessory=discord.ui.Thumbnail(civ_image),
        )
    return discord.ui.TextDisplay(text)


def _card_map_section(card: dict[str, Any], ctx: dict[str, Any], labels: dict[str, Any] | None = None) -> Any:
    """Build the card's map section.

    The post link carries the title, the stored image rides as the
    section accessory, the when reads the end (finished) or the
    start, the duration renders when finished.
    """
    map_name = str(card.get("map_name") or "").strip()
    titled = bool(map_name) and map_name.lower() != "my map"
    # the DISPLAY name localizes (the reference tables stay English);
    # the post url resolution already tried every handed name form
    map_shown = str((ctx.get("map_display") or {}).get(map_name) or map_name)
    map_label = map_shown if titled else (str(card.get("lobby_title") or "").strip() or "Match")
    map_url = ctx["map_urls"].get(map_name, "") if titled else ""
    map_link = f"[{map_label}]({map_url})" if map_url else f"**{map_label}**"
    labels = labels or {}
    when_at = int(card.get("finished_at") or card.get("started_at") or 0)
    when_line = str(labels.get("when", "Il y a {when}")).format(when=f"<t:{when_at}:R>") if when_at else ""
    sub_lines = [when_line]
    if card.get("status") == "finished":
        duration = max(0, int(card.get("finished_at") or 0) - int(card.get("started_at") or 0))
        if duration:
            sub_lines.append(
                "-# " + str(labels.get("duration", "Durée : {clock}")).format(clock=_fmt_clock(duration))
            )
    title = str(card.get("lobby_title") or "").strip()
    title_line = ""
    if title and title.upper() != "AUTOMATCH":
        title_line = f"**{title}**\n"
    map_text = f"{title_line}### {map_link}\n" + "\n".join(line for line in sub_lines if line)
    image = ctx["map_images"].get(map_name, "") if titled else ""
    if image:
        return discord.ui.Section(discord.ui.TextDisplay(map_text), accessory=discord.ui.Thumbnail(image))
    return discord.ui.TextDisplay(map_text)


def _card_header(
    badge: str, noun: str, match_id: str, me_ids: set[str] | None = None, card: dict[str, Any] | None = None
) -> str:
    """Render the card's header: the badge line, the match id linked.

    The insights match page wraps the id (owner 2026-11-22: a link
    button left the row, the id itself carries it). A SCOPED view
    (owner 2026-11-23) rides the scoped player's OWN outcome emoji
    before the badge: one emoji per view, none per team.
    """
    insights_match = (
        INSIGHTS_MATCH_URL.format(match_id=match_id) if match_id and match_id != "?" else ""
    )
    # the owner's 2026-11-23 pattern: the insights link wraps the
    # part-name badge, the id rides backticks for an easy copy
    name_part = f"[[ {badge} ]]({insights_match})" if insights_match else f"[ {badge} ]"
    id_part = f"`{match_id}`"
    scope_icon = ""
    me_ids = me_ids or set()
    card = card or {}
    winners = {str(w) for w in card.get("winners") or []}
    if me_ids and winners and card.get("status") == "finished":
        scope_icon = "\U0001f3c6 " if winners & me_ids else "\U0001f480 "
    return f"{scope_icon}**{name_part}** {noun}{id_part}"



def _card_team_blocks(
    card: dict[str, Any],
    teams: list[tuple[int, list[dict[str, Any]]]],
    me_ids: set[str],
    labels: dict[str, Any],
    ctx: dict[str, Any],
) -> list[Any]:
    """Render the card's team sections: ONE block per seat.

    The SCOPE (owner 2026-11-23): a view scoped onto one player
    strikes the LOSING teams' titles and rides no per-team medal -
    the header's emoji already tells the outcome; an unscoped view
    keeps one \U0001f3c6/\U0001f480 medal per team.
    """
    scoped = bool(me_ids)
    winners = {str(w) for w in card.get("winners") or []}
    finished = card.get("status") == "finished"
    blocks: list[Any] = []
    for index, (_team, seats) in enumerate(teams):
        if index:
            blocks.append(discord.ui.Separator())
        if len(teams) > 1:
            won = any(str((p or {}).get("profile_id", "")) in winners for p in seats)
            medal = ""
            if not scoped and winners and finished:
                medal = "\U0001f3c6 " if won else "\U0001f480 "
            # the SCOPE carries no per-team medal: the scoped player's
            # team reads BOLD, every other team reads italics, the
            # losers strike through (owner 2026-11-23)
            mine = any(str((p or {}).get("profile_id", "")) in me_ids for p in seats)
            base = f"{labels.get('team', 'Team')} {index + 1}"
            title = f"**{base}**" if mine else f"*{base}*"
            if scoped and winners and finished and not won:
                title = f"~~{title}~~"
            blocks.append(discord.ui.TextDisplay(f"{medal}{title}"))
        for player in seats:
            text, civ_image = _seat_text(player, card, ctx, labels, me_ids)
            blocks.append(_seat_component(text, civ_image))
    return blocks

def _match_card_view(
    card: dict[str, Any],
    ctx: dict[str, Any],
    me_ids: set[str],
    labels: dict[str, Any],
) -> discord.ui.LayoutView:
    """Build ONE match card's view - the SAME panel everywhere.

    Lobbies, ongoing games and finished matches share the panel; the
    status only drives the badge, the duration, the action row and
    the links.

    The owner's 2026-11-22 grammar:
    - header: ``[ Ranked 4v4 ] Match - #508712854`` (Lobby when not started);
    - the map section: its post link, the stored image in accessory,
      the when (end when finished, start when not), the duration when finished;
    - the seats: one section per seat (civ icon in accessory), a
      separator BETWEEN the teams;
    - the footer: Source : libre:match, then the status-led buttons -
      join while the lobby stands, spectate while the game runs,
      insights once the match lives on.
    """
    from botforge.discord.ui.view_footer import add_view_footer

    status = card["status"]  # lobby | ongoing | finished
    fmt = _card_format(card)
    kind = _card_kind(card)
    match_id = str(card.get("match_id") or card.get("match_ref") or "?")
    badge = " ".join(part for part in [kind.upper(), fmt] if part)
    noun_key = "lobby_noun" if status == "lobby" else "match_noun"
    noun = str(labels.get(noun_key, "Match n\u00b0" if status != "lobby" else "Lobby n\u00b0"))
    winners = {str(w) for w in card.get("winners") or []}
    accent = (
        _OUTCOME_COLOURS["win"]
        if winners and winners & me_ids
        else _OUTCOME_COLOURS["loss"]
        if winners
        else _OUTCOME_COLOURS.get(status, 0x5865F2)
    )
    # the SCOPE (owner 2026-11-23): the view scoped onto one player
    # rides his OWN outcome emoji on the header and strikes the
    # losers' titles - see _card_team_blocks
    blocks: list[Any] = [
        discord.ui.TextDisplay(_card_header(badge, noun, match_id, me_ids=me_ids, card=card)),
    ]
    blocks.append(_card_map_section(card, ctx, labels))
    blocks.append(discord.ui.Separator())
    blocks.extend(_card_team_blocks(card, _ordered_teams(card, me_ids), me_ids, labels, ctx))
    # the footer: the source, then the status-led action row
    blocks.append(discord.ui.Separator())
    blocks.append(discord.ui.TextDisplay(_card_footer_text(card, labels, me_ids)))
    buttons: list[discord.ui.Button[Any]] = []
    if status == "lobby" and card.get("lobby_url"):
        buttons.append(
            discord.ui.Button(
                label=labels.get("join", "Rejoindre"),
                emoji="\U0001f3ae",
                style=discord.ButtonStyle.link,
                url=str(card["lobby_url"]),
            )
        )
    if status == "ongoing" and card.get("spectate_url"):
        buttons.append(
            discord.ui.Button(
                label=labels.get("spectate", "Regarder"),
                emoji="\U0001f441\ufe0f",
                style=discord.ButtonStyle.link,
                url=str(card["spectate_url"]),
            )
        )
    # the full settings live behind their own button (owner 2026-11-23:
    # the footer stays the source line only); the row rides OUTSIDE the
    # container, the view id beneath
    buttons.append(_MatchSettingsButton(card, labels))
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.Container(*blocks, accent_colour=discord.Colour(accent)))
    if buttons:
        view.add_item(discord.ui.ActionRow(*buttons))
    return add_view_footer(view, f"panel:match:aoe2:{match_id}")


def _entry_settings_of(entry: Any) -> list[list[str]]:
    """Read the stored settings snapshot of one history entry."""
    raw = getattr(entry, "settings_json", "") or ""
    try:
        import json as _json

        data = _json.loads(raw)
        return [list(pair) for pair in data if isinstance(pair, list) and len(pair) == 2]
    except Exception:
        return []


async def _live_cards(interaction: discord.Interaction, me_ids: set[str]) -> list[dict[str, Any]]:
    """Build the ONGOING/lobby cards from the aggregator snapshot.

    One card per distinct match the viewed profiles play in;
    ``in_lobby`` renders a lobby card (join), ``in_game`` an ongoing
    one (spectate).
    """
    client = _live_client_for(interaction.client, "aoe2")
    if client is None or not me_ids:
        return []
    try:
        snapshot = await client.watch("aoe2")
    except Exception:
        logger.debug("the live snapshot read failed", exc_info=True)
        return []
    by_ref: dict[str, dict[str, Any]] = {}
    for player in snapshot.get("players") or []:
        record = player if isinstance(player, dict) else {}
        if str(record.get("profile_id", "")) not in me_ids:
            continue
        state = str(record.get("state", ""))
        if state not in ("in_lobby", "in_game"):
            continue
        summary = record.get("match") or {}
        if not isinstance(summary, dict) or not summary.get("match_ref"):
            continue
        ref = str(summary["match_ref"])
        if ref in by_ref:
            continue
        by_ref[ref] = {
            "status": "lobby" if state == "in_lobby" else "ongoing",
            "match_ref": ref,
            "match_id": ref,
            "map_name": str(summary.get("map") or ""),
            "description": str(summary.get("match_type") or ""),
            "started_at": 0,
            "finished_at": 0,
            "winners": [],
            "players": [
                dict(p)
                for p in summary.get("players") or []
                if isinstance(p, dict)
            ],
            "lobby_url": str(summary.get("lobby_url") or ""),
            "spectate_url": str(summary.get("spectate_url") or ""),
        }
    return list(by_ref.values())


async def _finished_cards(
    interaction: discord.Interaction,
    me_ids: set[str],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Build the FINISHED cards - only the INTERESTING matches.

    A match displays only when it truly ended AND its winner came
    back (owner 2026-11-22): a capture without a completion time is a
    game that started and never ended on record, a finished capture
    without winners is a result we never read - both stay invisible
    rather than lie.
    """
    from botforge.discord.stats_views import recent_match_entries

    entries = await recent_match_entries(sorted(me_ids), limit=limit)
    cards: list[dict[str, Any]] = []
    for entry in entries:
        finished_at = int(getattr(entry, "finished_at", 0) or 0)
        winners = tuple(getattr(entry, "winners", ()) or ())
        if not finished_at or not winners:
            continue
        cards.append(
            {
                "status": "finished",
                "match_id": str(getattr(entry, "match_id", "") or ""),
                "map_name": str(getattr(entry, "map_name", "") or ""),
                "lobby_title": str(getattr(entry, "description", "") or "").strip(),
                "description": str(getattr(entry, "description", "") or ""),
                "started_at": int(getattr(entry, "started_at", 0) or 0),
                "finished_at": finished_at,
                "winners": winners,
                "players": _entry_players_of(entry),
                "settings": _entry_settings_of(entry),
                "options_json": str(getattr(entry, "options_json", "") or ""),
            }
        )
    return cards


def _entry_players_of(entry: Any) -> list[dict[str, Any]]:
    """Parse the entry's players_json into seat dicts.

    Each seat carries the alias, the civ, the team and the
    pre/post ratings of the match.
    """
    import json as _json

    try:
        seats = _json.loads(getattr(entry, "players_json", "") or "[]")
    except Exception:
        return []
    return [dict(seat) for seat in seats if isinstance(seat, dict)]


async def _send_match_panels(
    interaction: discord.Interaction,
    me_ids: set[str],
    known_ids: set[str],
    labels: dict[str, Any],
) -> None:
    """Send the match cards: live/lobbies first, then the finished ones.

    ONE panel implementation for every status (owner 2026-11-22):
    lobbies, ongoing games and finished matches render the same card,
    the status only drives the badge, the duration, the buttons and
    the links.
    """
    cards = await _live_cards(interaction, me_ids)
    cards += await _finished_cards(interaction, me_ids)
    if not cards:
        await interaction.followup.send(await reply(interaction, "profile.matches_empty"), ephemeral=True)
        return
    ctx = await _match_panels_ctx(interaction, cards)
    for card in cards:
        view = _match_card_view(card, ctx, me_ids, labels)
        try:
            await interaction.followup.send(view=view, ephemeral=True)
        except Exception:
            logger.warning("the match panel send failed (%s)", card.get("match_id"), exc_info=True)
            return


class ProfileMatchesButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"home:profile:matches",
):
    """Show the accounts' last matches (ephemeral, 10 lines)."""

    def __init__(self, label: str = "Derniers matchs") -> None:
        super().__init__(
            discord.ui.Button(
                label=label,
                emoji="\U0001f3ae",
                style=discord.ButtonStyle.secondary,
                custom_id="home:profile:matches",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> ProfileMatchesButton:
        """Rebuild the item from the wire."""
        del interaction, item, match
        return cls()

    async def callback(self, interaction: discord.Interaction) -> None:
        """List the matches: live first (when any), then the last finished ones."""
        registration = getattr(interaction.client, "registration_service", None)
        if registration is None:
            await interaction.response.send_message(await reply(interaction, "not_configured"), ephemeral=True)
            return
        # the listing takes seconds (history fetch): the visible thinking
        # state first, never silent work
        await interaction.response.defer(ephemeral=True, thinking=True)
        bindings = await registration.list_bindings(str(interaction.user.id))
        me_ids = {str(b.get("profile_id", "")) for b in bindings if b.get("game_key") == "aoe2"}
        # the highlight contract (owner direction 2026-11-20): the viewed
        # profiles render bold, every other profile bound in this guild's
        # game renders italic — the server, not the match, decides ties
        known_ids: set[str] = set()
        try:
            for binding in await registration.list_bindings_for_game("aoe2"):
                known_ids.add(str(binding.get("profile_id", "")))
        except Exception:
            logger.debug("the guild-wide bindings read failed", exc_info=True)
        known_ids -= me_ids
        labels = {
            "team": await reply(interaction, "profile.matches_team"),
            "with": await reply(interaction, "profile.matches_with"),
            "join": await reply(interaction, "profile.matches_join"),
            "spectate": await reply(interaction, "profile.matches_spectate"),
            # every hardcoded panel word rides the locale (owner
            # 2026-11-22: the panels mixed untranslated fr and en)
            "when": await reply(interaction, "profile.matches_when"),
            "duration": await reply(interaction, "profile.matches_duration"),
            "source": await reply(interaction, "profile.matches_source"),
            "colours": {
                slot: await reply(interaction, f"profile.matches_colour_{slot}") for slot in SLOT_COLOURS
            },
            "settings": {
                plain: await reply(interaction, key) for plain, key in SETTING_LABEL_KEYS.items()
            },
            "setting_bools": {
                key: await reply(interaction, label_key) for key, label_key in SETTING_BOOLEANS.items()
            },
            "match_noun": await reply(interaction, "profile.match_noun"),
            "lobby_noun": await reply(interaction, "profile.lobby_noun"),
            "settings_button": await reply(interaction, "profile.matches_settings_button"),
            "settings_title": await reply(interaction, "profile.matches_settings_title"),
        }
        if not me_ids:
            await interaction.followup.send(
                await reply(interaction, "profile.matches_empty"), ephemeral=True
            )
            return
        await _send_match_panels(interaction, me_ids, known_ids, labels)


class ProfileRenameButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"home:profile:rename",
):
    """Open the rename modal (the user's chosen gamer name)."""

    def __init__(self, label: str = "Changer de pseudo") -> None:
        super().__init__(
            discord.ui.Button(
                label=label, emoji="\u270f", style=discord.ButtonStyle.secondary, custom_id="home:profile:rename"
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> ProfileRenameButton:
        """Rebuild the item from the wire."""
        del interaction, item, match
        return cls()

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the rename modal, prefilled with the current nickname."""
        import asyncio

        current = ""
        identity = getattr(interaction.client, "identity_service", None)
        if identity is not None:
            try:
                user = await asyncio.wait_for(identity.get_user(f"discord:{interaction.user.id}"), timeout=2.5)
                current = user.display_name if user is not None and user.display_name else ""
            except Exception:
                current = ""
        await interaction.response.send_modal(
            ProfileRenameModal(current, origin=EphemeralOrigin.capture(interaction))
        )


class ProfileSiteSelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]],
    template=r"home:profile:site:(?P<game>[a-z0-9]+)",
):
    """Pick the preferred profile site for a game (persisted per user).

    The sites come from ``config/games/<game>/profile_sites.yaml`` —
    the select is rebuilt from the registry at every profile render,
    so a config change shows up without a deploy.
    """

    def __init__(self, game_key: str, options: list[discord.SelectOption]) -> None:
        super().__init__(
            discord.ui.Select(
                placeholder="Preferred profile site",
                options=options,
                custom_id=f"home:profile:site:{game_key}",
            )
        )
        self.game_key = game_key

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> ProfileSiteSelect:
        """Rebuild the picker from the wire (registry options)."""
        game_key = str(match.group("game"))
        return cls(game_key, _site_options(interaction, game_key))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Persist the choice and re-render the profile in place."""
        data = getattr(interaction, "data", None) or {}
        values = [str(v) for v in data.get("values", [])]
        if not values:
            return
        await _set_user_preferred_site(interaction, self.game_key, values[0])
        await _profile_followup(
            interaction,
            banner=f"Preferred profile site: **{values[0]}**.",
        )


def _site_options(interaction: discord.Interaction, game_key: str) -> list[discord.SelectOption]:
    """Build the site options from the registry (current choice marked)."""
    from botforge.core.services.profile_sites import profile_sites_registry

    registry = profile_sites_registry()
    current = ""
    default = registry.default_site(game_key)
    options = [
        discord.SelectOption(
            label=site.label,
            value=site.key,
            default=(site.key == current) or (not current and default is not None and site.key == default.key),
        )
        for site in registry.sites_for(game_key)
    ]
    return options


class ProfileRenameModal(discord.ui.Modal):
    """The rename form: the user's chosen name (1-16 chars)."""

    def __init__(self, current: str = "", origin: Any = None) -> None:
        super().__init__(title="Ton pseudo", timeout=None)
        self.origin = origin
        self.name: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="Name (16 characters max)",
            max_length=16,
            min_length=1,
            required=True,
            default=current or None,
        )
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Persist the new name, confirm, then refresh the profile view."""
        identity = getattr(interaction.client, "identity_service", None)
        if identity is None:
            await interaction.response.send_message(await reply(interaction, "not_configured"), ephemeral=True)
            return
        user_id = f"discord:{interaction.user.id}"
        # the ONLY valid ephemeral modal defer (discord.py): thinking=True —
        # the bind takes seconds, the 3s window survives it
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            user = await identity.get_user(user_id)
            if user is None:
                user = await identity.get_or_create_user(
                    platform="discord",
                    platform_user_id=str(interaction.user.id),
                    display_name=str(interaction.user.display_name or interaction.user.name),
                )
            await identity.set_display_name(user.id, str(self.name.value))
        except ValueError:
            await interaction.followup.send(await reply(interaction, "profile.rename_bad_length"), ephemeral=True)
            return
        except Exception:
            logger.warning("PROFILE RENAME failed", exc_info=True)
            await interaction.followup.send(await reply(interaction, "profile.rename_failed"), ephemeral=True)
            return
        await _dm_profile_notice(interaction, "pseudo_updated", name=self.name.value)
        await _profile_followup(
            interaction,
            banner=await reply(interaction, "profile.rename_success", name=self.name.value),
            origin=self.origin,
        )


def _remove_options(bindings: list[dict[str, Any]]) -> list[discord.SelectOption]:
    """Build the remove modal's options: name + game + profile id."""
    options: list[discord.SelectOption] = []
    for b in bindings[:25]:
        profile = b.get("profile") or {}
        label = str(
            profile.get("display_name")
            or next(iter(profile.get("aliases") or []), None)
            or b.get("profile_id", "?")
        )[:100]
        options.append(
            discord.SelectOption(
                label=label,
                value=f"{b.get('game_key', '')}|{b.get('profile_id', '')}",
                description=f"{b.get('game_key', '?')} \u00b7 {b.get('profile_id', '?')}"[:100],
            )
        )
    return options


class ProfileRemoveAccountButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"home:profile:remove",
):
    """Open the remove-account modal (multi-select of the linked accounts)."""

    def __init__(self, label: str = "Retirer un compte") -> None:
        super().__init__(
            discord.ui.Button(
                label=label, emoji="\U0001F5D1", style=discord.ButtonStyle.danger, custom_id="home:profile:remove"
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> ProfileRemoveAccountButton:
        """Rebuild the item from the wire (bindings resolve at click time)."""
        del interaction, item, match
        return cls()

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the multi-select remove modal (accounts read fast, aoe2 cap)."""
        import asyncio

        registration = getattr(interaction.client, "registration_service", None)
        if registration is None:
            await interaction.response.send_message(await reply(interaction, "not_configured"), ephemeral=True)
            return
        try:
            bindings = await asyncio.wait_for(registration.list_bindings(str(interaction.user.id)), timeout=2.5)
        except Exception:
            bindings = []
        if not bindings:
            await interaction.response.send_message(await reply(interaction, "no_account"), ephemeral=True)
            return
        await interaction.response.send_modal(
            ProfileRemoveAccountModal(
                _remove_options(bindings), origin=EphemeralOrigin.capture(interaction)
            )
        )


class ProfileRemoveAccountModal(discord.ui.Modal):
    """The remove-account form: one multi-select of the linked accounts."""

    def __init__(self, options: list[discord.SelectOption], origin: Any = None) -> None:
        super().__init__(title="Retirer des comptes", timeout=None)
        self.origin = origin
        self.accounts: discord.ui.Select[Any] = discord.ui.Select(
            custom_id="home:profile:remove:select",
            options=options,
            placeholder="Comptes \u00e0 retirer...",
            min_values=1,
            max_values=len(options),
        )
        self.add_item(discord.ui.Label(text="Comptes \u00e0 retirer", component=self.accounts))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Unlink every chosen account, then refresh the profile view."""
        registration = getattr(interaction.client, "registration_service", None)
        if registration is None:
            await interaction.response.send_message(await reply(interaction, "not_configured"), ephemeral=True)
            return
        chosen = list(self.accounts.values or [])
        # the ONLY valid ephemeral modal defer (discord.py): thinking=True —
        # the bind takes seconds, the 3s window survives it
        await interaction.response.defer(ephemeral=True, thinking=True)
        removed: list[str] = []
        failures: list[str] = []
        for entry in chosen:
            game_key, _, profile_id = str(entry).partition("|")
            try:
                if await registration.unlink_profile(str(interaction.user.id), game_key, profile_id):
                    url = _game_account_url(game_key, str(profile_id))
                    removed.append(f"[{game_key} {profile_id}]({url})" if url else f"{game_key} (`{profile_id}`)")
                else:
                    failures.append(f"{game_key} `{profile_id}`")
                    await _report_profile_error(
                        interaction, "profile.remove", game_key, RuntimeError(f"binding not found: {entry}")
                    )
            except Exception as exc:
                failures.append(f"{game_key} `{profile_id}` ({type(exc).__name__})")
                await _report_profile_error(interaction, "profile.remove", game_key, exc)
        # ONE surface (owner direction, the view SDK): the result rides
        # the refreshed profile view's banner — no standalone followup
        # messages, the deferred thinking residue is cleaned by the
        # followup's origin edit
        banner_bits: list[str] = []
        if removed:
            listed = ", ".join(removed)
            banner_bits.append(await reply(interaction, "profile.accounts_removed", listed=listed))
        if failures:
            banner_bits.append(
                "Removal failed for: " + ", ".join(failures) + " — the details went to the admins."
            )
        if removed:
            await _dm_profile_notice(interaction, "accounts_removed", listed=", ".join(removed))
        banner = "\n".join(banner_bits)
        if not removed and not failures:
            banner = await reply(interaction, "profile.no_account")
        await _profile_followup(interaction, banner=banner, origin=self.origin)


async def _tree_channel_link(guild_id: str, scope: str, key: str) -> str:
    """Resolve one tree channel into a Discord mention (empty when unknown)."""
    from botforge.discord.ui.panels_provisioning import stored_channel_id

    channel_id = await stored_channel_id(guild_id, scope, key)
    return f"<#{channel_id}>" if channel_id else ""




async def _granted_games_with_counts(
    guild_id: str, fallback: tuple[str, ...]
) -> tuple[tuple[str, ...], dict[str, tuple[int, int, int]]]:
    """Read the guild's granted games with their catalog counts."""
    from botforge.discord.maps_forum import maps_forum_wiring_ready

    games = fallback
    counts: dict[str, tuple[int, int, int]] = {}
    if not maps_forum_wiring_ready():
        return games, counts
    try:
        from botforge.discord.admin_panel_games import _games_wiring
        from botforge.discord.wiring import granted_game_keys

        service = _games_wiring()
        if service is None:
            return games, counts
        games = await granted_game_keys(guild_id, tuple(await service.list_game_keys()))
        for key in games:
            civs = sum(1 for c in await service.list_factions(key) if c.archived_at is None)
            maps = sum(1 for m in await service.list_maps(key) if m.archived_at is None)
            pools = sum(1 for pl in await service.list_map_pools(key) if pl.archived_at is None)
            counts[key] = (civs, maps, pools)
    except Exception:
        logger.warning("GAMES VIEW failed to read the catalog", exc_info=True)
    return games, counts


async def _view_games_for_guild(interaction: discord.Interaction, guild_id: str) -> None:
    """Render the guild's games: one section per game, links, counts."""
    from botforge.discord.bot.factory import BotforgeBot

    bot = interaction.client
    await interaction.response.defer(ephemeral=True, thinking=False)
    games = bot.status_service.games() if isinstance(bot, BotforgeBot) else ()
    games, counts = await _granted_games_with_counts(guild_id, games)

    header = await reply(interaction, "profile.games_title")
    blocks: list[Any] = [
        discord.ui.TextDisplay(header + "\n" + await reply(interaction, "profile.games_subtitle")),
        discord.ui.Separator(),
    ]
    if not games:
        blocks.append(discord.ui.TextDisplay(await reply(interaction, "profile.games_none", admin_role="bot-admins")))
    if games:
        game_names = "\n".join(f"\u2022 **{_game_label(game)}**" for game in games[:25])
        blocks.append(
            discord.ui.TextDisplay(await reply(interaction, "profile.games_available") + "\n" + game_names)
        )
    for game in games[:25]:
        civs, maps, pools = counts.get(game, (0, 0, 0))
        general = await _tree_channel_link(guild_id, f"games/{game}", "general")
        civs_link = await _tree_channel_link(guild_id, f"games/{game}", "civs")
        maps_link = await _tree_channel_link(guild_id, f"games/{game}", "maps")
        pools_link = await _tree_channel_link(guild_id, f"games/{game}", "map-pools")
        lines = [f"## \u2694\ufe0f {game}"]
        stats = f"{civs} civs \u00b7 {maps} maps \u00b7 {pools} map pools"
        lines.append(stats)
        if general:
            lines.append(f"\u2022 {await reply(interaction, 'profile.general_label')} : {general}")
        if civs_link:
            lines.append(f"\u2022 {await reply(interaction, 'profile.civs_label')} : {civs_link}")
        if maps_link:
            lines.append(f"\u2022 {await reply(interaction, 'profile.maps_label')} : {maps_link}")
        if pools_link:
            lines.append(f"\u2022 {await reply(interaction, 'profile.pools_label')} : {pools_link}")
        blocks.append(discord.ui.Separator())
        blocks.append(discord.ui.TextDisplay("\n".join(lines)))
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.Container(*blocks, accent_colour=discord.Colour(0x5865F2)))
    await interaction.followup.send(view=view, ephemeral=True)


async def _view_live(interaction: discord.Interaction, game_key: str = "aoe2") -> None:
    """Render one game's live dashboard ephemerally (/live, the menu panel)."""
    await interaction.response.defer(ephemeral=True, thinking=False)
    view = await _build_live_view(interaction, game_key)
    await interaction.followup.send(view=view, ephemeral=True)


async def _build_live_view(
    interaction: discord.Interaction, game_key: str = "aoe2"
) -> Any:
    """Build the ephemeral live dashboard view (no defer, no send).

    Shared by /live, the menu button and the dashboard's refresh
    button (which already deferred): the caller owns the transport.
    """
    from botforge.discord.live import collect_profile_stats, render_dashboard

    snapshot: dict[str, Any] = {"players": [], "generated_at": 0, "degraded": True}
    client = _live_client_for(interaction.client, game_key)
    if client is not None:
        try:
            snapshot = await client.watch(game_key)
        except Exception:
            logger.warning("HOME: live snapshot failed (game %s)", game_key, exc_info=True)
    guild = interaction.client.get_guild(int(interaction.guild_id)) if interaction.guild_id else None
    if guild is not None:
        from botforge.discord.live import scope_snapshot_to_guild

        snapshot = await scope_snapshot_to_guild(snapshot, guild)
    active_ids = [
        str(p.get("profile_id", ""))
        for p in snapshot.get("players", [])
        if p.get("state") != "offline"
    ]
    stats = await collect_profile_stats(active_ids, game_key)
    from botforge.discord.content_posts import guild_locale

    locale = await guild_locale(str(interaction.guild_id), interaction.client)
    body = render_dashboard(snapshot, locale=locale, stats=stats, bot=interaction.client)
    from botforge.discord.live import build_dashboard_view

    # THE dashboard rendering (unified, owner direction): the same view
    # the pinned channel shows — Container + the id under it, one code path.
    view = build_dashboard_view(snapshot, body, interaction.client, locale=locale, game_key=game_key)
    return view


async def _view_mods_for_guild(interaction: discord.Interaction, guild_id: str) -> None:
    """Render the guild's mods (DM re-dispatch friendly: ack first, then read)."""
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    await interaction.followup.send(view=await _mods_layout(interaction.client, guild_id, interaction), ephemeral=True)


def _mod_visible_to(
    bot: Any, mod: str, user_id: str | None
) -> bool:
    """Whether a mod is visible to one user.

    Public mods always are; private mods only to their owners and the
    bot admins (click-time guards apply on top for actions).
    """
    registry = getattr(bot, "registry", None)
    definition = registry.enabled().get(mod) if registry is not None else None
    if definition is None or not definition.is_private():
        return True
    if not user_id:
        return False
    admins = set(getattr(getattr(bot, "status_service", None), "bot_admins", ()) or ())
    return str(user_id) in admins or definition.owned_by(str(user_id))


async def _mods_layout(
    bot: Any, guild_id: str, interaction: Any = None
) -> discord.ui.LayoutView:
    """Build the server's mods view: available mods, bullets, no doc line."""
    from botforge.discord.wiring import build_guild_access_service, guild_access_platform

    _, all_mods = guild_access_platform()
    granted: tuple[str, ...] = ()
    service = build_guild_access_service()
    if service is not None:
        try:
            granted = await service.enabled_mods(guild_id)
        except Exception:
            logger.warning("MODS VIEW access read failed", exc_info=True)
    if service is None:
        granted = tuple(all_mods)
    viewer = (
        str(getattr(interaction.user, "id", "") or "")
        if interaction is not None
        else None
    )
    # wired: the active set is the truth (empty = no mod installed — the
    # catalog forum installs them); unwired: open degradation to all
    visible = tuple(mod for mod in granted if _mod_visible_to(bot, mod, viewer))
    lines: list[str] = []
    for mod in visible[:25]:
        channels: list[str] = []
        general = await _tree_channel_link(guild_id, f"mods/{mod}", "general")
        if general:
            channels.append(general)
        admin = await _tree_channel_link(guild_id, f"mods/{mod}", "admin")
        if admin:
            channels.append(f"admin : {admin}")
        suffix = f" \u2014 {', '.join(channels)}" if channels else ""
        lines.append(f"\u2022 **{mod}**{suffix}")
    header = await reply(interaction, "profile.mods_title") if interaction is not None else "# \U0001f9e9 Mods"
    subtitle = (
        await reply(interaction, "profile.mods_subtitle") if interaction is not None else ""
    )
    body = header + ("\n" + subtitle if subtitle else "")
    if lines:
        available = (
            await reply(interaction, "profile.mods_available") if interaction is not None else "Mods disponibles :"
        )
        body += "\n\n" + available + "\n" + "\n".join(lines)
    else:
        none_note = (
            await reply(interaction, "profile.mods_none") if interaction is not None else "Aucun mod actif."
        )
        body += "\n\n" + none_note
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(body),
            accent_colour=discord.Colour(0x5865F2),
        )
    )
    return view


async def _collect_roster_bindings(bot: Any, guild_id: str) -> list[dict[str, Any]]:
    """Collect the bindings across every known game (deduplicated)."""
    roster = getattr(bot, "_registration_database", None)
    if roster is None:
        return []
    bindings: list[dict[str, Any]] = []
    try:
        from botforge.discord.admin_panel_games import _games_wiring
        from botforge.discord.wiring import granted_game_keys

        service = _games_wiring()
        catalog = tuple(await service.list_game_keys()) if service is not None else ()
        keys = await granted_game_keys(guild_id, catalog) if guild_id else catalog
        for key in keys[:5]:
            bindings.extend(await roster.list_bindings_for_game(key))
    except Exception:
        logger.warning("USERS VIEW catalog listing failed", exc_info=True)
    if not bindings:
        bindings = await roster.list_bindings_for_game("aoe2")
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for b in bindings:
        bid = str(b.get("_id", ""))
        if bid not in seen:
            seen.add(bid)
            unique.append(b)
    return unique


async def _is_guild_member(guild: Any, user_id: int) -> bool:
    """Return whether one user is a member of the guild (the cached roster).

    An unresolvable roster (empty fetch) accepts everyone — fail open:
    an API hiccup must never blank the roster panel.
    """
    from botforge.discord.member_cache import guild_members

    members = await guild_members(guild)
    if not members:
        return True
    return user_id in members


async def _view_users_for_guild(interaction: discord.Interaction, guild_id: str) -> None:
    """Render the guild's roster (DM re-dispatch friendly: ack first)."""
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True, thinking=False)
    bot = interaction.client
    roster = getattr(bot, "_registration_database", None)
    if roster is None:
        await interaction.followup.send(await reply(interaction, "profile.roster_unavailable"), ephemeral=True)
        return
    guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
    if guild is None:
        await interaction.followup.send(await reply(interaction, "profile.guild_not_found"), ephemeral=True)
        return
    unique = await _collect_roster_bindings(bot, guild_id)
    from collections import defaultdict


    by_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for binding in unique:
        user_id = str(binding.get("user_id", ""))
        if not user_id.isdigit() or not await _is_guild_member(guild, int(user_id)):
            continue
        by_member[user_id].append(binding)
    member_lines: list[str] = []
    # the pseudo rides the member cache (the chunked roster — the
    # guild's internal cache misses members it never saw)
    from botforge.discord.member_cache import guild_members

    cached_members = await guild_members(guild) if guild is not None else {}
    for user_id, bindings in list(by_member.items())[:25]:
        display = cached_members.get(int(user_id), "") if cached_members else ""
        header_name = display or f"<@{user_id}>"
        member_lines.append(f"## {header_name} \u2014 @{display or user_id}")
        for binding in bindings:
            profile = binding.get("profile") or {}
            aliases = [str(a) for a in (profile.get("aliases") or []) if str(a)]
            name = (
                str(profile.get("display_name") or profile.get("name") or "")
                or (aliases[0] if aliases else "")
                or "?"
            )
            pid = str(binding.get("profile_id", "?"))
            game = str(binding.get("game_key", "?"))
            url = _game_account_url(game, pid)
            account = f"[{name}]({url})" if url else name
            member_lines.append(f"\u2022 {account} (`{pid}`)")
    if not member_lines:
        await interaction.followup.send(await reply(interaction, "profile.no_members_bound"), ephemeral=True)
        return
    title = await reply(interaction, "profile.users_title", count=len(by_member))
    server_line = await reply(interaction, "profile.users_server", server=guild.name)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(f"{title}\n\n{server_line}\n\n" + "\n".join(member_lines)),
            accent_colour=discord.Colour(0x5865F2),
        )
    )
    await interaction.followup.send(view=view, ephemeral=True)


class LiveGamePicker(discord.ui.Modal):
    """The /live game picker: one select, the installed games.

    A modal (not a bare select response) per the owner's direction —
    the picker presents the games, the chosen game's dashboard renders
    ephemerally on submit.
    """

    def __init__(self, games: list[tuple[str, str]]) -> None:
        super().__init__(title="Live dashboard — pick a game")
        self._games = dict(games)
        self.game_select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder="Game",
            options=[
                discord.SelectOption(label=label, value=game_key)
                for game_key, label in games
            ],
        )
        self.add_item(self.game_select)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Render the chosen game's dashboard ephemerally."""
        game_key = self.game_select.values[0] if self.game_select.values else "aoe2"
        await _view_live(interaction, game_key)


def register_live_command(
    tree: app_commands.CommandTree[discord.Client],
    catalog: Any = None,
    games: tuple[str, ...] = ("aoe2",),
) -> None:
    """Register the /live command: pick a game, see its live dashboard.

    Generic (owner direction 2026-10-23): a modal + select lists the
    installed games; the chosen game's dashboard renders ephemerally.
    """

    @tree.command(
        name=localized("commands.live_name", "live"),
        description=localized(
            "commands.live_description",
            "Live dashboard: pick a game, see its linked players",
        ),
    )
    async def live_command(interaction: discord.Interaction) -> None:
        """Open the game picker modal."""
        options = [(game_key, _game_label(game_key)) for game_key in games]
        if len(options) == 1:
            await _view_live(interaction, options[0][0])
            return
        await interaction.response.send_modal(LiveGamePicker(options))

    del catalog


def _view_users_for_game(game_key: str) -> Any:
    """Build the players panel opener for one game (generic, per game).

    One line per registered member — pseudo, Discord mention, then
    every profile of that game as an aoe2insights link — sorted
    alphabetically by pseudo. The whole roster shows: the lines are
    paginated across as many ephemeral messages as the 4000-char V2
    text budget needs (no [:25] truncation).
    """

    async def _open(interaction: discord.Interaction) -> None:
        # thinking=True: the roster read takes seconds (the bindings +
        # the stats + the member roster) — the user sees the panel
        # building instead of a dead button (owner ask 2026-10-31)
        await interaction.response.defer(ephemeral=True, thinking=True)
        bot = interaction.client
        roster = getattr(bot, "_registration_database", None)
        if roster is None:
            await interaction.followup.send(await reply(interaction, "not_configured"), ephemeral=True)
            return
        import time as _t0

        _phase0 = _t0.monotonic()
        try:
            bindings = await roster.list_bindings_for_game(game_key)
        except Exception:
            logger.warning("PLAYERS PANEL roster read failed (%s)", game_key, exc_info=True)
            bindings = []

        from collections import defaultdict

        by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for binding in bindings:
            user_id = str(binding.get("user_id", "") or "")
            if user_id:
                by_user[user_id].append(binding)

        guild = bot.get_guild(int(interaction.guild_id)) if interaction.guild_id else None
        # guild-scoped: only the enrolled players who are MEMBERS of this
        # guild render (owner direction — the platform's roster, not the
        # game's global one)
        if guild is not None:
            member_ids = [
                user_id
                for user_id in by_user
                if await _is_guild_member(guild, int(user_id))
            ]
            by_user = {user_id: by_user[user_id] for user_id in member_ids}
        logger.info("PLAYERS PANEL: bindings %d in %dms", len(bindings), int((_t0.monotonic() - _phase0) * 1000))
        _phase1 = _t0.monotonic()
        profile_ids = [str(b.get("profile_id", "")) for bs in by_user.values() for b in bs]
        from botforge.discord.live import collect_profile_stats

        names = await collect_profile_stats(profile_ids, game_key)
        logger.info("PLAYERS PANEL: stats %d in %dms", len(names), int((_t0.monotonic() - _phase1) * 1000))
        _phase2 = _t0.monotonic()
        lines = await _roster_lines(game_key, by_user, guild, names, bot=bot)
        logger.info("PLAYERS PANEL: lines %d in %dms", len(lines), int((_t0.monotonic() - _phase2) * 1000))
        if not lines:
            lines = [await reply(interaction, "profile.no_members_bound")]
        for view in _roster_views(game_key, lines):
            await interaction.followup.send(view=view, ephemeral=True)

    return _open


async def _kingdoms_pseudos(bot: Any, by_user: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    """Resolve every user's kingdoms pseudo — ONE batched read.

    The chosen display name — the owner's ask: the roster shows the
    PSEUDO ('Merlin'), not the Discord account's display name. The
    users collection reads once with $in (the per-user loop was the
    panel's real bottleneck: one Mongo round-trip per enrolled user);
    empty map when the identity service is unwired, callers fall back.
    """
    identity = getattr(bot, "identity_service", None)
    pseudos: dict[str, str] = {}
    if identity is None or not by_user:
        return pseudos
    try:
        # ONE batched read (get_many_display_names): the per-user loop
        # was the panel's real bottleneck — one Mongo round-trip per
        # enrolled member. The keys strip the 'discord:' prefix back.
        resolved = await identity.get_many_display_names(
            [f"discord:{uid}" for uid in by_user]
        )
        for full_id, name in resolved.items():
            if full_id.startswith("discord:"):
                pseudos[full_id[len("discord:"):]] = name
        return pseudos
    except Exception:
        logger.debug("identity batched lookup failed — per-user fallback", exc_info=True)
    for user_id in by_user:
        try:
            user = await identity.get_user(f"discord:{user_id}")
        except Exception:
            logger.debug("identity lookup failed (user %s) — best-effort", user_id, exc_info=True)
            continue
        name = str(getattr(user, "display_name", "") or "")
        if name:
            pseudos[user_id] = name
    return pseudos




async def _roster_lines(
    game_key: str,
    by_user: dict[str, list[dict[str, Any]]],
    guild: Any,
    names: dict[str, dict[str, Any]] | None = None,
    bot: Any = None,
) -> list[str]:
    """One line per member (pseudo, mention, profile links), alphabetical by pseudo.

    A profile link's label is the profile's NAME — the binding's stored
    display name, else the provider-resolved alias (librematch identity),
    never the raw profile id.
    """
    names = names or {}
    from botforge.discord.member_cache import guild_members

    cached_members = await guild_members(guild) if guild is not None else {}
    kingdoms_pseudos = await _kingdoms_pseudos(bot, by_user)
    entries: list[tuple[str, str, str]] = []
    for user_id, user_bindings in by_user.items():
        # the label: the kingdoms PSEUDO first (the identity service's
        # chosen name — 'Merlin'), the Discord display name next, the
        # raw id last; the mention follows, always the same shape
        pseudo = (
            kingdoms_pseudos.get(user_id)
            or (cached_members.get(int(user_id), "") if cached_members else "")
            or f"user {user_id}"
        )
        mention = f"<@{user_id}>"
        profiles: list[str] = []
        for binding in user_bindings:
            # the link label: the stored name, else the provider-resolved
            # alias (passed through ``names``), never the raw profile id
            pid = str(binding.get("profile_id", "?"))
            profile = binding.get("profile") or {}
            stored = str(profile.get("profile_name") or "")
            alias = str((names.get(pid) or {}).get("display_name") or "")
            name = stored or alias or pid
            url = _game_account_url(game_key, pid)
            profiles.append(f"[{name}]({url})" if url else name)
        entries.append((pseudo or f"user {user_id}", mention, ", ".join(profiles)))
    entries.sort(key=lambda e: _casefold_key(e[0]))
    return [f"\u2022 **{pseudo}** \u2014 {mention}: {profiles}" for pseudo, mention, profiles in entries]


def _roster_views(game_key: str, lines: list[str]) -> list[Any]:
    """Build the roster's V2 views: one per page of the character budget."""
    from botforge.core.ids import footer

    header = f"# \U0001F465 {_game_label(game_key)}\n\n"
    view_id = f"panel:game:{game_key}:players"
    budget = 4000 - len(header) - len(footer(view_id)) - 64
    pages = _paginate_lines(lines, budget)
    views: list[Any] = []
    from botforge.discord.ui.view_footer import add_view_footer

    for page_index, page in enumerate(pages):
        title = header
        if len(pages) > 1:
            title += f"*({page_index + 1}/{len(pages)})*\n\n"
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(title + page),
                accent_colour=discord.Colour(0x5865F2),
            )
        )
        views.append(add_view_footer(view, view_id))
    return views


def _casefold_key(text: str) -> str:
    """Sort key that ignores case and diacritics (pseudo alphabetical order)."""
    import unicodedata

    stripped = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in stripped if not unicodedata.combining(ch)).casefold()


def _paginate_lines(lines: list[str], budget: int) -> list[str]:
    """Split lines into pages that each fit the character budget."""
    pages: list[str] = []
    current: list[str] = []
    used = 0
    for line in lines:
        cost = len(line) + 1
        if current and used + cost > budget:
            pages.append("\n".join(current))
            current = []
            used = 0
        current.append(line)
        used += cost
    if current:
        pages.append("\n".join(current))
    return pages or [""]


async def open_home_view_for_guild(interaction: discord.Interaction, view_key: str, guild_id: str) -> None:
    """Re-dispatch a declared view with an explicit guild scope (DM pick).

    The DM guild picker re-dispatches a view on a chosen guild; the
    declared router owns the resolution (the legacy view keys map
    through the same table as the home buttons).
    """
    from botforge.discord.views_routing import open_declared_view

    await open_declared_view(interaction, _LEGACY_VIEW_KEYS.get(view_key, view_key))


async def _view_admin_for_guild(interaction: discord.Interaction, guild_id: str) -> None:
    """Open the new admin menu ephemerally, guarded at click time."""
    from botforge.discord.guards import require_admin

    bot = interaction.client
    admins = tuple(getattr(getattr(bot, "status_service", None), "bot_admins", ()) or ())
    if not await require_admin(interaction, admins, getattr(bot, "roles_service", None)):
        return
    from botforge.discord.admin_tree import build_admin_menu

    logs = getattr(bot, "logs_service", None)
    locale = "en"
    if logs is not None:
        try:
            locale = str(await logs.get_locale(guild_id) or "en")
        except Exception:
            locale = "en"
    await interaction.response.send_message(view=await build_admin_menu(guild_id, locale), ephemeral=True)


async def _view_mod(interaction: discord.Interaction, mod: str) -> None:
    """Route to a mod's home view builder (private mods: owners/admins)."""
    bot = interaction.client
    viewer = str(getattr(interaction.user, "id", "") or "")
    if not _mod_visible_to(bot, mod, viewer):
        await interaction.response.send_message(await reply(interaction, "no_home_view"), ephemeral=True)
        return
    builder = getattr(bot, "mod_home_builders", {}).get(mod)
    if builder is None:
        await interaction.response.send_message(await reply(interaction, "no_home_view"), ephemeral=True)
        return
    await builder(interaction)


async def _resolve_menu_message_id(bot: discord.Client, guild_id: str) -> str | None:
    """Resolve the registered menu id (registry first, memory fallback)."""
    registry = getattr(bot, "message_registry", None)
    if registry is not None:
        try:
            registered = await registry.resolve(HOME_MESSAGE_PLATFORM, HOME_MESSAGE_KEY, guild_id)
            if registered is None:
                registered = await registry.resolve(
                    HOME_MESSAGE_PLATFORM, HOME_MESSAGE_LEGACY_KEY, guild_id
                )
            if registered is not None:
                return str(registered.message_id)
        except Exception:
            logger.warning("PINNED HOME MENU registry resolve failed - best-effort")
    store = getattr(bot, "_home_menu_message_ids", None)
    if isinstance(store, dict):
        value = store.get(guild_id)
        return str(value) if value is not None else None
    return None


async def _register_menu_message(bot: discord.Client, guild_id: str, channel_id: str, message_id: str) -> None:
    """Persist the new menu id: memory fallback + registry (durable)."""
    store = getattr(bot, "_home_menu_message_ids", None)
    if not isinstance(store, dict):
        store = {}
        bot._home_menu_message_ids = store  # type: ignore[attr-defined]
    store[guild_id] = message_id
    registry = getattr(bot, "message_registry", None)
    if registry is None:
        return
    try:
        await registry.register(
            platform=HOME_MESSAGE_PLATFORM,
            message_key=HOME_MESSAGE_KEY,
            entity_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            guild_id=guild_id,
        )
    except Exception:
        logger.warning("PINNED HOME MENU registry register failed - best-effort")


def register_home_command(
    tree: app_commands.CommandTree[discord.Client],
    home: HomeService,
    catalog: MessageCatalog | None = None,
) -> None:
    """Register the /home slash command and the persistent home buttons."""

    @tree.command(
        name=localized("commands.home_name", "home"),
        description=localized("commands.home_description", "The guild's home menu"),
    )
    async def home_command(interaction: discord.Interaction) -> None:
        """Answer /home with the declared home menu (ephemeral, localized)."""
        from botforge.discord.views_routing import open_declared_view

        await open_declared_view(interaction, "menu:home")


