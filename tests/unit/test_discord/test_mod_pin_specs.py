"""The mod pin lifecycle covers the mod's WHOLE scope (Drasah 18/11).

`ensure_mod_pins` (the install/repair path) must land every static pin
registered under ``mod/<name>`` — the SDK home/admin menus AND the
mod's own pinned surfaces (its cogs register them at boot). The
postuler-hybride-v1 regression: the repair created the declared
« apply » channel but never pinned its golden panel, because
``_mod_pin_specs`` filtered to the menus only.
"""

from __future__ import annotations

from typing import Any

from botforge.discord.scope_pins import (
    _mod_pin_specs,
    ensure_mod_pins,
    ensure_mod_pins_report,
)
from botforge.discord.static_pins import StaticPinnedView, register_static_pin, reset_static_pins


def _spec(key: str, scope: str) -> StaticPinnedView:
    async def _channel(guild_id: str) -> str:
        return "1"

    async def _layout(guild_id: str) -> Any:
        return None

    return StaticPinnedView(
        key=key,
        mark_suffix=key,
        resolve_channel=_channel,
        build_layout=_layout,
        scope=scope,
    )


def setup_function() -> None:
    reset_static_pins()


def teardown_function() -> None:
    reset_static_pins()


def test_the_mod_specs_cover_home_admin_and_the_mods_own_pins() -> None:
    """home + admin + the cog-declared panels — the WHOLE mod scope."""
    register_static_pin(_spec("view:mod:kingdom:home", "mod/kingdom"))
    register_static_pin(_spec("view:mod:kingdom:admin", "mod/kingdom"))
    register_static_pin(_spec("view:mod:kingdom:apply", "mod/kingdom"))
    register_static_pin(_spec("view:mod:other:home", "mod/other"))
    register_static_pin(_spec("view:home", ""))

    keys = {spec.key for spec in _mod_pin_specs(None, "kingdom")}
    assert keys == {
        "view:mod:kingdom:home",
        "view:mod:kingdom:admin",
        "view:mod:kingdom:apply",
    }, "the mod's own pinned surfaces ride the install/repair lifecycle"


def test_the_mod_specs_stay_empty_without_pins() -> None:
    """No registered pins — the mod specs degrade to empty."""
    assert _mod_pin_specs(None, "kingdom") == []


# ── the repair's per-pin report (Drasah 18/11, kingdom-tests panel missing) ──
# A pin that silently missed its salon is the UNDEBUGGABLE kind of failure:
# `ensure_mod_pins_report` must name the failing step for EVERY spec that
# did not land (no resolution / channel out of cache / exception), and
# `ensure_mod_pins` keeps its int contract.


class _StubGuild:
    """A guild whose channel cache may or may not hold one channel."""

    def __init__(self, has_channel: bool = True) -> None:
        self._has = has_channel

    def get_channel(self, channel_id: int) -> object | None:
        return object() if self._has else None


class _StubBot:
    """No registry enabled → register_mod_pins degrades to empty."""

    def __init__(self, guild: object | None) -> None:
        self._guild = guild

    def get_guild(self, guild_id: int) -> object | None:
        return self._guild


def _spec_with(key: str, channel_id: str | None) -> StaticPinnedView:
    """A mod-scope pin spec resolving to `channel_id` (None = missing)."""

    async def _channel(guild_id: str) -> str | None:
        return channel_id

    view = _spec(key, "mod/kingdom")
    # _spec() builds its own resolver; swap in ours
    object.__setattr__(view, "resolve_channel", _channel)
    return view


async def test_the_report_names_the_missing_channel_resolution() -> None:
    """No stored resolution — the report says so, nothing lands."""
    register_static_pin(_spec_with("view:mod:kingdom:settings", None))

    landed, report = await ensure_mod_pins_report(_StubBot(None), "1", "kingdom")

    assert landed == 0
    assert [key for key, _reason in report] == ["view:mod:kingdom:settings"]
    assert "résolution" in report[0][1]


async def test_the_report_names_the_channel_out_of_cache() -> None:
    """A stored id the cache no longer resolves — the report says so."""
    register_static_pin(_spec_with("view:mod:kingdom:settings", "55"))

    bot = _StubBot(_StubGuild(has_channel=False))
    landed, report = await ensure_mod_pins_report(bot, "1", "kingdom")

    assert landed == 0
    assert "cache" in report[0][1]


async def test_the_report_names_the_ensure_exception(
    monkeypatch: Any,
) -> None:
    """An exception during the ensure — the report carries its summary."""
    import botforge.discord.static_pins as static_pins

    async def _boom(bot: Any, spec: Any, guild_id: str) -> bool:
        raise RuntimeError("boom")

    monkeypatch.setattr(static_pins, "ensure_static_pin", _boom)
    register_static_pin(_spec_with("view:mod:kingdom:settings", "55"))

    bot = _StubBot(_StubGuild(has_channel=True))
    landed, report = await ensure_mod_pins_report(bot, "1", "kingdom")

    assert landed == 0
    assert "RuntimeError: boom" in report[0][1]


async def test_the_report_lands_the_healthy_pin(monkeypatch: Any) -> None:
    """A healthy spec lands and stays out of the report."""

    async def _ok(bot: Any, spec: Any, guild_id: str) -> bool:
        return True

    import botforge.discord.static_pins as static_pins

    monkeypatch.setattr(static_pins, "ensure_static_pin", _ok)
    register_static_pin(_spec_with("view:mod:kingdom:settings", "55"))

    bot = _StubBot(_StubGuild(has_channel=True))
    landed, report = await ensure_mod_pins_report(bot, "1", "kingdom")

    assert landed == 1
    assert report == []


async def test_ensure_mod_pins_keeps_its_int_contract() -> None:
    """The legacy seam returns the landed count only."""
    register_static_pin(_spec_with("view:mod:kingdom:settings", None))

    assert await ensure_mod_pins(_StubBot(None), "1", "kingdom") == 0
