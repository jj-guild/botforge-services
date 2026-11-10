"""The ops console: a destructive surface for the test guilds only.

Three layers of protection (developer-mandated \u2014 "que \u00e7a n'arrive
jamais en prod"):

1. **Visibility gate** \u2014 the console section renders in the /admin
   panel only on the env-declared test guilds
   (``BOTFORGE_TEST_GUILD_IDS``) and only for bot admins: nowhere
   else, no flag to flip.
2. **Runtime gate** \u2014 every click re-reads ``BOTFORGE_DEPLOY_ENV``
   and refuses on ``prod``, and re-checks the guard at click time (the
   mandate: seeing the button never implies being allowed to click it).
3. **Permission gate** \u2014 bot admins only (``require_admin``).

Capabilities:

- **clean managed** \u2014 delete only what the bot created: the persisted
  channels (the ``channels`` collection), the declared mod roles
  (``role_mappings``) and the ``bot-admins`` role. Roles are deleted
  but ``bot-admins`` privileges never depended on it (guards read
  BOT_ADMINS first), so a re-run of /admin re-provisions everything.
- **clean nuke** \u2014 delete EVERY channel, category and role of the guild
  (except the @everyone role, undeletable). Behind a triple
  confirmation: three consecutive clicks, each one restating the
  destruction, the third requiring a fresh deliberate click.
- **install modal** \u2014 a multi-select of mods and a multi-select of
  games; selecting a mod auto-installs its declared games (the YAML
  ``games:`` list), uninstalling a game uninstalls every mod that
  needs it. On submit: grants are replaced, channels/roles of
  uninstalled mods/games are deleted, then the newly granted mods are
  provisioned (the same seam as startup).
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import discord

from botforge.discord.console_guilds import is_test_guild
from botforge.discord.guards import require_admin

logger = logging.getLogger("botforge.discord.console")

DEPLOY_ENV_VAR = "BOTFORGE_DEPLOY_ENV"

PROD_ENV_NAMES = ("prod", "production")

_NS = "console"


@dataclass(frozen=True)
class ConsoleAction:
    """One console action: a button the console home renders dynamically.

    The console is extensible (the mods-init platform): a mod (or the
    core) registers its action — a stable key, the DynamicItem class
    to re-register at every startup, a builder taking the ``disabled``
    flag, and one description line for the home's intro. The same
    three gates (test guild, never prod, bot admin) guard every
    registered action's click — an action never re-implements them.

    - ``key`` \u2014 stable action id (e.g. ``clean-managed``); unique, and
    must not collide with another registered action;
    - ``item_cls`` \u2014 the DynamicItem subclass (re-registered at boot);
    - ``build`` \u2014 ``build(disabled)`` returns the button instance;
    - ``description`` \u2014 one line of the home's intro text.
    """

    key: str
    item_cls: type[discord.ui.DynamicItem[Any]]
    build: Callable[[bool], discord.ui.DynamicItem[Any]]
    description: str


_ACTIONS: dict[str, ConsoleAction] = {}


def register_console_action(action: ConsoleAction) -> ConsoleAction:
    """Register one console action (fail loudly on a key collision)."""
    if not action.key or ":" in action.key:
        raise ValueError(f"console action key {action.key!r} must be a simple slug")
    if action.key in _ACTIONS:
        raise ValueError(f"console action {action.key!r} is already registered")
    _ACTIONS[action.key] = action
    return action


def registered_console_actions() -> tuple[ConsoleAction, ...]:
    """Return the registered actions in registration order."""
    return tuple(_ACTIONS.values())


def console_action(key: str) -> ConsoleAction | None:
    """Return one registered action by key; None when unknown."""
    return _ACTIONS.get(key)


def _deploy_env(environ: dict[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    return env.get(DEPLOY_ENV_VAR, "").strip().lower()


def _prod_refusal() -> str:
    return (
        "The console is disabled: this bot runs on a production environment "
        f"({DEPLOY_ENV_VAR}). It is available on test environments only."
    )


def _guild_refusal() -> str:
    return (
        "This guild is not on the console allowlist: only the guild ids declared "
        "in the environment (BOTFORGE_TEST_GUILD_IDS) may use it."
    )


def _wire(bot: discord.Client) -> dict[str, Any]:
    """Collect the bot's provisioned seams (attached at build time)."""
    return {
        "bot": bot,
        "channel_service": getattr(bot, "channel_service", None),
        "mod_roles_service": getattr(bot, "mod_roles_service", None),
        "registry": getattr(bot, "registry", None),
    }


async def _delete_managed_for_guild(guild: discord.Guild) -> tuple[int, int]:
    """Delete the bot-created channels and roles; return (channels, roles).

    Guild-based seam: the Discord callbacks and the headless CLI
    (botforge.cli.console_ops) share this one implementation.
    """
    from botforge.core.models.db import get_async_database
    from botforge.core.services.channel import CHANNELS_COLLECTION
    from botforge.core.services.roles import ROLE_MAPPINGS_COLLECTION

    guild_id = str(guild.id)
    database = get_async_database()
    channels_deleted = 0
    roles_deleted = 0
    async for doc in database[CHANNELS_COLLECTION].find({"guild_id": guild_id}):
        channel = guild.get_channel(int(str(doc["channel_id"])))
        if channel is not None:
            try:
                await channel.delete(reason="botforge dev console: managed clean")
                channels_deleted += 1
            except Exception:
                logger.warning("CONSOLE channel delete failed (%s)", doc.get("name"), exc_info=True)
        await database[CHANNELS_COLLECTION].delete_one({"_id": doc["_id"]})
    async for mapping in database[ROLE_MAPPINGS_COLLECTION].find({"guild_id": guild_id}):
        role = guild.get_role(int(str(mapping["role_id"])))
        if role is not None:
            try:
                await role.delete(reason="botforge dev console: managed clean")
                roles_deleted += 1
            except Exception:
                logger.warning("CONSOLE role delete failed (%s)", mapping.get("role_key"), exc_info=True)
        await database[ROLE_MAPPINGS_COLLECTION].delete_one({"_id": mapping["_id"]})
    bot_admins = discord.utils.get(guild.roles, name="bot-admins")
    if bot_admins is not None:
        try:
            await bot_admins.delete(reason="botforge console: managed clean")
            roles_deleted += 1
        except Exception:
            logger.warning("CONSOLE bot-admins role delete failed", exc_info=True)
    return channels_deleted, roles_deleted


async def _delete_managed(interaction: discord.Interaction) -> tuple[int, int]:
    """Delete the bot-created channels and roles of the invoking guild."""
    guild = interaction.guild
    assert guild is not None  # noqa: S101 - guarded by the command check
    return await _delete_managed_for_guild(guild)


async def _nuke_everything_for_guild(guild: discord.Guild) -> tuple[int, int]:
    """Delete every channel and role of the guild; return (channels, roles).

    Guild-based seam: the Discord callbacks and the headless CLI
    (botforge.cli.console_ops) share this one implementation. Nothing
    is recreated afterwards: the platform's surfaces are declarations,
    never creators — a deleted salon degrades until an admin provisions
    it again (the scope's Synchroniser or the console's install).
    """
    return await _nuke_everything_for_guild_inner(guild)


def _client_of(guild: discord.Guild) -> discord.Client:
    """Recover the client from a guild object (discord.py state seam)."""
    return guild._state._get_client()


async def _safe_followup(interaction: discord.Interaction, content: str) -> None:
    """Send an ephemeral followup, tolerating a vanished channel.

    The destructive actions (clean-managed, nuke) may delete the very
    channel the console panel lives in: the followup webhook then
    targets an unknown channel (10003) while the action itself
    SUCCEEDED \u2014 a clean warning, never a traceback (same seam as
    the admin tree's provisioning verdicts).
    """
    try:
        await interaction.followup.send(content, ephemeral=True)
    except discord.HTTPException as exc:
        if getattr(exc, "code", None) == 10003:
            logger.warning(
                "CONSOLE verdict undeliverable (channel deleted by the action "
                "itself) \u2014 the action succeeded",
            )
            return
        raise


async def _nuke_everything_for_guild_inner(guild: discord.Guild) -> tuple[int, int]:
    """Delete every channel and role of the guild."""
    channels_deleted = 0
    roles_deleted = 0
    for channel in list(getattr(guild, "channels", ()) or ()):
        try:
            await channel.delete(reason="botforge dev console: nuke")
            channels_deleted += 1
        except Exception:
            logger.warning("CONSOLE nuke channel failed", exc_info=True)
    for role in list(getattr(guild, "roles", ()) or ()):
        if role.is_default() or role.managed:
            continue
        try:
            await role.delete(reason="botforge dev console: nuke")
            roles_deleted += 1
        except discord.Forbidden:
            # a role above the bot's highest role is not deletable by
            # design \u2014 skip it, never fail the nuke
            logger.warning("CONSOLE nuke role skipped (above the bot): %s", role.name)
        except Exception:
            logger.warning("CONSOLE nuke role failed", exc_info=True)
    from botforge.core.models.db import get_async_database
    from botforge.core.services.channel import CHANNELS_COLLECTION
    from botforge.core.services.roles import ROLE_MAPPINGS_COLLECTION

    guild_id = str(guild.id)
    database = get_async_database()
    await database[CHANNELS_COLLECTION].delete_many({"guild_id": guild_id})
    await database[ROLE_MAPPINGS_COLLECTION].delete_many({"guild_id": guild_id})
    return channels_deleted, roles_deleted


async def _nuke_everything(interaction: discord.Interaction) -> tuple[int, int]:
    """Delete every channel and role of the invoking guild."""
    guild = interaction.guild
    assert guild is not None  # noqa: S101 - guarded by the command check
    return await _nuke_everything_for_guild(guild)


def _mod_games(registry: Any, mod_name: str) -> tuple[str, ...]:
    """Return the games a mod requires (its YAML ``required_games:`` declaration)."""
    definition = registry.get(mod_name)
    return tuple(getattr(definition, "required_games", ()) or ()) if definition is not None else ()


def _propagate(
    registry: Any,
    all_games: tuple[str, ...],
    all_mods: tuple[str, ...],
    selected_mods: list[str],
    selected_games: list[str],
) -> tuple[list[str], list[str]]:
    """Apply the mod\u2192game and game\u2192mod propagation rules.

    Selecting a mod installs its declared games; unselecting a game
    unselects every mod that requires it. Idempotent and convergent.
    """
    games = set(selected_games)
    mods = set(selected_mods)
    for mod_name in selected_mods:
        games.update(_mod_games(registry, mod_name))
    surviving = {mod for mod in all_mods if not (required := set(_mod_games(registry, mod))) or required <= games}
    mods &= surviving
    return sorted(games), sorted(mods)


async def _reset_guild_data(guild_id: str) -> dict[str, int]:
    """Wipe one test guild's data from Mongo \u2014 nothing else.

    Every deletion carries a guild scope: ``guild_id`` documents, ids
    prefixed ``<guild_id>:`` or ``...:<guild_id>``. Global content
    (maps, pools, factions, rules, identities, profile stats, user
    settings, audits) is NEVER touched: the reset is isolated to the
    test guild, and the queries below fail closed on scope.
    """
    from botforge.core.models.db import get_async_database

    database = get_async_database()
    deleted: dict[str, int] = {}
    guild_scoped: dict[str, Any] = {
        "channels": {"guild_id": guild_id},
        "role_mappings": {"guild_id": guild_id},
        "channel_access_policies": {"_id": {"$regex": f"^{guild_id}:"}},
        "guild_settings": {"_id": guild_id},
        "guild_access": {"_id": f"guild:{guild_id}"},
        "staff": {"_id": {"$regex": f"^staff:{guild_id}:"}},
        "registrations": {"_id": {"$regex": f"^registration:{guild_id}:"}},
        "workflow_states": {"guild_id": guild_id},
        "platform_messages": {"guild_id": guild_id},
        "seasons": {"_id": {"$regex": f"^ladder:{guild_id}:[a-z0-9]+:[0-9]+$"}},
    }
    for collection, query in guild_scoped.items():
        try:
            result = await database[collection].delete_many(query)
            deleted[collection] = int(result.deleted_count)
        except Exception:
            logger.warning("CONSOLE reset failed (%s)", collection, exc_info=True)
            deleted[collection] = -1
    return deleted


async def _uninstall_mod(interaction: discord.Interaction, mod_name: str) -> None:
    """Delete one uninstalled mod's channels and roles, then their mappings."""
    wire = _wire(interaction.client)
    channel_service = wire["channel_service"]
    mod_roles_service = wire["mod_roles_service"]
    registry = wire["registry"]
    guild = interaction.guild
    guild_id = str(interaction.guild_id)
    definition = registry.get(mod_name) if registry is not None else None
    for category_def in getattr(definition, "channel_categories", ()) or ():
        category = f"{mod_name}:{category_def.key}"
        if channel_service is None:
            continue
        stored = await channel_service._db.find_channel(guild_id, category)
        if stored is not None and guild is not None:
            channel = guild.get_channel(int(stored.channel_id))
            if channel is not None:
                try:
                    await channel.delete(reason=f"botforge dev console: uninstall {mod_name}")
                except Exception:
                    logger.warning("CONSOLE uninstall channel failed (%s)", category, exc_info=True)
        await channel_service._db.delete_channel(guild_id, category)
        await channel_service._cache.delete_state("channels", f"{guild_id}:{category}")
    if mod_roles_service is None:
        return
    for mapping in await mod_roles_service._db.list_role_mappings(guild_id, mod_name):
        role = guild.get_role(int(mapping.role_id)) if guild is not None else None
        if role is not None:
            try:
                await role.delete(reason=f"botforge dev console: uninstall {mod_name}")
            except Exception:
                logger.warning("CONSOLE uninstall role failed (%s)", mapping.role_key, exc_info=True)
        await mod_roles_service._db.delete_role_mapping(guild_id, mod_name, mapping.role_key)
        await mod_roles_service._cache.delete_state("roles:mod", f"{guild_id}:{mod_name}:{mapping.role_key}")


async def _apply_selection(interaction: discord.Interaction, mods: list[str], games: list[str]) -> str:
    """Replace the grants, clean the uninstalled, provision the installed."""
    from botforge.discord.wiring import build_guild_access_service

    guild_id = str(interaction.guild_id)
    access = build_guild_access_service()
    if access is None:
        return "Mongo unavailable \u2014 grants cannot be persisted."
    previous_mods = set(await access.enabled_mods(guild_id))
    doc = await access.set_grants(guild_id, games=games, mods=mods)
    removed = previous_mods - set(mods)
    lines = [f"Grants updated: mods `{doc['mods']}`, games `{doc['games']}`."]
    for mod_name in sorted(removed):
        await _uninstall_mod(interaction, mod_name)
    if removed:
        lines.append(f"Uninstalled mods cleaned (channels + roles): {sorted(removed)}.")
    wire = _wire(interaction.client)
    channel_service = wire["channel_service"]
    mod_roles_service = wire["mod_roles_service"]
    provisioned = 0
    if channel_service is not None and mod_roles_service is not None:
        for mod_name in mods:
            try:
                await channel_service.setup_mod_channels(guild_id, mod_name)
                await mod_roles_service.setup_mod_roles(guild_id, mod_name)
                provisioned += 1
            except Exception:
                logger.warning("CONSOLE provisioning failed (%s)", mod_name, exc_info=True)
    lines.append(f"{provisioned} mod(s) provisioned.")
    return "\n".join(lines)


async def _guard(interaction: discord.Interaction) -> bool:
    """Gate the click-time check: test guild, bot admin, never prod."""
    if _deploy_env() in PROD_ENV_NAMES:
        try:
            await interaction.response.send_message(_prod_refusal(), ephemeral=True)
        except Exception:
            logger.warning("CONSOLE prod refusal answer failed", exc_info=True)
        return False
    if not is_test_guild(interaction.guild_id):
        try:
            await interaction.response.send_message(_guild_refusal(), ephemeral=True)
        except Exception:
            logger.warning("CONSOLE guild refusal answer failed", exc_info=True)
        return False
    bot = interaction.client
    admins = getattr(getattr(bot, "status_service", None), "bot_admins", ())
    roles = getattr(bot, "roles_service", None)
    return await require_admin(
        interaction, admins, roles, denied_message="The console is reserved for bot admins."
    )


async def _tr_guild(bot: Any, guild_id: str | int | None, key: str, fallback: str) -> str:
    """Render one console string in the guild's locale (en fallback)."""
    from botforge.discord.scope_pins import _catalog, _locale_of, _tr

    catalog = _catalog(bot)
    locale = await _locale_of(bot, str(guild_id or ""))
    return _tr(catalog, f"console.{key}", locale, fallback)


async def _console_view(guild_id: str | int | None, client: Any = None) -> discord.ui.LayoutView:
    """Build the console home: Install + Danger Zone, localized.

    The buttons are always rendered (visible), but disabled unless the
    invoking guild is on the env-defined allowlist: an operator sees
    the console exists, yet cannot act on a guild outside the test
    scope. Extension actions (register_console_action) ride along.
    """
    allowed = is_test_guild(guild_id)
    view = discord.ui.LayoutView(timeout=None)
    note_key, note_fallback = (
        ("note_allowed", "This guild is on the test allowlist \u2014 the actions below apply to **this guild only**.")
        if allowed
        else (
            "note_denied",
            "This guild is **not** on the test allowlist \u2014 the actions are disabled "
            "(BOTFORGE_TEST_GUILD_IDS decides, env-defined).",
        )
    )
    note = await _tr_guild(client, guild_id, note_key, note_fallback)
    intro = note + "\n" + "\n".join(action.description for action in registered_console_actions())
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.TextDisplay(await _tr_guild(client, guild_id, "title", "# \u2699 Console")),
        discord.ui.TextDisplay(intro),
        accent_colour=discord.Colour(0xED4245),
    )
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row.add_item(
        DevDangerButton(
            label=await _tr_guild(client, guild_id, "danger_btn", "\u26a0\ufe0f Danger Zone"),
            disabled=not allowed,
        )
    )
    container.add_item(row)
    for action in registered_console_actions():
        ext_row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        ext_row.add_item(action.build(not allowed))
        container.add_item(ext_row)
    view.add_item(container)
    back_row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    back_row.add_item(ConsoleBackButton())
    view.add_item(back_row)
    return view


class DevDangerButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:danger",
):
    """Open the Danger Zone modal (channels / roles / data)."""

    def __init__(self, label: str = "\u26a0\ufe0f Danger Zone", disabled: bool = False) -> None:
        super().__init__(
            discord.ui.Button(
                label=label,
                disabled=disabled,
                style=discord.ButtonStyle.danger,
                custom_id=f"{_NS}:danger",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> DevDangerButton:
        """Rebuild the item from the wire."""
        del interaction, item, match
        return cls()

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the Danger Zone modal."""
        if not await _guard(interaction):
            return
        await interaction.response.send_modal(await DevDangerModal.build(interaction))


class DevDangerModal(discord.ui.Modal):
    """The destructive picker: channels, roles, data \u2014 three selects.

    Every select is optional (required=False + min_values=0): an
    untouched select means the safe default (nothing deleted, data
    kept). The options are explicit (All / Bot-managed / None) so the
    operator states the blast radius instead of stacking separate
    destructive buttons.
    """

    CHANNELS_NONE, CHANNELS_BOT, CHANNELS_ALL = "channels:none", "channels:bot", "channels:all"
    ROLES_NONE, ROLES_BOT, ROLES_ALL = "roles:none", "roles:bot", "roles:all"
    DATA_KEEP, DATA_DELETE = "data:keep", "data:delete"

    @classmethod
    async def build(cls, interaction: discord.Interaction) -> DevDangerModal:
        """Build the modal with the guild's locale (en fallback)."""
        bot = interaction.client
        guild_id = interaction.guild_id

        async def tr(key: str, fallback: str) -> str:
            return await _tr_guild(bot, guild_id, key, fallback)

        return cls(
            title=await tr("danger_modal_title", "\u26a0\ufe0f Danger Zone"),
            label_channels=await tr("danger_label_channels", "Channels"),
            label_roles=await tr("danger_label_roles", "Roles"),
            label_data=await tr("danger_label_data", "Data"),
            opt_none=await tr("danger_opt_none", "None"),
            opt_bot=await tr("danger_opt_bot", "Bot-managed only"),
            opt_all=await tr("danger_opt_all", "All"),
            opt_keep=await tr("danger_opt_keep", "Keep everything"),
            opt_delete=await tr("danger_opt_delete", "Delete everything"),
            nothing=await tr("danger_nothing", "Nothing selected \u2014 nothing done."),
            done=await tr(
                "danger_done",
                "Danger Zone applied \u2014 channels: {channels}, roles: {roles}, data: {data}.",
            ),
            data_kept=await tr("danger_data_kept", "kept"),
        )

    def __init__(
        self,
        *,
        title: str,
        label_channels: str,
        label_roles: str,
        label_data: str,
        opt_none: str,
        opt_bot: str,
        opt_all: str,
        opt_keep: str,
        opt_delete: str,
        nothing: str,
        done: str,
        data_kept: str,
    ) -> None:
        super().__init__(title=title[:45], timeout=600.0)
        self.nothing = nothing
        self.done = done
        self.data_kept = data_kept
        self.channels_select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder=label_channels[:100],
            min_values=0,
            max_values=1,
            required=False,
            options=[
                discord.SelectOption(label=opt_none, value=self.CHANNELS_NONE),
                discord.SelectOption(label=opt_bot, value=self.CHANNELS_BOT),
                discord.SelectOption(label=opt_all, value=self.CHANNELS_ALL),
            ],
        )
        self.roles_select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder=label_roles[:100],
            min_values=0,
            max_values=1,
            required=False,
            options=[
                discord.SelectOption(label=opt_none, value=self.ROLES_NONE),
                discord.SelectOption(label=opt_bot, value=self.ROLES_BOT),
                discord.SelectOption(label=opt_all, value=self.ROLES_ALL),
            ],
        )
        self.data_select: discord.ui.Select[Any] = discord.ui.Select(
            placeholder=label_data[:100],
            min_values=0,
            max_values=1,
            required=False,
            options=[
                discord.SelectOption(label=opt_keep, value=self.DATA_KEEP),
                discord.SelectOption(label=opt_delete, value=self.DATA_DELETE),
            ],
        )
        self.add_item(discord.ui.Label(text=label_channels[:45], component=self.channels_select))
        self.add_item(discord.ui.Label(text=label_roles[:45], component=self.roles_select))
        self.add_item(discord.ui.Label(text=label_data[:45], component=self.data_select))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Guard, then apply the stated blast radius."""
        if not await _guard(interaction):
            return
        channels_mode = self.channels_select.values[0] if self.channels_select.values else self.CHANNELS_NONE
        roles_mode = self.roles_select.values[0] if self.roles_select.values else self.ROLES_NONE
        data_mode = self.data_select.values[0] if self.data_select.values else self.DATA_KEEP
        if (channels_mode, roles_mode, data_mode) == (self.CHANNELS_NONE, self.ROLES_NONE, self.DATA_KEEP):
            await interaction.response.send_message(self.nothing, ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        assert guild is not None  # noqa: S101 - guarded by the command check
        channels_deleted = 0
        if channels_mode != self.CHANNELS_NONE:
            channels_deleted = await _delete_channels_for_guild(
                guild, managed_only=channels_mode == self.CHANNELS_BOT
            )
        roles_deleted = 0
        if roles_mode != self.ROLES_NONE:
            roles_deleted = await _delete_roles_for_guild(
                guild, managed_only=roles_mode == self.ROLES_BOT
            )
        data_deleted: dict[str, int] = {}
        if data_mode == self.DATA_DELETE:
            data_deleted = await _reset_guild_data(str(guild.id))
        logger.warning(
            "CONSOLE DANGER ZONE executed (guild %s): channels=%s roles=%s data=%s",
            interaction.guild_id,
            channels_mode,
            roles_mode,
            data_mode,
        )
        data_summary = (
            ", ".join(f"{name}: {count}" for name, count in sorted(data_deleted.items()))
            or self.data_kept
        )
        await _safe_followup(
            interaction,
            self.done.format(channels=channels_deleted, roles=roles_deleted, data=data_summary),
        )


async def _delete_channels_for_guild(guild: discord.Guild, *, managed_only: bool) -> int:
    """Delete the guild's channels (all, or the bot-managed ones); return the count."""
    from botforge.core.models.db import get_async_database
    from botforge.core.services.channel import CHANNELS_COLLECTION

    guild_id = str(guild.id)
    database = get_async_database()
    deleted = 0
    if managed_only:
        async for doc in database[CHANNELS_COLLECTION].find({"guild_id": guild_id}):
            channel = guild.get_channel(int(str(doc["channel_id"])))
            if channel is not None:
                try:
                    await channel.delete(reason="botforge dev console: danger zone")
                    deleted += 1
                except Exception:
                    logger.warning("CONSOLE channel delete failed (%s)", doc.get("name"), exc_info=True)
            await database[CHANNELS_COLLECTION].delete_one({"_id": doc["_id"]})
    else:
        for channel in list(getattr(guild, "channels", ()) or ()):
            try:
                await channel.delete(reason="botforge dev console: danger zone")
                deleted += 1
            except Exception:
                logger.warning("CONSOLE channel delete failed", exc_info=True)
        await database[CHANNELS_COLLECTION].delete_many({"guild_id": guild_id})
    return deleted


async def _delete_roles_for_guild(guild: discord.Guild, *, managed_only: bool) -> int:
    """Delete the guild's roles (all, or the bot-managed ones); return the count."""
    from botforge.core.models.db import get_async_database
    from botforge.core.services.roles import ROLE_MAPPINGS_COLLECTION

    guild_id = str(guild.id)
    database = get_async_database()
    deleted = 0
    if managed_only:
        deleted = await _delete_managed_roles(guild, database, guild_id)
    else:
        deleted = await _delete_all_roles(guild)
        await database[ROLE_MAPPINGS_COLLECTION].delete_many({"guild_id": guild_id})
    return deleted


async def _delete_managed_roles(guild: discord.Guild, database: Any, guild_id: str) -> int:
    """Delete the bot-managed roles (mappings + bot-admins); return the count."""
    from botforge.core.services.roles import ROLE_MAPPINGS_COLLECTION

    deleted = 0
    async for mapping in database[ROLE_MAPPINGS_COLLECTION].find({"guild_id": guild_id}):
        role = guild.get_role(int(str(mapping["role_id"])))
        if role is not None:
            try:
                await role.delete(reason="botforge dev console: danger zone")
                deleted += 1
            except Exception:
                logger.warning("CONSOLE role delete failed (%s)", mapping.get("role_key"), exc_info=True)
        await database[ROLE_MAPPINGS_COLLECTION].delete_one({"_id": mapping["_id"]})
    bot_admins = discord.utils.get(guild.roles, name="bot-admins")
    if bot_admins is not None:
        try:
            await bot_admins.delete(reason="botforge dev console: danger zone")
            deleted += 1
        except Exception:
            logger.warning("CONSOLE bot-admins role delete failed", exc_info=True)
    return deleted


async def _delete_all_roles(guild: discord.Guild) -> int:
    """Delete every deletable role of the guild; return the count."""
    deleted = 0
    for role in list(getattr(guild, "roles", ()) or ()):
        if role.is_default() or role.managed:
            continue
        try:
            await role.delete(reason="botforge dev console: danger zone")
            deleted += 1
        except discord.Forbidden:
            # a role above the bot's highest role is not deletable by
            # design \u2014 skip it, never fail the action
            logger.warning("CONSOLE role delete skipped (above the bot): %s", role.name)
        except Exception:
            logger.warning("CONSOLE role delete failed", exc_info=True)
    return deleted


PIN_CONSOLE_BUTTON_ID = "admin:pin:button:console"
CONSOLE_BACK_BUTTON_ID = "console:back"


class AdminConsoleButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{PIN_CONSOLE_BUTTON_ID}",
):
    """The /admin panel's console opener (test environments only).

    Rendered on the env-declared test guilds (allowlist); the click
    re-runs the full console guard (bot admin, never prod, allowlist)
    before opening the console view \u2014 the mandate: seeing the
    button never implies being allowed to click it.
    """

    def __init__(self) -> None:
        super().__init__(
            discord.ui.Button(
                label="\u2699 Console",
                style=discord.ButtonStyle.danger,
                custom_id=PIN_CONSOLE_BUTTON_ID,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> AdminConsoleButton:
        """Rebuild the item from the wire."""
        del interaction, item, match
        return cls()

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the console view from the /admin panel."""
        if _deploy_env() in PROD_ENV_NAMES or not is_test_guild(interaction.guild_id):
            await interaction.response.edit_message(view=await _console_view(interaction.guild_id, interaction.client))
            return
        if not await _guard(interaction):
            return
        await interaction.response.edit_message(view=await _console_view(interaction.guild_id, interaction.client))


class ConsoleBackButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{CONSOLE_BACK_BUTTON_ID}",
):
    """Return from the console view to the /admin main menu."""

    def __init__(self) -> None:
        super().__init__(
            discord.ui.Button(
                label="\u2190 Admin",
                style=discord.ButtonStyle.secondary,
                custom_id=CONSOLE_BACK_BUTTON_ID,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> ConsoleBackButton:
        """Rebuild the item from the wire."""
        del interaction, item, match
        return cls()

    async def callback(self, interaction: discord.Interaction) -> None:
        """Return to the /admin main menu."""
        from botforge.discord.admin_persistent import _handle_back

        await _handle_back(interaction)


def register_console_items(bot: discord.Client) -> None:
    """Register the console's DynamicItems (called at every startup).

    The registered actions' item classes ride along \u2014 an extension
    action registers its button once and the boot wiring follows.
    """
    bot.add_dynamic_items(AdminConsoleButton, ConsoleBackButton, DevDangerButton)
    for action in registered_console_actions():
        bot.add_dynamic_items(action.item_cls)
