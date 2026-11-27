"""beta-fixes-v1 (Drasah 25/11) — the four live-beta corrections.

Affaire 17's frozen batch: (1) the auto-opened dispute keeps its own
label on the 🏆 button, (2) the score clock re-anchors on the REAL
opening (the scoreboard landing), (3) the battle-room vocal follows
the Affaire 11 naming rule, (4) a retarded salon skips its scheduled
event quietly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from botforge.mods.kingdom.models import AttackState
from test_kingdom_attack_score import _T, ScoreBundle

_T15H = _T + timedelta(hours=15)


# ---------------------------------------------------------------------------
# 1 — the auto-opened dispute keeps its own label (Affaires 14/17)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_auto_opened_dispute_gets_its_own_label(monkeypatch: pytest.MonkeyPatch) -> None:
    import botforge.mods.kingdom.cogs.battle as battle

    sent: list[str] = []

    attack = SimpleNamespace(
        id="a1",
        is_over=False,
        state=AttackState.MEETING,
        lobby_url="",
        score={"all_ready": True, "disputed": True, "auto_dispute": True},
    )

    async def _by_id(stack: Any, attack_id: str) -> Any:
        return attack

    class _Resp:
        async def send_message(self, content: str, **kwargs: Any) -> None:
            sent.append(str(content))

    monkeypatch.setattr(battle, "wiring", lambda: SimpleNamespace())
    monkeypatch.setattr(battle, "attack_by_id", _by_id)
    monkeypatch.setattr(battle, "room_side_of", lambda attack, player_id: "attacker")

    interaction = SimpleNamespace(
        user=SimpleNamespace(id="u1"), locale="fr", response=_Resp()
    )
    button = battle.RoomResultButton("a1", "🏆 Résultat")
    await button.callback(interaction)
    assert len(sent) == 1
    assert "automatiquement" in sent[0], "the auto-opened dispute says so"
    assert "délai dépassé" in sent[0]
    assert "contradictoire" not in sent[0], "nobody contradicted anything"


@pytest.mark.asyncio
async def test_real_contradictory_declarations_keep_the_generic_label(monkeypatch: pytest.MonkeyPatch) -> None:
    import botforge.mods.kingdom.cogs.battle as battle

    sent: list[str] = []

    attack = SimpleNamespace(
        id="a1",
        is_over=False,
        state=AttackState.MEETING,
        lobby_url="",
        score={"all_ready": True, "disputed": True},
    )

    async def _by_id(stack: Any, attack_id: str) -> Any:
        return attack

    class _Resp:
        async def send_message(self, content: str, **kwargs: Any) -> None:
            sent.append(str(content))

    monkeypatch.setattr(battle, "wiring", lambda: SimpleNamespace())
    monkeypatch.setattr(battle, "attack_by_id", _by_id)
    monkeypatch.setattr(battle, "room_side_of", lambda attack, player_id: "attacker")

    interaction = SimpleNamespace(
        user=SimpleNamespace(id="u1"), locale="fr", response=_Resp()
    )
    button = battle.RoomResultButton("a1", "🏆 Résultat")
    await button.callback(interaction)
    assert len(sent) == 1
    assert "contradictoire" in sent[0], "a real pair keeps the old label"


# ---------------------------------------------------------------------------
# 2 — the score clock rides the REAL opening (Affaires 14/17)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restamp_reanchors_the_dispute_window(monkeypatch: pytest.MonkeyPatch) -> None:
    from botforge.mods.kingdom import attacks as attacks_module

    late = _T + timedelta(hours=2)
    monkeypatch.setattr(attacks_module, "_now", lambda: late)

    bundle = ScoreBundle()
    await bundle.launch_season()
    await bundle.draw(9)
    attack, aquitaine, _bourgogne = await bundle.open_meeting()

    fresh = next(item for item in await bundle.attacks.attacks() if item.id == attack.id)
    old = int(fresh.score["opened_at"])
    assert old == int(_T.timestamp()), "the phase opened at T"

    # The scoreboard lands 2h late (the meeting heal) — the window restarts.
    await bundle.attacks.restamp_score_opening(attack.id)
    fresh2 = next(item for item in await bundle.attacks.attacks() if item.id == attack.id)
    assert int(fresh2.score["opened_at"]) == int(late.timestamp())

    # The old 15h line no longer fires « 5 min after » the real opening.
    assert await bundle.attacks.dispute_due(now=_T15H) == []
    del aquitaine


@pytest.mark.asyncio
async def test_restamp_never_touches_a_meeting_that_already_decided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from botforge.mods.kingdom import attacks as attacks_module

    late = _T + timedelta(hours=2)
    monkeypatch.setattr(attacks_module, "_now", lambda: late)

    bundle = ScoreBundle()
    await bundle.launch_season()
    await bundle.draw(9)
    attack, aquitaine, _bourgogne = await bundle.open_meeting()
    await bundle.attacks.declare_score(attack.id, "king-a", aquitaine, "game-1", now=_T)

    fresh = next(item for item in await bundle.attacks.attacks() if item.id == attack.id)
    opened_at = int(fresh.score["opened_at"])
    await bundle.attacks.restamp_score_opening(attack.id)
    fresh2 = next(item for item in await bundle.attacks.attacks() if item.id == attack.id)
    assert int(fresh2.score["opened_at"]) == opened_at, "a declared meeting is never re-anchored"


@pytest.mark.asyncio
async def test_the_scoreboard_landing_restamps_the_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    import botforge.mods.kingdom.cogs.battle as battle

    async def _record(*args: Any) -> Any:
        return SimpleNamespace(id="a1")

    restamped: list[str] = []

    async def _restamp(attack_id: str) -> Any:
        restamped.append(str(attack_id))

    stack = SimpleNamespace(
        attacks=SimpleNamespace(
            record_meeting_message=_record,
            record_ping_message=_record,
            restamp_score_opening=_restamp,
        )
    )

    class _Salon:
        id = 55

        async def send(self, content: str, view: Any = None, **kwargs: Any) -> Any:
            # retour-testeurs-v1 (affaire 49): the meeting message may
            # carry the Civ-VS-Civ banner as an attachment.
            return SimpleNamespace(id=77)

    async def _body(stack: Any, attack: Any, strings: Any) -> Any:
        return "body"

    async def _view(stack: Any, attack: Any, strings: Any) -> Any:
        return None

    monkeypatch.setattr(battle, "attack_salon", lambda guild, attack: _Salon())
    monkeypatch.setattr(battle, "room_body_text", _body)
    monkeypatch.setattr(battle, "room_view", _view)
    monkeypatch.setattr(battle, "sweep_pre_room_announces_safe", _no_sweep)

    attack = SimpleNamespace(
        id="a1", defender_lord_id=None, ai_defender=True, score={}, labels={}
    )
    await battle.post_meeting_message(None, stack, attack, {"room_ping_attacker_only": "<@{attacker}>"})
    assert restamped == ["a1"], "the first scoreboard re-anchors the score clock"


async def _no_sweep(guild: Any, stack: Any, attack: Any) -> None:
    return None


# ---------------------------------------------------------------------------
# 3 — the vocal's name follows the Affaire 11 rule
# ---------------------------------------------------------------------------


def _label_stack() -> SimpleNamespace:
    async def _kingdoms() -> list[Any]:
        return [SimpleNamespace(id="k-b", name="Bourgogne")]

    async def _lords() -> list[Any]:
        return [
            SimpleNamespace(id="l1", display_name="Blanc"),
            SimpleNamespace(id="l2", display_name="Bob"),
        ]

    return SimpleNamespace(
        kingdoms=SimpleNamespace(lords=_lords, kingdoms=_kingdoms)
    )


@pytest.mark.asyncio
async def test_the_vocal_opens_on_the_attacker_and_the_adverse_kingdom() -> None:
    import botforge.mods.kingdom.cogs.battle as battle
    from botforge.mods.kingdom.cogs.strings import strings

    attack = SimpleNamespace(
        ai_defender=False,
        defender_lord_id="l2",
        defender_kingdom_id="k-b",
        pickban={},
    )
    guild = SimpleNamespace(channels=[])
    label = await battle.battle_room_defender_label(_label_stack(), attack, strings("fr"))
    assert label == "Bourgogne", "the kingdom answers for the hidden defender"
    assert battle.room_channel_name(guild, "⚔️", "Blanc", label) == "⚔️-blanc-vs-bourgogne"


@pytest.mark.asyncio
async def test_the_vocal_says_the_ai_when_the_bot_defends() -> None:
    import botforge.mods.kingdom.cogs.battle as battle
    from botforge.mods.kingdom.cogs.strings import strings

    attack = SimpleNamespace(
        ai_defender=True,
        defender_lord_id=None,
        defender_kingdom_id="k-b",
        pickban={},
    )
    guild = SimpleNamespace(channels=[])
    label = await battle.battle_room_defender_label(_label_stack(), attack, strings("fr"))
    assert label == "l'IA", "the room stays open, named after the AI"
    assert battle.room_channel_name(guild, "⚔️", "Blanc", label) == "⚔️-blanc-vs-l-ia"


@pytest.mark.asyncio
async def test_the_vocal_swaps_the_kingdom_for_the_defender_at_the_reveal() -> None:
    import botforge.mods.kingdom.cogs.battle as battle
    from botforge.mods.kingdom.cogs.strings import strings

    renames: list[str] = []

    class _Channel:
        name = "⚔️-blanc-vs-bourgogne"

        async def edit(self, name: Any = None) -> None:
            if name is not None:
                renames.append(str(name))

    channel = _Channel()
    guild = SimpleNamespace(channels=[channel])
    guild.get_channel = lambda channel_id: channel

    attack = SimpleNamespace(
        id="a1",
        ai_defender=False,
        attacker_lord_id="l1",
        defender_lord_id="l2",
        defender_kingdom_id="k-b",
        pickban={"matchup_announced": True},
        map_key="k2",
        score={"room_channel_id": 4242},
    )
    await battle.rename_battle_room_vocal_safe(guild, _label_stack(), attack, strings("fr"))
    assert renames == ["⚔️-blanc-vs-bob"], "the real defender replaces the kingdom"

    # Idempotent: the converged name never re-edits.
    channel.name = "⚔️-blanc-vs-bob"
    await battle.rename_battle_room_vocal_safe(guild, _label_stack(), attack, strings("fr"))
    assert renames == ["⚔️-blanc-vs-bob"]


# ---------------------------------------------------------------------------
# 4 — a retarded salon skips its scheduled event quietly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_past_meeting_skips_the_room_event(monkeypatch: pytest.MonkeyPatch) -> None:
    import botforge.mods.kingdom.cogs.battle as battle

    created: list[str] = []

    async def _create_scheduled_event(**kwargs: Any) -> Any:
        created.append(str(kwargs.get("name")))
        return SimpleNamespace(id=777)

    async def _kingdom_name(kingdoms: Any, kingdom_id: Any) -> str:
        return "Royaume"

    class _StubDiscord:
        VoiceChannel = type("VoiceChannel", (), {})
        StageChannel = type("StageChannel", (), {})
        TextChannel = type("TextChannel", (), {})
        Thread = type("Thread", (), {})
        EntityType = SimpleNamespace(voice="voice")
        PrivacyLevel = SimpleNamespace(guild_only="guild_only")

    monkeypatch.setattr(battle, "discord", _StubDiscord())
    monkeypatch.setattr(battle, "kingdom_name", _kingdom_name)

    guild = SimpleNamespace(create_scheduled_event=_create_scheduled_event)
    channel = _StubDiscord.TextChannel()
    channel.guild = guild
    past = datetime.now(UTC) - timedelta(hours=12)
    attack = SimpleNamespace(
        id="a1",
        map_key="k2",
        attacker_kingdom_id="k-a",
        defender_kingdom_id="k-b",
        score={"ready_deadline": int(past.timestamp())},
    )
    # The retarded room: the RDV window is long over — no event, no raise.
    await battle.create_room_event_safe(None, SimpleNamespace(kingdoms=None), attack, {}, channel)
    assert created == [], "a room past its RDV never schedules an event"

    fresh = datetime.now(UTC) + timedelta(hours=1)
    attack.score = {"ready_deadline": int(fresh.timestamp())}
    strings = {"room_event_name": "{attacker} vs {defender}", "room_event_description": "x"}
    await battle.create_room_event_safe(None, SimpleNamespace(kingdoms=None), attack, strings, channel)
    assert created == ["Royaume vs Royaume"], "an on-time room keeps its event"
