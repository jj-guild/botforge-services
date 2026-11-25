"""affaire-27 (Drasah 25/11) — the locks of the leftover sweep + the
immediate habitat closure.

Drasah's live findings: (1) the battle-room sweep hammered Discord
with 403 « Missing Access » every pass on leftover channels the bot
may NOT manage — the vocaux never swept away; (2) tranché : toute
résolution AUTO (forfait, no-show) ferme l'habitat immédiatement, une
partie jouée ferme immédiatement en bêta (délai officiel sinon).
"""


from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


@pytest.mark.asyncio
async def test_the_sweep_skips_undeletable_leftovers() -> None:
    """A channel the bot can't manage is never DELETEd — no 403 storm."""

    from botforge.mods.kingdom.cogs import battle

    deleted: list[str] = []

    class _Channel:
        def __init__(self, name: str, allowed: bool) -> None:
            self.name = name
            self.allowed = allowed

        def permissions_for(self, member: Any) -> Any:
            return SimpleNamespace(manage_channels=self.allowed)

        async def delete(self) -> None:
            deleted.append(self.name)

    voc = _Channel("vocal", allowed=False)
    salon = _Channel("salon", allowed=True)
    me = SimpleNamespace(top_role=SimpleNamespace(position=2))

    class _Guild:
        me: Any

        def get_channel(self, channel_id: int) -> Any:
            return {1: salon, 2: voc}.get(channel_id)

        def get_role(self, role_id: int) -> Any:
            return None

    _Guild.me = me

    bot = SimpleNamespace(guilds=[_Guild()])
    attack = SimpleNamespace(
        score={"attack_channel_id": 1, "room_channel_id": 2},
        map_key="pataugeoire",
    )
    swept = await battle._sweep_recorded_leftovers_safe(bot, [attack])
    assert swept == 1, "only the MANAGEABLE channel is deleted"
    assert deleted == ["salon"], "the undeletable vocal is skipped, not hammered"


@pytest.mark.asyncio
async def test_the_sweep_skips_roles_above_the_bot() -> None:
    """A role hoisted above the bot is never delete-attempted."""

    from botforge.mods.kingdom.cogs import battle

    deleted: list[str] = []

    class _Role:
        name = "⚔️ bataille"
        position = 5

        async def delete(self) -> None:
            deleted.append(self.name)

    role = _Role()
    me = SimpleNamespace(top_role=SimpleNamespace(position=2))

    class _Guild:
        me: Any

        def get_channel(self, channel_id: int) -> Any:
            return None

        def get_role(self, role_id: int) -> Any:
            return role if role_id == 7 else None

    _Guild.me = me

    bot = SimpleNamespace(guilds=[_Guild()])
    attack = SimpleNamespace(score={"room_role_id": 7}, map_key="pataugeoire")
    swept = await battle._sweep_recorded_leftovers_safe(bot, [attack])
    assert swept == 0 and not deleted, "an above-the-bot role is silently skipped"


def kingdoms_stub() -> Any:
    """A minimal kingdoms side for the phases loops (never called)."""
    return SimpleNamespace(current_season=None)


@pytest.mark.asyncio
async def test_a_noshow_announces_then_closes_the_habitat(monkeypatch: pytest.MonkeyPatch) -> None:
    """The T+5 no-show announces FIRST, then the habitat closes at once."""

    from botforge.mods.kingdom.cogs import battle as cbattle
    from botforge.mods.kingdom.cogs import common as ccommon
    from botforge.mods.kingdom.cogs import phases as cphases

    order: list[str] = []

    async def _send(guild: Any, attack: Any, content: str) -> None:
        order.append("announce")

    async def _name(kingdoms: Any, kingdom_id: Any) -> str:
        return "aegis"

    async def _stamped(bot: Any, attack: Any, kingdom: Any, strings: Any) -> None:
        order.append("ping")

    async def _notes(bot: Any, attack: Any) -> None:
        order.append("notes")

    monkeypatch.setattr(ccommon, "attack_salon_send_safe", _send)
    monkeypatch.setattr(ccommon, "kingdom_name", _name)
    monkeypatch.setattr(cbattle, "stamp_room_ping_winner_safe", _stamped)
    monkeypatch.setattr(cbattle, "sweep_reveal_notes_safe", _notes)

    async def _cleanup(bot: Any, stack: Any, attack: Any) -> None:
        order.append("close")

    monkeypatch.setattr(cbattle, "cleanup_decided_attack_safe", _cleanup)

    class _Attacks:
        async def ready_due(self) -> list[Any]:
            return [
                SimpleNamespace(
                    is_over=True,
                    map_key="pataugeoire",
                    score={"noshow": "attacker"},
                    winner_kingdom_id="k1",
                )
            ]

    stack = SimpleNamespace(attacks=_Attacks(), kingdoms=kingdoms_stub())
    played = await cphases._run_noshows_safe(
        None, stack, None, {"noshow_side": "forfait {side}", "side_attacker": "attaquant"}
    )
    assert played == 1
    assert order == ["announce", "ping", "notes", "close"], (
        "the winner ping rides the salon BEFORE the habitat closes"
    )


@pytest.mark.asyncio
async def test_an_unresolved_ai_defense_never_closes_the_habitat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The forfeit loop closes only what the resolution actually ended."""

    from botforge.mods.kingdom.cogs import battle as cbattle
    from botforge.mods.kingdom.cogs import common as ccommon
    from botforge.mods.kingdom.cogs import phases as cphases

    order: list[str] = []

    async def _send(guild: Any, attack: Any, content: str) -> None:
        order.append("announce")

    monkeypatch.setattr(ccommon, "attack_salon_send_safe", _send)

    closed: list[Any] = []

    async def _cleanup(bot: Any, stack: Any, attack: Any) -> None:
        closed.append(attack)

    monkeypatch.setattr(cbattle, "cleanup_decided_attack_safe", _cleanup)

    class _Attacks:
        async def expire_stale(self) -> list[Any]:
            # the anti-blocking AI defense announces, but the game GOES ON
            return [
                SimpleNamespace(
                    is_over=False,
                    ai_defender=True,
                    pickban={},
                    map_key="p",
                    winner_kingdom_id="k1",
                    defender_kingdom_id="k2",
                    effects={},
                )
            ]

    stack = SimpleNamespace(attacks=_Attacks(), kingdoms=kingdoms_stub())
    played = await cphases._run_forfeits_safe(
        None, stack, None, {"reveal_ai": "{map}", "forfeit_side": "x", "side_attacker": "a"}
    )
    assert played == 1
    assert order == ["announce"]
    assert not closed, "an ongoing AI game keeps its habitat"


@pytest.mark.asyncio
async def test_the_forfeit_side_closes_after_the_announce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A meeting-time forfeit-side resolution closes its habitat."""

    from botforge.mods.kingdom.cogs import battle as cbattle
    from botforge.mods.kingdom.cogs import common as ccommon
    from botforge.mods.kingdom.cogs import phases as cphases

    order: list[str] = []

    async def _send(guild: Any, attack: Any, content: str) -> None:
        order.append("announce")

    async def _name(kingdoms: Any, kingdom_id: Any) -> str:
        return "aegis"

    monkeypatch.setattr(ccommon, "attack_salon_send_safe", _send)
    monkeypatch.setattr(ccommon, "kingdom_name", _name)

    async def _cleanup(bot: Any, stack: Any, attack: Any) -> None:
        order.append("close")

    monkeypatch.setattr(cbattle, "cleanup_decided_attack_safe", _cleanup)

    class _Attacks:
        async def expire_stale(self) -> list[Any]:
            return [
                SimpleNamespace(
                    is_over=True,
                    ai_defender=False,
                    pickban={"forfeit_side": "attacker"},
                    winner_kingdom_id="k1",
                    map_key="p",
                )
            ]

    stack = SimpleNamespace(attacks=_Attacks(), kingdoms=kingdoms_stub())
    played = await cphases._run_forfeits_safe(
        None, stack, None, {"forfeit_side": "{side}", "side_attacker": "attaquant"}
    )
    assert played == 1
    assert order == ["announce", "close"], "the forfeit announces, then closes"


@pytest.mark.asyncio
async def test_a_played_result_closes_now_only_under_an_armed_beta() -> None:
    """The played-result closure rides the beta gate — never in official."""

    from botforge.mods.kingdom.beta_weekend import beta_started
    from botforge.mods.kingdom.cogs import battle as cbattle

    class _Seasons:
        def __init__(self, season: Any) -> None:
            self._season = season

        async def current_season(self) -> Any:
            return self._season

    armed = SimpleNamespace(beta_name="beta", beta_start_at=None)
    quiet = SimpleNamespace(beta_name=None)
    stack = SimpleNamespace(kingdoms=_Seasons(armed))
    assert await cbattle._played_result_closes_now_safe(stack) is True, (
        "an armed beta closes the played habitat at once"
    )
    assert beta_started(armed, armed.beta_start_at) is True
    stack_official = SimpleNamespace(kingdoms=_Seasons(quiet))
    assert await cbattle._played_result_closes_now_safe(stack_official) is False, (
        "an official season keeps the discussion delay"
    )
