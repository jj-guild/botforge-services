""" temporalites-beta-v1 (Drasah 25/11) — unit tests.

The live beta report: the defender's draft DM died silently (Discord
403, « no mutual guilds »), the 5-minute tick landed every phase late
under the 10-minute beta itinerary, the post-decision habitat
survived 30 minutes and the admin had to WAIT for T to clear a stuck
flank. This batch pins the fixes: the LOUD dm failure note, the fast
lane sleeping at the next deadline, the 5-minute beta cleanup, and
the admin cancel of a LIVE (non-meeting) attack — budgets refunded,
habitat closable, terminal.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from botforge.mods.kingdom.attacks import AttackStateError
from botforge.mods.kingdom.models import AttackState
from test_kingdom_attack_phases import PhasesBundle

_DECLARE = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
_DEFENSE = _DECLARE + timedelta(minutes=5)
_CANCEL = _DECLARE + timedelta(minutes=8)


async def _declared(bundle: PhasesBundle) -> Any:
    await bundle.launch_season()
    await bundle.draw(5)
    return await bundle.fresh_attack()


async def _lord(bundle: PhasesBundle, lord_id: str) -> Any:
    return next(item for item in await bundle.kingdoms.lords() if item.id == lord_id)


# -- the admin cancel of a LIVE attack --------------------------------------


async def test_admin_cancel_of_a_declared_attack_is_terminal_and_refunds() -> None:
    """DECLARED: state flip EXPIRED, attacker budget back, refused twice."""
    bundle = PhasesBundle()
    attack = await _declared(bundle)
    assert (await _lord(bundle, "king-a")).attack_used == 1
    fresh = await bundle.attacks.admin_cancel_attack(
        attack.id, now=_CANCEL, reason="flanc de test cassé"
    )
    assert fresh.state is AttackState.EXPIRED
    assert fresh.score["admin_cancelled"] is True
    assert fresh.winner_kingdom_id is None
    assert fresh.is_over is True
    assert (await _lord(bundle, "king-a")).attack_used == 0
    # the lock lifted: the declarant may strike again
    await bundle.attacks._refuse_engaged("king-a", _CANCEL)  # no LordEngagedError
    # a second cancel refuses — never a double refund
    with pytest.raises(AttackStateError):
        await bundle.attacks.admin_cancel_attack(attack.id, now=_CANCEL, reason="double")
    assert (await _lord(bundle, "king-a")).attack_used == 0


async def test_admin_cancel_of_a_defended_attack_refunds_the_defender() -> None:
    """DEFENDED: the recorded player defense comes back too."""
    bundle = PhasesBundle()
    attack = await _declared(bundle)
    await bundle.attacks.respond_defense(attack.id, "lord-b", now=_DEFENSE)
    assert (await _lord(bundle, "lord-b")).defense_used == 1
    fresh = await bundle.attacks.admin_cancel_attack(
        attack.id, now=_CANCEL, reason="draft bloqué"
    )
    assert fresh.is_over is True
    assert (await _lord(bundle, "king-a")).attack_used == 0
    assert (await _lord(bundle, "lord-b")).defense_used == 0


async def test_admin_cancel_requires_a_reason() -> None:
    """The admin trace is mandatory — an empty reason refuses."""
    bundle = PhasesBundle()
    attack = await _declared(bundle)
    with pytest.raises(AttackStateError):
        await bundle.attacks.admin_cancel_attack(attack.id, now=_CANCEL, reason="  ")
    assert attack.state is AttackState.DECLARED


async def test_live_attacks_lists_only_ongoing_attacks() -> None:
    """The drawer's source: live in, terminal out."""
    bundle = PhasesBundle()
    attack = await _declared(bundle)
    live = await bundle.attacks.live_attacks()
    assert [item.id for item in live] == [attack.id]
    await bundle.attacks.admin_cancel_attack(attack.id, now=_CANCEL, reason="nettoyage")
    assert await bundle.attacks.live_attacks() == []


# -- the deadline probe the fast lane consumes -------------------------------


async def test_next_phase_deadline_tracks_the_reveal_then_t() -> None:
    """DECLARED: the reveal cutoff then T, to the second."""
    bundle = PhasesBundle()
    attack = await _declared(bundle)
    now = _DECLARE + timedelta(minutes=1)
    deadline = await bundle.attacks.next_phase_deadline(now=now)
    cutoff = attack.expires_at - timedelta(minutes=bundle.config.attacks.defense_cutoff_minutes)
    assert deadline == cutoff
    # revealed (past the cutoff): the next deadline is T itself
    deadline = await bundle.attacks.next_phase_deadline(now=cutoff + timedelta(seconds=1))
    assert deadline == attack.expires_at


async def test_the_fast_lane_sleeps_at_the_next_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lane wakes within seconds of a deadline, never 5 late."""
    from botforge.mods.kingdom import beta_weekend
    from botforge.mods.kingdom.cogs import common, phases
    from botforge.mods.kingdom.game_clock import game_now

    async def _deadline(*, now: Any = None) -> Any:
        return game_now() + timedelta(seconds=30)

    stack = SimpleNamespace(
        kingdoms=SimpleNamespace(current_season=lambda: object()),
        attacks=SimpleNamespace(next_phase_deadline=_deadline),
    )
    monkeypatch.setattr(common, "wiring", lambda: stack)
    # beta armed + a deadline at 30 s: the lane sleeps ~32 s, not 60 nor 300
    monkeypatch.setattr(beta_weekend, "beta_started", lambda season, now: True)
    assert await phases.attack_fastlane_sleep_seconds(object(), 300) <= 32
    assert await phases.attack_fastlane_sleep_seconds(object(), 300) >= 5
    # a deadline already due: run the work within the second
    async def _due(*, now: Any = None) -> Any:
        return game_now() - timedelta(seconds=1)

    stack.attacks = SimpleNamespace(next_phase_deadline=_due)
    assert await phases.attack_fastlane_sleep_seconds(object(), 300) == 1
    # beta off + no deadline at all: the stock cadence stays
    monkeypatch.setattr(beta_weekend, "beta_started", lambda season, now: False)
    async def _none(*, now: Any = None) -> None:
        return None

    stack.attacks = SimpleNamespace(next_phase_deadline=_none)
    assert await phases.attack_fastlane_sleep_seconds(object(), 300) == 300


# -- the 5-minute beta cleanup ----------------------------------------------


async def test_room_cleanup_delay_shrinks_under_an_armed_beta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Beta: 5 minutes. Official: the configured 30."""
    from botforge.mods.kingdom import beta_weekend

    bundle = PhasesBundle()
    await _declared(bundle)
    monkeypatch.setattr(beta_weekend, "beta_started", lambda season, now: True)
    assert await bundle.attacks.room_cleanup_delay() == 5
    monkeypatch.setattr(beta_weekend, "beta_started", lambda season, now: False)
    assert await bundle.attacks.room_cleanup_delay() == bundle.attacks.room_cleanup_delay_minutes


# -- the LOUD fallback of a refused draft DM --------------------------------


async def test_a_refused_draft_dm_leaves_a_note_in_the_attack_salon(monkeypatch: pytest.MonkeyPatch) -> None:
    """A DM refused (403 privacy) never stays silent: the salon warns."""
    from botforge.mods.kingdom.cogs import pickban

    sent: list[str] = []

    async def _send(guild: Any, attack: Any, content: str) -> None:
        sent.append(str(content))

    monkeypatch.setattr(pickban, "attack_salon_send_safe", _send)
    bot = SimpleNamespace(guilds=[SimpleNamespace()])
    attack = SimpleNamespace(map_key="m", expires_at=_DECLARE)
    await pickban._salon_dm_failure_note_safe(bot, attack, "123", {"pickban_dm_failed_sal": "<@{player}> réglages"})
    assert len(sent) == 1
    assert "123" in sent[0]


async def test_send_pickban_dm_falls_back_loud_on_each_side(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both the attacker's and the defender's failed DMs warn the salon."""
    from botforge.mods.kingdom.cogs import pickban

    sent: list[str] = []

    async def _send(guild: Any, attack: Any, content: str) -> None:
        sent.append(str(content))

    async def _hand(*args: Any, **kwargs: Any) -> list[str]:
        return ["Aztecs", "Britons", "Celts"]

    async def _view(*args: Any, **kwargs: Any) -> None:
        return None

    async def _stock(*args: Any, **kwargs: Any) -> str:
        return ""

    async def _record(*args: Any, **kwargs: Any) -> None:
        return None

    async def _dm(*args: Any, **kwargs: Any) -> None:
        return None  # Discord refuses: the privacy wall

    monkeypatch.setattr(pickban, "pickban_hand_safe", _hand)
    monkeypatch.setattr(pickban, "pickban_dm_view", _view)
    monkeypatch.setattr(pickban, "sabotage_stock_line", _stock)
    monkeypatch.setattr(pickban, "record_pickban_dm_safe", _record)
    monkeypatch.setattr(pickban, "dm_user_safe", _dm)
    monkeypatch.setattr(pickban, "attack_salon_send_safe", _send)
    monkeypatch.setattr(pickban, "wiring", lambda: SimpleNamespace())
    bot = SimpleNamespace(guilds=[SimpleNamespace()])
    attack = SimpleNamespace(
        id="attack-1",
        map_key="m",
        expires_at=_DECLARE,
        attacker_kingdom_id="king-a",
        attacker_lord_id="111",
        defender_kingdom_id="king-b",
        defender_lord_id="222",
        ai_defender=False,
    )
    await pickban.send_pickban_dm(bot, attack, "fr")
    # both sides refused → both sides warned
    assert len(sent) == 2
    assert "111" in sent[0]
    assert "222" in sent[1]
