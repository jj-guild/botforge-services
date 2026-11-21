"""vague2-actions-v1 — les tests (Drasah 21/11).

La vague 2 des actions de lieux :
- rangée 2 des Remparts : ⚔️ Jeu d'armes · 🚨 Patrouille · 💂 Garde
  (VERT si en réserve, GRIS + disabled sinon, jamais caché) ;
- rangée 2 du Conseil : 🧭 Exploration · 🪤 Traquenard, Traquenard
  consommé par la fenêtre éphémère de choix de cible ;
- rangée 1 de la Paroisse : 💍 Se marier (la DynamicItem de marry.py)
  + ⛪ Améliorer (le seam moteur upgrade_parish derrière une carte de
  confirmation) ;
- Chambre des comptes : les fenêtres 📜 Historique achats / ⚔️
  Historique actions du registre (50 dernières entrées, dates Paris) ;
- le sous-système technologies du moteur (techno-port-v1) : la
  Traquenard activée consomme la charge, la fenêtre 2h Facile est
  CUMULATIVE, les verrous vivants gagnent +2h en one-shot, et les
  refus penaux (soi-même, Gaïa, faucon immunité) restent des notes.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from botforge.mods.kingdom.models import TechnologyState


# ---------------------------------------------------------------------------
# The cog faces — the rows' stock rules + the windows' wiring
# ---------------------------------------------------------------------------


def _lieux() -> Any:
    import botforge.mods.kingdom.cogs.lieux as lieux_module

    return lieux_module


def _strings() -> dict[str, str]:
    return _lieux().lieux_strings("fr")


def _ids(view: Any) -> list[str]:
    return [
        str(item.custom_id)
        for item in view.walk_children()  # type: ignore[attr-defined]
        if getattr(item, "custom_id", None)
    ]


def test_remparts_row_two_follows_the_stock_rules() -> None:
    lieux = _lieux()
    strings = _strings()
    held = {"purchases": {"jeu_d_armes_stock": 2, "patrouille_slot_1": 18, "garde_royale_stock": 1}}
    row = lieux._remparts_use_row(strings, held)
    assert [item.custom_id for item in row] == [
        "kingdoms:lieux:remparts:use:jeu_d_armes",
        "kingdoms:lieux:remparts:use:patrouille",
        "kingdoms:lieux:remparts:use:garde_royale",
    ], "the wire ids must match the registered DynamicItem template"
    assert all(item.style.value == 3 for item in row), "held cards render GREEN (success)"
    assert not any(item.disabled for item in row)

    empty = lieux._remparts_use_row(strings, {"purchases": {}})
    assert all(item.disabled for item in empty), "grey + disabled when nothing is held"
    assert all(item.style.value == 2 for item in empty), "secondary style when not held"
    # The patrouille counts an unlocked-but-unplaced slot as held.
    unlocked = lieux._remparts_use_row(strings, {"purchases": {"patrouille_unlock_2": 1}})
    assert unlocked[1].disabled is False, "an unlocked patrouille slot IS usable"


def test_conseil_row_two_follows_the_card_rules() -> None:
    lieux = _lieux()
    strings = _strings()
    row = lieux._conseil_cards_row(strings, {"purchases": {"explorateur_stock": 1, "traquenard": 1}}, None)
    assert [item.custom_id for item in row] == ["kingdoms:lieux:exploration", "kingdoms:lieux:traquenard"]
    assert not any(item.disabled for item in row)
    empty = lieux._conseil_cards_row(strings, {"purchases": {}}, None)
    assert all(item.disabled for item in empty), "no stock = grey + disabled, never hidden"


@pytest.mark.asyncio
async def test_the_paroisse_window_carries_marry_and_upgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    lieux = _lieux()
    strings = _strings()

    class _Tier:
        key = "eglise"
        display_name = "Église"
        offering = 4
        cost = 2

    stack = SimpleNamespace(
        config=SimpleNamespace(parish=SimpleNamespace(tiers=(_Tier(), _Tier()))),
        attacks=None,
    )
    monkeypatch.setattr(lieux, "wiring", lambda: stack)
    kingdom = SimpleNamespace(
        name="AEGIS",
        parish_tier=1,
        marriage_points=1,
        arranged_marriage_stock=0,
    )
    view, files = await lieux._paroisse_window(strings, kingdom, {"wallet": 5})
    ids = _ids(view)
    assert "kingdom:attack:marry" in ids, "the 💍 button is marry.py's own DynamicItem (harmonisation)"
    assert "kingdoms:lieux:paroisse:upgrade" in ids
    assert "kingdoms:lieux:sortir" in ids


@pytest.mark.asyncio
async def test_the_comptes_window_carries_the_two_hist_buttons(monkeypatch: pytest.MonkeyPatch) -> None:
    lieux = _lieux()
    strings = _strings()

    async def fake_chamber_text(stack: Any, kingdom: Any, catalog: dict) -> str:
        return "## Chambre"

    import botforge.mods.kingdom.cogs.market as market_module

    monkeypatch.setattr(market_module, "chamber_text", fake_chamber_text)
    kingdom = SimpleNamespace(id="k-1", name="AEGIS", tech_points_bank=7)
    view, files = await lieux._comptes_window(strings, kingdom, {})
    ids = _ids(view)
    assert "kingdoms:lieux:hist:achats" in ids and "kingdoms:lieux:hist:actions" in ids
    assert "kingdoms:lieux:sortir" in ids


@pytest.mark.asyncio
async def test_the_hist_window_reads_the_ledgers(monkeypatch: pytest.MonkeyPatch) -> None:
    lieux = _lieux()
    opened: list[Any] = []

    async def fake_open(interaction: Any, *args: Any, **kwargs: Any) -> None:
        opened.append(kwargs.get("view"))

    async def fake_resolve(interaction: Any, strings: dict[str, str]) -> tuple[Any, Any, Any]:
        kingdom = SimpleNamespace(
            market_registry=[
                {"item": "traquenard", "detail": "achat", "cost": 3, "at": 1764000000},
                {"item": "explorateur", "detail": "jeton", "cost": 3, "at": 1764000600},
            ],
            market_actions=[
                {"item": "traquenard", "detail": "royaume k-2", "at": 1764001200},
            ],
        )
        return (SimpleNamespace(id="1", role="lord"), kingdom, SimpleNamespace())

    monkeypatch.setattr(lieux, "_lord_kingdom_of", fake_resolve)
    monkeypatch.setattr(lieux, "open_unique_ephemeral", fake_open)

    class _Resp:
        done = False

        async def defer(self, **kw: Any) -> None:
            self.done = True

    interaction = SimpleNamespace(user=SimpleNamespace(id="1"), locale="fr", response=_Resp())
    button = lieux.LieuxHistButton("achats", _strings())
    await button.callback(interaction)
    view = opened[-1]
    body = "\n".join(str(c.content) for c in view.walk_children() if hasattr(c, "content"))
    assert "🪤" in body and "3" in body, "the purchase line carries emoji + cost"
    assert "📜" in body, "the achats title rides the window"

    opened.clear()
    button = lieux.LieuxHistButton("actions", _strings())
    await button.callback(interaction)
    view = opened[-1]
    body = "\n".join(str(c.content) for c in view.walk_children() if hasattr(c, "content"))
    assert "k-2" in body, "the action line carries the detail"
    assert "⚔️" in body, "the actions title rides the window"


@pytest.mark.asyncio
async def test_the_traquenard_select_consumes_the_charge_and_notes(monkeypatch: pytest.MonkeyPatch) -> None:
    lieux = _lieux()
    opened: list[Any] = []

    async def fake_open(interaction: Any, *args: Any, **kwargs: Any) -> None:
        opened.append(kwargs.get("content"))

    async def fake_resolve(interaction: Any, strings: dict[str, str]) -> tuple[Any, Any, Any]:
        return (
            SimpleNamespace(id="1", role="lord", kingdom_id="k-1"),
            SimpleNamespace(id="k-1", name="AEGIS", traquenard_uses={}),
            None,
        )

    activated: list[tuple[str, str]] = []

    async def fake_activate(player_id: str, target_id: str) -> Any:
        activated.append((player_id, target_id))
        return SimpleNamespace(until=1764004800, affected=[("l2", ["marriage"])])

    async def fake_kingdoms() -> list[Any]:
        return [SimpleNamespace(id="k-2", name="Bourgogne", is_gaia=False)]

    stack = SimpleNamespace(
        attacks=SimpleNamespace(activate_traquenard=fake_activate),
        kingdoms=SimpleNamespace(kingdoms=fake_kingdoms),
    )

    async def fake_resolve_full(interaction: Any, strings: dict[str, str]):
        lord, kingdom, _ = await fake_resolve(interaction, strings)
        return (lord, kingdom, stack)

    monkeypatch.setattr(lieux, "_lord_kingdom_of", fake_resolve_full)
    monkeypatch.setattr(lieux, "open_unique_ephemeral", fake_open)

    select = lieux.LieuxTraquenardSelect([__import__("discord").SelectOption(label="Bourgogne", value="k-2")])
    select.item._values = ["k-2"]

    class _Resp:
        done = False

        async def defer(self, **kw: Any) -> None:
            self.done = True

    interaction = SimpleNamespace(user=SimpleNamespace(id="1"), locale="fr", response=_Resp())
    await select.callback(interaction)
    assert activated == [("1", "k-2")], "the select fires the engine seam with the player id"
    assert "Bourgogne" in str(opened[-1]) and "Traquenard" in str(opened[-1])


@pytest.mark.asyncio
async def test_the_traquenard_select_refusals_are_notes(monkeypatch: pytest.MonkeyPatch) -> None:
    lieux = _lieux()
    opened: list[Any] = []

    async def fake_open(interaction: Any, *args: Any, **kwargs: Any) -> None:
        opened.append(kwargs.get("content"))

    async def fake_resolve(interaction: Any, strings: dict[str, str]) -> tuple[Any, Any, Any]:
        opened.append("refused_note")
        return (None, None, None)

    monkeypatch.setattr(lieux, "_lord_kingdom_of", fake_resolve)
    monkeypatch.setattr(lieux, "open_unique_ephemeral", fake_open)
    select = lieux.LieuxTraquenardSelect([__import__("discord").SelectOption(label="X", value="k-9")])
    select.item._values = ["k-9"]

    class _Resp:
        done = False

        async def defer(self, **kw: Any) -> None:
            self.done = True

    interaction = SimpleNamespace(user=SimpleNamespace(id="1"), locale="fr", response=_Resp())
    await select.callback(interaction)
    assert "refused_note" in opened, "an unresolvable clicker ends on the resolver's note, never a crash"


# ---------------------------------------------------------------------------
# The engine — techno-port-v1: the Traquenard itself (in-memory store)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_traquenard_consumes_and_extends_and_refuses() -> None:
    from test_kingdom_attacks import Bundle

    bundle = Bundle()
    await bundle.launch_season()
    await bundle.draw(12)
    aquitaine = await bundle.kingdom_id("Aquitaine")
    bourgogne = await bundle.kingdom_id("Bourgogne")
    monday = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)

    # No stock → the pre-activation complaint (TechnologyLimitReached).
    with pytest.raises(Exception):
        await bundle.attacks.activate_traquenard("king-a", bourgogne, now=monday)

    funded = TechnologyState(_id=aquitaine, season_id="s", tech_points=10)
    await bundle.store.upsert_technology(funded.to_mongo())
    await bundle.attacks.buy_technology(aquitaine, "traquenard")
    bought = (await bundle.attacks.technology_state(aquitaine)).purchases["traquenard"]
    assert bought == 1

    # One living marriage lock on the target's lord.
    lord_b = next(item for item in await bundle.kingdoms.lords() if item.id == "lord-b")
    lord_b.marriage_locked_until = int((monday + timedelta(hours=3)).timestamp())
    await bundle.store.upsert_lord(lord_b.to_mongo())

    result = await bundle.attacks.activate_traquenard("king-a", bourgogne, now=monday)
    assert result.target.id == bourgogne
    assert result.until == int((monday + timedelta(hours=2)).timestamp())
    assert result.affected == [("lord-b", ["marriage"])]
    # The charge was consumed.
    left = (await bundle.attacks.technology_state(aquitaine)).purchases["traquenard"]
    assert left == 0
    # The living lock gained exactly +2h, one-shot marked.
    locked = next(item for item in await bundle.kingdoms.lords() if item.id == "lord-b")
    assert locked.marriage_locked_until == int((monday + timedelta(hours=5)).timestamp())
    assert locked.traquenard_lock_marks == {"marriage": int((monday + timedelta(hours=5)).timestamp())}
    # The activator records the live window.
    activator = next(item for item in await bundle.kingdoms.kingdoms() if item.id == aquitaine)
    assert activator.traquenard_uses == {bourgogne: result.until}

    # The window is CUMULATIVE: a second buy + activation pushes 2h further.
    await bundle.attacks.buy_technology(aquitaine, "traquenard")
    second = await bundle.attacks.activate_traquenard("king-a", bourgogne, now=monday + timedelta(hours=1))
    assert second.until == int((monday + timedelta(hours=4)).timestamp())

    # Penal refusals: self-target and Gaïa raise, stock untouched otherwise.
    with pytest.raises(Exception):
        await bundle.attacks.activate_traquenard("king-a", aquitaine, now=monday)
    gaia = next(k.id for k in await bundle.kingdoms.kingdoms() if k.is_gaia)
    with pytest.raises(Exception):
        await bundle.attacks.activate_traquenard("king-a", gaia, now=monday)


@pytest.mark.asyncio
async def test_the_faucon_grants_the_traquenard_immunity() -> None:
    from test_kingdom_attacks import Bundle

    bundle = Bundle()
    await bundle.launch_season()
    await bundle.draw(12)
    aquitaine = await bundle.kingdom_id("Aquitaine")
    bourgogne = await bundle.kingdom_id("Bourgogne")
    monday = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)

    funded = TechnologyState(_id=aquitaine, season_id="s", tech_points=10)
    await bundle.store.upsert_technology(funded.to_mongo())
    await bundle.attacks.buy_technology(aquitaine, "traquenard")

    target = next(k for k in await bundle.kingdoms.kingdoms() if k.id == bourgogne)
    target.faucon_release_until = int((monday + timedelta(hours=1)).timestamp())
    await bundle.store.upsert_kingdom(target.to_mongo())

    with pytest.raises(Exception):
        await bundle.attacks.activate_traquenard("king-a", bourgogne, now=monday)
    # The charge was NOT consumed by the refused activation.
    left = (await bundle.attacks.technology_state(aquitaine)).purchases["traquenard"]
    assert left == 1
