"""The admin menu: language, games, mods, and the provisioning ensure.

One ephemeral menu, three openers, every item a DynamicItem (the §3b
reconstruction contract — a click is restart-proof):

- ``admin:tree:games`` / ``admin:tree:mods`` — the scope admin menus
  (the shared admin dispatches);
- ``admin:tree:ensure:<scope>`` — re-provision one scope's channels
  (and the mod/game roles) and refresh the pinned menus.

The roles/channel-management views are gone: the tree is declared and
provisioned (panels_scopes + panels_provisioning), the admin surfaces
carry an ensure button instead, and the homes explain the layout in a
contextual notice.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import discord

logger = logging.getLogger("botforge.admin.tree")

_NS = "admin:tree"

LOCALE_LABELS = {"en": "\U0001f1ec\U0001f1e7 English", "fr": "\U0001f1eb\U0001f1f7 Français"}


async def _tree_tr(interaction: Any, key: str, **kwargs: Any) -> str:
    """Render one admin_tree key in the interaction's locale."""
    from botforge.discord.commands_i18n import reply

    return await reply(interaction, key, **kwargs)


def _wiring(interaction: discord.Interaction) -> Any:
    from botforge.discord.admin_persistent import _wiring as panel_wiring

    return panel_wiring()


async def _guard(interaction: discord.Interaction) -> bool:
    from botforge.discord.guards import require_admin

    bot = interaction.client
    admins = tuple(getattr(getattr(bot, "status_service", None), "bot_admins", ()) or ())
    roles = getattr(bot, "roles_service", None)
    return await require_admin(interaction, admins, roles)


async def _ensure_scope_roles(bot: Any, guild_id: str, scope: str) -> int:
    """Ensure the scope's roles live (mods roles, the bot-admins role).

    A role deleted on Discord comes back at the next sync: the stored
    mapping is existence-checked, the missing roles re-adopt by name
    or re-create (the declared roles always live).
    """
    ensured = 0
    # the bot-admins role belongs to the bot menu's perimeter
    if scope in ("bot", "root"):
        roles_service = getattr(bot, "roles_service", None)
        if roles_service is not None:
            try:
                await roles_service.provision_admin_role(guild_id)
                ensured += 1
            except Exception:
                logger.warning("admin role ensure failed — best-effort", exc_info=True)
    # the mods' declared roles live under the mods perimeter
    if scope == "mods" or scope.startswith("mods/"):
        mod_roles_service = getattr(bot, "mod_roles_service", None)
        registry = getattr(bot, "registry", None)
        if mod_roles_service is not None and registry is not None:
            for mod_name in registry.enabled():
                try:
                    resolved = await mod_roles_service.setup_mod_roles(guild_id, mod_name)
                    ensured += len(resolved)
                except Exception:
                    logger.warning("mod roles ensure failed (%s) — best-effort", mod_name, exc_info=True)
    return ensured


async def _ensure_scope_pins(bot: Any, guild_id: str, scope: str) -> int:
    """Ensure every pinned view registered for the scope (and its sub-scopes).

    A deleted pin is recreated: the pin is only a mirror of its view.
    Best-effort per pin; returns how many pins were (re-)created.
    """
    from botforge.discord.static_pins import ensure_static_pin, registered_static_pins

    ensured = 0
    for pin in registered_static_pins():
        if not pin.scope or not (pin.scope == scope or pin.scope.startswith(scope + "/")):
            continue
        try:
            if await ensure_static_pin(bot, pin, guild_id):
                ensured += 1
        except Exception:
            logger.warning("pin ensure failed (%s) \u2014 best-effort", pin.key, exc_info=True)
    return ensured


def _repair_view(steps: list[str], running: str, title: str) -> discord.ui.LayoutView:
    """Build the repair's progress view (owner 2026-11-26).

    A container, a checked step per line, the running banner while
    it works.
    """
    view = discord.ui.LayoutView(timeout=None)
    blocks: list[Any] = [discord.ui.TextDisplay(title)]
    if steps:
        blocks.append(discord.ui.Separator())
        blocks.extend(discord.ui.TextDisplay(f"\u2705 {step}") for step in steps)
    blocks.append(discord.ui.Separator())
    blocks.append(discord.ui.TextDisplay(running))
    view.add_item(
        discord.ui.Container(*blocks, accent_colour=discord.Colour(0x5865F2))
    )
    return view


async def _edit_plan(interaction: Any, report: Any, title: str, running: str) -> None:
    """Mirror the repair's steps onto the deferred thinking message (best-effort)."""
    try:
        await interaction.edit_original_response(
            view=_repair_view(list(report.steps), running, title)
        )
    except Exception:
        logger.debug("the repair plan edit failed - best-effort", exc_info=True)


def _scope_parts(scope: str) -> list[str]:
    """Split the button's comma-separated scope list."""
    return [part for part in scope.split(",") if part]


def _scope_specs_of(scope: str) -> list[Any]:
    """Return the registered specs the button's scope list names."""
    from botforge.discord.ui.panels import registered_scopes

    wanted = set(_scope_parts(scope))
    return [spec for spec in registered_scopes() if spec.scope in wanted]


async def _guild_locale(bot: Any, guild_id: str) -> str:
    """Return the guild's own locale (the repair speaks the admin's language)."""
    from botforge.core.services.i18n import DEFAULT_LOCALE

    logs = getattr(bot, "logs_service", None)
    if logs is None:
        return DEFAULT_LOCALE
    try:
        return str(await logs.get_locale(guild_id) or DEFAULT_LOCALE)
    except Exception:
        return DEFAULT_LOCALE


def _say_of(bot: Any, locale: str) -> Any:
    """Build the repair's localized speaker (replies.admin_tree.*)."""
    catalog = getattr(bot, "messages", None)

    def _translate(key: str, loc: str) -> str:
        if catalog is None:
            return key
        rendered: str = catalog.render(key, loc)
        return rendered if rendered != key else catalog.render(key, "en")

    def _say(key: str, **values: Any) -> str:
        # the repair keys live under replies.admin_tree.* (the locale
        # tree) - the bare prefix misses the section and the RAW
        # DOTTED KEY would hit the admin's view
        return _translate(f"replies.admin_tree.{key}", locale).format(**values)

    _say.translate = _translate  # type: ignore[attr-defined]
    return _say


class _ThrottledError(Exception):
    """Signal a channel-creation throttle.

    The verdict carries the LIVE retry timestamp - the runner returns
    it as the answer.
    """

    def __init__(self, retry_at: int) -> None:
        super().__init__(str(retry_at))
        self.retry_at = retry_at


async def _provision_one_scope(
    bot: Any,
    guild_id: str,
    spec: Any,
    locale: str,
    say: Any,
    report: Any,
) -> list[str]:
    """Provision ONE scope's channels + pins; return the answer lines."""
    from botforge.discord.ui.panels_provisioning import persist_resolutions, provision_scope

    guild = getattr(bot, "get_guild", lambda _gid: None)(int(guild_id)) if guild_id.isdigit() else None
    if guild is None:
        return ["Guild not found — cannot re-provision."]
    translate = say.translate
    lines: list[str] = []
    resolved = await provision_scope(guild, spec, locale, translate)
    await persist_resolutions(guild_id, spec.scope, resolved)
    # the guild-admin reads WORDS, not paths (owner 2026-11-26: "tu
    # parles à des admin de guild discord, pas des admin sys") - the
    # scope names its localized category, the channels their mentions,
    # only a MISSING channel names its key
    scope_label = translate(spec.category_key, locale)
    lines.append(say("repair_scope", scope=scope_label))
    for decl in spec.channels:
        channel_id = resolved.get(decl.key, "")
        lock = "\U0001F512" if decl.access == "admin" else ""
        where = f"<#{channel_id}>{lock}" if channel_id else f"**{decl.key}** ({say('repair_absent')})"
        lines.append(f"\u2022 {where}")
    report.step(
        f"scope {spec.scope} provisioned",
        display=say("repair_channels", scope=scope_label, count=len(spec.channels)),
        channels=len(spec.channels),
    )
    pins_ok = await _ensure_scope_pins(bot, guild_id, spec.scope)
    roles_ok = await _ensure_scope_roles(bot, guild_id, spec.scope)
    report.step(
        f"scope {spec.scope} surfaced",
        display=say("repair_pins_roles", pins=pins_ok, roles=roles_ok),
        pins=pins_ok,
        roles=roles_ok,
    )
    lines.append(say("repair_summary_pins", pins=pins_ok))
    lines.append(say("repair_summary_roles", roles=roles_ok))
    return lines


async def _recreate_scope_roles(bot: Any, guild_id: str, values: list[str]) -> int:
    """Recreate the CHOSEN role sets (owner 2026-11-27).

    The selected roles die and come back fresh (teardown then setup -
    the mappings and the Discord roles both); the channels'
    permissions are REAPPLIED right after by the provisioning pass -
    the roles recreation implies it (a fresh role id must reach the
    channels' overwrites).
    """
    recreated = 0
    for value in values:
        if value == "admin":
            roles_service = getattr(bot, "roles_service", None)
            if roles_service is None:
                continue
            try:
                await roles_service.provision_admin_role(guild_id)
                recreated += 1
            except Exception:
                logger.warning("the admin role recreate failed - best-effort", exc_info=True)
        elif value.startswith("mod:"):
            mod_name = value.split(":", 1)[1]
            svc = getattr(bot, "mod_roles_service", None)
            if svc is None:
                continue
            try:
                await svc.teardown_mod_roles(guild_id, mod_name)
                resolved = await svc.setup_mod_roles(guild_id, mod_name)
                recreated += len(resolved)
            except Exception:
                logger.warning(
                    "the mod roles recreate failed (%s) - best-effort", mod_name, exc_info=True
                )
    return recreated


async def _refresh_game_data(bot: Any, kinds: list[str]) -> list[str]:  # noqa: C901 - one fold
    """Refresh the game's provider data (owner 2026-11-27).

    The DM admin sync buttons are GONE - the civs (techtree, fast) and
    the maps (Liquipedia, long and paced) refresh through the aoe2
    repair, the bot admins only. The forums' mirrors ride along so the
    fresh data shows up on the posts right away.
    """
    import os

    from botforge.game_aoe2.client import GameDataClient

    uri = os.environ.get("GAME_AOE2_URI", "")
    if not uri:
        logger.warning("REPAIR: the game data refresh has no GAME_AOE2_URI - skipped")
        return []
    client = GameDataClient(uri)
    kind_map = {"civs": "factions", "maps": "maps"}
    done: list[str] = []
    for kind in kinds:
        try:
            result = await client.sync_content("aoe2", kind_map.get(kind, kind))
            if result.get("ok"):
                done.append(kind)
            else:
                logger.warning(
                    "REPAIR: the %s data refresh failed (%s)", kind, result.get("error", "?")
                )
        except Exception:
            logger.warning("REPAIR: the %s data refresh failed - best-effort", kind, exc_info=True)
    # the mirrors: the refreshed content reaches the forums' posts now
    for kind in done:
        try:
            if kind == "civs":
                from botforge.core.services.entity_forum import sync_entity_forum
                from botforge.discord.factions_forum import factions_forum_spec

                for guild in getattr(bot, "guilds", []) or []:
                    await sync_entity_forum(str(guild.id), bot, factions_forum_spec(bot))
            elif kind == "maps":
                from botforge.discord.maps_forum import sync_maps_forum

                for guild in getattr(bot, "guilds", []) or []:
                    await sync_maps_forum(str(guild.id), "aoe2", bot)
        except Exception:
            logger.warning(
                "REPAIR: the %s forum mirror failed - best-effort", kind, exc_info=True
            )
    return done


async def run_scope_repair(  # noqa: C901 - one orchestration, no branch soup
    bot: Any,
    guild_id: str,
    scope: str,
    plan: dict[str, list[str]],
    progress: Any = None,
    say: Any = None,
) -> tuple[str, Any]:
    """Run the CHOSEN repair plan (owner 2026-11-27).

    The modal owns the perimeter - roles recreated, channels
    provisioned with their permissions, forums refreshed, the players'
    history re-synced.

    The mod repair and the game repair run the SAME code: the plan's
    sections decide what happens, the scope decides what the sections
    offer. Returns (answer, report).
    """
    from botforge.discord.repair import RepairReport

    if say is None:
        say = _say_of(bot, await _guild_locale(bot, guild_id))
    locale = await _guild_locale(bot, guild_id)
    tree_repair = RepairReport(logger, "tree repair", subject=guild_id, progress=progress)
    lines: list[str] = []
    chosen = {key: list(values or []) for key, values in plan.items()}

    # 1. the game data (bot admins only - the civs and maps refresh)
    if chosen.get("data"):
        done = await _refresh_game_data(bot, chosen["data"])
        if done:
            tree_repair.step(
                f"game data refreshed ({','.join(done)})",
                display=say("repair_data_done", kinds="\u00b7 ".join(done)),
            )
    # 2. the roles - recreated, the channels pass REAPPLIES the
    # permissions (a fresh role id must reach the overwrites)
    roles_recreated = 0
    if chosen.get("roles"):
        roles_recreated = await _recreate_scope_roles(bot, guild_id, chosen["roles"])
        tree_repair.step(
            f"roles recreated ({roles_recreated})",
            display=say("repair_roles_done", count=roles_recreated),
            roles=roles_recreated,
        )
    # 3. the channels - the roles recreation implies the provisioning
    # pass (the permissions ride it); otherwise the CHOSEN scopes only
    channel_values = list(chosen.get("channels") or [])
    if roles_recreated and not channel_values:
        channel_values = [spec.scope for spec in _scope_specs_of(scope)]
    for spec in _scope_specs_of(",".join(channel_values) if channel_values else ""):
        try:
            lines.extend(
                await _provision_one_scope(bot, guild_id, spec, locale, say, tree_repair)
            )
        except discord.errors.RateLimited as exc:
            # Discord throttled the channel creation for THIS bot: the
            # retry_after is Discord's own word (minutes for a routine
            # bucket, HOURS on a hard throttle).
            import time as _time

            raise _ThrottledError(int(_time.time() + exc.retry_after)) from exc
        except Exception:
            logger.warning(
                "ADMIN TREE: ensure failed (scope %s, guild %s)", spec.scope, guild_id, exc_info=True
            )
            return "Channel provisioning failed — see the bot logs.", tree_repair
    # 4. the forums (the games): the entity forums' posts, the players'
    # posts, the heavy matchs pass
    forum_values = list(chosen.get("forums") or [])
    if forum_values:
        entity_values = [
            value for value in forum_values if not value.startswith("__") and value != "joueurs"
        ]
        posts = 0
        if entity_values:
            from botforge.discord.scope_surfaces import run_scope_syncs

            posts = await run_scope_syncs(guild_id, bot, scope)
            tree_repair.step(
                "the forums synced",
                display=say("repair_forums", posts=posts),
                posts=posts,
            )
        if "joueurs" in forum_values or "__matchs__" in forum_values:
            from botforge.discord.live_activity import repair_players_forum

            heavy = "__matchs__" in forum_values
            counts = await repair_players_forum(bot, guild_id, full=heavy)
            tree_repair.step(
                "the players forum repaired",
                display=say("repair_players_done", posts=counts.get("posts", 0)),
                posts=counts.get("posts", 0),
            )
            if heavy:
                tree_repair.step(
                    "the match cards re-rendered",
                    display=say("repair_matchs_done", cards=counts.get("cards", 0)),
                    cards=counts.get("cards", 0),
                )
    tree_repair.done(
        "the scopes stand",
        display=say("repair_done", duration="{duration}"),
    )
    if not lines:
        lines.append(say("repair_done", duration="{duration}").replace("{duration}", "0"))
    return "\n".join(lines), tree_repair


async def _repair_sections(  # noqa: C901 - one options fold
    bot: Any, scope: str, bot_admin: bool, tr: Any
) -> dict[str, list[dict[str, Any]]]:
    """Build the repair modal's option sets (owner 2026-11-27).

    The MOD and the GAME repairs offer the SAME sections - roles,
    channels - and the games add their forums and (the bot admins) the
    provider data: the modal is one, the scope decides the options.
    """
    sections: dict[str, list[dict[str, Any]]] = {}
    roles: list[dict[str, Any]] = []
    for part in _scope_parts(scope):
        if part in ("bot", "root"):
            roles.append(
                {
                    "value": "admin",
                    "label": await tr("admin_tree.repair_roles_admin"),
                    "selected": True,
                }
            )
        elif part == "mods" or part.startswith("mods/"):
            registry = getattr(bot, "registry", None)
            names = (
                [part.split("/", 1)[1]] if "/" in part else list(registry.enabled() or [])
                if registry is not None
                else []
            )
            for name in names:
                roles.append(
                    {
                        "value": f"mod:{name}",
                        "label": await tr("admin_tree.repair_roles_mod", mod=name),
                        "selected": True,
                    }
                )
    if roles:
        sections["roles"] = roles
    channels = [
        {"value": spec.scope, "label": await tr(spec.category_key), "selected": True}
        for spec in _scope_specs_of(scope)
    ]
    if channels:
        sections["channels"] = channels
    specs = _scope_specs_of(scope)
    if any(spec.scope.startswith("games/") for spec in specs):
        forums: list[dict[str, Any]] = []
        for spec in specs:
            if not spec.scope.startswith("games/"):
                continue
            for decl in spec.channels:
                if getattr(decl, "kind", "") == "forum":
                    forums.append(
                        {"value": decl.key, "label": await tr(decl.label_key), "selected": True}
                    )
            # the heavy pass - the match cards of every player's post
            # (owner: "matchs non sélectionné, trop lourd")
            forums.append(
                {
                    "value": "__matchs__",
                    "label": await tr("admin_tree.repair_forums_matchs"),
                    "selected": False,
                }
            )
        if forums:
            sections["forums"] = forums
        if bot_admin:
            sections["data"] = [
                {"value": "civs", "label": await tr("admin_tree.repair_data_civs"), "selected": False},
                {"value": "maps", "label": await tr("admin_tree.repair_data_maps"), "selected": False},
            ]
    return sections


class TreeOpenButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:open:(?P<section>[a-z]+)",
):
    """One admin menu button: opens its section's ephemeral view."""

    SECTIONS = ("games", "mods")

    def __init__(self, section: str, label: str, emoji: str) -> None:
        self.section = section
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:open:{section}",
                label=label,
                emoji=emoji,
                style=discord.ButtonStyle.secondary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> TreeOpenButton:
        """Rebuild the opener from the wire (label from the locale)."""
        section = match.group("section")
        label = await _tree_tr(interaction, f"admin_tree.{section}_btn")
        emoji = {
            "games": "\U0001f3ae",
            "mods": "\U0001f9e9",
        }.get(section, "\u2795")
        return cls(section, label, emoji)

    @classmethod
    async def create(cls, bot: Any, guild_id: str, section: str) -> TreeOpenButton:
        """Build an opener for a pinned menu (locale from the guild's logs)."""
        from botforge.discord.commands_i18n import tr_guild

        label = await tr_guild(guild_id, bot, f"admin_tree.{section}_btn")
        emoji = {
            "games": "\U0001f3ae",
            "mods": "\U0001f9e9",
        }.get(section, "\u2795")
        return cls(section, label, emoji)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the section's view (guarded at click time)."""
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=False)
        if self.section in ("games", "mods"):
            # the declared menus own the navigation: the scope's admin
            # menu renders from the views registry
            from botforge.discord.views_routing import open_declared_view

            view_id = f"menu:{self.section}:admin"
            try:
                await open_declared_view(interaction, view_id)
            except Exception:
                logger.warning("ADMIN TREE: scope admin view failed (%s)", self.section, exc_info=True)
                await interaction.followup.send(
                    await _tree_tr(interaction, "admin_tree.route_failed"), ephemeral=True
                )
                return
            return


class RepairModal(discord.ui.Modal):
    """Pick the repair PLAN (owner 2026-11-27).

    No silent healing (owner: "si on a cassé des trucs, on clique sur
    réparer - jamais de autoheal"): the click opens the plan, the admin
    CHOOSES the perimeter - the roles to recreate, the channels to
    repair, the forums to refresh, the provider data to update. The
    MOD and the GAME repairs ride the same modal: the scope decides the
    options, the plan decides the run.
    """

    def __init__(
        self, scope: str, sections: dict[str, list[dict[str, Any]]], texts: dict[str, str]
    ) -> None:
        super().__init__(title=str(texts.get("title", ""))[:45], timeout=None)
        self.scope = scope
        self.selects: dict[str, discord.ui.Select[discord.ui.LayoutView]] = {}
        for key in ("roles", "channels", "forums", "data"):
            options = sections.get(key) or []
            if not options:
                continue
            select: discord.ui.Select[discord.ui.LayoutView] = discord.ui.Select(
                custom_id=f"{_NS}:repair:plan:{key}",
                min_values=0,
                max_values=len(options),
                options=[
                    discord.SelectOption(
                        label=str(option["label"])[:100],
                        value=str(option["value"])[:100],
                        default=bool(option.get("selected")),
                    )
                    for option in options
                ],
            )
            self.selects[key] = select
            # a bare select inside a modal is silently rejected by the
            # API - the Label wrapper is REQUIRED (the modal constraint)
            self.add_item(
                discord.ui.Label(text=str(texts.get(f"label:{key}", key)), component=select)
            )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Run the CHOSEN plan; the live view mirrors the steps."""
        if not await _guard(interaction):
            return
        plan = {key: [str(v) for v in select.values or []] for key, select in self.selects.items()}
        if not any(plan.values()):
            await interaction.response.send_message(
                await _tree_tr(interaction, "admin_tree.repair_nothing"), ephemeral=True
            )
            return
        # THINKING (owner 2026-11-26: "ne dit pas que ça travaille"):
        # the repair takes minutes - the live plan rides the deferred
        # message's edits
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        title = await _tree_tr(interaction, "admin_tree.repair_title")
        running = await _tree_tr(interaction, "admin_tree.repair_running")

        plan_tasks: list[asyncio.Task[None]] = []

        def _plan_mirror(line: str, report: Any) -> None:
            del line  # the view renders the report's display steps
            plan_tasks.append(
                asyncio.ensure_future(_edit_plan(interaction, report, title, running))
            )

        say = _say_of(interaction.client, await _guild_locale(interaction.client, guild_id))
        try:
            answer, report = await run_scope_repair(
                interaction.client, guild_id, self.scope, plan, _plan_mirror, say
            )
        except _ThrottledError as throttled:
            answer = (
                f"\u23f3 Discord bloque la cr\u00e9ation de salons pour ce bot \u2014 "
                f"r\u00e9essaie <t:{throttled.retry_at}:R> (<t:{throttled.retry_at}:t>).\n"
                f"_Ce message dispara\u00eetra \u00e0 ce moment-l\u00e0._"
            )
            report = None
        final_steps = list(report.steps) if report is not None else []
        for task in plan_tasks:
            task.cancel()
        await asyncio.gather(*plan_tasks, return_exceptions=True)
        import time as _time

        delete_after: float | None = None
        match = re.search(r"<t:(\d+):R>", answer)
        if match:
            delete_after = max(1.0, int(match.group(1)) - _time.time() + 2.0)
        # the provisioning may RECREATE the very channel this
        # interaction lives in: the followup webhook then targets a
        # vanished channel (10003) - the provisioning SUCCEEDED, the
        # verdict just cannot be delivered there
        try:
            final_view = discord.ui.LayoutView(timeout=None)
            final_blocks: list[Any] = [discord.ui.TextDisplay(title)]
            final_blocks.append(discord.ui.Separator())
            final_blocks.extend(discord.ui.TextDisplay(f"\u2705 {step}") for step in final_steps)
            final_blocks.append(discord.ui.Separator())
            final_blocks.append(discord.ui.TextDisplay(answer))
            final_view.add_item(
                discord.ui.Container(*final_blocks, accent_colour=discord.Colour(0x2ECC71))
            )
            message: Any = await interaction.edit_original_response(view=final_view, content=None)
        except discord.HTTPException as exc:
            if getattr(exc, "code", None) == 10003:
                logger.warning(
                    "ADMIN TREE: the invoking channel vanished during the "
                    "repair (scope %s) \u2014 the verdict is undeliverable, "
                    "the channels themselves are in place",
                    self.scope,
                )
                return
            raise
        if delete_after is not None:
            await message.delete(delay=delete_after)


class TreeEnsureButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:ensure:(?P<scope>[a-z0-9_/,]+)",
):
    """Open the repair PLAN modal (the scopes' channels, roles, forums).

    The custom id carries a comma-separated scope list: the repair of
    an admin menu heals its own scope plus anything it owns. The click
    never runs anything silent - the modal shows the plan, the admin
    picks the perimeter (owner 2026-11-27).
    """

    def __init__(self, scope: str, label: str = "Sync now", emoji: str = "") -> None:
        from botforge.discord.ui.emoji import EMOJI

        self.scope = scope
        emoji = emoji or EMOJI.WRENCH
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:ensure:{scope}"[:100],
                label=label,
                emoji=emoji,
                style=discord.ButtonStyle.secondary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> TreeEnsureButton:
        """Rebuild the ensure button from the wire."""
        del interaction, item
        return cls(match["scope"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the repair modal - the plan is the admin's choice."""
        if not await _guard(interaction):
            return
        bot = interaction.client
        admins = tuple(getattr(getattr(bot, "status_service", None), "bot_admins", ()) or ())
        bot_admin = str(interaction.user.id) in {str(a) for a in admins}

        async def _tr(key: str, **kwargs: Any) -> str:
            return await _tree_tr(interaction, key, **kwargs)

        sections = await _repair_sections(bot, self.scope, bot_admin, _tr)
        if not sections:
            await interaction.response.defer(ephemeral=True)
            return
        texts = {"title": await _tree_tr(interaction, "admin_tree.repair_modal_title")}
        for key in ("roles", "channels", "forums", "data"):
            if key in sections:
                texts[f"label:{key}"] = await _tree_tr(interaction, f"admin_tree.repair_{key}_label")
        await interaction.response.send_modal(RepairModal(self.scope, sections, texts))


async def build_admin_menu(
    guild_id: str, locale: str, interaction: Any = None
) -> discord.ui.LayoutView:
    """Build the light admin menu: lang/games/mods openers + ensure."""
    from botforge.discord.commands_i18n import tr_guild

    bot = getattr(interaction, "client", None) if interaction is not None else None

    async def _label(key: str, fallback: str) -> str:
        if bot is not None and guild_id:
            rendered = await tr_guild(guild_id, bot, f"replies.{key}", fallback)
            return rendered
        return fallback

    buttons = (
        ("games", await _label("admin_tree.games_btn", "Jeux"), "\U0001f3ae"),
        ("mods", await _label("admin_tree.mods_btn", "Mods"), "\U0001f9e9"),
    )
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(
                await tr_guild(guild_id, bot, "ui.views.menu.admin.title", "Admin")
            ),
            accent_colour=discord.Colour(0x5865F2),
        )
    )
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    for section, label, emoji in buttons:
        row.add_item(TreeOpenButton(section, label, emoji))
    view.add_item(row)
    ensure_row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    ensure_row.add_item(TreeEnsureButton("bot", await _label("admin_tree.ensure_btn", "Sync now")))
    view.add_item(ensure_row)
    from botforge.discord.console import AdminConsoleButton
    from botforge.discord.console_guilds import is_test_guild
    from botforge.discord.ui.view_footer import add_view_footer

    # test guilds only (allowlist): the console's own guards re-check the
    # invoker on every click — seeing the button never implies permission
    if is_test_guild(guild_id):
        console_row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        console_row.add_item(AdminConsoleButton())
        view.add_item(console_row)
    return add_view_footer(view, "panel:bot:admin")


def ensure_button(scope: str, label: str = "Sync now") -> TreeEnsureButton:
    """Build an ensure button for one scope (the scope admin menus)."""
    return TreeEnsureButton(scope, label)


def register_admin_tree_items(bot: discord.Client) -> None:
    """Register the admin menu's DynamicItems (every startup)."""
    bot.add_dynamic_items(TreeOpenButton)
    bot.add_dynamic_items(TreeEnsureButton)


__all__ = ["build_admin_menu", "ensure_button", "register_admin_tree_items"]
