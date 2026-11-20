"""Kingdoms mod diplomacy surfaces (P4.2) — wiring smoke tests (#368).

The marriage wizard and the alliances view degrade quietly when the
stack is not wired; the pure helpers (cost, princess label, alliances
text) stay stable across locales, and the event slots tick is a no-op
without a stack.
"""

from __future__ import annotations

import pytest


def test_marry_modules_import() -> None:
    """The P4.2 surface modules import (marry, alliances, phases)."""
    from botforge.mods.kingdom.cogs.kingdom import alliances, marry, phases  # noqa: F401


def test_marry_cost_adapts_to_role() -> None:
    """A lord pays one ring, a King pays two — and the doubled lock (D34/D45)."""
    from botforge.mods.kingdom.cogs.marry import _marry_cost

    class _Tier:
        marriage_lock_hours = 12

    class _Lord:
        role = "lord"

    class _King:
        role = "king"

    kingdom = object()
    assert _marry_cost(_Lord(), kingdom, _Tier()) == (1, 12, False)
    assert _marry_cost(_King(), kingdom, _Tier()) == (2, 24, True)


def test_princess_label_is_stable_and_named() -> None:
    """The princess label is seeded (stable) and names a Princess, never a civ."""
    from botforge.mods.kingdom.cogs.marry import _princess_label
    from botforge.mods.kingdom.cogs.strings import strings

    s = strings("fr")
    names = {"bretons": "Bretons"}
    a = _princess_label(s, "lord:1", "bretons", names)
    b = _princess_label(s, "lord:1", "bretons", names)
    assert a == b
    assert a.startswith("Princesse ")
    assert "Bretons" in a


def test_alliances_text_composes_every_section() -> None:
    """The alliances window renders hand, projection and near-unlock hints."""
    from botforge.mods.kingdom.cogs.alliances import alliances_text
    from botforge.mods.kingdom.cogs.strings import strings

    class _Kingdom:
        name = "Bulgares"
        marriage_points = 2
        arranged_marriage_stock = 1

    projection = {
        "held": ["bretons"],
        "kept": ["bretons"],
        "arriving": ["viking"],
        "dropping": [],
        "married_elsewhere": ["aztecs"],
        "near_unlocks": [{"civ": "francs", "hint": "+1 map: foret"}],
    }
    text = alliances_text(strings("fr"), _Kingdom(), projection, {"bretons": "Bretons"})
    assert "Bulgares" in text
    assert "Bretons" in text
    assert "+1 map: foret" in text
    # the empty dropping list renders the dash, never an empty line
    assert "Perdues : —" in text


def test_marry_error_note_maps_engine_errors() -> None:
    """Each diplomacy engine refusal maps to its player-facing note."""
    from botforge.mods.kingdom.cogs.marry import _marry_error_note
    from botforge.mods.kingdom.cogs.strings import strings
    from botforge.mods.kingdom.diplomacy import (
        AlreadyMarriedError,
        MarriageError,
        NoMarriagePointsError,
        RoyalMarriagePointsError,
    )

    s = strings("fr")
    assert _marry_error_note(AlreadyMarriedError("x"), s) == s["church_marry_already"]
    assert _marry_error_note(NoMarriagePointsError("x"), s) == s["church_marry_no_points"]
    assert _marry_error_note(RoyalMarriagePointsError("x"), s) == s["church_marry_no_points_royal"]
    assert s["marry_error"].split("{0}")[0] in _marry_error_note(MarriageError("boom"), s)


@pytest.mark.asyncio
async def test_event_slots_degrade_without_stack() -> None:
    """The weekly-slots tick is a no-op when the stack is not wired."""
    from botforge.mods.kingdom.cogs.kingdom import phases

    class _Bot:
        guilds: list = []

    await phases.run_event_slots_safe(_Bot())


@pytest.mark.asyncio
async def test_event_report_text_renders_each_kind() -> None:
    """Cycle, age and end reports render through the locale strings."""
    from botforge.mods.kingdom.cogs.phases import _event_report_text
    from botforge.mods.kingdom.cogs.strings import strings

    s = strings("fr")
    cycle = _event_report_text(s, {"kind": "cycle", "cycle": 3, "gaia_new_maps": ["a"]})
    assert "Cycle 3" in cycle and "1" in cycle
    age = _event_report_text(
        s, {"kind": "age", "display_name": "Âge de Fer", "tech_points": 2, "extra_marriages": 1}
    )
    assert "Âge de Fer" in age
    end = _event_report_text(s, {"kind": "end", "winner_name": "Bulgares"})
    assert "Bulgares" in end
    showmatch = _event_report_text(s, {"kind": "end", "showmatch": True})
    assert showmatch == s["event_end_showmatch"]
