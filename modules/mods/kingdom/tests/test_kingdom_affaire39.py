"""Affaire 39 (Drasah 26/11) : branchement du 📜 Scriptorium et de la
🍺 Taverne.

Les salons étaient DÉCLARÉS dans conf/mod.yaml (scriptorium position
20, tavern position 24) mais restaient VIDES — leurs surfaces vivaient
dans la référence. Le portage : deux pins statiques (le seam du
Marché, zéro envoi ad hoc), les rubriques éphémères paginées (Cadastre
/ Diplomatie / Seigneurie), la fiche seigneur GATED par corbeau_track
(l'identité toujours, statut + chronique sur suivi 24h), et le comptoir
de la Taverne (menu + renseignement + bourse, TOUTES les fenêtres
réutilisées).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
NOW_TS = int(NOW.timestamp())


# ---------------------------------------------------------------------------
# The fakes
# ---------------------------------------------------------------------------


def _fake_stack(*, maps: tuple = (), civilizations: tuple = ()) -> Any:
    config = SimpleNamespace(
        maps=maps,
        civilizations=civilizations,
        attacks=SimpleNamespace(attacks_per_week=2, defenses_per_week=1),
        tavern=SimpleNamespace(
            drinks=(
                SimpleNamespace(key="verre", label="🍺 Cervoise", price=2, lock_minutes=60),
                SimpleNamespace(key="vin", label="🍷 Hypocras", price=4, lock_minutes=180),
            )
        ),
    )
    return SimpleNamespace(config=config)


def _fake_lord(**kwargs: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "id": "l1",
        "display_name": "Anna",
        "role": "king",
        "kingdom_id": "k1",
        "in_queue": False,
        "left": False,
        "attack_used": 1,
        "defense_used": 0,
        "marriage_locked_until": None,
        "exploration_locked_until": None,
        "tavern_locked_until": None,
        "ffa_locked_until": None,
        "insight_name": "Insight",
        "married_civilization": None,
        "chronicle": [],
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


class _Kingdoms:
    def __init__(self, kingdoms: list, lords: list) -> None:
        self._kingdoms = kingdoms
        self._lords = lords

    async def kingdoms(self) -> list:
        return self._kingdoms

    async def lords(self) -> list:
        return self._lords


class _Territories:
    def __init__(self, count: int = 0) -> None:
        self._count = count

    async def territories(self) -> list:
        owned = [SimpleNamespace(owner_kingdom_id="k1") for _ in range(self._count)]
        owned.append(SimpleNamespace(owner_kingdom_id="other"))
        return owned


# ---------------------------------------------------------------------------
# The Cadastre rubric
# ---------------------------------------------------------------------------


def test_cadastre_renders_tags_and_bonus() -> None:
    """One Cadastre line carries the map, its tags and its bonus verbatim."""
    from botforge.mods.kingdom.cogs import scriptorium
    from botforge.mods.kingdom.cogs.strings import strings

    entry = SimpleNamespace(
        key="acropolis",
        display_name="Acropolis",
        types=SimpleNamespace(montagne=True, ouverte=True),
        cadastre={"bonus": "Offre un contre-espionnage/semaine"},
    )
    lines = scriptorium._cadastre_lines(strings("fr"), _fake_stack(maps=(entry,)))
    joined = "\n".join(lines)
    assert "**Acropolis**" in joined
    assert "contre-espionnage" in joined
    assert "⛰️" in joined and "🌞" in joined  # the Drasah tag icons


def test_cadastre_empty_catalog() -> None:
    """An empty catalog renders the empty note, never a crash."""
    from botforge.mods.kingdom.cogs import scriptorium
    from botforge.mods.kingdom.cogs.strings import strings

    lines = scriptorium._cadastre_lines(strings("fr"), _fake_stack())
    assert strings("fr")["scriptorium_cadastre_empty"] in "\n".join(lines)


# ---------------------------------------------------------------------------
# The Diplomatie rubric (the official conditions)
# ---------------------------------------------------------------------------


def test_diplomatie_renders_the_official_conditions() -> None:
    """Every condition kind of the config renders into its player text."""
    from botforge.mods.kingdom.cogs import scriptorium
    from botforge.mods.kingdom.cogs.strings import strings

    civ = SimpleNamespace(
        key="archipel",
        display_name="Archipel",
        requires_map_keys=("archipel",),
        min_map_key_count=1,
        requires_map_types=(),
        min_map_type_count=1,
        min_map_count=2,
        max_map_count=None,
        requires_civilization=None,
        requires_kingdom_name_pattern=None,
        requires_tech_points=3,
        requires_marriages=None,
        requires_civilization_count=None,
    )
    catalog = (
        civ,
        SimpleNamespace(key="vikings", display_name="Vikings"),
    )
    lines = scriptorium._diplomatie_lines(strings("fr"), _fake_stack(civilizations=catalog))
    joined = "\n".join(lines)
    # the CONDITION civ unlocks via its own map — the key reads as the name
    assert "posséder la map Archipel" in joined
    assert "posséder au moins 2 map(s)" in joined
    assert "3 point(s) technologique(s)" in joined
    # the display-only fallback: no conditions = the bare civ name
    assert "**Vikings**" in joined


def test_condition_text_every_kind() -> None:
    """Each condition field maps to its string (fr), with the live params."""
    from botforge.mods.kingdom.cogs import scriptorium
    from botforge.mods.kingdom.cogs.strings import strings

    s = strings("fr")
    civ = SimpleNamespace(
        requires_map_keys=("a", "b"),
        min_map_key_count=2,
        requires_map_types=("eau",),
        min_map_type_count=1,
        min_map_count=1,
        max_map_count=5,
        requires_civilization="a",
        requires_kingdom_name_pattern=" Rune",
        requires_tech_points=2,
        requires_marriages=1,
        requires_civilization_count=2,
    )
    text = scriptorium._condition_text(s, civ, {"a": "Alpha"})
    assert "au moins 2 de" in text and "Alpha" in text
    assert "type eau" in text
    assert "au plus 5" in text
    assert "civilisation Alpha" in text
    assert "Rune" in text
    assert "2 point(s) technologique(s)" in text
    assert "1 seigneur(s) marié(s)" in text
    assert "au moins 2 civilisation(s)" in text


# ---------------------------------------------------------------------------
# The Seigneurie rubric + the fiche (the corbeau gate)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seigneurie_budgets_locks_and_queue() -> None:
    """King + lord lines carry the remaining budgets and live lock stamps."""
    from botforge.mods.kingdom.cogs import scriptorium
    from botforge.mods.kingdom.cogs.strings import strings

    stack = _fake_stack()
    stack.kingdoms = _Kingdoms(
        kingdoms=[SimpleNamespace(id="k1", name="Asgard", is_gaia=False)],
        lords=[
            _fake_lord(),
            _fake_lord(
                id="l2",
                display_name="Bjarne",
                role="lord",
                attack_used=0,
                defense_used=1,
                tavern_locked_until=NOW_TS + 3600,
            ),
            _fake_lord(id="q1", display_name="Cleo", in_queue=True),
        ],
    )
    lines = await scriptorium._seigneurie_lines(
        strings("fr"), stack, await stack.kingdoms.kingdoms(), await stack.kingdoms.lords()
    )
    joined = "\n".join(lines)
    assert "**Asgard**" in joined
    assert "👑 Roi : Anna — ⚔️ 1/2 · 🛡️ 1/1" in joined
    assert f"🍺 <t:{NOW_TS + 3600}:R>" in joined  # the live lock stamp
    assert "Cleo" in joined  # the waiting queue


@pytest.mark.asyncio
async def test_fiche_identity_only_without_corbeau() -> None:
    """Without a corbeau_track, the fiche shows identity + the gate note."""
    from botforge.mods.kingdom.cogs import scriptorium
    from botforge.mods.kingdom.cogs.strings import strings

    stack = _fake_stack()
    stack.kingdoms = _Kingdoms(
        kingdoms=[
            SimpleNamespace(
                id="k1",
                name="Asgard",
                is_gaia=False,
                secured_civilizations=[],
                parish_tier=1,
                corbeau_tracking=[],
            )
        ],
        lords=[_fake_lord()],
    )
    stack.territories = _Territories(2)
    consultant = _fake_lord(id="me", kingdom_id="k2")
    body = await scriptorium._fiche_body(strings("fr"), "fr", stack, "l1", consultant)
    assert "Anna" in body
    assert strings("fr")["scriptorium_fiche_gated"] in body
    assert "Territoires" not in body  # the status stays behind the gate


@pytest.mark.asyncio
async def test_fiche_full_with_corbeau_track() -> None:
    """A live corbeau_track (24h) opens status + chronicle."""
    from botforge.mods.kingdom.cogs import scriptorium
    from botforge.mods.kingdom.cogs.strings import strings

    kingdom = SimpleNamespace(
        id="k1",
        name="Asgard",
        is_gaia=False,
        secured_civilizations=["Vikings"],
        parish_tier=2,
        corbeau_tracking=[{"lord_id": "l1", "until": NOW_TS + 3600}],
    )
    entry = SimpleNamespace(
        at=NOW_TS - 60,
        kind="market_purchase",
        params={"item": "Patrouille", "cost": "3"},
    )
    lord = _fake_lord(married_civilization="Japonais", chronicle=[entry])
    stack = _fake_stack()
    stack.kingdoms = _Kingdoms(kingdoms=[kingdom], lords=[lord])
    stack.territories = _Territories(3)
    consultant = _fake_lord(id="me", kingdom_id="k1")
    body = await scriptorium._fiche_body(strings("fr"), "fr", stack, "l1", consultant)
    assert strings("fr")["scriptorium_fiche_tracked"] in body
    assert "Japonais" in body  # the married civilization
    assert "Vikings" in body  # the secured civs
    assert ": 3" in body  # territory count
    assert "Patrouille" in body  # the chronicle line


def test_chronicle_line_renders_templates() -> None:
    """The chronicle templates carry the params, timestamped natively."""
    from botforge.mods.kingdom.cogs import scriptorium

    line = scriptorium._chronicle_line(
        "fr",
        SimpleNamespace(at=NOW_TS, kind="crowned", params={"kingdom": "Asgard"}),
    )
    assert line == f"<t:{NOW_TS}:f> — 👑 Couronné Roi de Asgard."

    enrolled = scriptorium._chronicle_line(
        "fr",
        SimpleNamespace(at=NOW_TS, kind="enrolled", params={"status": "queue"}),
    )
    assert "file d'attente" in enrolled


def test_history_body_stays_under_discord_limit() -> None:
    """The full history never exceeds Discord's 2000-character ceiling."""
    from botforge.mods.kingdom.cogs import scriptorium
    from botforge.mods.kingdom.cogs.strings import strings

    entries = [
        SimpleNamespace(
            at=NOW_TS - i * 60, kind="market_purchase", params={"item": "X", "cost": "1"}
        )
        for i in range(60)
    ]
    lord = _fake_lord(chronicle=entries)
    body = scriptorium._history_body(strings("fr"), "fr", lord)
    assert len(body) <= 2000


# ---------------------------------------------------------------------------
# The pager
# ---------------------------------------------------------------------------


def test_paginate_keeps_every_page_small() -> None:
    """A 97-map rubric splits into pages under Discord's limit."""
    from botforge.mods.kingdom.cogs import scriptorium

    lines = [f"- **Map {i}** — un bonus assez long pour forcer la coupe" for i in range(200)]
    pages = scriptorium.paginate(lines)
    assert len(pages) > 1
    assert all(len(page) <= 1800 for page in pages)
    # nothing is lost: every line rides one page
    flat = "\n".join(pages)
    assert "**Map 0**" in flat and "**Map 199**" in flat


# ---------------------------------------------------------------------------
# The pinned panels + the wiring
# ---------------------------------------------------------------------------


def _collect_custom_ids(view: Any) -> list[str]:
    ids: list[str] = []
    pending = list(view.children)
    while pending:
        item = pending.pop(0)
        ids.append(str(getattr(item, "custom_id", "") or ""))
        pending.extend(getattr(item, "children", []) or [])
    return [i for i in ids if i]


@pytest.mark.asyncio
async def test_scriptorium_panel_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pinned sommaire carries the three rubric buttons."""
    from botforge.mods.kingdom.cogs import panel, scriptorium

    async def _fake_locale(guild_id: str) -> str:
        return "fr"

    monkeypatch.setattr(panel, "_guild_locale", _fake_locale)
    view = await scriptorium.build_scriptorium_panel("123")
    custom_ids = _collect_custom_ids(view)
    assert "kingdom:scriptorium:rubric:cadastre" in custom_ids
    assert "kingdom:scriptorium:rubric:diplomatie" in custom_ids
    assert "kingdom:scriptorium:rubric:seigneurie" in custom_ids


@pytest.mark.asyncio
async def test_tavern_panel_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pinned Taverne carries menu/mercenary/info/purse buttons."""
    from botforge.mods.kingdom.cogs import panel, tavern

    async def _fake_locale(guild_id: str) -> str:
        return "fr"

    monkeypatch.setattr(panel, "_guild_locale", _fake_locale)
    view = await tavern.build_tavern_panel("123")
    custom_ids = _collect_custom_ids(view)
    assert "kingdom:tavern:menu" in custom_ids
    assert "kingdom:attack:mercenary" in custom_ids  # the ONE Chef Mercenaire button
    assert "kingdom:tavern:info" in custom_ids
    assert "kingdom:tavern:purse" in custom_ids


def test_pins_and_items_are_registered() -> None:
    """The cog source registers BOTH pins and the new DynamicItems."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "cogs" / "kingdom" / "__init__.py").read_text()
    assert '"panel:mod:kingdom:scriptorium"' in source
    assert '"panel:mod:kingdom:tavern:pin"' in source
    assert '"mod/kingdom", "scriptorium"' in source
    assert '"mod/kingdom", "tavern"' in source
    assert "ScriptoriumRubricButton" in source
    assert "TavernMenuButton" in source
    assert "TavernInfoButton" in source
    assert "TavernPurseButton" in source


def test_views_yaml_declares_the_new_surfaces() -> None:
    """Every rendered id is declared (drift « NOT declared » impossible)."""
    root = Path(__file__).resolve().parents[1]
    yaml_text = (root / "conf" / "views.yaml").read_text()
    for key in (
        "panel:mod:kingdom:scriptorium:",
        "panel:mod:kingdom:scriptorium:cadastre:",
        "panel:mod:kingdom:scriptorium:diplomatie:",
        "panel:mod:kingdom:scriptorium:seigneurie:",
        "panel:mod:kingdom:scriptorium:fiche:",
        "panel:mod:kingdom:tavern:",
        "panel:mod:kingdom:tavern:pin:",
        "panel:mod:kingdom:tavern:confirm:",
        "panel:mod:kingdom:tavern:info:",
        "panel:mod:kingdom:mercenary:",
        "panel:mod:kingdom:mercenary:ladder:",
    ):
        assert key in yaml_text, key


def test_strings_carry_both_locales() -> None:
    """The new keys exist in FR and EN (the per-module strings rule)."""
    from botforge.mods.kingdom.cogs.strings import strings

    keys = (
        "scriptorium_title",
        "scriptorium_intro",
        "scriptorium_topic_cadastre",
        "scriptorium_fiche_gated",
        "scriptorium_fiche_tracked",
        "scriptorium_condition_map",
        "tavern_pin_title",
        "tavern_pin_rules",
        "tavern_menu_button",
        "tavern_info_button",
        "tavern_purse_button",
        "tavern_effect_verre",
        "tavern_effect_vin",
        "tavern_effect_alcool",
        "tavern_purse_line",
    )
    for locale in ("fr", "en"):
        m = strings(locale)
        for key in keys:
            assert m.get(key), f"{key} missing in {locale}"


def test_rubric_button_is_restart_proof() -> None:
    """The rubric button carries its topic on the wire custom_id."""
    from botforge.mods.kingdom.cogs import scriptorium
    from botforge.mods.kingdom.cogs.strings import strings

    button = scriptorium.ScriptoriumRubricButton("cadastre", strings("fr")["scriptorium_topic_cadastre"])
    assert button.item.custom_id == "kingdom:scriptorium:rubric:cadastre"


def test_mercenary_button_stays_shared() -> None:
    """The attack panel button and the pin share ONE DynamicItem body."""
    from botforge.mods.kingdom.cogs import tavern

    source = Path(tavern.__file__).read_text()
    assert source.count('"kingdom:attack:mercenary"') == 1  # the single custom_id
    assert "await _open_tavern_menu(interaction)" in source  # TavernButton reuses the body
