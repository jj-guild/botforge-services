"""The admin pin diagnosis (kingdom-tests 18/11, epic #412 T1).

The platform's pin cycle is best-effort SILENT — the settings-panel
regression was invisible (the salon resynced, the panel never landed,
no message anywhere). ``pins_report`` must name the failing step for
every one of the mod's pinned surfaces, using only the platform's
public seams, and never raise.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import discord

from botforge.discord.static_pins import (
    StaticPinnedView,
    register_static_pin,
    reset_static_pins,
)
from botforge.mods.kingdom.cogs.pins_diag import admin_pin_lines, pins_report


class _Resp:
    """A minimal HTTP response for discord.NotFound construction."""

    status = 404
    reason = "Not Found"


class _Message:
    def __init__(self, pinned: bool = True) -> None:
        self.pinned = pinned
        self.id = 777


class _Channel:
    """fetch_message(777) → the message; anything else → NotFound."""

    def __init__(self, message: _Message | None) -> None:
        self._message = message

    async def fetch_message(self, message_id: int) -> _Message:
        if self._message is not None and message_id == self._message.id:
            return self._message
        raise discord.NotFound(_Resp(), "unknown message")  # type: ignore[arg-type]


class _Guild:
    def __init__(self, has_channel: bool, message: _Message | None) -> None:
        self._has = has_channel
        self._message = message

    def get_channel(self, channel_id: int) -> _Channel | None:
        if not self._has:
            return None
        assert self._message is not None
        return _Channel(self._message)


class _Client:
    def __init__(self, guild: _Guild | None) -> None:
        self._guild = guild

    def get_guild(self, guild_id: int) -> _Guild | None:
        return self._guild


class _Registry:
    """The message registry's minimal surface (resolve → id or None)."""

    def __init__(self, message_id: str | None) -> None:
        self._message_id = message_id

    async def resolve(self, platform: str, message_key: str, entity_id: str) -> Any:
        if self._message_id is None:
            return None
        return SimpleNamespace(message_id=self._message_id)


def _pin(
    channel_id: str | None,
    message_id: str | None,
    scope: str = "mod/kingdom",
    key: str = "view:mod:kingdom:settings",
) -> StaticPinnedView:
    async def _channel(guild_id: str) -> str | None:
        return channel_id

    def _layout(guild_id: str) -> None:
        return None

    return StaticPinnedView(
        key=key,
        mark_suffix=key,
        resolve_channel=_channel,
        build_layout=_layout,  # type: ignore[arg-type,return-value]
        registry=_Registry(message_id),
        scope=scope,
    )


def setup_function() -> None:
    reset_static_pins()


def teardown_function() -> None:
    reset_static_pins()


async def test_the_report_names_the_missing_resolution() -> None:
    """A pin with no stored salon resolution says so, in French."""
    register_static_pin(_pin(None, None))

    report = await pins_report(_Client(None), "1")

    assert report == [
        (
            "view:mod:kingdom:settings",
            "salon non provisionné (résolution absente — refaire un Repair)",
        )
    ]


async def test_the_report_names_the_channel_out_of_cache() -> None:
    """A stored id the bot's cache no longer holds."""
    register_static_pin(_pin("55", None))

    report = await pins_report(_Client(_Guild(has_channel=False, message=_Message())), "1")

    assert report[0][0] == "view:mod:kingdom:settings"
    assert "hors cache du bot" in report[0][1]


async def test_the_report_names_the_never_pinned_panel() -> None:
    """The salon is reachable but no pin message was ever registered."""
    register_static_pin(_pin("55", None))

    report = await pins_report(_Client(_Guild(has_channel=True, message=_Message())), "1")

    assert "jamais épinglé" in report[0][1]


async def test_the_report_names_the_deleted_pin_message() -> None:
    """A registered pin id whose message is gone — the heal contract."""
    register_static_pin(_pin("55", "777"))

    # the channel holds NOTHING: fetch_message(777) → NotFound
    report = await pins_report(_Client(_Guild(has_channel=True, message=None)), "1")

    assert "supprimé" in report[0][1]


async def test_the_report_confirms_the_healthy_pin() -> None:
    """A pinned, fetchable message reads as OK."""
    register_static_pin(_pin("55", "777"))

    report = await pins_report(_Client(_Guild(has_channel=True, message=_Message())), "1")

    assert "épinglé dans" in report[0][1]


async def test_the_report_ignores_other_scopes() -> None:
    """Only the mod's own pins ride the diagnosis."""
    register_static_pin(_pin("55", "777", scope="mod/other", key="view:mod:other:home"))
    register_static_pin(_pin("55", "777", scope="", key="view:home"))

    assert await pins_report(_Client(None), "1") == []


async def test_admin_pin_lines_render_one_line_per_pin() -> None:
    """The /kingdom followup carries a title + one line per pin."""
    register_static_pin(_pin("55", "777"))
    register_static_pin(_pin(None, None, key="view:mod:kingdom:apply"))

    lines = await admin_pin_lines(_Client(_Guild(has_channel=True, message=_Message())), "1")

    assert lines[0] == "**Panneaux du mod — diagnostic**"
    assert len(lines) == 3
    assert "view:mod:kingdom:settings" in lines[2]
    assert "view:mod:kingdom:apply" in lines[1]
    assert "résolution absente" in lines[1]


async def test_the_report_never_raises() -> None:
    """A raising seam becomes its own line — the report survives."""

    async def _boom(guild_id: str) -> Any:
        raise RuntimeError("boom")

    spec = StaticPinnedView(
        key="view:mod:kingdom:settings",
        mark_suffix="x",
        resolve_channel=_boom,
        build_layout=lambda guild_id: None,  # type: ignore[arg-type,return-value]
        scope="mod/kingdom",
    )
    register_static_pin(spec)

    report = await pins_report(_Client(None), "1")

    assert report == [("view:mod:kingdom:settings", "erreur : RuntimeError")]
