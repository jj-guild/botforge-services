"""Unit tests for the bot factory (kingdoms-services#12)."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import discord
import pytest

from kingdoms.discord.bot.factory import (
    READY_LOG_LINE,
    BotConfig,
    KingdomsBot,
    _log_guild_member_locales,
    _log_guild_native_locales,
    create_bot,
)


@pytest.fixture
def config_dir() -> str:
    """Path to the repository's real config directory."""
    from pathlib import Path

    return str(Path(__file__).resolve().parents[3] / "config")


def test_bot_config_from_env_reads_environment() -> None:
    config = BotConfig.from_env(
        {
            "MONGO_URI": "mongodb://localhost:27017",
            "REDIS_URI": "redis://localhost:6379",
            "DISCORD_TOKEN": "token",
            "BOT_ADMINS": "111,222",
            "CICD_GUILD_ID": "12345",
            "LOG_LEVEL": "DEBUG",
        }
    )
    assert config.mongo_uri == "mongodb://localhost:27017"
    assert config.redis_uri == "redis://localhost:6379"
    assert config.discord_token == "token"  # noqa: S105 — test value, not a credential
    assert config.bot_admins == "111,222"
    assert config.sync_guild_id == "12345"
    assert config.log_level == "DEBUG"


def test_bot_config_from_env_defaults_are_empty() -> None:
    config = BotConfig.from_env({})
    assert config.mongo_uri == ""
    assert config.sync_guild_id == ""


def test_create_bot_builds_client_with_tree_and_services(config_dir: str) -> None:
    bot = create_bot(BotConfig(config_dir=config_dir))
    assert isinstance(bot, KingdomsBot)
    assert isinstance(bot, discord.Client)
    assert isinstance(bot.tree, discord.app_commands.CommandTree)
    assert bot.status_service is not None
    assert "status" in {command.name for command in bot.tree.get_commands()}


def test_create_bot_keeps_ready_marker_contract(config_dir: str) -> None:
    """CI smoke greps KINGDOMS_BOT_READY; the factory must log the same marker."""
    assert READY_LOG_LINE == "KINGDOMS_BOT_READY"


async def test_ready_marker_logged_on_ready(config_dir: str, caplog: pytest.LogCaptureFixture) -> None:
    bot = create_bot(BotConfig(config_dir=config_dir))
    with caplog.at_level(logging.INFO, logger="kingdoms.bot"):
        await bot.on_ready()
    assert any(READY_LOG_LINE in record.message for record in caplog.records)


def test_create_bot_parses_bot_admins(config_dir: str) -> None:
    bot = create_bot(BotConfig(config_dir=config_dir, bot_admins="111,222"))
    assert bot.status_service.bot_admins == ("111", "222")


class _FakeLogsService:
    """Minimal LogService stand-in recording resolve_channel + locale calls."""

    def __init__(self) -> None:
        self.resolved: list[str] = []
        self.ensured_guild_locales: list[tuple[str, str]] = []
        self.ensured_user_locales: list[tuple[str, str]] = []
        self.observed_user_locales: list[tuple[str, str]] = []
        self.observed_member_locales: list[tuple[str, str, str]] = []

    async def get_locale(self, guild_id: str) -> str:
        return "en"

    async def resolve_channel(self, guild_id: str) -> str:
        self.resolved.append(guild_id)
        return "logs-channel"

    async def ensure_guild_locale(self, guild_id: str, locale: str) -> None:
        self.ensured_guild_locales.append((guild_id, locale))

    async def ensure_user_locale(self, user_id: str, locale: str) -> None:
        self.ensured_user_locales.append((user_id, locale))

    async def observe_user_locale(self, user_id: str, locale: str) -> None:
        self.observed_user_locales.append((user_id, locale))

    async def observe_guild_member_locale(self, guild_id: str, user_id: str, locale: str) -> None:
        self.observed_member_locales.append((guild_id, user_id, locale))


class _FakeAdminChannelService:
    """Minimal AdminChannelService stand-in recording resolve_channel calls."""

    def __init__(self) -> None:
        self.resolved: list[tuple[str, tuple[str, ...]]] = []

    async def resolve_channel(self, guild_id: str, admin_ids: tuple[str, ...] = ()) -> str:
        self.resolved.append((guild_id, admin_ids))
        return "admin-channel"


@pytest.mark.asyncio
async def test_boot_route_channels_resolves_both_services(config_dir: str) -> None:
    bot = create_bot(BotConfig(config_dir=config_dir))
    logs = _FakeLogsService()
    admin = _FakeAdminChannelService()
    bot.logs_service = logs  # type: ignore[assignment]
    bot.admin_channel_service = admin  # type: ignore[assignment]
    bot._connection._guilds[42] = SimpleNamespace(id=42)
    await bot._boot_route_channels()
    # the tree owns the channels: the managed services are routed onto
    # the tree's stored ids (nothing stored here — Mongo unwired in tests),
    # never resolved by name at boot.
    assert logs.resolved == []
    assert admin.resolved == []


@pytest.mark.asyncio
async def test_boot_route_channels_gated_by_announce_enabled(config_dir: str) -> None:
    """The CI/CD smoke bot (KINGDOMS_ANNOUNCE_ENABLED=0) never provisions channels."""
    bot = create_bot(BotConfig(config_dir=config_dir, announce_enabled="0"))
    logs = _FakeLogsService()
    bot.logs_service = logs  # type: ignore[assignment]
    bot._connection._guilds[42] = SimpleNamespace(id=42)
    await bot._boot_route_channels()
    assert logs.resolved == []


@pytest.mark.asyncio
async def test_boot_route_channels_runs_once_across_reconnects(config_dir: str) -> None:
    bot = create_bot(BotConfig(config_dir=config_dir))
    logs = _FakeLogsService()
    bot.logs_service = logs  # type: ignore[assignment]
    bot._connection._guilds[42] = SimpleNamespace(id=42)
    await bot._boot_route_channels()
    await bot._boot_route_channels()
    # idempotent boot: the managed services are routed (not name-resolved)
    assert logs.resolved == []


@pytest.mark.asyncio
async def test_boot_route_channels_survives_one_guild_failure(config_dir: str) -> None:
    bot = create_bot(BotConfig(config_dir=config_dir))
    logs = _FakeLogsService()
    admin = _FakeAdminChannelService()
    bot.logs_service = logs  # type: ignore[assignment]
    bot.admin_channel_service = admin  # type: ignore[assignment]
    bot._connection._guilds[42] = SimpleNamespace(id=42)

    async def _boom(guild_id: str, *args: object, **kwargs: object) -> None:
        raise RuntimeError("routing exploded")

    bot.logs_service.set_channel = _boom  # type: ignore[method-assign]
    await bot._boot_route_channels()
    # best-effort boot: one service's routing failure never blocks the rest
    assert admin.resolved == []


def test_create_bot_without_redis_has_no_shared_state(config_dir: str) -> None:
    """No REDIS_URI (unit tests, local runs): no shared state, degraded paths."""
    bot = create_bot(BotConfig(config_dir=config_dir))
    assert bot.state_service is None
    assert bot.roles_service is None
    assert bot.registration_engine is None


def test_create_bot_with_redis_shares_one_state_service(config_dir: str) -> None:
    """With Redis configured, every wired service holds the SAME StateService.

    Regression guard (kingdoms-services#225): each service used to build its
    own never-started store; the shared instance is what setup_hook connects.
    """
    from kingdoms.core.services.state import StateService

    bot = create_bot(
        BotConfig(config_dir=config_dir, mongo_uri="mongodb://localhost:27017", redis_uri="redis://localhost:6379")
    )
    assert isinstance(bot.state_service, StateService)
    assert bot.roles_service is not None
    assert bot.roles_service._cache is bot.state_service
    assert bot.channel_service is not None
    assert bot.channel_service._cache is bot.state_service
    assert bot.logs_service is not None
    assert bot.logs_service._state is bot.state_service
    assert bot.registration_engine is not None
    assert bot.registration_engine._state is bot.state_service


async def test_setup_hook_starts_shared_state_and_registration_engine(config_dir: str) -> None:
    """setup_hook must connect the shared state and resume workflows.

    Regression guard (kingdoms-services#225): 'state store not started' meant
    nothing ever called start() — the bot booted degraded in production with
    green CI because no test asserted the store connects on the startup path.
    """
    from tests.mocks.state_mock import InMemoryStateStore

    class _RecordingStore(InMemoryStateStore):
        started = False
        stopped = False

        async def start(self) -> None:
            self.started = True
            await super().start()

        async def stop(self) -> None:
            self.stopped = True
            await super().stop()

    store = _RecordingStore()
    bot = create_bot(
        BotConfig(config_dir=config_dir, mongo_uri="mongodb://localhost:27017", redis_uri="redis://localhost:6379")
    )
    assert bot.state_service is not None
    bot.state_service._store = store

    class _NullWorkflowStore:
        """Store-less engine stand-in: resume finds nothing, start is a no-op."""

        started = False
        stopped = False

        async def start(self) -> None:
            self.started = True

        async def stop(self) -> None:
            self.stopped = True

        async def list_by_status(self, status: object) -> list[object]:
            return []

    assert bot.registration_engine is not None
    workflow_store = _NullWorkflowStore()
    bot.registration_engine._store = workflow_store

    await bot.setup_hook()
    assert store.started, "setup_hook must start the shared state store"
    assert workflow_store.started, "setup_hook must start the registration workflow store"
    await bot.registration_engine.stop()
    assert workflow_store.stopped
    await bot.state_service.close()
    assert store.stopped, "close() must stop the shared state store"


async def test_on_guild_join_resolves_the_native_guild_locale(
    config_dir: str, caplog: pytest.LogCaptureFixture
) -> None:
    """on_guild_join reads guild.preferred_locale through the native seam.

    The GUILD_CREATE payload always carries preferred_locale, so the guild's
    language is resolvable at join time; the locale is resolved (and logged),
    never stored on our side.
    """
    from tests.mocks import MockGuild

    bot = create_bot(BotConfig(config_dir=config_dir))
    guild = MockGuild(id=424242, preferred_locale=discord.Locale.french)
    with caplog.at_level(logging.INFO, logger="kingdoms.bot"):
        await bot.on_guild_join(guild)
    assert any("GUILD JOIN" in record.message and "native_locale=fr" in record.message for record in caplog.records)


async def test_on_guild_join_unknown_locale_falls_back_to_english(
    config_dir: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A locale outside the en/fr catalog resolves to English at join time."""
    from tests.mocks import MockGuild

    bot = create_bot(BotConfig(config_dir=config_dir))
    guild = MockGuild(id=424243, preferred_locale="ja")
    with caplog.at_level(logging.INFO, logger="kingdoms.bot"):
        await bot.on_guild_join(guild)
    assert any("GUILD JOIN" in record.message and "native_locale=en" in record.message for record in caplog.records)


def test_log_guild_native_locales_logs_raw_and_resolved_per_guild(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One greppable GUILD NATIVE LOCALE line per guild: raw + resolved.

    The discord-smoke CI job greps these lines on the real gateway to prove
    guild.preferred_locale is populated; raw=None must never happen.
    """
    from tests.mocks import MockGuild

    guilds = [
        MockGuild(id=424242, preferred_locale=discord.Locale.french),
        MockGuild(id=424243, preferred_locale="en-US"),
    ]
    with caplog.at_level(logging.INFO, logger="kingdoms.bot"):
        _log_guild_native_locales(guilds)
    lines = [r.message for r in caplog.records if "GUILD NATIVE LOCALE" in r.message]
    assert len(lines) == 2
    assert any("guild=424242" in line and "raw=fr" in line and "resolved=fr" in line for line in lines)
    assert any("guild=424243" in line and "raw=en-US" in line and "resolved=en" in line for line in lines)


def test_log_guild_member_locales_probes_each_member(caplog: pytest.LogCaptureFixture) -> None:
    """One GUILD MEMBER LOCALE line per member, raw=None (no member.locale in the API).

    Discord exposes a user's language only inside interactions; the boot
    enumeration is the proof probe the discord-smoke CI greps.
    """
    from tests.mocks import MockGuild, MockMember

    guild = MockGuild(id=424242)
    guild.add_member(MockMember(name="alice", guild=guild))
    guild.add_member(MockMember(name="bob", guild=guild))
    with caplog.at_level(logging.INFO, logger="kingdoms.bot"):
        _log_guild_member_locales([guild])
    lines = [r.message for r in caplog.records if "GUILD MEMBER LOCALE" in r.message]
    assert len(lines) == 2
    assert all("guild=424242" in line and "raw=None" in line for line in lines)


async def test_on_interaction_logs_the_clicker_locale(config_dir: str, caplog: pytest.LogCaptureFixture) -> None:
    """on_interaction logs INTERACTION USER LOCALE with raw + resolved locale.

    This is the only per-user language signal Discord exposes
    (interaction.locale) — the clicker's own client language.
    """
    from tests.mocks import MockGuild, MockInteraction, MockMember

    bot = create_bot(BotConfig(config_dir=config_dir))
    guild = MockGuild(id=424242, preferred_locale="en-US")
    member = MockMember(name="alice", guild=guild)
    interaction = MockInteraction(user=member, guild=guild, locale="fr")
    with caplog.at_level(logging.INFO, logger="kingdoms.bot"):
        await bot.on_interaction(interaction)
    assert any(
        "INTERACTION USER LOCALE" in r.message
        and f"user={member.id}" in r.message
        and f"guild={guild.id}" in r.message
        and "raw=fr" in r.message
        and "resolved=fr" in r.message
        for r in caplog.records
    )


async def test_on_guild_join_seeds_the_detected_guild_locale(config_dir: str) -> None:
    """The join-detected native locale is stored as the guild's default."""
    from tests.mocks import MockGuild

    bot = create_bot(BotConfig(config_dir=config_dir))
    fake = _FakeLogsService()
    bot.logs_service = fake
    await bot.on_guild_join(MockGuild(id=424242, preferred_locale=discord.Locale.french))
    assert ("424242", "fr") in fake.ensured_guild_locales


async def test_on_interaction_seeds_the_detected_user_locale(config_dir: str) -> None:
    """The clicker's client language (interaction.locale) is stored as the user default."""
    from tests.mocks import MockGuild, MockInteraction, MockMember

    bot = create_bot(BotConfig(config_dir=config_dir))
    fake = _FakeLogsService()
    bot.logs_service = fake
    guild = MockGuild(id=424242, preferred_locale="en-US")
    member = MockMember(name="alice", guild=guild)
    await bot.on_interaction(MockInteraction(user=member, guild=guild, locale="fr"))
    assert (str(member.id), "fr") in fake.ensured_user_locales
