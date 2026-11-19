r"""Headless install runner: the console's install action without a bot.

The Discord ``/console`` install modal and this runner are the same
action (replace the grants, clean the uninstalled mods' channels and
roles, provision the installed ones through the standard seams). The
modal rides the running bot's wirings; this runner rebuilds them from a
bare ``discord.Client`` \\u2014 the CLI (botforge.cli.console_ops) and the
env-console workflow use it on the environment's botforge-core
container, where the code and the Mongo network are both available
(same execution model as the seed CLIs).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import discord

logger = logging.getLogger("botforge.discord.console_ops_runner")

__all__ = [
    "apply_install_for_guild",
    "build_console_wirings",
]

# The repo layout (the image copies both at the workdir root): the runner
# lives at src/botforge/discord/, so parents[3] is the root — same
# resolution as the other config readers (profile_sites, ratelimits).
# The mod registry ALSO needs the repo root: the §7 layout declares
# mods under modules/mods/<mod>/, not config/mods/.
_REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = _REPO_ROOT / "config"


def build_console_wirings(client: discord.Client) -> dict[str, Any] | None:
    """Rebuild the console's wirings from a bare client; None unwired."""
    import os

    if not os.environ.get("MONGO_URI") or not os.environ.get("REDIS_URI"):
        logger.error("CONSOLE OPS wiring needs MONGO_URI and REDIS_URI")
        return None
    try:
        from botforge.core.models.db import get_async_database
        from botforge.core.services.channel import ChannelService
        from botforge.core.services.mod_registry import ModRegistry, load_mod_definitions
        from botforge.core.services.roles import ModRolesService
        from botforge.core.services.state import StateService
        from botforge.discord.channels_platform import DiscordChannelsPlatform
        from botforge.discord.console import _propagate
        from botforge.discord.logs_platform import MongoLogsDatabase
        from botforge.discord.roles_platform import DiscordRolesPlatform, MongoRolesDatabase

        registry = ModRegistry(load_mod_definitions(CONFIG_DIR, _REPO_ROOT))
        database = get_async_database()
        state = StateService(redis_uri=os.environ["REDIS_URI"])
        channel_service = ChannelService(
            database=MongoLogsDatabase(database),
            platform=DiscordChannelsPlatform(client),
            cache=state,
            registry=registry,
        )
        mod_roles_service = ModRolesService(
            database=MongoRolesDatabase(database),
            platform=DiscordRolesPlatform(client),
            registry=registry,
            members=DiscordRolesPlatform(client),
            cache=state,
        )
        return {
            "registry": registry,
            "channel_service": channel_service,
            "mod_roles_service": mod_roles_service,
            "propagate": _propagate,
        }
    except Exception:
        logger.exception("CONSOLE OPS wiring build failed")
        return None


async def apply_install_for_guild(
    guild: discord.Guild,
    mods: list[str],
    games: list[str],
    propagate: bool = True,
) -> str:
    """Apply the install selection to one guild (grants + clean + provision)."""
    from botforge.core.models.db import get_async_database
    from botforge.core.services.guild_access import GuildAccessService
    from botforge.core.services.guild_access_mongo import MongoGuildAccessDatabase

    wirings = build_console_wirings(_client_of(guild))
    if wirings is None:
        return "Wiring unavailable (MONGO_URI/REDIS_URI) — grants cannot be applied."
    registry = wirings["registry"]
    if propagate:
        games, mods = wirings["propagate"](registry, _all_games(), _all_mods(registry), mods, games)

    guild_id = str(guild.id)
    access = GuildAccessService(
        MongoGuildAccessDatabase(get_async_database()), games=_all_games(), mods=_all_mods(registry)
    )
    previous_mods = set(await access.enabled_mods(guild_id))
    doc = await access.set_grants(guild_id, games=games, mods=mods)
    removed = previous_mods - set(mods)
    lines = [f"Grants updated: mods {doc['mods']}, games {doc['games']}."]

    channel_service = wirings["channel_service"]
    mod_roles_service = wirings["mod_roles_service"]
    for mod_name in sorted(removed):
        await _uninstall_mod_for_guild(guild, mod_name, channel_service, mod_roles_service)
    if removed:
        lines.append(f"Uninstalled mods cleaned (channels + roles): {sorted(removed)}.")

    # The provision rides the SAME machinery as the console modal and the
    # repair button (provision_mod_roles then provision_mod_channels): the
    # mod's own folder (category), its convention channels (général, admin,
    # the seasonal panels) and its declared channels — never the legacy
    # ChannelService path, which created the declared channels at the guild
    # ROOT with no folder (the merlin hierarchy bug of 2026-11-19).
    from botforge.discord.locales import guild_locale
    from botforge.discord.mods_forum import provision_mod_channels, provision_mod_roles

    seam = _ProvisioningSeam(
        _client_of(guild),
        registry=registry,
        mod_roles_service=mod_roles_service,
        locale=guild_locale(guild),
    )
    provisioned = 0
    for mod_name in mods:
        try:
            await provision_mod_roles(seam, guild_id, mod_name)
            ensured = await provision_mod_channels(seam, guild_id, mod_name)
            if ensured:
                lines.append(f"{mod_name}: {ensured} channel(s) provisioned in its folder.")
            provisioned += 1
        except Exception:
            logger.warning("CONSOLE OPS provisioning failed (%s)", mod_name, exc_info=True)
    lines.append(f"{provisioned} mod(s) provisioned (roles + folder + channels).")
    return "\n".join(lines)


async def apply_ensure_tree_for_guild(guild: discord.Guild) -> str:
    """Re-provision the guild's declared platform tree, headless.

    The inverse of reset-data (which wipes the stored channel
    resolutions): a nuked guild has no admin channel left, so no
    Synchroniser button is reachable — the boot deliberately never
    creates (a member deleting a salon owns the decision), and
    install provisions mod channels only. This action rebuilds the
    PLATFORM scopes (bot, games, mods, and every granted game's scope)
    through the same provision + persist seam the Synchroniser uses,
    behind the console's own gates.
    """
    from botforge.core.models.db import get_async_database
    from botforge.core.services.guild_access import GuildAccessService
    from botforge.core.services.guild_access_mongo import MongoGuildAccessDatabase
    from botforge.discord.ui.panels import registered_scopes
    from botforge.discord.ui.panels_provisioning import persist_resolutions, provision_scope
    from botforge.discord.ui.panels_scopes import register_platform_scopes

    wirings = build_console_wirings(_client_of(guild))
    if wirings is None:
        return "Wiring unavailable (MONGO_URI/REDIS_URI) — the tree cannot be provisioned."
    register_platform_scopes()

    from botforge.discord.locales import guild_locale

    locale = guild_locale(guild)  # Discord's own signal: the server's language

    access = GuildAccessService(
        MongoGuildAccessDatabase(get_async_database()),
        games=_all_games(),
        mods=_all_mods(wirings["registry"]),
    )
    granted_games = set(await access.enabled_games(str(guild.id)))

    lines: list[str] = []
    for spec in registered_scopes():
        if spec.scope.startswith("games/"):
            game_key = spec.scope.split("/", 1)[1]
            if game_key not in granted_games:
                lines.append(f"{spec.scope}: skipped (game not granted).")
                continue
        try:
            resolved = await provision_scope(guild, spec, locale, _tree_translate)
            await persist_resolutions(str(guild.id), spec.scope, resolved)
            lines.append(f"{spec.scope}: {len(resolved)} channel(s) ensured.")
        except Exception:
            logger.warning("CONSOLE OPS tree ensure failed (%s)", spec.scope, exc_info=True)
            lines.append(f"{spec.scope}: failed (see the logs).")
    lines.append(
        "Restart the bot (env-control) so the boot routing pins the "
        "menus into the fresh channels."
    )
    return "\n".join(lines)


def _tree_translate(key: str, locale: str) -> str:
    """Render a tree label through the REAL catalog — the channel NAME.

    provision_scope uses the translate seam for the created channels'
    names: a stub here once named the channels after the i18n KEYS
    ("uipanelschannelsgeneral" — the merlin incident of 2026-11-19).
    The guild locale first, the English catalog as the fallback.
    """
    from botforge.core.services.i18n import MessageCatalog

    catalog = MessageCatalog(CONFIG_DIR)
    rendered = catalog.render(key, locale)
    return rendered if rendered != key else catalog.render(key, "en")


def _client_of(guild: discord.Guild) -> discord.Client:
    """Recover the client from a guild object (discord.py state seam)."""
    return guild._state._get_client()


class _ProvisioningSeam:
    """The headless stand-in for the wired bot object (the provision path).

    ``provision_mod_roles``/``provision_mod_channels`` read their
    dependencies off the BOT (registry, mod_roles_service, the message
    catalog, the logs seam for the locale) and recover the guild via
    ``bot.get_guild`` — a bare console client carries none of the four.
    Every other attribute delegates to the real client.
    """

    def __init__(
        self,
        client: discord.Client,
        registry: Any,
        mod_roles_service: Any,
        locale: str,
    ) -> None:
        from botforge.core.services.i18n import MessageCatalog

        self._client = client
        self.registry = registry
        self.mod_roles_service = mod_roles_service
        self.messages = MessageCatalog(CONFIG_DIR)
        self.logs_service = self._LocaleOnly(locale)

    class _LocaleOnly:
        """A locale-only logs seam: the guild's language is already resolved."""

        def __init__(self, locale: str) -> None:
            self._locale = locale

        async def get_locale(self, guild_id: str) -> str:
            del guild_id  # resolved at the seam's construction — fail-safe
            return self._locale

    def __getattr__(self, item: str) -> Any:
        return getattr(self._client, item)


def _all_games() -> tuple[str, ...]:
    """Return the platform's known games (config/games directories)."""
    games_dir = CONFIG_DIR / "games"
    if not games_dir.is_dir():
        return ()
    return tuple(sorted(entry.name for entry in games_dir.iterdir() if entry.is_dir()))


def _all_mods(registry: Any) -> tuple[str, ...]:
    return tuple(registry.enabled())


async def _uninstall_mod_for_guild(
    guild: discord.Guild,
    mod_name: str,
    channel_service: Any,
    mod_roles_service: Any,
) -> None:
    """Delete one uninstalled mod's channels and roles, then their mappings."""
    registry_mods = channel_service._registry
    definition = registry_mods.get(mod_name) if registry_mods is not None else None
    guild_id = str(guild.id)
    for category_def in getattr(definition, "channel_categories", ()) or ():
        category = f"{mod_name}:{category_def.key}"
        stored = await channel_service._db.find_channel(guild_id, category)
        if stored is not None:
            channel = guild.get_channel(int(stored.channel_id))
            if channel is not None:
                try:
                    await channel.delete(reason=f"botforge console ops: uninstall {mod_name}")
                except Exception:
                    logger.warning("CONSOLE OPS uninstall channel failed (%s)", category, exc_info=True)
        await channel_service._db.delete_channel(guild_id, category)
        await channel_service._cache.delete_state("channels", f"{guild_id}:{category}")
    for mapping in await mod_roles_service._db.list_role_mappings(guild_id, mod_name):
        role = guild.get_role(int(mapping.role_id))
        if role is not None:
            try:
                await role.delete(reason=f"botforge console ops: uninstall {mod_name}")
            except Exception:
                logger.warning("CONSOLE OPS uninstall role failed (%s)", mapping.role_key, exc_info=True)
        await mod_roles_service._db.delete_role_mapping(guild_id, mod_name, mapping.role_key)
        await mod_roles_service._cache.delete_state("roles:mod", f"{guild_id}:{mod_name}:{mapping.role_key}")
