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

import pytest


@pytest.mark.asyncio
async def test_the_reveal_dm_is_actually_sent_now(monkeypatch) -> None:
    """The pick & ban validation used to crash: the reveal payload is
    an async def unpacked WITHOUT await. The reveal must reach BOTH
    players as a fresh DM (the crash killed the whole phase tail)."""
    import botforge.mods.kingdom.cogs.pickban as pb

    sent: list[tuple[str, str]] = []

    async def _dm(bot: object, player_id: str, content: str, view: object = None) -> object:
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
