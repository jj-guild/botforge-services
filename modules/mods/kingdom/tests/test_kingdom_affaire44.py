"""Affaire 44 (Drasah 26/11) : vitrine-v1 — le 🏛️ Panthéon.

Le salon solo et permanent qui vit hors de la partie : le panel
épinglé du score (territoires + alliances, ordre médailles, ligne
Gaïa), puis trois navigations — Palmarès (vainqueur + comment il a
gagné), Historique (le verdict d'une saison archivée), Chronique
(la timeline d'un royaume + la comparaison croisée de deux).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _pantheon() -> Any:
    import botforge.mods.kingdom.cogs.pantheon as pantheon_module

    return pantheon_module


def _strings(locale: str = "fr") -> dict[str, str]:
    from botforge.mods.kingdom.cogs.strings import strings

    return strings(locale)


def _texts(view: Any) -> str:
    return "\n".join(
        str(c.content) for c in view.walk_children() if hasattr(c, "content")
    )


def _lord(
    lord_id: str,
    kingdom_id: str,
    married_civ: str | None = None,
    left: bool = False,
    chronicle: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=lord_id,
        display_name=lord_id,
        kingdom_id=kingdom_id,
        married_civilization=married_civ,
        left=left,
        chronicle=chronicle or [],
    )


def _entry(at: int, kind: str, params: dict[str, str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(at=at, kind=kind, params=params or {})


def _stack(
    kingdoms: list[SimpleNamespace],
    lords: list[SimpleNamespace],
    counts: dict[str, int] | None = None,
    season: Any = None,
    archives: list[dict[str, Any]] | None = None,
) -> SimpleNamespace:
    class _Kingdoms:
        async def kingdoms(self) -> list[SimpleNamespace]:
            return kingdoms

        async def lords(self) -> list[SimpleNamespace]:
            return lords

        async def current_season(self) -> Any:
            return season

        async def season_archives(self) -> list[dict[str, Any]]:
            return archives or []

    class _Territories:
        async def territory_count_by_kingdom(self) -> dict[str, int]:
            return counts or {}

    return SimpleNamespace(kingdoms=_Kingdoms(), territories=_Territories())


def _wire(monkeypatch: pytest.MonkeyPatch, stack: SimpleNamespace) -> None:
    monkeypatch.setattr(_pantheon(), "wiring", lambda: stack)


# ---------------------------------------------------------------------------
# The pinned panel — the at-a-glance score
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_panel_scores_kingdoms_in_medals_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    stack = _stack(
        kingdoms=[
            SimpleNamespace(id="k-1", name="AEGIS", is_gaia=False),
            SimpleNamespace(id="k-2", name="BASTION", is_gaia=False),
            SimpleNamespace(id="gaia", name="Gaïa", is_gaia=True),
        ],
        lords=[
            _lord("l-1", "k-1", married_civ="french"),
            _lord("l-2", "k-1", married_civ="french"),
            _lord("l-3", "k-2", married_civ="english"),
        ],
        counts={"k-1": 5, "k-2": 7, "gaia": 2},
    )
    rows = await pantheon._score_rows(stack)
    assert [row[0] for row in rows] == ["BASTION", "AEGIS", "Gaïa"], (
        "rows are sorted by territories, medals order"
    )
    text = pantheon._score_text(_strings(), rows)
    assert "🥇 **BASTION** — 7 territoire(s) · 1 alliance(s)" in text
    assert "🥈 **AEGIS** — 5 territoire(s) · 1 alliance(s)" in text, (
        "a married civ counts ONCE per kingdom even with two lords"
    )
    assert "▫️ Gaïa — 2 territoire(s)" in text, "Gaïa has its own grey line"


@pytest.mark.asyncio
async def test_the_panel_says_it_when_no_season_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    text = pantheon._score_text(_strings(), [])
    assert "Aucune saison en cours" in text


# ---------------------------------------------------------------------------
# 🏆 Palmarès — one line per past season
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_palmares_names_the_winner_and_how_he_won(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    archive = {
        "season_id": "s-2026-1",
        "kingdoms": [{"_id": "k-1", "name": "AEGIS"}],
        "seasons": [{"winner_kingdom_id": "k-1"}],
        "showmatches": [],
    }
    stack = _stack(kingdoms=[], lords=[], archives=[archive])
    _wire(monkeypatch, stack)
    lines = await pantheon._palmares_lines(_strings())
    assert any(
        "**s-2026-1**" in line and "AEGIS" in line and "comptes" in line for line in lines
    ), "a clear win reads 'verdict aux comptes'"


@pytest.mark.asyncio
async def test_the_palmares_cites_the_showmatch_when_it_decided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    archive = {
        "season_id": "s-2026-2",
        "kingdoms": [{"_id": "k-2", "name": "BASTION"}],
        "seasons": [{"winner_kingdom_id": "k-2"}],
        "showmatches": [{"finished": True, "score_a": 2, "score_b": 1}],
    }
    stack = _stack(kingdoms=[], lords=[], archives=[archive])
    _wire(monkeypatch, stack)
    lines = await pantheon._palmares_lines(_strings())
    assert any("ShowMatch (2-1)" in line for line in lines), (
        "an archived tie settled by a ShowMatch cites its score"
    )


@pytest.mark.asyncio
async def test_the_palmares_shows_the_live_season_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    stack = _stack(
        kingdoms=[],
        lords=[],
        season=SimpleNamespace(id="s-live", name="Saison 1", phase="_paix"),
        archives=[{"season_id": "s-old", "kingdoms": [], "seasons": [], "showmatches": []}],
    )
    _wire(monkeypatch, stack)
    lines = await pantheon._palmares_lines(_strings())
    assert lines[0].startswith("• **Saison 1**"), "the live season comes first"


# ---------------------------------------------------------------------------
# 📜 Historique — one archived season's verdict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_verdict_reads_the_archived_podium(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    archive = {
        "season_id": "s-2026-1",
        "kingdoms": [{"_id": "k-1", "name": "AEGIS"}, {"_id": "k-2", "name": "BASTION"}],
        "seasons": [{"winner_kingdom_id": "k-1"}],
        "showmatches": [],
        "territories": [
            {"owner_kingdom_id": "k-1"},
            {"owner_kingdom_id": "k-1"},
            {"owner_kingdom_id": "k-1"},
            {"owner_kingdom_id": "k-2"},
        ],
    }
    stack = _stack(kingdoms=[], lords=[], archives=[archive])
    _wire(monkeypatch, stack)
    view = await pantheon._verdict_view(_strings(), "s-2026-1")
    body = _texts(view)
    assert "🥇 Vainqueur : **AEGIS**" in body
    assert "🥇 **AEGIS** — 3 territoire(s)" in body
    assert "🥈 **BASTION** — 1 territoire(s)" in body


@pytest.mark.asyncio
async def test_the_verdict_survives_an_unknown_season(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    stack = _stack(kingdoms=[], lords=[], archives=[])
    _wire(monkeypatch, stack)
    view = await pantheon._verdict_view(_strings(), "s-ghost")
    assert "Aucune saison archivée" in _texts(view)


# ---------------------------------------------------------------------------
# 📜 Chronique — one kingdom, then the crossed comparison
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_timeline_merges_lords_and_sorts_by_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    stack = _stack(
        kingdoms=[SimpleNamespace(id="k-1", name="AEGIS", is_gaia=False)],
        lords=[
            _lord("l-1", "k-1", chronicle=[_entry(200, "crowned", {"kingdom": "AEGIS"})]),
            _lord("l-2", "k-1", chronicle=[_entry(100, "enrolled")]),
            _lord("l-3", "k-2", chronicle=[_entry(50, "crowned")]),
            _lord("l-4", "k-1", left=True, chronicle=[_entry(10, "enrolled")]),
        ],
    )
    entries = await pantheon._timeline(stack, "k-1")
    assert [entry[1] for entry in entries] == ["l-2", "l-1"], (
        "only k-1's active lords, sorted by date — the left lord and the other kingdom are out"
    )


def test_the_entry_line_never_breaks_on_an_unknown_kind_or_param() -> None:
    pantheon = _pantheon()
    line = pantheon._entry_line(_strings(), (100, "l-1", "crowned", {"kingdom": "AEGIS"}))
    assert "👑 couronné Roi de AEGIS" in line
    mystery = pantheon._entry_line(_strings(), (100, "l-1", "dragon_seen", {}))
    assert "dragon_seen" in mystery, "an unknown kind falls back to pantheon_kind_other"
    sparse = pantheon._entry_line(_strings(), (100, "l-1", "crowned", {}))
    assert "couronné" in sparse, "a missing param never raises (the _SafeParams rule)"


@pytest.mark.asyncio
async def test_the_compare_window_merges_and_marks_the_crossed_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    stack = _stack(
        kingdoms=[
            SimpleNamespace(id="k-1", name="AEGIS", is_gaia=False),
            SimpleNamespace(id="k-2", name="BASTION", is_gaia=False),
        ],
        lords=[
            _lord(
                "l-1",
                "k-1",
                chronicle=[_entry(100, "attack_declared", {"map": "M1", "target": "BASTION"})],
            ),
            _lord(
                "l-2",
                "k-2",
                chronicle=[_entry(200, "defense", {"map": "M1"})],
            ),
        ],
    )
    _wire(monkeypatch, stack)
    view = await pantheon._compare_window(_strings(), "k-1", "k-2")
    body = _texts(view)
    assert "Chronique croisée — AEGIS vs BASTION" in body
    assert "**AEGIS** ·" in body and "**BASTION** ·" in body, (
        "each line carries its kingdom's tag"
    )
    assert "⚔️" in body, "the crossed event (the one citing the other kingdom) is marked"


# ---------------------------------------------------------------------------
# The wiring — items, ids and labels are DATA, not hard-coded
# ---------------------------------------------------------------------------


def test_the_module_registers_six_restart_proof_items() -> None:
    items = _pantheon().pantheon_dynamic_items()
    assert len(items) == 6


def _conf_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "conf"


def test_the_pantheon_salon_is_declared_in_mod_yaml() -> None:
    content = (_conf_dir() / "mod.yaml").read_text(encoding="utf-8")
    assert "key: pantheon" in content
    assert "🏛️ panthéon" in content
    # panthéon-manuel-v1 (Drasah 26/11) : le salon est MANUEL — jamais
    # provisionné, jamais dans un groupe (il naît hors catégorie)
    pantheon_block = content.split("- key: pantheon", 1)[1].split("- key:", 1)[0]
    assert "manual: true" in pantheon_block
    assert "group:" not in pantheon_block


def test_the_six_surfaces_are_declared_in_views_yaml() -> None:
    content = (_conf_dir() / "views.yaml").read_text(encoding="utf-8")
    for suffix in ("", ":palmares", ":historique", ":histo", ":chronique", ":compare"):
        assert f"panel:mod:kingdom:pantheon{suffix}:" in content


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_the_labels_live_in_the_locales(locale: str) -> None:
    strings = _strings(locale)
    for key in (
        "pantheon_pin_title",
        "pantheon_pin_line",
        "pantheon_pin_gaia_line",
        "pantheon_palmares_button",
        "pantheon_palmares_showmatch",
        "pantheon_historique_button",
        "pantheon_histo_winner",
        "pantheon_chronique_button",
        "pantheon_chronique_compare_button",
        "pantheon_compare_title",
        "pantheon_kind_crowned",
        "pantheon_kind_other",
    ):
        assert strings[key], f"{locale} misses {key}"
