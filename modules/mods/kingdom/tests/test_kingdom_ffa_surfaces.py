"""Kingdoms mod FFA Exploration (P4.5) — wiring smoke tests (#368).

The Saturday Expedition engine and its join surface degrade quietly
without a stack; the error mapping stays stable across locales, and
the ported FFAExplorationService carries its error hierarchy.
"""

from __future__ import annotations

import pytest


def test_ffa_modules_import() -> None:
    """The P4.5 modules import (the engine + the join surface)."""
    from botforge.mods.kingdom.cogs.kingdom import ffa  # noqa: F401
    from botforge.mods.kingdom.ffa_exploration import FFAExplorationService  # noqa: F401


def test_ffa_error_hierarchy() -> None:
    """The FFA errors nest under the mod's own error base."""
    from botforge.mods.kingdom.errors import KingdomModError
    from botforge.mods.kingdom.ffa_exploration import (
        FFAError,
        FFAFullError,
        FFAKingdomFullError,
        FFANotOpenError,
    )

    assert issubclass(FFAError, KingdomModError)
    assert issubclass(FFANotOpenError, FFAError)
    assert issubclass(FFAFullError, FFAError)
    assert issubclass(FFAKingdomFullError, FFAError)


def test_ffa_error_note_maps_engine_errors() -> None:
    """Each FFA engine refusal maps to its player-facing note."""
    from botforge.mods.kingdom.attacks import LordLockedError
    from botforge.mods.kingdom.cogs.kingdom.ffa import _ffa_error_note
    from botforge.mods.kingdom.cogs.kingdom.strings import strings
    from botforge.mods.kingdom.ffa_exploration import (
        FFAFullError,
        FFAKingdomFullError,
        FFANotOpenError,
    )

    s = strings("fr")
    assert _ffa_error_note(FFANotOpenError("x"), s) == s["ffa_not_open"]
    assert _ffa_error_note(FFAFullError("x"), s) == s["ffa_full"]
    assert _ffa_error_note(FFAKingdomFullError("x"), s) == s["ffa_kingdom_full"]
    assert _ffa_error_note(LordLockedError("x"), s) == s["ffa_locked"]
    assert _ffa_error_note(ValueError("boom"), s) is None


def test_ffa_strings_parity() -> None:
    """The FFA keys exist and format with the announce/start arities."""
    from botforge.mods.kingdom.cogs.kingdom.strings import strings

    for locale in ("fr", "en"):
        s = strings(locale)
        s["ffa_announce"].format("14h00", 75, 7, s["ffa_mode_one"])
        s["ffa_start"].format(3, 75)
        s["ffa_join_note"].format("Lord", 1, 7)
        s["ffa_left_note"].format("Lord", 0, 7)


@pytest.mark.asyncio
async def test_ffa_tick_degrades_without_stack() -> None:
    """The FFA tick is a no-op when the stack is not wired."""
    from botforge.mods.kingdom.cogs.kingdom import phases

    class _Bot:
        guilds: list = []

    await phases.run_ffa_tick_safe(_Bot())


def test_ffa_salon_resolves_by_stored_ref_only() -> None:
    """The FFA salon resolves by its STORED ref, never by name (#367)."""
    from botforge.mods.kingdom.cogs.kingdom.phases import _ffa_salon

    class _Channel:
        id = 555

    class _Guild:
        def get_channel(self, channel_id: int) -> object | None:
            return _Channel() if channel_id == 555 else None

    class _FFA:
        salon_id = "555"

    class _NoSalon:
        salon_id = None

    class _Other:
        salon_id = "999"

    assert _ffa_salon(_Guild(), _FFA()) is not None
    assert _ffa_salon(_Guild(), _NoSalon()) is None
    assert _ffa_salon(_Guild(), _Other()) is None
    assert _ffa_salon(None, _FFA()) is None


def test_ffa_salon_title_string_exists() -> None:
    """The salon's title key exists in both locales (the channel name)."""
    from botforge.mods.kingdom.cogs.kingdom.strings import strings

    for locale in ("fr", "en"):
        assert strings(locale)["ffa_salon_title"]
