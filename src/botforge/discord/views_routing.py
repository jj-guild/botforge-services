"""The view routing: declared view ids -> the handlers that open them.

Two wire conventions across every menu, both driven by the
registry (``config/views.yaml``):

- ``view:open:<view id>`` — navigation: the router opens the wired
  handler (ephemeral); an undeclared id answers with the
  unknown-view reply, never a silent failure;
- ``view:act:<view id>:<action id>`` — behavior: the router runs the
  action handler wired at boot (``wire_action``); an unwired action
  answers with the not-wired reply (and renders disabled).

Adding a view or an action means declaring it in the YAML and wiring
its handler — the menus pick both up mechanically.

Adding a view means: declaring it (``views_declared``), documenting
it (docs/DEVELOPMENT/VIEWS.md), and wiring its handler here — the
menus pick it up mechanically.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

import discord

from botforge.discord.views_registry import get_view

logger = logging.getLogger("botforge.discord.views_routing")

ROUTER_NS = "view:open"
BUTTON_TEMPLATE = re.compile(rf"{ROUTER_NS}:(?P<view_id>[a-z0-9:_-]+)")

Handler = Callable[[discord.Interaction], Awaitable[None]]


async def open_declared_view(interaction: discord.Interaction, view_id: str) -> None:
    """Open a declared view by id (ephemeral), unknown ids answered.

    A wired panel runs its handler; a menu (no handler — menus only
    navigate) builds from the registry and answers directly. Only
    an id that is neither wired nor declared answers "unknown view".
    """
    handler = _HANDLERS.get(view_id)
    if handler is not None:
        await handler(interaction)
        return
    if get_view(view_id) is not None:
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        builder = build_declared_menu(interaction.client, view_id)
        await interaction.response.defer(ephemeral=True, thinking=False)
        await interaction.followup.send(view=await builder(guild_id), ephemeral=True)
        return
    from botforge.discord.commands_i18n import reply

    await interaction.response.send_message(await reply(interaction, "unknown_view"), ephemeral=True)


def wire_view(view_id: str, handler: Handler) -> None:
    """Wire one declared view's handler (idempotent, last wins)."""
    _HANDLERS[view_id] = handler


def wired_views() -> tuple[str, ...]:
    """Return the wired view ids (diagnostics, tests)."""
    return tuple(sorted(_HANDLERS))


_HANDLERS: dict[str, Handler] = {}
_ACTION_HANDLERS: dict[str, Handler] = {}
ACT_NAMESPACE = "view:act"


def wire_action(view_id: str, action_id: str, handler: Handler) -> None:
    """Wire one declared action's handler (idempotent, last wins)."""
    _ACTION_HANDLERS[f"{view_id}:{action_id}"] = handler


def wired_actions() -> tuple[str, ...]:
    """Return the wired action keys (diagnostics, tests)."""
    return tuple(sorted(_ACTION_HANDLERS))


def action_is_wired(view_id: str, action_id: str) -> bool:
    """Whether a declared action has a handler."""
    return f"{view_id}:{action_id}" in _ACTION_HANDLERS


async def run_declared_action(interaction: discord.Interaction, view_id: str, action_id: str) -> None:
    """Run a declared action's handler; unwired actions answered."""
    handler = _ACTION_HANDLERS.get(f"{view_id}:{action_id}")
    if handler is None:
        from botforge.discord.commands_i18n import reply

        await interaction.response.send_message(
            await reply(interaction, "not_configured"), ephemeral=True
        )
        return
    await handler(interaction)


class ActionButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{ACT_NAMESPACE}:(?P<view_id>[a-z0-9:_-]+):(?P<action_id>[a-z0-9_-]+)",
):
    """One declared action button: runs its wired handler at click time.

    An action declared but not wired renders disabled (never dead):
    the builder checks ``action_is_wired`` before enabling it.
    """

    def __init__(self, view_id: str, action_id: str, label: str, emoji: str = "", disabled: bool = False) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{ACT_NAMESPACE}:{view_id}:{action_id}"[:100],
                label=label,
                emoji=discord.PartialEmoji.from_str(emoji) if emoji else None,
                style=discord.ButtonStyle.secondary,
                disabled=disabled,
            )
        )
        self.view_id = view_id
        self.action_id = action_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> ActionButton:
        """Rebuild the action button from the wire."""
        del interaction
        button = item if isinstance(item, discord.ui.Button) else None
        label = (button.label if button is not None else None) or "?"
        emoji = button.emoji.name if button is not None and isinstance(button.emoji, discord.PartialEmoji) else ""
        return cls(match["view_id"], match["action_id"], label, emoji)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Run the declared action (guarded actions guard themselves)."""
        await run_declared_action(interaction, self.view_id, self.action_id)


class ViewOpenButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{ROUTER_NS}:(?P<view_id>[a-z0-9:_-]+)",
):
    """One menu button: opens its declared target view at click time.

    Admin targets render with the padlock emoji and the most discreet
    style Discord offers (secondary, same as every menu button — the
    padlock alone carries the admin marker).
    """

    def __init__(self, view_id: str, label: str, emoji: str = "", disabled: bool = False) -> None:
        from botforge.discord.views_registry import ADMIN_EMOJI

        super().__init__(
            discord.ui.Button(
                custom_id=f"{ROUTER_NS}:{view_id}"[:100],
                label=label,
                emoji=discord.PartialEmoji.from_str(emoji) if emoji else None,
                style=discord.ButtonStyle.secondary,
                disabled=disabled,
            )
        )
        self.view_id = view_id
        self._admin_emoji = ADMIN_EMOJI

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> ViewOpenButton:
        """Rebuild the button from the wire (label kept from the item)."""
        del interaction
        button = item if isinstance(item, discord.ui.Button) else None
        label = (button.label if button is not None else None) or "?"
        emoji = button.emoji.name if button is not None and isinstance(button.emoji, discord.PartialEmoji) else ""
        return cls(match["view_id"], label, emoji)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the declared target view (guarded views guard themselves)."""
        await open_declared_view(interaction, self.view_id)


def register_view_router(bot: discord.Client) -> None:
    """Register the router's DynamicItems (every startup)."""
    bot.add_dynamic_items(ViewOpenButton)
    bot.add_dynamic_items(ActionButton)


LOCALE_LABELS = {"en": "\U0001F1EC\U0001F1E7 English", "fr": "\U0001F1EB\U0001F1F7 Fran\u00e7ais"}


class LanguageModal(discord.ui.Modal):
    """The language picker modal (guild or DM scope).

    One labelled select, applied on submit: the stored choice wins
    over every Discord signal (a non-Community server has no language
    setting at all), the pins refresh in the chosen language.
    """

    def __init__(self, title: str, guild_scoped: bool, current: str = "") -> None:
        super().__init__(title=title[:45], timeout=None)
        self.guild_scoped = guild_scoped
        options = [
            discord.SelectOption(label=label, value=code, default=code == current)
            for code, label in LOCALE_LABELS.items()
        ]
        placeholder = LOCALE_LABELS.get(current) or next(iter(LOCALE_LABELS.values()))
        self._select: discord.ui.Select[Any] = discord.ui.Select(
            custom_id=f"{ACT_NAMESPACE}:language-select",
            options=options,
            placeholder=placeholder,
        )
        self.add_item(discord.ui.Label(text=placeholder, component=self._select))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Persist the choice, refresh, confirm."""
        from botforge.discord.commands_i18n import reply

        value = ""
        for item in self.walk_children():
            select = getattr(item, "item", None) or item
            if isinstance(select, discord.ui.Select):
                value = str(select.values[0]) if select.values else ""
                break
        if not value:
            await interaction.response.defer(ephemeral=True)
            return
        logs = getattr(interaction.client, "logs_service", None)
        if logs is None:
            await interaction.response.send_message(
                await reply(interaction, "not_configured"), ephemeral=True
            )
            return
        try:
            if self.guild_scoped and interaction.guild_id:
                await logs.set_locale(
                    str(interaction.guild_id), value, by=str(interaction.user.id)
                )
            else:
                await logs.set_user_locale(str(interaction.user.id), value)
        except Exception:
            import logging

            logging.getLogger("botforge.views").warning(
                "language set failed", exc_info=True
            )
            await interaction.response.defer(ephemeral=True)
            return
        # Ack FIRST: the pin refresh is a slow cascade (provisioning reads),
        # and an exception inside it must never eat the modal's answer
        # (the 2026-10-20 Unknown interaction: the refresh crashed on a
        # category channel, the ack never landed).
        # the confirmation renders in the NEWLY CHOSEN language (a DM
        # user switching to English must read "Language updated.", not
        # the previous locale's wording)
        from botforge.core.services.i18n import MessageCatalog

        catalog = getattr(interaction.client, "messages", None) or MessageCatalog("config")
        key = "replies.admin_replies.language_changed"
        rendered = catalog.render(key, value)
        if rendered == key:
            rendered = catalog.render("admin_replies.language_changed", value)
        await interaction.response.send_message(rendered, ephemeral=True)
        if self.guild_scoped and interaction.guild_id:
            await _rerender_guild_surfaces(interaction)
        if not self.guild_scoped:
            await _rerender_dm_menu(interaction)


__all__ = [
    "ACT_NAMESPACE",
    "BUTTON_TEMPLATE",
    "ActionButton",
    "ViewOpenButton",
    "action_is_wired",
    "open_declared_view",
    "register_view_router",
    "run_declared_action",
    "wire_action",
    "wire_view",
    "wired_actions",
    "wired_views",
]




async def _rerender_dm_menu(interaction: discord.Interaction) -> None:
    """Re-render the user's pinned admin DM menu (their language changed)."""
    import logging

    try:
        from botforge.discord.admin_dm_panel import refresh_user_dm_menu

        await refresh_user_dm_menu(interaction.client, str(interaction.user.id))
    except Exception:
        logging.getLogger("botforge.views").warning(
            "DM menu refresh after language change failed — best-effort", exc_info=True
        )


async def _rerender_guild_surfaces(interaction: discord.Interaction) -> None:
    """Re-render the guild's pins and forums after a language change.

    The pins re-read their labels and the posts their per-locale
    content — best-effort, the answer already landed.
    """
    import logging

    from botforge.discord.pinned_views import refresh_registered_pins

    guild_id = str(interaction.guild_id)
    try:
        await refresh_registered_pins(guild_id)
    except Exception:
        logging.getLogger("botforge.views").warning(
            "pin refresh after language change failed — best-effort", exc_info=True
        )
    try:
        from botforge.core.services.entity_forum import forget_layout_renders
        from botforge.discord.scope_surfaces import run_scope_syncs

        forget_layout_renders()
        await run_scope_syncs(guild_id, interaction.client, "games")
    except Exception:
        logging.getLogger("botforge.views").warning(
            "forum re-render after language change failed — best-effort", exc_info=True
        )

async def _stored_locale(bot: Any, guild_id: str) -> str:
    """Resolve the guild's stored language (the picker's value)."""
    logs = getattr(bot, "logs_service", None)
    if logs is not None and guild_id:
        try:
            stored = str(await logs.get_locale(guild_id) or "")
            if stored in ("en", "fr"):
                return LOCALE_LABELS.get(stored, stored)
        except Exception:
            return "?"
    from botforge.discord.locales import guild_locale_by_id

    return LOCALE_LABELS.get(guild_locale_by_id(bot, guild_id), "?")


def _tr_line(catalog: Any, key: str, locale: str, current: str) -> str:
    """Render the current-language line (en fallback, raw fallback)."""
    rendered = str(catalog.render(key, locale, current=current))
    if rendered == key:
        rendered = str(catalog.render(key, "en", current=current))
    if rendered == key:
        rendered = f"**Language:** {current}"
    return rendered


def menu_buttons(decl: Any, catalog: Any, locale: str) -> list[discord.ui.Button[Any]]:
    """Build a declared view's buttons (labels i18n, admin/sync emojis).

    A menu button opens another view (``view:open:<target>``); a sync
    button carries the ensure custom id; an action button (a menu's
    declared action, e.g. "add a map") is not routable and therefore
    disabled unless its real handler wired it — kept here for the
    layout so the doc's menus render exactly as declared.
    """
    from botforge.discord.views_registry import default_button_emoji

    out: list[discord.ui.Button[Any]] = []
    for button in decl.buttons:
        emoji = button.emoji or default_button_emoji(button)
        item: Any
        if button.target:
            item = ViewOpenButton(button.target, _label(catalog, button.label_key, locale), emoji, button.disabled)
        elif button.sync:
            import re as _re

            # a MOD admin menu's repair button provisions the MOD's own
            # folder (mod/<name>: its declared channels + roles), not the
            # platform's mods scope
            _mod_admin = _re.match(r"^menu:mod:(?P<name>[a-z0-9_-]+):admin$", decl.id)
            if _mod_admin:
                from botforge.discord.mods_forum import ModRepairButton

                item = ModRepairButton(
                    _mod_admin["name"],
                    _label(catalog, button.label_key, locale) or "Repair channels & roles",
                )
                out.append(item)
                continue
            from botforge.discord.admin_tree import TreeEnsureButton

            # the sync re-provisions the declared tree scope (the folder),
            # never the pin channel — the pin scope ends with "/admin" or
            # "/general", which the tree does not declare
            scope = decl.scope.rsplit("/", 1)[0] if decl.scope and "/" in decl.scope else (decl.scope or "bot")
            # the bot menu also owns the guild's root channels (general,
            # discussions): no other scope covers them
            if decl.id == "menu:admin":
                scope = f"{scope},root"
            item = TreeEnsureButton(
                scope, _label(catalog, button.label_key, locale) or "Sync now"
            )
        elif button.action:
            item = ActionButton(
                decl.id,
                button.action,
                _label(catalog, button.label_key, locale),
                emoji,
                disabled=button.disabled or not action_is_wired(decl.id, button.action),
            )
        else:
            item = discord.ui.Button(
                label=_label(catalog, button.label_key, locale),
                emoji=discord.PartialEmoji.from_str(emoji) if emoji else None,
                style=discord.ButtonStyle.secondary,
                disabled=True,
            )
        out.append(item.item if isinstance(item, ViewOpenButton) else item)
    return out


def _label(catalog: Any, key: str, locale: str, fallback: str = "?") -> str:
    if catalog is None or not key:
        return fallback
    rendered = catalog.render(key, locale)
    return rendered if rendered != key else fallback


async def _clickable_image_entries(
    bot: Any,
    guild_id: str,
    view_id: str,
    catalog: Any,
    locale: str,
) -> list[Any]:
    """Build the home menus' clickable-image blocks (#334).

    An installed item whose declaration carries an ``image`` renders as
    a link wrapping the image (``[![alt](image)](target)`` — a Discord
    markdown link around an embedded image): the click jumps to the
    item's channel. The items without art keep their button.
    """
    import discord

    from botforge.discord.ui.panels_provisioning import stored_channel_id
    from botforge.discord.wiring import build_guild_access_service

    if view_id not in ("menu:games:home", "menu:mods:home"):
        return []
    access = build_guild_access_service()
    if view_id == "menu:games:home":
        entries = await _game_image_entries(bot, guild_id, catalog, locale, access)
    else:
        entries = await _mod_image_entries(bot, guild_id, catalog, locale, access)
    blocks: list[Any] = []
    for _name, label, image, scope in entries:
        # a components-v2 TextDisplay cannot embed a markdown image —
        # the valid pattern is a SECTION: the image rides the Thumbnail
        # accessory, the title carries the markdown LINK (the click
        # target); the merlin finding (the nested [![]()] renders raw)
        channel_id = await stored_channel_id(guild_id, scope, "general")
        if channel_id and str(channel_id).isdigit():
            target = f"https://discord.com/channels/{guild_id}/{channel_id}"
            blocks.append(
                discord.ui.Section(
                    discord.ui.TextDisplay(f"**[{label}]({target})**"),
                    accessory=discord.ui.Thumbnail(image),
                )
            )
        else:
            blocks.append(
                discord.ui.Section(
                    discord.ui.TextDisplay(f"**{label}**"),
                    accessory=discord.ui.Thumbnail(image),
                )
            )
    return blocks


async def _game_image_entries(
    bot: Any,
    guild_id: str,
    catalog: Any,
    locale: str,
    access: Any,
) -> list[tuple[str, str, str, str]]:
    """Collect the installed games' (name, label, image, scope) with art."""
    from botforge.discord.mods_forum import load_game_declarations
    from botforge.discord.scope_pins import _tr

    installed: set[str] = set()
    if access is not None:
        try:
            installed = set(await access.enabled_games(guild_id))
        except Exception:
            logger.warning("clickable images: the state unreadable", exc_info=True)
    game_decls = load_game_declarations(
        getattr(getattr(bot, "config", None), "config_dir", None) or "config"
    )
    out: list[tuple[str, str, str, str]] = []
    for game_key in sorted(installed):
        image = str((game_decls or {}).get(game_key, {}).get("image", "") or "")
        if image:
            label = _tr(catalog, f"ui.games.{game_key}.name", locale, game_key)
            out.append((game_key, label, image, f"games/{game_key}"))
    return out


async def _mod_image_entries(
    bot: Any,
    guild_id: str,
    catalog: Any,
    locale: str,
    access: Any,
) -> list[tuple[str, str, str, str]]:
    """Collect the installed mods' (name, label, image, scope) with art."""
    from botforge.discord.scope_pins import _tr

    installed: set[str] = set()
    if access is not None:
        try:
            installed = set(await access.enabled_mods(guild_id))
        except Exception:
            logger.warning("clickable images: the state unreadable", exc_info=True)
    registry = getattr(bot, "registry", None)
    out: list[tuple[str, str, str, str]] = []
    for mod_name in sorted(installed):
        definition = registry.get(mod_name) if registry is not None else None
        image = str(getattr(definition, "image", "") or "") if definition is not None else ""
        if image:
            label = _tr(catalog, f"ui.mods.homes.{mod_name}", locale, mod_name)
            out.append((mod_name, label, image, f"mod/{mod_name}"))
    return out


async def _auto_entries(
    bot: Any,
    guild_id: str,
    view_id: str,
    catalog: Any,
    locale: str,
) -> list[Any]:
    """Build the auto-injected entry buttons of a home/admin menu.

    menu:mods:home lists the INSTALLED mods; menu:mods:admin their
    admin surfaces; the games' home/admin mirror them — an item
    without its button is simply not installed: NOTHING grayed, no
    planned placeholders (owner direction 2026-11-13).
    """
    from botforge.discord.wiring import build_guild_access_service, guild_access_platform

    if view_id not in ("menu:mods:home", "menu:mods:admin", "menu:games:home", "menu:games:admin"):
        return []
    from botforge.discord.scope_pins import _tr

    registry = getattr(bot, "registry", None)
    access = build_guild_access_service()
    all_games, _all_mods = guild_access_platform()
    installed_games: set[str] = set()
    installed_mods: set[str] = set()
    if access is not None:
        try:
            installed_games = set(await access.enabled_games(guild_id))
            installed_mods = set(await access.enabled_mods(guild_id))
        except Exception:
            logger.warning("auto entries: the installed state unreadable — best-effort", exc_info=True)
    out: list[Any] = []
    from botforge.discord.mods_forum import load_game_declarations

    game_decls: dict[str, dict[str, Any]] = dict(
        load_game_declarations(getattr(getattr(bot, "config", None), "config_dir", None) or "config")
    )
    if view_id in ("menu:games:home", "menu:games:admin"):
        admin = view_id == "menu:games:admin"
        for game_key in all_games:
            if game_key not in installed_games:
                continue  # not installed on this guild: no button at all
            target = f"menu:game:{game_key}:admin" if admin else f"menu:games:{game_key}"
            label = _tr(catalog, f"ui.games.{game_key}.name", locale, game_key)
            # the emoji rides the declaration (#334: the visual identity is
            # data, never hardcoded)
            emoji = str((game_decls or {}).get(game_key, {}).get("emoji", "") or "")
            out.append(ViewOpenButton(target, label, emoji))
        return out
    admin = view_id == "menu:mods:admin"
    for mod_name in (registry.enabled() if registry is not None else ()):
        if mod_name not in installed_mods:
            continue  # not installed on this guild: no button at all
        target = f"menu:mod:{mod_name}:admin" if admin else f"menu:mod:{mod_name}"
        label = _tr(catalog, f"ui.mods.homes.{mod_name}", locale, mod_name)
        definition = registry.get(mod_name) if registry is not None else None
        emoji = str(getattr(definition, "emoji", "") or "") if definition is not None else ""
        out.append(ViewOpenButton(target, label, emoji))
    return out


def build_declared_menu(bot: Any, view_id: str) -> Any:  # noqa: C901
    """Build a declared menu's layout: title, description, buttons, footer.

    The single menu builder: every declared menu renders through it,
    so the layout rules (i18n, admin/sync emojis, view id footer,
    channel notice) live in one place and every menu follows.
    """
    import discord


    decl = get_view(view_id)
    if decl is None:
        raise KeyError(f"undeclared view {view_id!r} — declare it in views_declared")

    async def _build(guild_id: str) -> discord.ui.LayoutView:

        from botforge.discord.scope_pins import _catalog, _locale_of, _tr, _tree_notice

        catalog = _catalog(bot)
        locale = await _locale_of(bot, guild_id)
        prefix = "ui.views." + view_id.replace(":", ".")
        title = _tr(catalog, f"{prefix}.title", locale, view_id)
        description = _tr(catalog, f"{prefix}.description", locale)
        view = discord.ui.LayoutView(timeout=None)
        # the mod menus' STANDARD content (#378/#379): every mod's home
        # and admin render their declaration's presentation — a mod gets
        # its surfaces for free
        from botforge.discord.mod_standard import mod_standard_blocks

        standard_blocks = await mod_standard_blocks(bot, guild_id, view_id, _tr)
        header = f"# {title}"
        # the SDK constraint: an admin surface ALWAYS carries the open
        # padlock in its header (one glance tells the operator where they
        # stand) — declared per view never again, admin_surface decides
        title_emoji = "🔓" if getattr(decl, "admin_surface", False) else getattr(
            decl, "title_emoji", ""
        )
        if title_emoji:
            header = f"{header} {title_emoji}"
        blocks: list[Any] = [discord.ui.TextDisplay(header)]
        if description:
            blocks.append(discord.ui.TextDisplay(description))
        blocks.extend(standard_blocks)
        # the CLICKABLE IMAGES (#334): on the home menus, an installed
        # item with a declared image renders as an image wrapped in a
        # LINK (a click jumps to the item's channel) — the entry IS the
        # image; the items without art keep their button
        blocks.extend(await _clickable_image_entries(bot, guild_id, view_id, catalog, locale))
        # only the menus that carry the language picker state the current
        # language: the operator sees what they are about to switch
        if any(button.action == "set-language" for button in decl.buttons):
            current = await _stored_locale(bot, guild_id)
            blocks.append(
                discord.ui.TextDisplay(
                    _tr_line(catalog, f"ui.views.{view_id.replace(':', '.')}.current_language", locale, current)
                )
            )
        # the pin scope is the channel ("games/general" or "games/aoe2/admin");
        # the tree scope is the folder ("games", "games/aoe2") — every menu
        # carries its scope's notice (the homes AND the admin surfaces)
        tree_scope = decl.scope.split("/general")[0].split("/admin")[0] if decl.scope else ""
        notice = await _tree_notice(guild_id, tree_scope, catalog, locale, bot=bot) if tree_scope else ""
        if notice:
            blocks.append(discord.ui.TextDisplay(notice))
        # an admin surface reads red: one glance tells the operator where they stand
        accent = discord.Colour(0xE74C3C) if getattr(decl, "admin_surface", False) else discord.Colour(0x5865F2)
        view.add_item(discord.ui.Container(*blocks, accent_colour=accent))
        row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        for button in menu_buttons(decl, catalog, locale):
            row.add_item(button)
        # the AUTO-INJECTED entries (#377): the mods/games home and admin
        # menus list every item with its LIVE install state — installed
        # ones enabled, the rest grayed. The dev declares NOTHING; the
        # platform lists (the dev is constrained, not trusted).
        for button in await _auto_entries(bot, guild_id, decl.id, catalog, locale):
            row.add_item(button)
        # a menu with NO buttons sends no row: Discord rejects an empty
        # action row (50035 "Must be between 1 and 5 in length") — the
        # placeholder mod menus (kingdom until its portage) stay renderable
        if len(row.children) > 0:
            view.add_item(row)
        # The dev console rides the declared admin menu (the pin AND the
        # ephemeral home→admin both render this builder): test guilds only
        # (the allowlist), the button's own guards re-check every click.
        if view_id == "menu:admin":
            from botforge.discord.console import AdminConsoleButton
            from botforge.discord.console_guilds import is_test_guild

            if is_test_guild(guild_id):
                console_row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
                console_row.add_item(AdminConsoleButton())
                view.add_item(console_row)
        from botforge.discord.ui.view_footer import add_view_footer

        return add_view_footer(view, view_id)

    return _build
