"""remparts-managers-v1 (Affaire 35 / T-C, Drasah 26/11) — les salles de guerre.

Le portage de la rangée 1 des Remparts de la référence : 🛡️ Gestion de
la défense (l'effet de surprise — QUI défend ne se voit que dans le
royaume, plus le retrait de SA défense), ⚔️ Gestion d'attaque (declared
+ planned — l'état de la défense JAMAIS, synfoni-v1), 🔎 En savoir
plus, et 🏆 Classement au Conseil. Tout consomme les seams existants.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _kingdoms_service() -> Any:
    class _Kingdoms:
        async def kingdoms(self) -> list[Any]:
            return [
                SimpleNamespace(id="k1", name="Aquitaine", civilizations=[]),
                SimpleNamespace(id="k2", name="Bourgogne", civilizations=[]),
            ]

        async def lords(self) -> list[Any]:
            return [
                SimpleNamespace(id="10", display_name="Anna", kingdom_id="k1"),
                SimpleNamespace(id="20", display_name="Bernard", kingdom_id="k2"),
            ]

    return _Kingdoms()


def _strings() -> dict[str, str]:
    from botforge.mods.kingdom.cogs.lieux import lieux_strings

    return lieux_strings("fr")


def _async_list(items: list[Any]) -> Any:
    class _List:
        async def __call__(self) -> list[Any]:
            return items

    return _List()


@pytest.mark.asyncio
async def test_the_defense_manager_names_the_defender_and_offers_the_withdraw() -> None:
    """La fiche privée : qui défend, quand — et ↩️ sur SA défense seule."""
    from botforge.mods.kingdom.cogs import lieux
    from botforge.mods.kingdom.models import AttackState

    now = datetime(2026, 11, 26, 18, 0, tzinfo=UTC)
    mine = SimpleNamespace(  # défendue PAR le lord → bouton retrait attendu
        id="a1", map_key="Prairie", is_over=False, revealed=False,
        defender_kingdom_id="k1", defender_lord_id="10", ai_defender=False,
        state=AttackState.DEFENDED, expires_at=now,
    )
    other = SimpleNamespace(  # défendue par un AUTRE seigneur → pas de bouton
        id="a2", map_key="Steppe", is_over=False, revealed=False,
        defender_kingdom_id="k1", defender_lord_id="20", ai_defender=False,
        state=AttackState.DEFENDED, expires_at=now,
    )
    waiting = SimpleNamespace(  # pas encore défendue
        id="a3", map_key="Toundra", is_over=False, revealed=False,
        defender_kingdom_id="k1", defender_lord_id=None, ai_defender=False,
        state=AttackState.DECLARED, expires_at=now,
    )
    unreadable = SimpleNamespace(id="a9", is_over=True)  # déjà finie → hors fiche

    stack = SimpleNamespace(
        kingdoms=_kingdoms_service(),
        attacks=SimpleNamespace(attacks=_async_list([mine, other, waiting, unreadable])),
    )
    lord = SimpleNamespace(id="10", kingdom_id="k1")

    text, cancels = await lieux.defense_manager_payload(stack, lord, _strings())

    assert "défendue par **Anna** ✓" in text, "the sheet names MY defense"
    assert "en attente de défenseur ⏳" in text, "an undefended attack waits"
    assert "Prairie" in text and "Steppe" in text and "Toundra" in text
    assert [button.custom_id for button in cancels] == [
        f"kingdoms:lieux:remparts:cancel-defense:{lieux.room_key('a1')}"
    ], "ONE withdraw button — the lord's OWN defense only"


@pytest.mark.asyncio
async def test_the_attack_manager_never_leaks_the_defense_state() -> None:
    """synfoni-v1 : declared = auteur + royaume cible, JAMAIS la défense."""
    from botforge.mods.kingdom.cogs import lieux
    from botforge.mods.kingdom.models import PlanState

    when = datetime(2026, 11, 26, 18, 0, tzinfo=UTC)
    attack = SimpleNamespace(
        id="a1", map_key="Prairie", is_over=False,
        attacker_kingdom_id="k1", attacker_lord_id="10",
        defender_kingdom_id="k2", defender_lord_id="20",
        state=None, expires_at=when,
    )
    plan = SimpleNamespace(
        id="p1", lord_id="10", kingdom_id="k1",
        choices=["Prairie", "Steppe"], active_index=1, meeting_at=when,
        state=PlanState.PLANNED,
    )
    stack = SimpleNamespace(
        kingdoms=_kingdoms_service(),
        attacks=SimpleNamespace(
            attacks=_async_list([attack]), plans=_async_list([plan])
        ),
    )
    lord = SimpleNamespace(id="10", kingdom_id="k1")

    text = await lieux.attack_manager_payload(stack, lord, _strings())

    assert "déclarée par **Anna**" in text, "the declared row names the author"
    assert "royaume **Bourgogne**" in text, "the declared row names the TARGET"
    assert "défend" not in text, "the defense state NEVER leaks (synfoni-v1)"
    assert "Choix 1 : **Prairie**" in text, "the plan shows its first choice bare"
    assert "Choix 2 : **Steppe** ✅" in text, "the ✅ rides the ACTIVE choice"
    assert "choix 2/2" in text, "the recap row carries index/total"


def test_the_classement_wears_the_medals_and_the_podium_break() -> None:
    """🥇🥈🥉, une ligne vide avant le 4ᵉ, l'astuce du Conseil en pied."""
    from botforge.mods.kingdom.cogs import lieux

    rows = [(SimpleNamespace(name=f"K{index}"), index, index) for index in range(1, 6)]
    text = lieux.classement_content(_strings(), rows)

    assert text.splitlines()[0].endswith("Classement de la saison")
    assert "🥇 1. **K1**" in text and "🥈 2. **K2**" in text and "🥉 3. **K3**" in text
    assert "\n\n🏰 4. **K4**" in text, "a blank line between the podium and the rest"
    assert "🏰 5. **K5**" in text
    assert text.rstrip().endswith(_strings()["conseil_classement_hint"])


def test_the_tc_wires_live_in_the_source_and_both_locales() -> None:
    """Contrat : les crochets click des nouvelles surfaces sont branchés."""
    from botforge.mods.kingdom.cogs.lieux import lieux_dynamic_items, lieux_strings

    registered = {item.__name__ for item in lieux_dynamic_items()}
    for name in (
        "LieuxRempartsManagerButton",
        "LieuxRempartsInfoButton",
        "LieuxRempartsStateButton",
        "LieuxRempartsBackButton",
        "LieuxCancelDefenseButton",
        "LieuxClassementButton",
    ):
        assert name in registered, f"{name} must be restart-proof"

    source = Path(lieux_dynamic_items.__code__.co_filename).read_text(encoding="utf-8")
    assert 'await _open_lieu(interaction, "remparts")' in source, (
        "the back button walks through the ONE remparts opener — never ad hoc"
    )
    for locale in ("fr", "en"):
        strings = lieux_strings(locale)
        assert strings["classement_button"]
        assert strings["defense_manager_button"]
        assert strings["plan_manager_button"]
        assert strings["remparts_info_button"]
        assert strings["cancel_defense_button"]


def test_the_row_one_of_the_remparts_carries_the_managers() -> None:
    """Contrat : la rangée 1 porte managers + En savoir plus + Sortir."""
    from botforge.mods.kingdom.cogs.lieux import _remparts_window

    state: dict[str, Any] = {"purchases": {}, "territories": []}
    kingdom = SimpleNamespace(name="Aquitaine")
    view, _files = _remparts_window(_strings(), kingdom, state)
    wires: list[str] = []
    for child in view.children:
        for row in getattr(child, "children", []) or []:
            for button in getattr(row, "children", []) or []:
                custom_id = str(getattr(button, "custom_id", "") or "")
                if custom_id:
                    wires.append(custom_id)
    assert "kingdoms:lieux:remparts:defense-manager" in wires
    assert "kingdoms:lieux:remparts:attack-manager" in wires
    assert "kingdoms:lieux:remparts:info" in wires
    assert "kingdoms:lieux:sortir" in wires
    assert "kingdoms:lieux:remparts:use:jeu_d_armes" in wires, "row 2 keeps its cards"


@pytest.mark.asyncio
async def test_the_defense_manager_degrades_when_the_service_is_dead() -> None:
    """Une attaque service morte (raise) → fiche vide, jamais de raise."""
    from botforge.mods.kingdom.cogs import lieux

    class _Dead:
        async def attacks(self) -> list[Any]:
            raise RuntimeError("boom")

    stack = SimpleNamespace(
        kingdoms=_kingdoms_service(), attacks=SimpleNamespace(attacks=_Dead())
    )
    lord = SimpleNamespace(id="10", kingdom_id="k1")
    text, cancels = await lieux.defense_manager_payload(stack, lord, _strings())
    assert "Aucune attaque en cours" in text
    assert cancels == []
