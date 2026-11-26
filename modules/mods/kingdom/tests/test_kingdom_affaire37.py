"""Affaire 37 / paroisse-v3 (Drasah 26/11) : la présentation de la
référence revient dans la fenêtre Paroisse.

L'ANCIENNE vue (celle que Drasah préfère) affichait des blocs titrés
« Notre {palier} » et « Les Fidèles du Royaume » — un seigneur par
ligne avec son état de mariage — plus les états Lieu Sacrée en direct.
Le T-D n'avait gardé que deux lignes brutes. Ici on rapatrie TOUT,
sans toucher aux boutons de la rangée 2 (💐 arrangé, ⛪ consacrer) ni
au toggle 🔎 En savoir plus.

Corrigé au passage : le wizard 💐 de l'Affaire 36 passait le catalogue
lieux à ``marry._princess_label`` (qui lit ``church_marry_princess``)
sans que ce catalogue porte la clé — un KeyError silencieux au choix
de la civilisation. La clé vit maintenant dans LIEUX_STRINGS (fr/en).
"""

from __future__ import annotations

import time as _time
from types import SimpleNamespace
from typing import Any

import pytest


def _strings() -> dict[str, str]:
    from botforge.mods.kingdom.cogs.lieux import lieux_strings

    return lieux_strings("fr")


def _config() -> Any:
    from botforge.mods.kingdom.config import default_season_config

    return default_season_config()


def _lord(
    lid: str,
    name: str,
    *,
    civ: str | None = None,
    royal: bool = False,
    until: int = 0,
    left: bool = False,
    kingdom_id: str = "k1",
) -> Any:
    return SimpleNamespace(
        id=lid, display_name=name, kingdom_id=kingdom_id, left=left,
        married_civilization=civ, marriage_locked_until=until,
        royal_marriage=royal,
    )


def _stack(lords: list[Any]) -> Any:
    class _Lords:
        async def __call__(self, *_args: Any, **_kwargs: Any) -> list[Any]:
            return lords

    return SimpleNamespace(
        config=SimpleNamespace(parish=None, civilizations=(SimpleNamespace(key="azteques", display_name="Aztèques"),)),
        kingdoms=SimpleNamespace(lords=_Lords()),
    )


def _territory(tid: str, map_key: str, *, sacred: bool = False, until: Any = None) -> Any:
    return SimpleNamespace(
        id=tid, map_key=map_key, owner_kingdom_id="k1", sacred=sacred,
        cathedral_until=until,
    )


def _kingdom() -> Any:
    return SimpleNamespace(
        id="k1", name="Aquitaine", parish_tier=1,
        marriage_points=2, arranged_marriage_stock=0, tech_points_bank=4,
        civilizations=(),
    )


def _body(lords: list[Any], state: dict[str, Any] | None = None) -> str:
    from botforge.mods.kingdom.cogs import lieux

    kingdom = _kingdom()
    stack = _stack(lords)
    return lieux._paroisse_body(
        _strings(), stack, kingdom, state or {}, "Chapelle", 1, [], 0, lords
    )


# ---------------------------------------------------------------------------
# Le corps enrichi — la présentation de la référence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_household_carries_the_reference_sections() -> None:
    """Stats, « Notre {palier} », « Les Fidèles du Royaume », une ligne par état."""
    now = int(_time.time())
    body = _body([
        _lord("l1", "blanks_007", civ="azteques", royal=True, until=now + 3600),
        _lord("l2", "Luc", civ="byzantins", until=now - 10),
        _lord("l3", "Anna"),
    ])
    assert "💍 Bague : 2" in body, "the stats line stays first"
    assert "## 🙏 Notre Chapelle" in body, "the household-palier heading"
    assert "Palier : Chapelle (1/3)" in body, "the palier line under its heading"
    assert "## 💒 Les Fidèles du Royaume" in body, "the household heading"
    assert "blanks_007" in body
    assert "👑 Reine " in body, "a royal wedding names the QUEEN (the ref badge)"
    assert "🔒 verrou jusqu'à <t:" in body, "an ACTIVE lock renders as an epoch"
    assert "✅ verrou levé" in body, "an expired lock renders lifted"
    assert "— célibataire · prêt à se marier 💍" in body, "the bachelor line"


@pytest.mark.asyncio
async def test_left_members_never_show_and_an_empty_house_says_so() -> None:
    body = _body([_lord("l1", "Parti", left=True, kingdom_id="k2")])
    assert "Parti" not in body
    assert "Aucun fidèle pour le moment." in body


@pytest.mark.asyncio
async def test_the_body_carries_the_live_lieu_sacree_states() -> None:
    """Un chantier ⏳ et un sacré ⛪ vivent dans la feuille (les états motors)."""
    from datetime import UTC, datetime, timedelta

    verdict = datetime(2026, 11, 26, 12, 0, tzinfo=UTC) + timedelta(hours=70)
    state = {"territories": [
        _territory("t1", "arabia", until=verdict),
        _territory("t2", "steppe", sacred=True),
        # expiré il y a longtemps — le verdict 5 min l'a résolu, pas la feuille
        _territory("t3", "americas", until=datetime(2026, 11, 1, tzinfo=UTC)),
    ]}
    body = _body([], state)
    assert "Lieu Sacrée en chantier sur **arabia**" in body
    assert "verdict <t:" in body, "the verdict renders as an epoch"
    assert "Lieu Sacrée SACRÉ sur **steppe**" in body
    assert "americas" not in body, "an expired chantier left the sheet (the verdict owns it)"


@pytest.mark.asyncio
async def test_the_window_still_builds_on_a_dead_stack_with_row_two() -> None:
    """Le stack sans `kingdoms` (mort, CI) dégrade en silence — rangée 2 intacte."""
    from botforge.mods.kingdom.cogs import lieux

    stack = SimpleNamespace(config=_config())
    original = lieux.wiring
    lieux.wiring = lambda: stack  # type: ignore[assignment]
    try:
        view, _files = await lieux._paroisse_window(_strings(), _kingdom(), {})
        wires: list[str] = []
        for child in view.children:
            for row in getattr(child, "children", []) or []:
                for button in getattr(row, "children", []) or []:
                    if str(getattr(button, "custom_id", "") or ""):
                        wires.append(str(button.custom_id))
        assert "kingdoms:lieux:paroisse:arrange" in wires
        assert "kingdoms:lieux:paroisse:consecrate" in wires
        assert "kingdoms:lieux:paroisse:info" in wires
    finally:
        lieux.wiring = original  # type: ignore[assignment]


def test_the_princess_key_now_lives_in_the_lieux_catalog() -> None:
    """Le filtre du wizard 💐 (Affaire 36) lisait une clé absente — corrigé."""
    from botforge.mods.kingdom.cogs.lieux import lieux_strings

    assert lieux_strings("fr")["church_marry_princess"] == "Princesse {0}"
    assert lieux_strings("en")["church_marry_princess"] == "Princess {0}"
