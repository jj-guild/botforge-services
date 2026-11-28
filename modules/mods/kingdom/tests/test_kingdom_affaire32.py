"""battle-rooms-early-v1 (T-A, Drasah 25/11) — the early meeting open.

The live finding: during the attack phases « Voir la draft » was
unclickable — the scoreboard only landed AT the meeting hour. The
reference's v4 ruling: the LAST Sabotage Pass opens the meeting before
T. The engine seam (open_meeting_now) was already ported; the missing
piece was the cog wiring — ONE helper + ONE call, nothing else.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


class _Recorder:
    """The calls seen by the patched seams (order-preserving)."""

    def __init__(self, returns: Any = None) -> None:
        self.calls: list[Any] = []
        self.returns = returns

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(("call", args))
        return self.returns


@pytest.mark.asyncio
async def test_open_meeting_and_room_safe_opens_the_room_per_guild(monkeypatch: Any) -> None:
    """open_meeting_now flew → open_battle_room runs for EACH guild."""
    from botforge.mods.kingdom.cogs import battle

    fresh = SimpleNamespace(id="a1", map_key="Aquitaine")
    stack = SimpleNamespace(attacks=SimpleNamespace(open_meeting_now=_Recorder(fresh)))
    rooms = _Recorder()

    async def _fake_room(bot: Any, stack: Any, guild: Any, attack: Any, locale: str) -> None:
        rooms.calls.append((guild, attack, locale))

    monkeypatch.setattr(battle, "open_battle_room", _fake_room)
    guild_one, guild_two = SimpleNamespace(id=1), SimpleNamespace(id=2)
    bot = SimpleNamespace(guilds=[guild_one, guild_two])

    await battle.open_meeting_and_room_safe(bot, stack, SimpleNamespace(id="a1"), "fr")

    assert len(stack.attacks.open_meeting_now.calls) == 1, "the seam is called once"
    assert [entry[0] for entry in rooms.calls] == [guild_one, guild_two], "a room per guild"
    assert all(entry[1] is fresh for entry in rooms.calls), "the rooms carry the FRESH attack"
    assert rooms.calls[0][2] == "fr", "the caller's locale rides through"


@pytest.mark.asyncio
async def test_a_refused_or_late_meeting_never_touches_the_rooms(monkeypatch: Any) -> None:
    """A raising or not-yet-settled open_meeting_now: zero room opens, never a raise."""

    class _BoomError(Exception):
        pass

    async def _raising(*args: Any, **kwargs: Any) -> Any:
        raise _BoomError()

    from botforge.mods.kingdom.cogs import battle

    rooms = _Recorder()

    async def _fake_room(*args: Any, **kwargs: Any) -> None:
        rooms.calls.append(args)

    monkeypatch.setattr(battle, "open_battle_room", _fake_room)
    bot = SimpleNamespace(guilds=[SimpleNamespace(id=1)])

    # the seam raises — best effort, the retry belongs to score_due at T
    stack = SimpleNamespace(attacks=SimpleNamespace(open_meeting_now=_raising))
    await battle.open_meeting_and_room_safe(bot, stack, SimpleNamespace(id="a1"), "fr")
    assert rooms.calls == [], "a raised open never touches the rooms"

    # the phase is not settled yet (seam answers None)
    stack = SimpleNamespace(attacks=SimpleNamespace(open_meeting_now=_Recorder(None)))
    await battle.open_meeting_and_room_safe(bot, stack, SimpleNamespace(id="a1"), "fr")
    assert rooms.calls == [], "an unsettled phase opens nothing"

    # no wiring at all — the silent return
    await battle.open_meeting_and_room_safe(bot, None, SimpleNamespace(id="a1"), "fr")
    assert rooms.calls == [], "a missing stack degrades to silence"


@pytest.mark.asyncio
async def test_the_last_sabotage_pass_opens_the_meeting_before_t(monkeypatch: Any) -> None:
    """The LAST Passer (sabotage resolved) wires the early open; the FIRST does not."""
    from botforge.mods.kingdom.cogs import battle, pickban

    resolved = SimpleNamespace(
        id="a1",
        map_key="Aquitaine",
        pickban={"sabotage_resolved": True},
        attacker_lord_id="10",
        defender_lord_id="20",
    )
    not_resolved = SimpleNamespace(
        id="a1",
        map_key="Aquitaine",
        pickban={"sabotage_resolved": False},
        attacker_lord_id="10",
        defender_lord_id="20",
    )
    settled_side: dict[str, Any] = {}
    settle_returns: dict[str, Any] = {"1": not_resolved, "2": resolved}

    async def _settle(attack_id: str, player_id: str) -> Any:
        settled_side["last"] = player_id
        return settle_returns[player_id]

    stack = SimpleNamespace(attacks=SimpleNamespace(sabotage_settle=_settle))

    court: list[str] = []

    async def _nope(*args: Any, **kwargs: Any) -> Any:
        return None

    async def _record_open_meeting(bot: Any, stack: Any, attack: Any, locale: str) -> None:
        court.append(str(getattr(attack, "id", "")))

    monkeypatch.setattr(pickban, "wiring", lambda: stack)
    monkeypatch.setattr(pickban, "_delete_sabotage_panel", _nope)
    monkeypatch.setattr(pickban, "refresh_sabotage_dm_safe", _nope)
    monkeypatch.setattr(pickban, "edit_pickban_dms_phase_done", _nope)
    monkeypatch.setattr(pickban, "open_unique_ephemeral", _nope)
    monkeypatch.setattr(battle, "open_meeting_and_room_safe", _record_open_meeting)

    interaction = SimpleNamespace(
        client=SimpleNamespace(guilds=[]), user=SimpleNamespace(id="who"), locale="fr"
    )

    # the FIRST Pass — the side settles, the phase is NOT over: no early open
    await pickban.SabotagePassButton("a1", "1", "Passer").callback(interaction)
    assert court == [], "a single settled side never opens the meeting"

    # the LAST Pass — the phase resolves: the early open flies
    await pickban.SabotagePassButton("a1", "2", "Passer").callback(interaction)
    assert court == ["a1"], "the last Passer opens the meeting before T"


def test_the_pickban_source_carries_the_landed_wire() -> None:
    """Contract: the tranche-2c TODO is GONE, the seam import rides the callback."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "cogs" / "kingdom" / "pickban.py"
    ).read_text(encoding="utf-8")
    assert "until it lands, the tick opens the meeting at T" not in source, (
        "the tranche-2c placeholder must be gone"
    )
    assert "open_meeting_and_room_safe" in source, "the early open must ride the callback"
