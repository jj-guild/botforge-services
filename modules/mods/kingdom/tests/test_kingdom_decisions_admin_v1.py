"""decisions-admin-v1 (Drasah 25/11) - unit tests.

The admin decisions layer: the ONE inbox queue (``pending_disputes``,
both dispute roads), the ``cancel`` terminal choice (no winner, the
locks release), ``admin_cancel_attack`` on a stuck-but-not-litigated
meeting, the DecisionService ledger (mandatory reason, idempotent
announce flag) and the announce filter (concerned kingdoms, empty =
every realm).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from botforge.mods.kingdom.models import AttackState
from test_kingdom_attack_score import _T, ScoreBundle

_FROZEN_NOW = datetime(2026, 10, 11, 17, 50, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _freeze_attacks_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    from botforge.mods.kingdom import attacks as attacks_module

    monkeypatch.setattr(attacks_module, "_now", lambda: _FROZEN_NOW)


class LedgerStore:
    """The dict-store of the decisions collection (tests only)."""

    def __init__(self) -> None:
        self.decisions: dict[str, dict[str, object]] = {}

    async def upsert_decision(self, document: dict[str, object]) -> None:
        self.decisions[str(document["_id"])] = document

    async def find_decisions(self) -> list[dict[str, object]]:
        return list(self.decisions.values())


async def _disputed_meeting(
    bundle: ScoreBundle,
) -> tuple[Any, str, str]:
    """A MEETING carrying a contradictory-declaration dispute."""
    await bundle.launch_season()
    await bundle.draw(9)
    opened, aquitaine, bourgogne = await bundle.open_meeting()
    await bundle.attacks.declare_score(opened.id, "king-a", aquitaine, "g-1", now=_T)
    fresh, outcome = await bundle.attacks.declare_score(
        opened.id, "lord-b", bourgogne, "g-2", now=_T + timedelta(minutes=1)
    )
    assert outcome == "disputed"
    return fresh, aquitaine, bourgogne


async def test_pending_disputes_lists_both_roads_only() -> None:
    """The inbox asks the MEETING state, not the road that opened it."""
    bundle = ScoreBundle()
    attack, _, _ = await _disputed_meeting(bundle)
    pending = await bundle.attacks.pending_disputes()
    assert [item.id for item in pending] == [attack.id]
    # a healthy meeting never enters the inbox, a resolved one neither
    healthy = ScoreBundle()
    await healthy.launch_season()
    await healthy.draw(9)
    quiet, _, _ = await healthy.open_meeting()
    assert await healthy.attacks.pending_disputes() == []
    await healthy.attacks.admin_cancel_attack(quiet.id, now=_T)
    assert await healthy.attacks.pending_disputes() == []


async def test_pending_disputes_lists_the_auto_road_too() -> None:
    """An auto-opened dispute (no result in time) rides the SAME queue."""
    bundle = ScoreBundle()
    attack, _, _ = await _disputed_meeting(bundle)
    # the auto road: a meeting whose score carries auto_dispute
    raw = attack.to_mongo()
    score = dict(raw.get("score") or {})
    score["auto_dispute"] = True
    raw["score"] = score
    await bundle.store.upsert_attack(raw)
    pending = await bundle.attacks.pending_disputes()
    assert [item.id for item in pending] == [attack.id]


async def test_resolve_dispute_cancel_releases_everything() -> None:
    """« annuler » = no winner, no points, the lock releases."""
    bundle = ScoreBundle()
    attack, _, _ = await _disputed_meeting(bundle)
    fresh = await bundle.attacks.resolve_dispute(
        attack.id, "cancel", now=_T + timedelta(minutes=2)
    )
    assert fresh.state is AttackState.EXPIRED
    assert fresh.winner_kingdom_id is None
    assert fresh.score["admin_cancelled"] is True
    assert fresh.score["disputed"] is False
    assert fresh.is_over


async def test_admin_cancel_attack_terminal_on_a_healthy_meeting() -> None:
    """A dead match never litigated still aborts (the console typo fix)."""
    bundle = ScoreBundle()
    await bundle.launch_season()
    await bundle.draw(9)
    attack, _, _ = await bundle.open_meeting()
    fresh = await bundle.attacks.admin_cancel_attack(
        attack.id, now=_T + timedelta(minutes=2)
    )
    assert fresh.state is AttackState.EXPIRED
    assert fresh.winner_kingdom_id is None
    assert fresh.score["admin_cancelled"] is True
    # the cancellation is idempotent-ish: re-resolving refuses
    from botforge.mods.kingdom.attacks import AttackStateError

    with pytest.raises(AttackStateError):
        await bundle.attacks.resolve_dispute(attack.id, "cancel", now=_T)


async def test_record_decision_requires_a_reason() -> None:
    """Anti-abus: no decision without its written reason."""
    from botforge.mods.kingdom.decisions import DecisionService

    service = DecisionService(LedgerStore())
    with pytest.raises(ValueError):
        await service.record_decision(
            type="arbitrage",
            kingdom_ids=[],
            summary="Blanc gagne la pataugeoire",
            reason="   ",
            admin_id="admin-1",
        )


async def test_ledger_orders_and_flags_idempotently() -> None:
    """decisions asc, last_decisions desc, mark_announced replays safe."""
    from botforge.mods.kingdom.decisions import DecisionService

    store = LedgerStore()
    service = DecisionService(store)
    first = await service.record_decision(
        type="arbitrage", kingdom_ids=["k1"], summary="s1",
        reason="r1", admin_id="a", now=100,
    )
    second = await service.record_decision(
        type="annulation", kingdom_ids=["k1", "k2"], summary="s2",
        reason="r2", admin_id="a", now=200,
    )
    assert [doc["_id"] for doc in await service.decisions()] == [
        first["_id"], second["_id"],
    ]
    assert [doc["_id"] for doc in await service.last_decisions(10)] == [
        second["_id"], first["_id"],
    ]
    assert len(await service.to_announce()) == 2
    await service.mark_announced(first["_id"])
    await service.mark_announced(first["_id"])  # replay safe
    assert [doc["_id"] for doc in await service.to_announce()] == [second["_id"]]


async def test_announce_filters_the_concerned_kingdoms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty kingdom_ids announces EVERY realm, a list only its own."""
    from botforge.mods.kingdom.cogs import decisions as decisions_cog
    from botforge.mods.kingdom.cogs import realm_content
    from botforge.mods.kingdom.decisions import DecisionService

    posted: list[str] = []

    class _Salon:
        async def send(self, content: str) -> None:
            posted.append(content)

    async def _channels(guild: object, realm: object) -> dict[str, object]:
        return {"discussions": _Salon()}

    monkeypatch.setattr(realm_content, "_realm_channels", _channels)

    def _realm(slug: str, kingdom_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            slug=slug, engagement={"kingdom_id": kingdom_id}
        )

    realms = [_realm("alpha", "k1"), _realm("beta", "k2")]
    store = LedgerStore()
    stack = SimpleNamespace(
        decisions=DecisionService(store),
        realms=SimpleNamespace(
            realms=lambda: _async_list(realms),
        ),
        attacks=SimpleNamespace(
            attacks=lambda: _async_list([]),
        ),
    )
    bot = SimpleNamespace(guilds=[SimpleNamespace()])
    scoped = await stack.decisions.record_decision(
        type="arbitrage", kingdom_ids=["k1"], summary="s",
        reason="r", admin_id="admin", now=10,
    )
    await decisions_cog.announce_decision_safe(bot, stack, scoped, "fr")
    assert len(posted) == 1  # only the concerned realm
    # the announce flag landed (idempotence for the tick)
    assert await stack.decisions.to_announce() == []
    posted.clear()
    global_doc = await stack.decisions.record_decision(
        type="annulation", kingdom_ids=[], summary="s",
        reason="r", admin_id="admin", now=20,
    )
    await decisions_cog.announce_decision_safe(bot, stack, global_doc, "fr")
    assert len(posted) == 2  # empty list = every realm


async def _async_list(items: list[Any]) -> list[Any]:
    return items


async def test_apply_admin_decision_records_the_cancellation() -> None:
    """apply_admin_decision « cancel » : terminal attack + annulation ledger."""
    from botforge.mods.kingdom.cogs.decisions import apply_admin_decision
    from botforge.mods.kingdom.decisions import DecisionService

    bundle = ScoreBundle()
    attack, _, _ = await _disputed_meeting(bundle)
    store = LedgerStore()
    stack = SimpleNamespace(
        attacks=bundle.attacks,
        decisions=DecisionService(store),
        kingdoms=bundle.kingdoms,
    )
    fresh, decision = await apply_admin_decision(
        stack, attack, "cancel", "partie morte", "admin-1", "fr"
    )
    assert fresh.state is AttackState.EXPIRED
    assert decision["type"] == "annulation"
    assert decision["admin_id"] == "admin-1"
    with pytest.raises(ValueError):
        await apply_admin_decision(stack, fresh, "cancel", "  ", "admin-1", "fr")


async def _lord_of(bundle: ScoreBundle, lord_id: str) -> Any:
    return next(item for item in await bundle.kingdoms.lords() if item.id == lord_id)


async def test_admin_cancel_refunds_both_budgets() -> None:
    """annulation-joueur-v2: the admin cancel refunds attacker AND defender.

    A meeting that reached the RDV consumed the attacker's attack
    point and the defender's defense point — the aborted meeting gives
    BOTH back (the withdrawal is not a free restart of the budgets, it
    is the annulation).
    """
    bundle = ScoreBundle()
    attack, _, _ = await _disputed_meeting(bundle)
    assert (await _lord_of(bundle, "king-a")).attack_used == 1
    assert (await _lord_of(bundle, "lord-b")).defense_used == 1
    fresh = await bundle.attacks.resolve_dispute(
        attack.id, "cancel", now=_T + timedelta(minutes=2)
    )
    assert fresh.score["admin_cancelled"] is True
    assert (await _lord_of(bundle, "king-a")).attack_used == 0
    assert (await _lord_of(bundle, "lord-b")).defense_used == 0
    # the restitution latches (restatuting twice never double-refunds)
    assert (await bundle.attacks._find_attack(attack.id)).restituted is True


async def test_double_forfeit_keeps_the_budgets() -> None:
    """The double forfait is NOT the annulation: the budgets stay spent."""
    bundle = ScoreBundle()
    attack, _, _ = await _disputed_meeting(bundle)
    fresh = await bundle.attacks.resolve_dispute(
        attack.id, "both", now=_T + timedelta(minutes=2)
    )
    assert fresh.state is AttackState.EXPIRED
    assert "admin_cancelled" not in fresh.score
    assert (await _lord_of(bundle, "king-a")).attack_used == 1
    assert (await _lord_of(bundle, "lord-b")).defense_used == 1
    assert (await bundle.attacks._find_attack(attack.id)).restituted is False


async def test_decided_attack_habitat_closes_at_once() -> None:
    """annulation-joueur-v2: voice + role + salon close WITH the decision.

    The admin modal calls cleanup_decided_attack_safe right after the
    resolution — the flags keep the 30-minute cleanup tick idempotent
    and a second call touches nothing.
    """
    from botforge.mods.kingdom.cogs.battle import cleanup_decided_attack_safe

    deleted: list[str] = []
    flags: list[str] = []

    class _Channel:
        def __init__(self, name: str) -> None:
            self.name = name

        async def delete(self) -> None:
            deleted.append(self.name)

    class _Role(_Channel):
        pass

    salon = _Channel("salon")
    room = _Channel("room")
    role = _Role("role")

    class _Guild:
        def get_channel(self, channel_id: int) -> Any:
            return {1: salon, 2: room}.get(channel_id)

        def get_role(self, role_id: int) -> Any:
            return role if role_id == 3 else None

    class _Attacks:
        async def mark_room_cleaned(self, attack_id: str) -> None:
            flags.append("room")

        async def mark_attack_salon_cleaned(self, attack_id: str) -> None:
            flags.append("salon")

    attack = SimpleNamespace(
        id="a1",
        score={
            "attack_channel_id": 1,
            "room_channel_id": 2,
            "room_role_id": 3,
        },
    )
    bot = SimpleNamespace(guilds=[_Guild()])
    stack = SimpleNamespace(attacks=_Attacks())
    played = await cleanup_decided_attack_safe(bot, stack, attack)
    assert played == 2
    assert set(deleted) == {"salon", "room", "role"}
    assert set(flags) == {"room", "salon"}
    # the flags latched: a replay cleans NOTHING (tick idempotence)
    deleted.clear()
    flags.clear()
    attack = SimpleNamespace(
        id="a1",
        score={
            "attack_channel_id": 1,
            "attack_salon_cleaned": True,
            "room_channel_id": 2,
            "room_cleaned": True,
            "room_role_id": 3,
        },
    )
    assert await cleanup_decided_attack_safe(bot, stack, attack) == 0
    assert deleted == [] and flags == []
