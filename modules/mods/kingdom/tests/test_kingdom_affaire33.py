"""sabotage-source-v1 (Affaire 34, Drasah 26/11) — la source des frappes.

La demande live : sur la fiche 📜 draft, à droite de chaque civ barrée,
INDIQUER comment elle a été sabotée — la carte 🗡️ Sabotage ou le 🦅
Faucon — un marqueur simple, rien de plus. Les frappes antérieures
(sans source enregistrée) restent barrées nues. Le moteur enregistre
la source comme DONNÉE (pickban[{side}_sabotage_sources]) : le jour où
le seam volière faucon_sabotage atterrit, il écrit "faucon" et la
fiche l'affiche sans retoucher ce rail.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest


@pytest.mark.asyncio
async def test_a_sabotage_techno_strike_records_its_source(monkeypatch: Any) -> None:
    """La carte enregistre « techno » — la donnée que la fiche lira."""
    from botforge.mods.kingdom import attacks as attacks_module
    from test_kingdom_attack_phases import PhasesBundle

    # la frappe vit DANS la fenêtre de grâce après le défaut (T + 5 min)
    monkeypatch.setattr(
        attacks_module, "_now", lambda: datetime(2026, 10, 11, 18, 5, tzinfo=UTC)
    )

    bundle = PhasesBundle()
    await bundle.launch_season()
    await bundle.draw(12)
    attack = await bundle.fresh_attack()
    await bundle.give_civs("Aquitaine", "francs", "bretons", "goths", "huns")
    await bundle.give_civs("Bourgogne", "perses", "byzantins", "celtes", "maya")
    await bundle.attacks.respond_defense(
        attack.id, "lord-b", now=datetime(2026, 10, 11, 12, 30, tzinfo=UTC)
    )
    await bundle.attacks.reveal_due(now=datetime(2026, 10, 11, 17, 45, tzinfo=UTC))
    _ = await bundle.attacks.pick_ban_due(now=datetime(2026, 10, 11, 17, 46, tzinfo=UTC))
    _ = await bundle.attacks.expire_stale(now=attack.expires_at)
    fresh = next(a for a in await bundle.attacks.attacks() if a.id == attack.id)
    target = str(fresh.pickban["defender_picks"][0])
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.stock(aquitaine, sabotage=1)
    struck = await bundle.attacks.sabotage_techno(attack.id, "king-a", target)
    assert (struck.pickban or {}).get("attacker_sabotages") == [target]
    assert (struck.pickban or {}).get("attacker_sabotage_sources") == {target: "techno"}, (
        "the techno strike must record its kind as DATA"
    )


@pytest.mark.asyncio
async def test_the_draft_sheet_wears_the_source_marker(monkeypatch: Any) -> None:
    """La fiche : barre + marqueur 🗡️/🦅 quand la source est connue, barre nue sinon."""
    from botforge.mods.kingdom.cogs import battle
    from botforge.mods.kingdom.cogs.common import strings_by_locale

    attack = SimpleNamespace(
        id="a1",
        map_key="Aquitaine",
        ai_defender=False,
        attacker_lord_id="10",
        defender_lord_id="20",
        pickban={
            "sabotage_resolved": True,
            "attacker_picks": ["francs", "bretons", "goths"],
            "defender_picks": ["perses", "byzantins", "celtes"],
            # l'attaquant frappe 2 civs : une par carte, une par faucon
            "attacker_sabotages": ["perses", "byzantins"],
            "attacker_sabotage_sources": {"perses": "techno", "byzantins": "faucon"},
            # le défenseur frappe une civ ANTÉRIEURE : source inconnue
            "defender_sabotages": ["francs"],
        },
    )
    embed = await battle.draft_sheet_embed(
        SimpleNamespace(kingdoms=None), attack, strings_by_locale("fr")
    )
    by_name = {field.name: field.value for field in embed.fields}
    attacker_side = by_name["⚔️ —"]
    defender_side = by_name["🛡️ —"]
    assert "~~perses~~ ❌ · 🗡️ Sabotage" in defender_side, "the techno marker rides the struck civ"
    assert "~~byzantins~~ ❌ · 🦅 Faucon" in defender_side, "the faucon marker rides the struck civ"
    assert "~~francs~~ ❌" in attacker_side and "~~francs~~ ❌ ·" not in attacker_side, (
        "a legacy strike without a recorded kind stays BARE"
    )
    assert "bretons" in attacker_side and "bretons ·" not in attacker_side, (
        "an unstruck pick never wears a marker"
    )


def test_the_source_labels_live_in_both_locales() -> None:
    """Contrat : les deux libellés existent en FR et en EN (données, pas du codé en dur)."""
    from botforge.mods.kingdom.cogs.common import strings_by_locale

    fr = strings_by_locale("fr")
    en = strings_by_locale("en")
    assert fr["draft_source_techno"] == "🗡️ Sabotage"
    assert fr["draft_source_faucon"] == "🦅 Faucon"
    assert en["draft_source_techno"] == "🗡️ Sabotage"
    assert en["draft_source_faucon"] == "🦅 Falcon"
