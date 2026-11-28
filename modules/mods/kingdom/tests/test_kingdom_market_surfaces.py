"""Kingdom mod market surfaces (P4.3) — wiring smoke tests (#368).

The Marché and the Chambre des comptes degrade quietly without a
stack; the pure helpers (cost lookup, error mapping, market shelves)
stay stable across locales, and the ported EconomyService carries
its error hierarchy.
"""

from __future__ import annotations

import pytest


def test_market_modules_import() -> None:
    """The P4.3 surface modules import (market + the ported economy engine)."""
    from botforge.mods.kingdom.cogs.kingdom import market  # noqa: F401
    from botforge.mods.kingdom.economy import EconomyService  # noqa: F401


def test_economy_error_hierarchy() -> None:
    """The economy errors nest under the mod's own error base."""
    from botforge.mods.kingdom.economy import EconomyError, InsufficientPointsError
    from botforge.mods.kingdom.errors import KingdomModError

    assert issubclass(EconomyError, KingdomModError)
    assert issubclass(InsufficientPointsError, EconomyError)


def test_market_cost_reads_the_config() -> None:
    """The cost lookup reads the configured technologies section."""
    from botforge.mods.kingdom.cogs.market import _cost

    class _Tech:
        corruption = 4
        patrouille = 2

    class _Config:
        technologies = _Tech()

    class _Stack:
        config = _Config()

    assert _cost(_Stack(), "corruption") == 4
    assert _cost(_Stack(), "patrouille") == 2
    assert _cost(_Stack(), "unknown") == 0


def test_market_error_note_maps_engine_errors() -> None:
    """Each economy engine refusal maps to its player-facing note."""
    from botforge.mods.kingdom.cogs.market import _market_error_note
    from botforge.mods.kingdom.cogs.strings import strings
    from botforge.mods.kingdom.economy import (
        EconomyError,
        EconomyLimitReachedError,
        InsufficientPointsError,
    )

    s = strings("fr")
    assert _market_error_note(InsufficientPointsError("x"), s) == s["market_no_points"]
    assert _market_error_note(EconomyLimitReachedError("x"), s) == s["market_limit"]
    assert s["market_error"].split("{0}")[0] in _market_error_note(EconomyError("boom"), s)


def test_market_options_carry_costs() -> None:
    """The stall's shelves list the articles with their price."""
    from botforge.mods.kingdom.cogs.market import MARKET_SECTIONS, market_shelf_items
    from botforge.mods.kingdom.cogs.strings import strings

    class _Tech:
        embuscade = 1
        traquenard = 2
        contre_espionnage = 1
        sabotage = 2
        mariage_arrange = 3
        explorateur = 2
        corruption = 4
        jeu_d_armes = 1
        garde_royale = 2
        patrouille = 2

    class _Config:
        technologies = _Tech()

    class _Stack:
        config = _Config()

    items = market_shelf_items(_Stack(), strings("fr"))
    keys = [key for key, _label, _cost in items]
    assert "embuscade" in keys
    assert "mariage_arrange" in keys
    assert "patrouille" in keys
    assert len(keys) == sum(len(k) for _h, k in MARKET_SECTIONS)
    assert all(label and cost >= 0 for _key, label, cost in items)


@pytest.mark.asyncio
async def test_economy_due_degrades_without_stack() -> None:
    """The economy tick is a no-op when the stack is not wired."""
    from botforge.mods.kingdom.cogs.kingdom import phases

    class _Bot:
        guilds: list = []

    await phases.run_economy_due_safe(_Bot())
