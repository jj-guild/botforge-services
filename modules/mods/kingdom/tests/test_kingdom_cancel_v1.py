""" annulation-joueur-v2 (Drasah 25/11) — unit tests.

The live diagnostic (the « annulation joueur » batch): cancel_attack
refunded the budgets and STOPPED there — no CANCELLED state, no
upsert, no return. The attack stayed DECLARED for everyone: the
seigneur lock never lifted, a defender could defend a dead attack, a
double cancel double-refunded, and the salon purge received None.

These tests pin the TERMINAL withdrawal: state CANCELLED (is_over),
budgets refunded (attacker, defender, cover), the late-defense refusal
reading « annulée », the release of the battle lock and the defender's
DM on a cancellation that had a defense recorded.
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


async def test_the_declarant_cancel_terminates_the_attack() -> None:
    """CANCELLED latches: is_over, terminal, the lock releases."""
    bundle = PhasesBundle()
    attack = await _declared(bundle)
    fresh = await bundle.attacks.cancel_attack(attack.id, "king-a", now=_CANCEL)
    assert fresh is not None, "the cog needs the model back to purge the salon"
    assert fresh.state is AttackState.CANCELLED
    assert fresh.is_over is True
    assert fresh.resolved_at == _CANCEL
    # the attacker's budget is back
    assert (await _lord(bundle, "king-a")).attack_used == 0
    # a second cancel refuses — never a double refund
    with pytest.raises(AttackStateError):
        await bundle.attacks.cancel_attack(attack.id, "king-a", now=_CANCEL)
    assert (await _lord(bundle, "king-a")).attack_used == 0
    # the battle lock lifted: the declarant may strike again
    await bundle.attacks._refuse_engaged("king-a", _CANCEL)  # no LordEngagedError
    # a defense on the dead attack refuses with the withdrawal line
    with pytest.raises(AttackStateError) as exc:
        await bundle.attacks.respond_defense(attack.id, "lord-b", now=_DEFENSE)
    assert "annulée" in str(exc.value)


async def test_the_cancel_refunds_the_defender_and_the_cover() -> None:
    """A defense already posed and a burned cover come back in full."""
    bundle = PhasesBundle()
    await bundle.launch_season()
    await bundle.draw(5)
    aquitaine = await bundle.kingdom_id("Aquitaine")
    bourgogne = await bundle.kingdom_id("Bourgogne")
    await bundle.stock(aquitaine, contre_espionnage=1)
    attack = await bundle.attacks.declare_attack(
        "king-a",
        (await bundle.owner_maps(bourgogne))[0],
        "aoe2de://lobby",
        cover_lord_id="lord-a",
        now=_DECLARE,
    )
    await bundle.attacks.respond_defense(attack.id, "lord-b", now=_DEFENSE)
    assert (await _lord(bundle, "lord-b")).defense_used == 1
    await bundle.attacks.cancel_attack(attack.id, "king-a", now=_CANCEL)
    # the cover returned to the STOCK (persisted)
    state = await bundle.attacks.technology_state(aquitaine)
    assert state.purchases["contre_espionnage"] == 1
    # the recorded defense is refunded
    assert (await _lord(bundle, "lord-b")).defense_used == 0
    assert (await _lord(bundle, "king-a")).attack_used == 0


# ---------------------------------------------------------------------------
# The cog surfaces (the late click and the defender DM)
# ---------------------------------------------------------------------------


async def test_a_late_defense_click_reads_the_withdrawal_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 🛡️ button never disappears: a late click says « annulée »."""
    import botforge.mods.kingdom.cogs.panel as panel

    attack = SimpleNamespace(
        id="a1",
        is_over=True,
        state=AttackState.CANCELLED,
        attacker_kingdom_id="k1",
        defender_kingdom_id="k2",
    )

    async def _attacks() -> list[Any]:
        return [attack]

    posted: list[str] = []

    async def _open(interaction: Any, content: str | None = None, **kwargs: Any) -> None:
        posted.append(str(content))

    monkeypatch.setattr(panel, "open_unique_ephemeral", _open)
    monkeypatch.setattr(
        panel, "wiring", lambda: SimpleNamespace(attacks=SimpleNamespace(attacks=_attacks))
    )

    class _Resp:
        async def defer(self, **kwargs: Any) -> None:
            return None

    interaction = SimpleNamespace(user=SimpleNamespace(id="u1"), locale="fr", response=_Resp())
    button = panel.DefendButton("a1", "🛡️ Défendre")
    await button.callback(interaction)
    assert len(posted) == 1
    assert "annulée" in posted[0]


async def test_the_cancel_button_dms_the_recorded_defender(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A withdrawal with a defense posed TELLS the defender (Drasah 25/11)."""
    import botforge.mods.kingdom.cogs.common as common
    import botforge.mods.kingdom.cogs.panel as panel

    attack = SimpleNamespace(
        id="a1",
        map_key="Pataugeoire",
        is_over=True,
        state=AttackState.CANCELLED,
        embuscade=False,
        cover_lord_id=None,
        defender_lord_id="lord-b",
        ai_defender=False,
        score={},
    )
    cancelled: dict[str, str] = {}

    async def _cancel(attack_id: str, player_id: str, **kwargs: Any) -> Any:
        cancelled["player"] = player_id
        return attack

    async def _flag(attack_id: str) -> None:
        return None

    async def _attacks() -> list[Any]:
        return [attack]

    stack = SimpleNamespace(
        attacks=SimpleNamespace(
            attacks=_attacks, cancel_attack=_cancel, mark_attack_salon_cleaned=_flag
        )
    )
    dms: list[str] = []

    class _Member:
        async def send(self, content: str, **kwargs: Any) -> None:
            dms.append(str(content))

    class _Guild:
        def get_member(self, member_id: str) -> Any:
            return _Member() if str(member_id) == "lord-b" else None

    monkeypatch.setattr(panel, "wiring", lambda: stack)
    monkeypatch.setattr(panel, "attack_salon", lambda guild, atk: None)

    async def _close(user_id: str) -> None:
        return None

    monkeypatch.setattr(common, "close_previous_ephemeral", _close)

    notes: list[str] = []

    class _Followup:
        async def send(self, content: str, **kwargs: Any) -> None:
            notes.append(str(content))

    class _Resp:
        async def defer(self, **kwargs: Any) -> None:
            return None

    interaction = SimpleNamespace(
        user=SimpleNamespace(id="king-a"),
        locale="fr",
        guild=None,
        response=_Resp(),
        followup=_Followup(),
        client=SimpleNamespace(guilds=[_Guild()]),
    )
    button = panel.CancelButton("a1", "❌ Annuler l'attaque")
    await button.callback(interaction)
    assert cancelled["player"] == "king-a"
    # the recorded defender received the withdrawal DM
    assert len(dms) == 1
    assert "Pataugeoire" in dms[0]
    assert "remboursé" in dms[0]
    # and the declarant keeps his confirmation note
    assert len(notes) == 1


async def test_the_cancel_dm_survives_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    """The DM helper is best-effort: no member, no crash, no DM."""
    import botforge.mods.kingdom.cogs.panel as panel

    dms: list[str] = []

    class _Member:
        async def send(self, content: str, **kwargs: Any) -> None:
            dms.append(content)

    class _Guild:
        def get_member(self, member_id: str) -> Any:
            return None

        async def fetch_member(self, member_id: str) -> Any:
            return _Member()

    bot = SimpleNamespace(guilds=[_Guild()])
    interaction = SimpleNamespace(client=bot)
    strings = {"cancel_attack_defender_dm": "info {map}"}
    attack = SimpleNamespace(map_key="Pataugeoire", defender_lord_id="lord-b", ai_defender=False)
    await panel._notify_defender_cancel_safe(interaction, strings, attack)
    assert dms == ["info Pataugeoire"]
    # a silent attack (AI defense) never notifies
    attack.ai_defender = True
    await panel._notify_defender_cancel_safe(interaction, strings, attack)
    assert len(dms) == 1
    # silent guild: the helper walks away quietly
    attack.ai_defender = False
    await panel._notify_defender_cancel_safe(
        SimpleNamespace(client=SimpleNamespace(guilds=[])), strings, attack
    )
    assert len(dms) == 1
