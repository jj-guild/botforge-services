"""Kingdom mod tavern surfaces (P4.4) — wiring smoke tests (#368).

The Taverne and the Chef Mercenaire degrade quietly without a stack;
the pure helpers (civ names, error mapping, market lines, drinks
options) stay stable across locales, and the ported engines carry
their error hierarchies.
"""

from __future__ import annotations

import pytest


def test_tavern_modules_import() -> None:
    """The P4.4 surface modules import (tavern + the ported engines)."""
    from botforge.mods.kingdom.cogs.kingdom import tavern  # noqa: F401
    from botforge.mods.kingdom.mercenary import MercenaryService  # noqa: F401
    from botforge.mods.kingdom.tavern import TavernService  # noqa: F401


def test_tavern_error_hierarchy() -> None:
    """The tavern and mercenary errors nest under the mod's own error base."""
    from botforge.mods.kingdom.errors import KingdomModError
    from botforge.mods.kingdom.mercenary import MercenaryError, MercenaryWindowError
    from botforge.mods.kingdom.tavern import TavernError, TavernCooldownError

    assert issubclass(TavernError, KingdomModError)
    assert issubclass(TavernCooldownError, TavernError)
    assert issubclass(MercenaryError, KingdomModError)
    assert issubclass(MercenaryWindowError, MercenaryError)


def test_civ_names_reads_the_catalog() -> None:
    """The civ-name lookup reads the config's civilizations catalog."""
    from botforge.mods.kingdom.cogs.tavern import _civ_names

    class _Civ:
        key = "britons"
        display_name = "Bretons"

    class _CivRaw:
        key = "raw"

    class _Config:
        civilizations = (_Civ(), _CivRaw())

    class _Stack:
        config = _Config()

    names = _civ_names(_Stack())
    assert names["britons"] == "Bretons"
    assert names["raw"] == "raw"  # a missing display_name falls back to the key


def test_tavern_error_note_maps_engine_errors() -> None:
    """Each tavern/mercenary engine refusal maps to its player-facing note."""
    from botforge.mods.kingdom.cogs.strings import strings
    from botforge.mods.kingdom.cogs.tavern import _error_note
    from botforge.mods.kingdom.mercenary import (
        MercenaryBidTooLowError,
        MercenaryMarketClosedError,
    )
    from botforge.mods.kingdom.service import NoSeasonError
    from botforge.mods.kingdom.tavern import (
        TavernCooldownError,
        TavernInsufficientPurseError,
    )

    s = strings("fr")
    assert _error_note(NoSeasonError("x"), s) == s["tavern_no_season"]
    assert _error_note(TavernCooldownError("x", next_at="1"), s) == s["tavern_cooldown_note"]
    assert _error_note(TavernInsufficientPurseError("x"), s) == s["tavern_no_purse"]
    assert _error_note(MercenaryBidTooLowError("x"), s) == s["mercenary_bid_too_low"]
    assert _error_note(MercenaryMarketClosedError("x"), s) == s["mercenary_closed_note"]


def test_market_lines_carry_lots_and_own_bid() -> None:
    """The market view lists the lots, the highest bid and the own line."""
    from botforge.mods.kingdom.cogs.strings import strings
    from botforge.mods.kingdom.cogs.tavern import _market_lines

    doc = {
        "closed": False,
        "lots": [
            {
                "civ": "britons",
                "uses": 2,
                "bids": [{"lord": "u1", "amount": 5}],
                "winner": None,
            },
            {"civ": "french", "uses": 1, "bids": [], "winner": None},
        ],
    }
    lines = _market_lines(doc, "u1", strings("fr"), {"britons": "Bretons"})
    assert any("Bretons" in line and "5" in line for line in lines)
    assert any("Tu as misé 5" in line for line in lines)

    closed = {
        "closed": True,
        "lots": [{"civ": "britons", "uses": 2, "bids": [], "winner": "u1"}],
    }
    lines = _market_lines(closed, "u1", strings("fr"), {"britons": "Bretons"})
    assert any("Bretons" in line for line in lines)  # the winners line


def test_drinks_options_read_the_catalog() -> None:
    """The drinks select lists the configured catalog with prices."""
    from botforge.mods.kingdom.cogs.strings import strings
    from botforge.mods.kingdom.cogs.tavern import _drinks_options

    class _Drink:
        key = "verre"
        label = "🍺 Cervoise"
        price = 2
        lock_minutes = 60

    class _Tavern:
        drinks = (_Drink(),)

    class _Config:
        tavern = _Tavern()

    class _Stack:
        config = _Config()

    options = _drinks_options(_Stack(), strings("fr"))
    assert len(options) == 1
    assert options[0].value == "verre"
    assert "2" in options[0].label


@pytest.mark.asyncio
async def test_mercenary_tick_degrades_without_stack() -> None:
    """The mercenary tick is a no-op when the stack is not wired."""
    from botforge.mods.kingdom.cogs.kingdom import phases

    class _Bot:
        guilds: list = []

    await phases.run_mercenary_tick_safe(_Bot())
