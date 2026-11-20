"""Panels provisioning: apply the channel-tree rules to a guild.

The declarative counterpart of the SDK: the scopes registered at
boot (games, mods, their games/mods) are provisioned here —
categories with slash names, channels in the canonical order,
guild-locale naming, read-only menu channels, admin channels for
the bot-admins. Idempotent and heal-safe: the resolution matches
channels by their stable registry keys (never by the translated
displayed name), so a rename heals to the right channel.

The heavy lifting (create, overwrites, position) reuses the
existing channels platform — this module only owns the tree rules.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import discord

from botforge.discord.ui.panels import ChannelDecl, ScopeSpec, registered_scopes

logger = logging.getLogger("botforge.discord.panels_provisioning")

_POSITION_BANDS = {
    "general": 0,
    "discussions": 1,
    "data": 2,
    "admin": 3,
    "decisions": 4,
}


def _band(decl: ChannelDecl) -> int:
    """Return the canonical position band of one channel declaration."""
    if decl.key == "general":
        return _POSITION_BANDS["general"]
    if decl.key == "discussions":
        return _POSITION_BANDS["discussions"]
    if decl.key == "admin":
        return _POSITION_BANDS["admin"]
    if decl.key == "decisions":
        return _POSITION_BANDS["decisions"]
    return _POSITION_BANDS["data"]


def _sorted_channels(spec: ScopeSpec) -> tuple[ChannelDecl, ...]:
    """Sort a scope's channels into the canonical order."""
    return tuple(sorted(spec.channels, key=lambda c: (_band(c), c.position or 0, c.key)))


class _Platform:
    """Thin idempotent create-if-missing over the raw guild."""

    def __init__(self, guild: discord.Guild) -> None:
        self._guild = guild

    def _category(self, category_id: str) -> discord.CategoryChannel | None:
        """Return the category channel (typed), None when absent."""
        if not category_id.isdigit():
            return None
        channel = self._guild.get_channel(int(category_id))
        if isinstance(channel, discord.CategoryChannel):
            return channel
        return None

    async def ensure_category(self, name: str) -> str:
        """Return the category id, creating it when missing."""
        category = discord.utils.get(self._guild.categories, name=name)
        if category is not None:
            return str(category.id)
        created = await self._guild.create_category(name, reason="botforge: panels provisioning")
        return str(created.id)

    async def ensure_channel(self, name: str, category_id: str) -> str:
        """Return the text channel id, creating it when missing."""
        category = self._category(category_id)
        # category-scoped FIRST (two scopes may declare the same channel
        # NAME — the games and mods catalogs are both "catalogue": a
        # name match in ANOTHER folder is not this channel); a stray
        # channel with no folder is still ADOPTED (moved into place)
        channel = discord.utils.get(
            self._guild.text_channels, name=name, category=(category or None)
        ) or discord.utils.get(
            self._guild.text_channels, name=name, category=None
        )
        if channel is not None:
            if category is not None and channel.category_id != category.id:
                try:
                    await channel.edit(category=category, reason="botforge: panels provisioning (adopt)")
                except discord.HTTPException:
                    logger.warning(
                        "panels provisioning: moving %s into its folder failed — kept in place",
                        name,
                        exc_info=True,
                    )
            return str(channel.id)
        created = await self._guild.create_text_channel(
            name, category=category, reason="botforge: panels provisioning"
        )
        return str(created.id)

    async def reorder_channels(self, category_id: str, ordered_ids: list[str]) -> None:
        """Apply a category's declared channel order to the Discord sidebar.

        Discord lists a category's channels by their STORED position —
        a channel adopted by name or a legacy rename keeps the position
        history gave it, so the sidebar can contradict the declared
        tree. The provisioning's canonical order is the contract: each
        pass re-pins the resolved ids to their declared index (a move
        only when the position already differs — idempotent).
        """
        if self._category(category_id) is None:
            return
        for index, channel_id in enumerate(ordered_ids):
            if not channel_id.isdigit():
                continue
            channel = self._guild.get_channel(int(channel_id))
            if channel is None:
                continue
            if getattr(channel, "position", None) == index:
                continue
            try:
                await channel.edit(
                    position=index,
                    reason="botforge: panels provisioning (the declared order)",
                )
            except discord.HTTPException:
                logger.warning(
                    "panels provisioning: reordering %s at index %s failed — best-effort",
                    channel_id,
                    index,
                    exc_info=True,
                )

    async def ensure_forum(self, name: str, category_id: str) -> str:
        """Return the forum id, creating it when missing."""
        category = self._category(category_id)
        # category-scoped first (see ensure_channel); a stray forum is
        # still adopted (moved into its folder)
        forum = discord.utils.get(
            self._guild.forums, name=name, category=(category or None)
        ) or discord.utils.get(self._guild.forums, name=name, category=None)
        if forum is not None:
            if category is not None and forum.category_id != category.id:
                try:
                    await forum.edit(category=category, reason="botforge: panels provisioning (adopt)")
                except discord.HTTPException:
                    logger.warning(
                        "panels provisioning: moving %s into its folder failed — kept in place",
                        name,
                        exc_info=True,
                    )
            return str(forum.id)
        created = await self._guild.create_forum(
            name, category=category, reason="botforge: panels provisioning"
        )
        return str(created.id)


async def _apply_access(guild: discord.Guild, channel_id: str, decl: ChannelDecl) -> None:
    """Apply the channel's access band (overwrites, best-effort).

    The bot's own member always carries an explicit allow (view, send,
    manage) — without it a ``view_channel=False`` for @everyone locks
    the bot out of the very channel it provisioned, and every surface
    (pins, syncs, dashboards) degrades with 403s.
    """
    channel = guild.get_channel(int(channel_id)) if channel_id.isdigit() else None
    if channel is None:
        return
    try:
        me = guild.me
        if me is not None:
            await channel.set_permissions(
                me,
                overwrite=discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    manage_threads=True,
                    read_message_history=True,
                    embed_links=True,
                    attach_files=True,
                ),
                reason="botforge: the bot operates its own channel",
            )
        policy = getattr(decl, "policy", None)
        if policy is not None:
            # the DECLARED policy (the salons-as-data gating, #216
            # tranche I): @everyone's view is data, the view roles are
            # data — the roles resolve by their provisioned display
            # name (the mod's roles are provisioned from the same
            # declaration)
            if not getattr(policy, "everyone_view", True):
                await channel.set_permissions(
                    guild.default_role,
                    overwrite=discord.PermissionOverwrite(view_channel=False),
                    reason="botforge: the declared policy gates @everyone",
                )
            # the view roles ride as RESOLVED IDS (the persisted
            # mapping is the resolver — a renamed role keeps its grant;
            # never a name lookup at apply time)
            for role_id in getattr(decl, "view_role_ids", ()) or ():
                role = guild.get_role(int(role_id)) if str(role_id).isdigit() else None
                if role is None:
                    logger.warning(
                        "panels provisioning: the view role id %r is not resolved — skipped",
                        role_id,
                    )
                    continue
                await channel.set_permissions(
                    role,
                    overwrite=discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=not getattr(policy, "everyone_post", False),
                        read_message_history=True,
                    ),
                    reason="botforge: the declared policy grants the view role",
                )
        elif decl.access == "readonly":
            overwrite = discord.PermissionOverwrite(send_messages=False, add_reactions=True)
            await channel.set_permissions(
                guild.default_role, overwrite=overwrite, reason="botforge: readonly menu channel"
            )
        elif decl.access == "admin":
            overwrite = discord.PermissionOverwrite(view_channel=False)
            await channel.set_permissions(
                guild.default_role, overwrite=overwrite, reason="botforge: admin channel"
            )
    except Exception:
        logger.warning(
            "panels provisioning: access apply failed (%s) — best-effort",
            decl.key,
            exc_info=True,
        )


async def _ensure_scope_category(
    guild: discord.Guild,
    platform: _Platform,
    scope: str,
    name: str,
) -> str:
    """Resolve (or create) the scope's category by stored id, then name.

    The stored id wins: a label refresh (an emoji added to the label)
    renames the category in place — never a duplicate. Without a
    stored id the name resolves or creates, and the caller persists.
    """
    stored = await stored_channel_id(str(guild.id), scope, "category")
    if stored and stored.isdigit():
        category = guild.get_channel(int(stored))
        if isinstance(category, discord.CategoryChannel):
            if category.name != name:
                await category.edit(name=name, reason="botforge: panels provisioning (label refresh)")
            return stored
    return await platform.ensure_category(name)


def _category_matches(channel: Any, category_id: str) -> bool:
    """Whether a live channel lives in the scope's declared folder.

    A scope without a category (the guild root) accepts anything; a
    scoped channel found in ANOTHER folder is not this scope's channel
    (the merlin case: the mods catalog's stored id pointed at the
    games forum — a valid forum, in the wrong folder).
    """
    if not category_id:
        return True
    return str(getattr(channel, "category_id", "") or "") == category_id


def _kind_matches(channel: Any, kind: str) -> bool:
    """Whether a live channel's Discord type matches the declared kind."""
    import discord

    if kind == "forum":
        return isinstance(channel, discord.ForumChannel)
    if kind == "text":
        return isinstance(channel, discord.TextChannel) and not isinstance(channel, discord.ForumChannel)
    return True


async def _decl_category(
    guild: discord.Guild,
    platform: _Platform,
    spec: ScopeSpec,
    decl: ChannelDecl,
    category_id: str,
    group_categories: dict[str, str],
    resolved: dict[str, str],
    group_view_roles: dict[str, tuple[str, ...]] | None = None,
) -> str:
    """Resolve one channel's category: its declared group's, or the scope's.

    The group categories are created lazily (once per group) and ride
    the resolved dict — ``persist_resolutions`` stores them under
    ``tree:<scope>:cat:<group>``. A group declared admin-only gates its
    category (bot allow + @everyone deny + the group's view roles).
    """
    group_name = str(getattr(decl, "group", "") or "")
    if not group_name:
        return category_id
    channel_category = group_categories.get(group_name, "")
    if not channel_category:
        channel_category = await _ensure_group_category(
            guild,
            platform,
            spec.scope,
            group_name,
            admin_only=bool(getattr(decl, "group_admin_only", False)),
            view_role_ids=tuple((group_view_roles or {}).get(group_name, ())),
        )
        group_categories[group_name] = channel_category
        resolved[f"cat:{group_name}"] = channel_category
    return channel_category


async def _ensure_group_category(
    guild: discord.Guild,
    platform: _Platform,
    scope: str,
    group_name: str,
    admin_only: bool = False,
    view_role_ids: tuple[str, ...] = (),
) -> str:
    """Resolve (or create) one GROUP category of a scope (the mods' structure).

    Stored under ``cat:<group>`` inside the scope — the group's
    channels keep their own resolution keys; a label refresh renames
    in place, never a duplicate. A group declared admin-only carries
    the gate on its category (bot allow + @everyone deny + view roles),
    exactly like a gated scope category.
    """
    storage_key = f"cat:{group_name}"
    category_id = ""
    stored = await stored_channel_id(str(guild.id), scope, storage_key)
    if stored and stored.isdigit():
        category = guild.get_channel(int(stored))
        if isinstance(category, discord.CategoryChannel):
            if category.name != group_name:
                await category.edit(
                    name=group_name, reason="botforge: panels provisioning (label refresh)"
                )
            category_id = stored
    if not category_id:
        for category in guild.categories:
            if category.name == group_name:
                category_id = str(category.id)
                break
    if not category_id:
        category_id = await platform.ensure_category(group_name)
    if admin_only and category_id:
        await _apply_category_access(guild, category_id, view_role_ids)
    return category_id


async def _apply_category_access(
    guild: discord.Guild, category_id: str, view_role_ids: tuple[str, ...] = ()
) -> None:
    """Apply the scope category's gate (the machine-room rule, best-effort).

    The bot's own member always carries an explicit allow — without it
    the category's ``view_channel=False`` for @everyone locks the bot
    out of the folder it provisioned (the same lesson as the channels).
    The view roles ride as RESOLVED IDS (the persisted mapping is the
    resolver — a renamed role keeps its grant).
    """
    category = guild.get_channel(int(category_id)) if category_id.isdigit() else None
    if category is None:
        return
    try:
        me = guild.me
        if me is not None:
            await category.set_permissions(
                me,
                overwrite=discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    manage_threads=True,
                    # without manage_channels on the category a private
                    # folder locks the bot out of creating/purging the
                    # rooms inside it (the console's blocker, #413)
                    manage_channels=True,
                    read_message_history=True,
                ),
                reason="botforge: the bot operates its own category",
            )
        await category.set_permissions(
            guild.default_role,
            overwrite=discord.PermissionOverwrite(view_channel=False),
            reason="botforge: the declared category gate hides @everyone",
        )
        for role_id in view_role_ids or ():
            role = guild.get_role(int(role_id)) if str(role_id).isdigit() else None
            if role is None:
                logger.warning(
                    "panels provisioning: the category view role id %r is not resolved — skipped",
                    role_id,
                )
                continue
            await category.set_permissions(
                role,
                overwrite=discord.PermissionOverwrite(
                    view_channel=True, read_message_history=True
                ),
                reason="botforge: the declared category gate grants the view role",
            )
    except Exception:
        logger.warning(
            "panels provisioning: the category gate apply failed — best-effort",
            exc_info=True,
        )


def _group_view_role_map(spec: ScopeSpec) -> dict[str, tuple[str, ...]]:
    """Map each declared group to the union of its channels' view role ids."""
    out: dict[str, tuple[str, ...]] = {}
    for decl in spec.channels:
        gname = str(getattr(decl, "group", "") or "")
        if gname:
            out[gname] = tuple(
                dict.fromkeys(
                    out.get(gname, ()) + tuple(getattr(decl, "view_role_ids", ()) or ())
                )
            )
    return out


async def _restore_category_access(guild: discord.Guild, category_id: str) -> None:
    """Remove a category's gate overwrites (back to normal rights).

    The uninstall counterpart of the gate: @everyone's deny and the
    bot's explicit allow are both dropped — the folder returns to the
    guild's default permissions.
    """
    category = guild.get_channel(int(category_id)) if category_id.isdigit() else None
    if category is None:
        return
    try:
        await category.set_permissions(
            guild.default_role,
            overwrite=None,
            reason="botforge: restore normal rights (mod uninstalled)",
        )
        me = guild.me
        if me is not None:
            await category.set_permissions(
                me, overwrite=None, reason="botforge: restore normal rights (mod uninstalled)"
            )
    except Exception:
        logger.warning(
            "panels provisioning: the category gate restore failed — best-effort",
            exc_info=True,
        )


def _category_label_names(spec: ScopeSpec) -> set[str]:
    """Render a scope's category label in every locale — the name fallback.

    The stored id is the primary resolution, but a guild provisioned
    before its ids were persisted (or with an unwired Mongo at the
    time) has live categories with NO stored id — the translated name
    (fr and en renders of the declared category key) finds them.
    """
    names: set[str] = set()
    try:
        from botforge.core.services.i18n import MessageCatalog
        from botforge.core.services.mod_layout import default_repo_root

        root = default_repo_root()
        if root is None:
            return names
        catalog = MessageCatalog(str(root / "config"))
        for locale in ("fr", "en"):
            rendered = str(catalog.render(spec.category_key, locale))
            if rendered and rendered != spec.category_key:
                names.add(rendered)
    except Exception:
        logger.warning(
            "panels provisioning: category label render failed (scope %s) — stored ids only",
            spec.scope,
            exc_info=True,
        )
    return names


async def _platform_category_candidates(guild: discord.Guild, spec: ScopeSpec) -> list[str]:
    """Resolve one platform scope's category ids: stored id first, then name.

    The name fallback (the fr/en renders of the declared category key)
    covers guilds whose ids were never persisted — the Kingdoms - Tests
    case: the categories exist, the stored ids are missing.
    """
    candidates: list[str] = []
    stored = await stored_channel_id(str(guild.id), spec.scope, "category")
    if stored and str(stored).isdigit():
        candidates.append(str(stored))
    for name in _category_label_names(spec):
        category = discord.utils.get(guild.categories, name=name)
        if category is not None:
            candidates.append(str(category.id))
    return list(dict.fromkeys(candidates))


async def set_platform_categories_private(guild: discord.Guild, private: bool) -> int:
    """Gate (or restore) every PLATFORM scope's category — the install rule.

    Installing a mod makes the bot's own folders staff-only (the
    machine-room rule extended: while a mod is installed, the platform
    plumbing hides from players — the mod's declared categories carry
    their own permissions). Uninstalling the last mod restores the
    normal (public) rights. Mod scopes (``mod/<name>``) are never
    touched here — they keep their own declared gates. Returns how many
    categories were touched.
    """
    touched = 0
    seen: set[str] = set()
    for spec in registered_scopes():
        if spec.scope.startswith("mod/") or not spec.category_key:
            continue
        candidates = await _platform_category_candidates(guild, spec)
        view_role_ids = tuple(getattr(spec, "category_view_role_ids", ()) or ())
        for category_id in candidates:
            if category_id in seen:
                continue
            category = guild.get_channel(int(category_id)) if category_id.isdigit() else None
            if not isinstance(category, discord.CategoryChannel):
                continue
            seen.add(category_id)
            if private:
                await _apply_category_access(guild, category_id, view_role_ids)
            else:
                await _restore_category_access(guild, category_id)
            touched += 1
    return touched


async def provision_scope(
    guild: discord.Guild,
    spec: ScopeSpec,
    locale: str,
    translate: Callable[[str, str], str],
) -> dict[str, str]:
    """Provision one scope folder; return key -> channel id.

    ``translate`` renders a label key in the guild's locale
    (``MessageCatalog.render``-shaped callable).
    """
    platform = _Platform(guild)
    resolved: dict[str, str] = {}
    category_id = ""
    if spec.category_key:
        category_name = translate(spec.category_key, locale)
        category_id = await _ensure_scope_category(guild, platform, spec.scope, category_name)
        resolved["category"] = category_id
        # the scope category's own gate (the machine-room rule): the
        # folder's front door hides from @everyone, the rooms' bands
        # stay untouched
        if getattr(spec, "category_admin_only", False) and category_id:
            await _apply_category_access(
                guild, category_id, tuple(getattr(spec, "category_view_role_ids", ()) or ())
            )
    # the GROUP categories (the mods' salons-as-data structure, #216
    # tranche I): a channel declaring a group lives in the group's own
    # category — created lazily, stored under cat:<group>, the channel
    # resolution keys stay tree:<scope>:<key> (the doors keep working)
    group_categories: dict[str, str] = {}
    # each group's view roles = the union of its channels' resolved view
    # role ids (the gate on the group's category grants them all)
    group_view_roles = _group_view_role_map(spec)
    # each category's resolved channel ids in the DECLARED order — the
    # canonical order applied to the sidebar at the end of the pass
    # (adopted channels otherwise keep the position history gave them)
    category_order: dict[str, list[str]] = {}
    # an empty category_key is the guild root: its channels live uncategorised
    for decl in _sorted_channels(spec):
        name = translate(decl.label_key, locale)
        channel_category = await _decl_category(
            guild,
            platform,
            spec,
            decl,
            category_id,
            group_categories,
            resolved,
            group_view_roles=group_view_roles,
        )
        try:
            stored = await stored_channel_id(str(guild.id), spec.scope, decl.key)
            if stored and stored.isdigit():
                channel = guild.get_channel(int(stored))
                if (
                    channel is not None
                    and _kind_matches(channel, decl.kind)
                    and _category_matches(channel, channel_category)
                ):
                    existing = getattr(channel, "name", "")
                    if existing != name:
                        await channel.edit(
                            name=name, reason="botforge: panels provisioning (label refresh)"
                        )
                    await _apply_access(guild, stored, decl)
                    resolved[decl.key] = stored
                    if channel_category:
                        category_order.setdefault(channel_category, []).append(stored)
                    continue
                # a stored channel of the WRONG kind (a corrupted
                # provisioning, a manual conversion): it is treated as
                # absent — a fresh channel of the declared kind replaces
                # it and its stored id is overwritten (self-healing)
                if channel is not None:
                    logger.warning(
                        "panels provisioning: stored channel %s/%s has the wrong kind "
                        "(declared %s, found %s) — recreating",
                        spec.scope,
                        decl.key,
                        decl.kind,
                        type(channel).__name__,
                    )
            if decl.kind == "forum":
                channel_id = await platform.ensure_forum(name, channel_category)
            else:
                channel_id = await platform.ensure_channel(name, channel_category)
        except discord.HTTPException:
            logger.warning(
                "panels provisioning: channel %s/%s failed — best-effort, skipped",
                spec.scope,
                decl.key,
                exc_info=True,
            )
            continue
        await _apply_access(guild, channel_id, decl)
        resolved[decl.key] = channel_id
        if channel_category:
            category_order.setdefault(channel_category, []).append(channel_id)
    # the sidebar mirrors the declared order (creation order is NOT a
    # contract — the adoptions and renames prove it)
    for ordered_category, ordered_ids in category_order.items():
        await platform.reorder_channels(ordered_category, ordered_ids)
    return resolved


async def provision_all(
    guild: discord.Guild, locale: str, translate: Callable[[str, str], str]
) -> None:
    """Provision every registered scope folder (boot pass, best-effort).

    Every resolution is persisted under its stable key — the stored
    channel ids the syncs resolve by (never by name).
    """
    for spec in registered_scopes():
        try:
            resolved = await provision_scope(guild, spec, locale, translate)
            await persist_resolutions(str(guild.id), spec.scope, resolved)
        except Exception:
            logger.warning(
                "panels provisioning failed (scope %s, guild %s) — best-effort",
                spec.scope,
                guild.id,
                exc_info=True,
            )


async def persist_resolutions(guild_id: str, scope: str, resolved: dict[str, str]) -> None:
    """Persist one scope's resolved channel ids under their stable keys.

    ``tree:<scope>:<channel key>`` — the channels registry documents
    them; the syncs and the pins resolve by these stored ids, never by
    the translated name. Best-effort: a failed write logs and moves on
    (the next boot re-resolves).
    """
    try:
        from botforge.core.models.db import get_async_database

        collection = get_async_database()["channels"]
        for key, channel_id in resolved.items():
            await collection.replace_one(
                {"_id": f"{guild_id}:tree:{scope}:{key}"},
                {
                    "_id": f"{guild_id}:tree:{scope}:{key}",
                    "guild_id": guild_id,
                    "platform": "discord",
                    "category": f"tree:{scope}:{key}",
                    "channel_id": channel_id,
                    "name": key,
                },
                upsert=True,
            )
    except Exception:
        logger.warning(
            "panels provisioning: resolution persist failed (scope %s, guild %s) — best-effort",
            scope,
            guild_id,
            exc_info=True,
        )


async def stored_channel_id(guild_id: str, scope: str, channel_key: str) -> str | None:
    """Resolve one tree channel by its stored id (never by name).

    The syncs' resolution contract: the provisioning stored the id at
    creation time; a miss (virgin guild, unwired Mongo) returns None
    and the caller falls back to the provisioning.
    """
    try:
        from botforge.core.models.db import get_async_database

        document = await get_async_database()["channels"].find_one(
            {"_id": f"{guild_id}:tree:{scope}:{channel_key}"}
        )
        return str(document["channel_id"]) if document and document.get("channel_id") else None
    except Exception:
        return None


__all__ = [
    "persist_resolutions",
    "provision_all",
    "provision_scope",
    "stored_channel_id",
]
