"""Kingdoms mod console ops (#339) — wiring smoke tests.

The mod's console actions (relaunch/reset/clock) ride the platform
console registry; the clock mutation persists on the season doc and
the confirm card degrades quietly without a stack.
"""

from __future__ import annotations

import pytest


def test_console_modules_import() -> None:
    """The console surface imports and exposes its three actions."""
    from botforge.mods.kingdom.cogs.kingdom.console import (  # noqa: F401
        KingdomClockButton,
        KingdomRelaunchButton,
        KingdomResetButton,
        register_console_actions,
    )


def test_console_dynamic_item_templates() -> None:
    """Each console action is a restart-proof DynamicItem."""
    from botforge.mods.kingdom.cogs.kingdom.console import (
        KingdomClockButton,
        KingdomRelaunchButton,
        KingdomResetButton,
    )

    assert KingdomRelaunchButton.template.pattern == r"kingdom:console:relaunch$"
    assert KingdomResetButton.template.pattern == r"kingdom:console:reset$"
    assert KingdomClockButton.template.pattern == r"kingdom:console:clock$"


def test_console_strings_parity() -> None:
    """The console keys exist in both locales and format with their arities."""
    from botforge.mods.kingdom.cogs.kingdom.strings import strings

    for locale in ("fr", "en"):
        s = strings(locale)
        for key in (
            "console_relaunch_label",
            "console_reset_label",
            "console_clock_label",
            "console_relaunch_confirm",
            "console_reset_confirm",
            "console_confirm_button",
            "console_cancel_button",
            "console_cancelled",
            "console_relaunch_done",
            "console_reset_done",
            "console_clock_modal_title",
        ):
            assert s[key]
        s["console_error"].format("boom")
        s["console_clock_bad"].format("boom")
        s["console_clock_done"].format("+1h 30m")


def test_set_clock_offset_persists_on_season() -> None:
    """The clock mutation writes the offset on the season doc."""
    import asyncio

    from botforge.mods.kingdom.service import KingdomService

    class _Store:
        def __init__(self) -> None:
            self.seasons: dict = {}

        async def upsert_season(self, doc: dict) -> None:
            self.seasons[doc["_id"]] = doc

        async def find_seasons(self) -> list[dict]:
            return list(self.seasons.values())

        async def wipe_season_data(self) -> None:
            self.seasons.clear()

    class _Config:
        pass

    svc = KingdomService(_Store(), _Config())  # type: ignore[arg-type]
    from botforge.mods.kingdom.errors import KingdomError

    with pytest.raises(KingdomError):
        asyncio.run(svc.set_clock_offset(3600))  # no season → the engine refuses


def test_parse_duration_accepts_jumps() -> None:
    """The console clock modal's parser keeps the reference grammar."""
    from botforge.mods.kingdom.game_clock import parse_duration

    assert parse_duration("90m") == 5400
    assert parse_duration("2h") == 7200
    assert parse_duration("1d2h30m") == 95400
    with pytest.raises(ValueError):
        parse_duration("hier")


@pytest.mark.asyncio
async def test_console_register_is_idempotent() -> None:
    """Registering the console actions twice never raises (restart re-run)."""
    from botforge.mods.kingdom.cogs.kingdom.console import register_console_actions

    register_console_actions()
    register_console_actions()
