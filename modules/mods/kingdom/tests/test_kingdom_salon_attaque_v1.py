"""salon-attaque-v1 (Drasah 24/11) — the live-incident regression pins.

The pick & ban reveal crashed on a coroutine packed unpacked bare
(« TypeError: cannot unpack non-iterable coroutine object », heard
live as « les délais n'ont pas été respectés » + a meeting without
its salon). The attack-salon client lookup itself was fixed by
salon-dynamique-client-v1 — this file pins the REVEAL tail.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest


@pytest.mark.asyncio
async def test_the_reveal_dm_is_actually_sent_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pick & ban validation used to crash: the reveal payload is
    an async def unpacked WITHOUT await. The reveal must reach BOTH
    players as a fresh DM (the crash killed the whole phase tail)."""
    import botforge.mods.kingdom.cogs.pickban as pb

    sent: list[tuple[str, str]] = []

    async def _dm(
        bot: object,
        player_id: str,
        content: str,
        view: object = None,
        files: object = None,
    ) -> object:
        sent.append((player_id, content))
        return SimpleNamespace(channel_id="1", message_id="2")

    async def _delete(bot: object, ref: object) -> None:
        return None

    async def _record(attack_id: str, player_id: str, message: object) -> None:
        return None

    async def _stock(stack: object, attack: object, side: str, strings: dict[str, str]) -> str:
        return ""

    async def _view(stack: object, attack: object, side: str, strings: dict[str, str]) -> object:
        return None

    monkeypatch.setattr(pb, "dm_user_safe", _dm)
    monkeypatch.setattr(pb, "delete_dm_message_safe", _delete)
    monkeypatch.setattr(pb, "record_pickban_dm_safe", _record)
    monkeypatch.setattr(pb, "sabotage_stock_line", _stock)
    monkeypatch.setattr(pb, "sabotage_dm_view", _view)

    attack = SimpleNamespace(
        id="a1",
        attacker_lord_id="1",
        defender_lord_id="2",
        ai_defender=False,
        map_key="pataugeoire",
        expires_at=datetime(2026, 11, 24, 22, 45, tzinfo=UTC),
        pickban={"attacker_picks": ["celtes"], "defender_picks": ["gaulois"]},
    )
    from botforge.mods.kingdom.cogs.strings import strings as _strings

    strings = _strings("fr")
    await pb.edit_pickban_dms_reveal(None, attack, strings)
    assert [pid for pid, _ in sent] == ["1", "2"], "BOTH players got their reveal DM"
    assert any("celtes" in c or "gaulois" in c for _, c in sent), "the reveal content rides"


@pytest.mark.asyncio
async def test_the_sabotage_panel_survives_its_own_arm(monkeypatch: pytest.MonkeyPatch) -> None:
    """affaire-26 (Drasah 25/11 live report): the panel flashed for a
    millisecond then vanished. The arm used to DELETE the panel before
    arming — every open or click erased its own surface. The arm now
    NEVER deletes; only a close (Passer, replacement, sweep) does."""
    import asyncio

    import botforge.mods.kingdom.cogs.pickban as pb

    deleted: list[object] = []

    class _FakeInteraction:
        async def delete_original_response(self) -> None:
            deleted.append(self)

    pb._SABOTAGE_PANELS.clear()
    key = ("a1", "u1")
    pb._SABOTAGE_PANELS[key] = {"interaction": _FakeInteraction()}
    pb._arm_sabotage_panel_timer(key)
    await asyncio.sleep(0)
    assert key in pb._SABOTAGE_PANELS, "the arm NEVER deletes its panel"
    assert not deleted, "no delete may fire at open time"

    # the explicit close still deletes, and cancels the timer
    await pb._delete_sabotage_panel(key)
    assert key not in pb._SABOTAGE_PANELS and len(deleted) == 1

    # a short sweep (no action left) really closes the panel
    pb._SABOTAGE_PANELS.clear()
    pb._SABOTAGE_PANELS[key] = {"interaction": _FakeInteraction()}
    pb._arm_sabotage_panel_timer(key, seconds=0.01)
    await asyncio.sleep(0.05)
    assert key not in pb._SABOTAGE_PANELS or not pb._SABOTAGE_PANELS.get(key, {}).get("task")
    assert len(deleted) == 2
    pb._SABOTAGE_PANELS.clear()


async def _stock_stub(stack: object, attack: object, side: str, strings: dict[str, str]) -> str:
    """The mosaic test's stock stub (no service)."""
    return ""


async def _view_stub(stack: object, attack: object, side: str, strings: dict[str, str]) -> object:
    """The mosaic test's DM view stub."""
    return None

@pytest.mark.asyncio
async def test_the_reveal_carries_the_crossed_crest_mosaic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """sabotage-visuel-v1 (Affaire 26): the reveal DM carries ONE
    composite mosaic — each civ name painted above its crest, every
    civ this side already sabotaged wearing the ❌ cross, the origin
    badge stripped."""
    import botforge.mods.kingdom.cogs.civ_crests as crests
    import botforge.mods.kingdom.cogs.pickban as pb

    calls: list[dict[str, Any]] = []

    class _FakeFile:
        pass

    async def _mosaic(
        entries: list[tuple[str, ...]],
        filename: str = "alliances.png",
        *,
        with_origin_badges: bool = True,
        crossed: object = None,
    ) -> object:
        calls.append(
            {"entries": list(entries), "filename": filename, "badges": with_origin_badges, "crossed": crossed}
        )
        return _FakeFile()

    monkeypatch.setattr(crests, "civ_crest_mosaic_file", _mosaic)
    monkeypatch.setattr(pb, "sabotage_stock_line", _stock_stub)
    monkeypatch.setattr(pb, "sabotage_dm_view", _view_stub)

    attack = SimpleNamespace(
        id="a1",
        attacker_lord_id="1",
        defender_lord_id="2",
        ai_defender=False,
        map_key="pataugeoire",
        expires_at=datetime(2026, 11, 24, 22, 45, tzinfo=UTC),
        pickban={
            "attacker_picks": ["celtes", "gaulois", "britons"],
            "defender_picks": ["francs", "huns", "perses"],
            "attacker_sabotages": ["francs"],
        },
    )
    from botforge.mods.kingdom.cogs.strings import strings as _strings

    _pid, _content, _view, files = await pb.sabotage_reveal_payload(
        None, attack, "attacker", _strings("fr")
    )
    assert files and len(files) == 1, "the reveal carries ONE mosaic file"
    call = calls[-1]
    assert call["filename"] == "reveal.png"
    assert call["badges"] is False, "the origin star stays home on a reveal"
    assert call["crossed"] == {"francs"}, "the sniped civ wears the ❌ cross"
    assert [e[0] for e in call["entries"]] == ["francs", "huns", "perses"], (
        "the tiles follow the SEEDED shuffled order"
    )
