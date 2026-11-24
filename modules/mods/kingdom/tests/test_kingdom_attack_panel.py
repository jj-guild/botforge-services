"""Kingdom mod attack panel (P4.1b tranche 1) — wiring smoke tests (#368).

The Discord surfaces degrade quietly when their stack (Mongo) is not
wired: these tests pin that contract — the cog modules import, the
strings carry every locale, and the panel build falls back to the
defaults without a catalog or a database.
"""

from __future__ import annotations

import pytest


def test_cog_modules_import() -> None:
    """The cog package's modules import (contract, wiring, panels)."""
    from botforge.mods.kingdom.cogs.kingdom import common, panel, pickban, strings  # noqa: F401


def test_strings_cover_both_locales() -> None:
    """FR/EN defaults carry the SAME key set (no half-translated panel)."""
    from botforge.mods.kingdom.cogs.strings import DEFAULTS

    assert set(DEFAULTS["fr"]) == set(DEFAULTS["en"])
    assert DEFAULTS["fr"]["defend_button"]
    assert DEFAULTS["en"]["defend_button"]


def test_strings_resolve_without_catalog() -> None:
    """``strings`` degrades to the defaults when no catalog is wired."""
    from botforge.mods.kingdom.cogs.strings import DEFAULTS, strings

    assert strings("fr")["defend_button"] == DEFAULTS["fr"]["defend_button"]
    assert strings("en")["panel_title"] == DEFAULTS["en"]["panel_title"]
    # an unknown locale falls back on the English defaults
    assert strings("zz")["panel_title"] == DEFAULTS["en"]["panel_title"]


def test_room_key_is_short_and_stable() -> None:
    """The salon buttons' digests stay under Discord's custom-id limit."""
    from botforge.mods.kingdom.cogs.common import room_key

    key = room_key("0123456789abcdef0123456789abcdef")
    assert len(key) == 16
    assert key == room_key("0123456789abcdef0123456789abcdef")
    assert key != room_key("0123456789abcdef0123456789abcdee")


@pytest.mark.asyncio
async def test_panel_build_degrades_without_stack() -> None:
    """``build_attack_panel`` renders the pinned layout (locale fallback)."""
    from botforge.mods.kingdom.cogs.panel import build_attack_panel

    view = await build_attack_panel("123")
    assert view is not None


@pytest.mark.asyncio
async def test_wiring_never_raises_without_mongo() -> None:
    """``wiring`` degrades (None) — the surfaces show no-service notes."""
    from botforge.mods.kingdom.cogs.common import wiring

    wiring()


def test_pickban_helpers_stay_stable() -> None:
    """The draft/sabotage digests and shuffles are stable + distinct."""
    from botforge.mods.kingdom.cogs.common import (
        final_civ,
        ready_key,
        reveal_civs,
        room_side_of,
        score_players,
    )

    assert ready_key("a1", "p1") == ready_key("a1", "p1")
    assert ready_key("a1", "p1") != ready_key("a1", "p2")
    assert reveal_civs("seed", ["a", "b", "c"]) == reveal_civs("seed", ["a", "b", "c"])
    assert reveal_civs("seed", ["a", "b", "c"]) != reveal_civs("other", ["a", "b", "c"])
    assert final_civ({"attacker_picks": ["x", "y"], "defender_sabotages": ["x"]}, "attacker") == "y"

    class _Attack:
        attacker_lord_id = "1"
        defender_lord_id = "2"
        ai_defender = False

    assert room_side_of(_Attack(), "1") == "attacker"
    assert room_side_of(_Attack(), "2") == "defender"
    assert room_side_of(_Attack(), "3") == ""
    assert score_players(_Attack()) == ["1", "2"]
    _Attack.ai_defender = True
    assert score_players(_Attack()) == ["1"]


def test_battle_scoreboard_helpers_stay_stable() -> None:
    """The monospace scoreboard keeps its alignment + key parity FR/EN."""
    from botforge.mods.kingdom.cogs.battle import _score_center, _score_row
    from botforge.mods.kingdom.cogs.strings import DEFAULTS

    line = _score_center("⚔️ Map")
    assert len(line) == 46
    row = _score_row("Alice", "Bob")
    assert len(row) == 46
    assert set(DEFAULTS["fr"]) == set(DEFAULTS["en"])
    for key in ("room_dm", "result_button", "dispute_not_admin", "conquest_title"):
        assert key in DEFAULTS["fr"], key


@pytest.mark.asyncio
async def test_battle_degrades_without_stack() -> None:
    """A None stack never raises — the surfaces show no-service notes."""
    from botforge.mods.kingdom.cogs.kingdom import battle

    assert await battle.resolve_room_key(None, "abc") == ""
    await battle.refresh_room_message_safe(None, None, None, "fr")


def test_plan_helpers_stay_stable() -> None:
    """The plan time composer enforces the 24h golden rule."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from botforge.mods.kingdom.cogs.plan import _meeting_from_selections

    tz = ZoneInfo("Europe/Paris")
    now = datetime(2026, 11, 17, 10, 0, tzinfo=tz)
    ok = _meeting_from_selections(0, 20, 0, now)
    assert ok.hour == 20
    assert _meeting_from_selections(0, 11, 0, now).hour == 11
    for args in ((0, 9, 0), (2, 20, 0)):
        try:
            _meeting_from_selections(*args, now)
            raised = False
        except ValueError:
            raised = True
        assert raised, args


@pytest.mark.asyncio
async def test_phases_tick_degrades_without_stack(monkeypatch) -> None:
    """P4.1b tranche 2e: the tick without a stack is a silent no-op."""
    from botforge.mods.kingdom.cogs.kingdom import phases

    class _Bot:
        guilds: list = []

    monkeypatch.setattr(phases, "_register_voice_listener", lambda _bot: None)
    await phases.run_attack_phases_safe(_Bot())


def test_phases_strings_are_phases_ready() -> None:
    """Every phase-run key exists FR and EN (the tick formats them)."""
    from botforge.mods.kingdom.cogs.strings import DEFAULTS

    keys = (
        "plan_event_executed",
        "plan_event_switched",
        "plan_event_broken",
        "plan_event_cancelled",
        "reveal_cover",
        "reveal_battle_anon",
        "reveal_ai",
        "matchup_v1",
        "matchup_ai",
        "forfeit_both",
        "forfeit_side",
        "side_attacker",
        "side_defender",
        "noshow_side",
        "noshow_both",
        "score_reminder_dm",
        "auto_dispute",
        "score_resolved",
    )
    for key in keys:
        assert key in DEFAULTS["fr"], key
        assert key in DEFAULTS["en"], key


def _panel_button_ids(view: object) -> list[str]:
    """Walk a LayoutView and collect every action-row button's custom_id."""
    ids: list[str] = []

    def _walk(node: object) -> None:
        children = getattr(node, "children", None)
        if isinstance(children, list):
            for child in children:
                custom = getattr(child, "custom_id", "")
                if isinstance(custom, str) and custom:
                    ids.append(custom)
                _walk(child)

    _walk(view)
    return ids


@pytest.mark.asyncio
async def test_panel_stays_clean_reference_four_buttons() -> None:
    """attaque-panel-clean-v1 (Drasah 24/11): the declare panel mirrors the
    reference — EXACTLY the four battlefield buttons, NO navigation
    (marry, alliances, market, treasury, tavern, mercenary belong to
    their own surfaces, not to the attack panel)."""
    from botforge.mods.kingdom.cogs.panel import build_attack_panel

    view = await build_attack_panel("123")
    ids = _panel_button_ids(view)
    assert ids == [
        "kingdom:attack:declare",
        "kingdom:attack:history",
        "kingdom:attack:plan",
        "kingdom:attack:info",
    ]
