"""The install/uninstall catalogs: one post per game, one per mod (botforge-services#374).

TWO forums, two perimeters, the same logic: the games catalog (the
``games`` scope's ``catalog`` channel) carries one post per declared
game; the mods catalog (the ``mods`` scope's ``catalog`` channel)
carries one post per declared mod. The posts are built from the
declarations and carry their state (installed or not) and the actions:

- **Install**: the item joins the guild's active set (the required
  games ride along — the service's rules).
- **Uninstall**: a modal with the data choice — keep the mod's data
  (a reinstall restores the state) or delete it (the ``<mod>:``
  namespace wipe). A game an active mod requires is refused with the
  dependents named.

The posts are idempotent: the sync (boot + the mods Synchroniser)
creates the missing ones and refreshes the existing ones — stored
thread ids under ``mod_catalog_posts``, the same resolution contract
as the maps forum. The norm: the post view carries its id footer, the
actions are guarded at click time (bot admin), every string renders
in the guild's locale.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord

logger = logging.getLogger("botforge.discord.mods_forum")

CATALOG_POSTS_COLLECTION = "mod_catalog_posts"
CATALOG_CHANNEL_KEY = "catalog"

# one catalog per perimeter: the kind decides the tree scope and the items
CATALOG_SCOPES: dict[str, str] = {"game": "games", "mod": "mods"}

_NS = "modcatalog"

_INSTALL_TEMPLATE = rf"{_NS}:install:(?P<kind>game|mod):(?P<name>[a-z0-9_-]+)"
_UNINSTALL_TEMPLATE = rf"{_NS}:uninstall:(?P<kind>game|mod):(?P<name>[a-z0-9_-]+)"


def _catalog_post_id(guild_id: str, kind: str, name: str) -> str:
    """Return the bookkeeping document id for one catalog post."""
    return f"{guild_id}:{kind}:{name}"


async def _catalog_forum_id(guild_id: str, kind: str) -> str | None:
    """Resolve one catalog forum's stored id (the provisioning owns creation)."""
    from botforge.discord.ui.panels_provisioning import stored_channel_id

    stored = await stored_channel_id(guild_id, CATALOG_SCOPES[kind], CATALOG_CHANNEL_KEY)
    return str(stored) if stored and str(stored).isdigit() else None


def _build_service(bot: Any) -> Any | None:
    """Build the install service over the wired seams; None unwired."""
    from botforge.core.services.mod_install import ModInstallService
    from botforge.discord.wiring import build_guild_access_service

    access = build_guild_access_service()
    registry = getattr(bot, "registry", None)
    if access is None or registry is None:
        return None
    try:
        from botforge.core.models.db import get_async_database

        database = get_async_database()
    except Exception:
        database = None
    return ModInstallService(access, registry, database=database)


async def _tr(bot: Any, guild_id: str, key: str, fallback: str) -> str:
    """Render one catalog string in the guild's locale (en fallback)."""
    from botforge.discord.scope_pins import _catalog, _locale_of, _tr

    return _tr(_catalog(bot), f"mods.forum.{key}", await _locale_of(bot, guild_id), fallback)


def _catalog_post_view(
    kind: str,
    name: str,
    installed: bool,
    required_games: tuple[str, ...] = (),
    labels: dict[str, str] | None = None,
) -> discord.ui.LayoutView:
    """Build one catalog post: the state, the actions, the id footer."""
    labels = labels or {}
    view = discord.ui.LayoutView(timeout=None)
    status = labels.get("installed" if installed else "not_installed", "")
    blocks: list[Any] = [
        discord.ui.TextDisplay(f"# {labels.get('title', name)}"),
        discord.ui.TextDisplay(status),
    ]
    if required_games:
        blocks.append(discord.ui.TextDisplay(f"{labels.get('requires', 'Requires')}: {', '.join(required_games)}"))
    view.add_item(discord.ui.Container(*blocks, accent_colour=discord.Colour(0x5865F2)))
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    if installed:
        row.add_item(ModUninstallButton(kind, name, label=labels.get("uninstall", "Uninstall")))
    else:
        row.add_item(ModInstallButton(kind, name, label=labels.get("install", "Install")))
    view.add_item(row)
    from botforge.discord.ui.view_footer import add_view_footer

    return add_view_footer(view, f"modcatalog:post:{kind}:{name}")


async def _stored_post_ids(guild_id: str) -> dict[str, str]:
    """Return the stored thread ids of a guild's catalog posts (id -> thread)."""
    from botforge.core.models.db import get_async_database

    database = get_async_database()
    out: dict[str, str] = {}
    async for doc in database[CATALOG_POSTS_COLLECTION].find({"guild_id": guild_id}):
        out[str(doc["_id"])] = str(doc.get("thread_id") or "")
    return out


async def _create_post(
    bot: Any,
    guild_id: str,
    forum_id: str,
    kind: str,
    name: str,
    view: discord.ui.LayoutView,
) -> str | None:
    """Create one catalog post in ITS perimeter's forum (game→games, mod→mods)."""
    """Create one catalog post; return its thread id (None on failure)."""
    guild = bot.get_guild(int(guild_id))
    forum = guild.get_channel(int(forum_id)) if guild is not None else None
    if guild is None or forum is None:
        return None
    try:
        thread = await forum.create_thread(
            name=name[:90],
            reason=f"botforge: mods catalog post {name}",
            silent=True,
            view=view,
        )
    except discord.HTTPException:
        logger.warning("mods forum: post creation failed for %s %s — best-effort", kind, name, exc_info=True)
        return None
    from botforge.core.models.db import get_async_database

    post_id = _catalog_post_id(guild_id, kind, name)
    await get_async_database()[CATALOG_POSTS_COLLECTION].update_one(
        {"_id": post_id},
        {"$set": {"guild_id": guild_id, "kind": kind, "name": name, "thread_id": str(thread.id)}},
        upsert=True,
    )
    return str(thread.id)


async def _refresh_post(
    bot: Any,
    guild_id: str,
    thread_id: str,
    view: discord.ui.LayoutView,
) -> bool:
    """Edit one catalog post's starter message; False when the thread is gone."""
    guild = bot.get_guild(int(guild_id))
    thread = guild.get_thread(int(thread_id)) if guild is not None else None
    if thread is None:
        return False
    try:
        message = await thread.fetch_message(thread.id)
        await message.edit(view=view)
    except discord.HTTPException:
        logger.warning("mods forum: post refresh failed (thread %s) — best-effort", thread_id, exc_info=True)
        return False
    return True


async def _sync_one_catalog(guild_id: str, bot: Any, kind: str) -> int:
    """Sync ONE catalog: its forum, its items, refreshed in place."""
    service = _build_service(bot)
    if service is None:
        return 0
    forum_id = await _catalog_forum_id(guild_id, kind)
    if forum_id is None:
        return 0  # the provisioning owns creation; nothing stored yet
    from botforge.discord.wiring import guild_access_platform

    all_games, all_mods = guild_access_platform()
    items = all_games if kind == "game" else all_mods
    status = await service.status(guild_id)
    installed_set = set(status.get(f"{kind}s") or ())
    registry = getattr(bot, "registry", None)

    async def _labels(installed: bool) -> dict[str, str]:
        return {
            "title": "",
            "installed": await _tr(bot, guild_id, "installed", "Installed"),
            "not_installed": await _tr(bot, guild_id, "not_installed", "Not installed"),
            "requires": await _tr(bot, guild_id, "requires", "Requires"),
            "install": await _tr(bot, guild_id, "install_btn", "Install"),
            "uninstall": await _tr(bot, guild_id, "uninstall_btn", "Uninstall"),
        }

    stored = await _stored_post_ids(guild_id)
    changed = 0
    for name in items:
        required: tuple[str, ...] = ()
        if kind == "mod" and registry is not None:
            definition = registry.get(name)
            required = tuple(getattr(definition, "required_games", ()) or ()) if definition else ()
        labels = await _labels(name in installed_set)
        view = _catalog_post_view(kind, name, name in installed_set, required, labels)
        post_id = _catalog_post_id(guild_id, kind, name)
        thread_id = stored.get(post_id, "")
        if thread_id and await _refresh_post(bot, guild_id, thread_id, view):
            changed += 1
            continue
        if await _create_post(bot, guild_id, forum_id, kind, name, view):
            changed += 1
    return changed


async def sync_catalogs(guild_id: str, bot: Any) -> int:
    """Sync both catalogs: the games' and the mods' — two perimeters, one pass."""
    return await _sync_one_catalog(guild_id, bot, "game") + await _sync_one_catalog(guild_id, bot, "mod")


async def _guard(interaction: discord.Interaction) -> bool:
    """Guard the catalog actions: bot-admin only, checked at click time."""
    from botforge.discord.guards import require_admin

    bot = interaction.client
    admins = tuple(getattr(getattr(bot, "status_service", None), "bot_admins", ()) or ())
    denied = await _tr(
        bot,
        str(interaction.guild_id or ""),
        "admin_only",
        "The catalog actions are reserved for bot admins.",
    )
    return await require_admin(
        interaction, admins, getattr(bot, "roles_service", None), denied_message=denied
    )


class ModInstallButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=re.compile(_INSTALL_TEMPLATE),
):
    """One catalog post's Install button (guarded at click time)."""

    def __init__(self, kind: str, name: str, label: str = "Install") -> None:
        self.kind = kind
        self.name = name
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                style=discord.ButtonStyle.success,
                custom_id=f"{_NS}:install:{kind}:{name}"[:100],
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> ModInstallButton:
        """Rebuild the item from the wire."""
        del interaction, item
        return cls(match["kind"], match["name"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Install the item; the service's rules apply (deps ride along)."""
        if not await _guard(interaction):
            return
        service = _build_service(interaction.client)
        if service is None:
            return
        kwargs: dict[str, tuple[str, ...]] = {f"{self.kind}s": (self.name,)}
        result = await service.install(str(interaction.guild_id), **kwargs)
        if not result.ok:
            await interaction.response.send_message(
                (
                await _tr(
                    interaction.client, str(interaction.guild_id or ""), "refused",
                    "Refused: {reason}",
                )
            ).format(reason=result.summary),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            await _tr(interaction.client, str(interaction.guild_id or ""), "installed_done", "Installed."),
            ephemeral=True,
        )
        await sync_catalogs(str(interaction.guild_id), interaction.client)


class ModUninstallButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=re.compile(_UNINSTALL_TEMPLATE),
):
    """One catalog post's Uninstall button — opens the data-choice modal."""

    def __init__(self, kind: str, name: str, label: str = "Uninstall") -> None:
        self.kind = kind
        self.name = name
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                style=discord.ButtonStyle.danger,
                custom_id=f"{_NS}:uninstall:{kind}:{name}"[:100],
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> ModUninstallButton:
        """Rebuild the item from the wire."""
        del interaction, item
        return cls(match["kind"], match["name"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the uninstall modal (the data choice is explicit)."""
        if not await _guard(interaction):
            return
        await interaction.response.send_modal(
            await ModUninstallModal.build(interaction, self.kind, self.name)
        )


class ModUninstallModal(discord.ui.Modal):
    """The uninstall modal: keep the data or delete it — explicit, never a default."""

    DATA_KEEP, DATA_DELETE = "keep", "delete"

    @classmethod
    async def build(cls, interaction: discord.Interaction, kind: str, name: str) -> ModUninstallModal:
        """Build the modal with the guild's locale (en fallback)."""
        bot = interaction.client
        guild_id = str(interaction.guild_id or "")

        async def tr(key: str, fallback: str) -> str:
            return await _tr(bot, guild_id, key, fallback)

        return cls(
            kind=kind,
            name=name,
            title=(await tr("uninstall_modal_title", "Uninstall {item}")).format(item=name)[:45],
            label=(await tr("uninstall_modal_label", "Data"))[:45],
            opt_keep=await tr("opt_keep", "Keep the data (a reinstall restores the state)"),
            opt_delete=await tr("opt_delete", "Delete the data (the mod's own collections)"),
            done=await tr("uninstalled_done", "Uninstalled."),
            refused=await tr("refused", "Refused: {reason}"),
        )

    def __init__(
        self,
        *,
        kind: str,
        name: str,
        title: str,
        label: str,
        opt_keep: str,
        opt_delete: str,
        done: str,
        refused: str,
    ) -> None:
        super().__init__(title=title, timeout=600.0)
        self.kind = kind
        self.name = name
        self.done = done
        self.refused = refused
        self.data_select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder=label[:100],
            min_values=0,
            max_values=1,
            required=False,
            options=[
                discord.SelectOption(label=opt_keep[:100], value=self.DATA_KEEP),
                discord.SelectOption(label=opt_delete[:100], value=self.DATA_DELETE),
            ],
        )
        self.add_item(discord.ui.Label(text=label, component=self.data_select))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Apply the uninstall with the stated data choice."""
        if not await _guard(interaction):
            return
        wipe = self.data_select.values and self.data_select.values[0] == self.DATA_DELETE
        service = _build_service(interaction.client)
        if service is None:
            return
        kwargs: dict[str, Any] = {f"{self.kind}s": (self.name,), "wipe_data": wipe}
        result = await service.uninstall(str(interaction.guild_id), **kwargs)
        if not result.ok:
            await interaction.response.send_message(
                self.refused.format(reason=result.summary), ephemeral=True
            )
            return
        await interaction.response.send_message(self.done, ephemeral=True)
        await sync_catalogs(str(interaction.guild_id), interaction.client)


def register_mods_forum_items(bot: discord.Client) -> None:
    """Register the catalog's DynamicItems (called at every startup)."""
    bot.add_dynamic_items(ModInstallButton, ModUninstallButton)


def register_catalog_syncs() -> None:
    """Register the catalogs' syncs per scope (the Synchroniser's contract).

    The games scope's Synchroniser re-syncs the games catalog, the mods
    scope's the mods catalog — the channels are provisioned first, the
    posts follow in the same pass (the boot alone cannot: the channels
    do not exist yet on a virgin guild).
    """
    from botforge.discord.scope_surfaces import register_scope_sync

    async def _sync_games(guild_id: str, bot: Any) -> int:
        return await _sync_one_catalog(guild_id, bot, "game")

    async def _sync_mods(guild_id: str, bot: Any) -> int:
        return await _sync_one_catalog(guild_id, bot, "mod")

    register_scope_sync("games", _sync_games)
    register_scope_sync("mods", _sync_mods)


__all__ = [
    "ModInstallButton",
    "ModUninstallButton",
    "ModUninstallModal",
    "register_catalog_syncs",
    "register_mods_forum_items",
    "sync_catalogs",
]
