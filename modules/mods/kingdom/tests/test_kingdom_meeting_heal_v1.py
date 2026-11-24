"""meeting-heal-v1 (Drasah 24/11) — the open meeting without its salon.

The salon-attaque-v1 incident left a live attack with a battle voice
room and NO text salon: the players could neither ready nor declare a
result and the meeting hung. The 5-minute phase tick now rebuilds the
missing half idempotently.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def _attack(attack_id: str = "a1", *, is_over: bool = False, **score: object) -> SimpleNamespace:
    return SimpleNamespace(id=attack_id, is_over=is_over, score=score)


def _stack(*attacks: SimpleNamespace) -> SimpleNamespace:
    async def _attacks() -> list[SimpleNamespace]:
        return list(attacks)

    return SimpleNamespace(attacks=SimpleNamespace(attacks=_attacks))


@pytest.mark.asyncio
async def test_a_meeting_without_salon_gets_it_back(monkeypatch) -> None:
    import botforge.mods.kingdom.cogs.battle as battle
    import botforge.mods.kingdom.cogs.common as common
    import botforge.mods.kingdom.cogs.panel as panel
    import botforge.mods.kingdom.cogs.phases as phases

    opened: list[str] = []
    posted: list[str] = []

    async def _open(guild, stack, strings, attack, locale="fr"):
        opened.append(str(attack.id))

    async def _post(guild, stack, attack, strings):
        posted.append(str(attack.id))
        return SimpleNamespace(id="chan")

    def _salon(guild, attack):
        return None

    monkeypatch.setattr(panel, "_open_attack_salon_safe", _open)
    monkeypatch.setattr(battle, "post_meeting_message", _post)
    monkeypatch.setattr(common, "attack_salon", _salon)

    stack = _stack(_attack(room_channel_id=5))
    await phases._meeting_salon_heal_safe(None, stack, None, {}, "fr")
    assert opened == ["a1"], "the salon is created late"
    assert posted == ["a1"], "the scoreboard lands right after"


@pytest.mark.asyncio
async def test_a_well_meeting_never_pays_the_heal(monkeypatch) -> None:
    import botforge.mods.kingdom.cogs.battle as battle
    import botforge.mods.kingdom.cogs.panel as panel
    import botforge.mods.kingdom.cogs.phases as phases

    async def _open(guild, stack, strings, attack, locale="fr"):
        raise AssertionError("no salon creation for a healthy meeting")

    async def _post(guild, stack, attack, strings):
        raise AssertionError("no repost for a healthy meeting")

    monkeypatch.setattr(panel, "_open_attack_salon_safe", _open)
    monkeypatch.setattr(battle, "post_meeting_message", _post)

    healthy = _attack(room_channel_id=5, meeting_message_id=99)
    over = _attack("a2", is_over=True, room_channel_id=6)
    pending = _attack("a3")  # no battle room yet — not a meeting
    stack = _stack(healthy, over, pending)
    await phases._meeting_salon_heal_safe(None, stack, None, {}, "fr")


@pytest.mark.asyncio
async def test_a_failing_salon_open_skips_the_post(monkeypatch) -> None:
    import botforge.mods.kingdom.cogs.battle as battle
    import botforge.mods.kingdom.cogs.common as common
    import botforge.mods.kingdom.cogs.panel as panel
    import botforge.mods.kingdom.cogs.phases as phases

    posted: list[str] = []

    async def _open(guild, stack, strings, attack, locale="fr"):
        raise RuntimeError("proxy refusing")

    async def _post(guild, stack, attack, strings):
        posted.append(str(attack.id))
        return None

    def _salon(guild, attack):
        return None

    monkeypatch.setattr(panel, "_open_attack_salon_safe", _open)
    monkeypatch.setattr(battle, "post_meeting_message", _post)
    monkeypatch.setattr(common, "attack_salon", _salon)

    stack = _stack(_attack(room_channel_id=5))
    await phases._meeting_salon_heal_safe(None, stack, None, {}, "fr")
    assert posted == [], "a failed salon open must not post anywhere"
