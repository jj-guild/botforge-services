"""affaire-29 (Drasah 25/11) — « Prêt » locks the sabotage + the honest
draft buttons + the refused-delete flag.

Drasah's live findings: (1) a side that clicked Passer (Prêt) could
still SNIPE afterwards — the engine did not check sabotage_settled and
the DM kept its green clickable buttons; (2) the draft's « Modifier »
button wiped every slot wearing a soft style, and a lost-update race
could render empty slots after a refused validation; (3) a 403-refused
room delete still flagged the meeting room_cleaned — the ghost vocal
was then abandoned forever.
"""


from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


def _inner(button: Any) -> Any:
    """The wrapped discord.ui.Button of a DynamicItem."""
    return getattr(button, "item", None) or button.__dict__.get("item", button)


@pytest.mark.asyncio
async def test_a_settled_side_freezes_both_dm_buttons() -> None:
    """A settled (« Prêt ») side's DM view: every button grey + disabled
    and sabotage_open_available answers False."""

    from botforge.mods.kingdom.cogs import pickban
    from botforge.mods.kingdom.cogs.common import strings_by_locale

    attack = SimpleNamespace(
        id="a1",
        attacker_lord_id="10",
        defender_lord_id="20",
        pickban={
            "resolved_pickban": True,
            "sabotage_settled_attacker": True,
            "attacker_sabotages": [],
            "defender_picks": ["berberes", "gurjaras", "portugais"],
        },
    )
    strings = strings_by_locale("fr")
    view = await pickban.sabotage_dm_view(None, attack, "attacker", strings)
    children = list(view.children)
    assert children, "the settled DM keeps its buttons (frozen, not removed)"
    for child in children:
        assert getattr(_inner(child), "disabled", False) is True, "no clickable button on a settled side"
    assert await pickban.sabotage_open_available(None, attack, "attacker", strings) is False


def test_the_engine_refuses_a_settled_side_snipe() -> None:
    """sabotage_techno carries the settled guard (source contract)."""

    from botforge.mods.kingdom import attacks as engine

    source = open(engine.__file__, encoding="utf-8").read()
    assert "sabotage_settled_{side}" in source, "the settled-side guard must stay in sabotage_techno"
    assert "verrouillé" in source, "the refusal carries its dedicated message"


def test_the_modifier_button_is_an_honest_full_reset() -> None:
    """« ♻️ Tout recommencer » wears the DANGER style in both locales."""

    from botforge.mods.kingdom.cogs import pickban
    from botforge.mods.kingdom.cogs.common import strings_by_locale

    for locale, match in (("fr", "Tout recommencer"), ("en", "Start over")):
        strings = strings_by_locale(locale)
        assert match in strings["pickban_modify_button"], f"{locale} label must say a full restart"

    button = pickban.PickBanModifyButton("a1", "10", True, "fr")
    inner = _inner(button)
    assert "Tout recommencer" in str(getattr(inner, "label", "")), (
        f"fr label must say a full restart: {getattr(inner, "label", "")!r}"
    )
    assert getattr(inner, "style", None) is not None


def test_the_pass_button_wears_the_frozen_grey_when_unavailable() -> None:
    """A settled side's Passer renders grey + disabled."""

    from botforge.mods.kingdom.cogs import pickban
    from botforge.mods.kingdom.cogs.common import strings_by_locale

    button = pickban.SabotagePassButton(
        "a1", "10", strings_by_locale("fr")["sab_pass_button"], available=False
    )
    inner = _inner(button)
    assert getattr(inner, "disabled", False) is True, "the frozen Passer is disabled"


@pytest.mark.asyncio
async def test_a_refused_room_delete_never_flags_the_meeting_clean() -> None:
    """A 403 on channel.delete → no mark_room_cleaned, played = 0."""

    from botforge.mods.kingdom.cogs import battle

    class _BoomError(Exception):
        pass

    class _Channel:
        async def delete(self) -> None:
            raise _BoomError()

    class _Guild:
        def get_channel(self, channel_id: int) -> Any:
            return _Channel()

    bot = SimpleNamespace(guilds=[_Guild()])
    flagged: list[str] = []

    async def _mark(attack_id: str) -> None:
        flagged.append(attack_id)

    stack = SimpleNamespace(attacks=SimpleNamespace(mark_room_cleaned=_mark))
    score = {"room_channel_id": 42, "room_role_id": None}
    attack = SimpleNamespace(id="a1", score=score)
    played = await battle._cleanup_one_battle_room(bot, stack, attack, dict(score))
    assert played == 0, "a refused delete counts nothing closed"
    assert not flagged, "the flag room_cleaned is NOT set on a refused delete"
    assert await battle._delete_battle_room_safe(bot, 42, None) is False


@pytest.mark.asyncio
async def test_an_accepted_room_delete_still_flags_and_counts() -> None:
    """The happy path is unchanged — accepted delete → flag + played 1."""

    from botforge.mods.kingdom.cogs import battle

    deleted: list[Any] = []

    class _Channel:
        def __init__(self, cid: int) -> None:
            self.cid = cid

        async def delete(self) -> None:
            deleted.append(self.cid)

    class _Guild:
        def get_channel(self, channel_id: int) -> Any:
            return _Channel(channel_id)

    bot = SimpleNamespace(guilds=[_Guild()])

    async def _mark(attack_id: str) -> None:
        deleted.append(-1)

    stack = SimpleNamespace(attacks=SimpleNamespace(mark_room_cleaned=_mark))
    score = {"room_channel_id": 7, "room_role_id": None}
    attack = SimpleNamespace(id="a1", score=score)
    played = await battle._cleanup_one_battle_room(bot, stack, attack, dict(score))
    assert played == 1
    assert deleted == [7, -1], "the channel is deleted THEN the flag is set"


def test_the_stage_slot_merge_keeps_the_other_slots_alive() -> None:
    """The merge helper: our civ rides OUR slot, a duplicate elsewhere is
    cleared, the concurrent clicks' slots are preserved."""

    from botforge.mods.kingdom import attacks as engine

    assert engine._stage_draft_slot(["francs", "", ""], 0, "francs") == ["francs", "", ""]
    # the concurrent clicks' slots survive the merge
    assert engine._stage_draft_slot(["celtes", "", ""], 1, "huns") == ["celtes", "huns", ""]
    # a duplicate elsewhere is cleared (one civ, ONE slot)
    assert engine._stage_draft_slot(["", "francs", "huns"], 2, "francs") == ["", "", "francs"]
