"""Unit tests for the console ops CLI's Discord session handling.

The regression these pin: ``login()`` only authenticates over HTTP, so
the gateway must run for the ready wait to ever fire — the first
headless run wedged forever in ``wait_until_ready()`` (env-console job
hung >1h). The CLI now starts the gateway as a task, waits for the
ready event with a hard timeout and always closes the client.
"""

from __future__ import annotations

import asyncio
import sys
import types
from typing import Any

import pytest

import botforge.cli.console_ops as console_ops


class _FakeIntents:
    def __init__(self) -> None:
        self.guilds = False
        self.members = False

    @classmethod
    def default(cls) -> _FakeIntents:
        return cls()


class _FakeGuild:
    def __init__(self, guild_id: int) -> None:
        self.id = guild_id
        self.name = f"guild-{guild_id}"


class _FakeClient:
    """A discord.Client stand-in: start() fires on_ready then parks."""

    def __init__(self, *, fire_ready: bool = True) -> None:
        self.intents: Any = None
        self._fire_ready = fire_ready
        self._on_ready: Any = None
        self._closed = asyncio.Event()
        self.started = False
        self.token = ""

    def event(self, func: Any) -> Any:
        self._on_ready = func
        return func

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def start(self, token: str) -> None:
        self.started = True
        self.token = token
        if self._fire_ready and self._on_ready is not None:
            await self._on_ready()
        await self._closed.wait()

    async def close(self) -> None:
        self._closed.set()

    def get_guild(self, guild_id: int) -> _FakeGuild:
        return _FakeGuild(guild_id)


@pytest.fixture()
def _fake_discord(monkeypatch: Any) -> _FakeClient:
    """Point the CLI's `import discord` at a fake module with one client.

    The real botforge.discord.console module loads first (its module-level
    DynamicItem subclasses need the real discord.ui), then only the CLI's
    runtime `import discord` resolves to the fake.
    """
    import botforge.discord.console  # noqa: F401 — load against the real discord

    client = _FakeClient()
    module = types.ModuleType("discord")
    module.Intents = _FakeIntents  # type: ignore[attr-defined]
    module.Client = lambda intents=None: client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "discord", module)
    return client


class TestConsoleOpsSession:
    @pytest.mark.asyncio
    async def test_reset_data_starts_the_gateway_and_closes_it(
        self, monkeypatch: Any, _fake_discord: _FakeClient
    ) -> None:
        monkeypatch.setenv("DISCORD_TOKEN", "token-1")
        calls: list[str] = []

        async def _fake_reset(guild_id: str) -> dict[str, int]:
            calls.append(guild_id)
            return {"channels": 3}

        monkeypatch.setattr("botforge.discord.console._reset_guild_data", _fake_reset)
        code = await console_ops._run("reset-data", ["1556420786720473178"], [], [], False)
        assert code == 0
        assert calls == ["1556420786720473178"]
        assert _fake_discord.started  # the gateway ran — the pinned regression
        assert _fake_discord._closed.is_set()  # closed on exit
        assert _fake_discord.token == "token-1"  # noqa: S105 — a fake token, not a secret

    @pytest.mark.asyncio
    async def test_a_gateway_that_never_becomes_ready_fails_loudly(
        self, monkeypatch: Any
    ) -> None:
        monkeypatch.setenv("DISCORD_TOKEN", "token-1")
        monkeypatch.setattr(console_ops, "_READY_TIMEOUT_S", 0.05)
        client = _FakeClient(fire_ready=False)
        module = types.ModuleType("discord")
        module.Intents = _FakeIntents  # type: ignore[attr-defined]
        module.Client = lambda intents=None: client  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "discord", module)
        code = await console_ops._run("reset-data", ["1"], [], [], False)
        assert code == 1
        assert client.started


def test_the_tree_translator_renders_real_labels() -> None:
    """Regression: a stub translator named the channels after the i18n KEYS.

    provision_scope builds the channel NAMES from the translate seam —
    the merlin incident of 2026-11-19 (dozens of channels named
    "uipanelschannelsgeneral"). The seam must render through the real
    catalog, never echo the key.
    """
    from botforge.discord.console_ops_runner import _tree_translate

    rendered = _tree_translate("ui.panels.channels.general", "en")
    assert rendered != "ui.panels.channels.general"
    assert rendered
