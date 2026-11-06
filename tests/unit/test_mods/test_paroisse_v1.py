"""paroisse-v1 (Drasah 06/11) — the Paroisse grande refonte.

The main sheet is CLEAN (stripped title, stats line, 🙏 Notre Chapelle,
Les Fidèles, live Lieu Sacrée states — zero ladder, zero legend), the
explanations live behind 🔎 En savoir plus (the word-for-word marriage
explainer + the four notes), the palier ladder lives in the ⛪
Améliorer view (three bandes with offrande +0/+1/+2 and the Lieu
Sacrée rules), the marriage flow is role-adapted with the sealed
wedding ANNOUNCED in Géopolitique, and D45 is RELÂCHÉ : a lord whose
link broke can wed again (one ACTIVE marriage at a time).
"""

from __future__ import annotations

from types import SimpleNamespace

import discord
import pytest

from kingdoms.mods.kingdoms.diplomacy import AlreadyMarriedError
from kingdoms.mods.kingdoms.kingdom_panels import _strings as panels_strings
from kingdoms.mods.kingdoms.kingdom_realm_content import (
    _build_church,
    _build_church_upgrade_view,
    _church_buttons,
    _strings as realm_strings,
)

from .test_kingdoms_parish import Bundle

# ---------------------------------------------------------------------
# The harness — a hand-built parish slice, no Discord mocks needed
# ---------------------------------------------------------------------


def _parish(tier: int = 1) -> dict:
    ladder = [
        {"name": "Chapelle", "cost": 0, "lock_hours": 24, "offering": 0},
        {"name": "Église", "cost": 2, "lock_hours": 12, "offering": 1},
        {"name": "Cathédrale", "cost": 4, "lock_hours": 6, "offering": 2},
    ]
    entry = ladder[tier - 1]
    return {
        "tier": tier,
        "name": entry["name"],
        "cost": ladder[tier]["cost"] if tier < len(ladder) else 0,
        "next_name": ladder[tier]["name"] if tier < len(ladder) else "",
        "offering": entry["offering"],
        "lock_hours": entry["lock_hours"],
        "max_tier": len(ladder),
        "ladder": ladder,
    }


def _kingdom(tier: int = 1, bank: int = 5) -> SimpleNamespace:
    return SimpleNamespace(
        name="Nilrem",
        marriage_points=3,
        arranged_marriage_stock=1,
        tech_points_bank=bank,
        parish_tier=tier,
    )


def _state(tier: int = 1, members: list | None = None) -> dict:
    return {
        "parish": _parish(tier),
        "members": members or [],
        "civ_names": {},
        "territories": [],
    }


def _view_text(view) -> str:
    chunks: list[str] = []
    stack = [view]
    while stack:
        node = stack.pop()
        content = getattr(node, "content", None)
        if content:
            chunks.append(str(content))
        stack.extend(getattr(node, "children", []) or [])
    return "\n".join(chunks)


def _view_buttons(view) -> list:
    """Every button of a view as (custom_id, style, disabled)."""
    found: list = []
    stack = [view]
    while stack:
        node = stack.pop()
        inner = getattr(node, "item", None)  # a DynamicItem wraps its Button
        target = inner if inner is not None and isinstance(inner, discord.ui.Button) else None
        if target is None and isinstance(node, discord.ui.Button):
            target = node
        if target is not None:
            found.append((target.custom_id, target.style, target.disabled))
        stack.extend(getattr(node, "children", []) or [])
    return found


# ---------------------------------------------------------------------
# The strings — both locales, wire-proof
# ---------------------------------------------------------------------


def test_church_strings_are_the_paroisse_v1_set() -> None:
    for locale in ("fr", "en"):
        strings = realm_strings(locale)
        # the title is stripped — the digits left for the stats line
        assert strings["church_title"] in ("⛪ Paroisse — {0}", "⛪ Parish — {0}")
        assert "{1}" not in strings["church_title"]
        # the stats line rides UNDER the title
        assert "💍" in strings["church_stats_line"]
        assert "💐" in strings["church_stats_line"]
        assert "⚙️" in strings["church_stats_line"]
        # 🙏 Notre Chapelle — the monastère clin d'œil
        assert strings["church_household_palier"].startswith("🙏")
        # the tier line speaks the 🎁 Offrande
        assert "🎁" in strings["church_tier_line"]
        # the sacred line reads until the season ends
        assert "saison" in strings["church_sacred_line"] or "season" in strings[
            "church_sacred_line"
        ]


def test_the_marriage_explainer_is_drashas_word_for_word_text() -> None:
    for locale in ("fr", "en"):
        strings = realm_strings(locale)
        body = strings["church_info_marry_body"]
        # one ACTIVE marriage at a time — never two
        assert "un seul mariage actif" in body or "one active marriage" in body.lower()
        # the marriage makes the civilization exclusive
        assert "exclusive" in body
        # a broken link can re-wed later in the season (D45 relâché)
        assert "se remarier" in body or "re-marry" in body.lower() or "remarry" in body.lower()
        # only the King seals a royal marriage — it survives defeats
        assert "mariage royal" in body or "royal marriage" in body.lower()
        assert "+2" in body


def test_the_upgrade_view_strings_carry_the_three_bandes() -> None:
    strings = realm_strings("fr")
    # the bandes badges
    assert "NOTRE PALIER" in strings["church_band_current"]
    assert "{0} ⚙️" in strings["church_band_next"]
    assert "VERROUILLÉE" in strings["church_band_locked"]
    # the bandes description — cost, offrande, marriage lock
    assert "Offrande +{2} ⚙️" in strings["church_band_desc"]
    # the Cathédrale bande carries the Lieu Sacrée rules
    sacree = strings["church_band_sacree"]
    assert "Lieu Sacrée" in sacree
    assert "72h" in sacree
    assert "Garde Royal" in sacree


def test_the_wedding_announcement_is_geopolitique_ready() -> None:
    for locale in ("fr", "en"):
        strings = panels_strings(locale)
        text = str(strings["church_wedding_announce"])
        # the announcement speaks the promise — exclusivity
        assert "exclusive" in text
        assert "{0}" in text


# ---------------------------------------------------------------------
# The main sheet — CLEAN (no ladder, no legend)
# ---------------------------------------------------------------------


def test_the_main_sheet_is_the_clean_paroisse_v1_face() -> None:
    strings = realm_strings("fr")
    view = _build_church(strings, _kingdom(), _state())
    content = _view_text(view)
    # the stripped title and the stats line under it
    assert "# ⛪ Paroisse — Nilrem" in content
    assert "💍 Bague : 3 · 💐 Mariage arrangé : 1 · ⚙️ Point Technologie : 5" in content
    # 🙏 Notre Chapelle — palier + Offrande 🎁
    assert "## 🙏 Notre Chapelle" in content
    assert "Palier : Chapelle (1/3) — Offrande 🎁 : +0 ⚙️ par mariage" in content
    # 💒 Les Fidèles
    assert "Les Fidèles du Royaume" in content
    # paroisse-v1: the ladder and the legend LEFT the main sheet
    assert "Aperçu des paliers" not in content
    assert "-# 🔒 Verrou :" not in content
    assert "-# 🎁 Offrande :" not in content
    assert "-# 💰 Jeton :" not in content
    assert "-# ⛪ Lieu Sacrée" not in content
    # the live Lieu Sacrée states stay — a sacred territory shows
    sacred = SimpleNamespace(map_key="arabia", sacred=True, cathedral_until=None)
    view = _build_church(strings, _kingdom(), {**_state(), "territories": [sacred]})
    assert "Lieu Sacrée SACRÉ sur **arabia**" in _view_text(view)


def test_the_info_face_carries_the_explainer_and_the_four_notes() -> None:
    strings = realm_strings("fr")
    view = _build_church(strings, _kingdom(), _state(), mode="info")
    content = _view_text(view)
    assert "Le mariage dans Kingdoms" in content
    assert "un seul mariage actif" in content
    assert "-# 🔒 Verrou :" in content
    assert "-# 🎁 Offrande :" in content
    assert "-# 💰 Jeton :" in content
    assert "-# ⛪ Lieu Sacrée" in content


# ---------------------------------------------------------------------
# The ⛪ Améliorer view — three bandes, green/gray/gone confirm
# ---------------------------------------------------------------------


def test_the_upgrade_view_shows_the_three_bandes() -> None:
    strings = realm_strings("fr")
    view = _build_church_upgrade_view(strings, _kingdom(tier=1), _state(tier=1))
    content = _view_text(view)
    # the three palier bandes with the paroisse-v1 values
    assert "⛪ Chapelle" in content
    assert "✅ NOTRE PALIER" in content
    assert "⛪ Église" in content
    assert "PROCHAIN · 2 ⚙️" in content
    assert "⛪ Cathédrale" in content
    assert "🔒 VERROUILLÉE" in content
    # the offrande reads +0 / +1 / +2 (Drasah 06/11 correction)
    assert "🎁 Offrande +0 ⚙️" in content
    assert "🎁 Offrande +1 ⚙️" in content
    assert "🎁 Offrande +2 ⚙️" in content
    # the marriage locks read 24h / 12h / 6h
    assert "Verrou mariage 24h" in content
    assert "Verrou mariage 12h" in content
    assert "Verrou mariage 6h" in content
    # the Lieu Sacrée rules ride the Cathédrale bande only
    assert content.count("Lieu Sacrée") == 1


def test_the_upgrade_confirm_is_green_when_the_treasury_pays() -> None:
    strings = realm_strings("fr")
    # bank 5 ≥ cost 2 → green, enabled
    view = _build_church_upgrade_view(strings, _kingdom(tier=1, bank=5), _state(tier=1))
    buttons = dict((cid, (style, disabled)) for cid, style, disabled in _view_buttons(view))
    assert buttons["kingdoms:church:upgrade"] == (discord.ButtonStyle.success, False)
    # bank 1 < cost 2 → gray, disabled
    view = _build_church_upgrade_view(strings, _kingdom(tier=1, bank=1), _state(tier=1))
    buttons = dict((cid, (style, disabled)) for cid, style, disabled in _view_buttons(view))
    assert buttons["kingdoms:church:upgrade"] == (discord.ButtonStyle.secondary, True)


def test_the_upgrade_confirm_is_gone_at_the_top_palier() -> None:
    strings = realm_strings("fr")
    view = _build_church_upgrade_view(strings, _kingdom(tier=3, bank=9), _state(tier=3))
    content = _view_text(view)
    # the max note replaces the confirm button
    assert "plus haut palier" in content
    ids = [cid for cid, _style, _disabled in _view_buttons(view)]
    assert "kingdoms:church:upgrade" not in ids
    assert "kingdoms:church:back" in ids
    # at the top palier the CURRENT bande is the Cathédrale
    content = _view_text(view)
    assert "✅ NOTRE PALIER" in content
    assert "Palier 3" in content


# ---------------------------------------------------------------------
# The Se marier button — gray when impossible, usable when a ring fits
# ---------------------------------------------------------------------


def test_the_marry_button_reads_the_clickers_state() -> None:
    strings = realm_strings("fr")
    free_lord = SimpleNamespace(id="p1", role="lord", married_civilization=None)
    married_lord = SimpleNamespace(id="p2", role="lord", married_civilization="shu")
    king = SimpleNamespace(id="p3", role="king", married_civilization=None)

    # a free lord with a ring → the button is usable
    marry = _church_buttons(strings, _kingdom(), _state(), free_lord)[0]
    assert marry.item.disabled is False
    assert marry.item.style == discord.ButtonStyle.primary
    # an already-married lord → gray, whatever the rings
    marry = _church_buttons(strings, _kingdom(), _state(), married_lord)[0]
    assert marry.item.disabled is True
    assert marry.item.style == discord.ButtonStyle.secondary
    # the King needs TWO rings — one ring grays him out (refuser)
    king_one_ring = SimpleNamespace(id="k-1", marriage_points=1, arranged_marriage_stock=1, tech_points_bank=5, parish_tier=1, name="Nilrem")
    marry = _church_buttons(strings, king_one_ring, _state(), king)[0]
    assert marry.item.disabled is True
    # two rings → the King may wed
    king_two_rings = SimpleNamespace(id="k-1", marriage_points=2, arranged_marriage_stock=1, tech_points_bank=5, parish_tier=1, name="Nilrem")
    marry = _church_buttons(strings, king_two_rings, _state(), king)[0]
    assert marry.item.disabled is False


# ---------------------------------------------------------------------
# D45 relâché — a broken link may wed again (one ACTIVE at a time)
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_lord_remarries_after_a_broken_link() -> None:
    bundle = Bundle()
    await bundle.launch_season()
    await bundle.give("Aquitaine", "celtes", "shu")
    kingdom = await bundle.kingdom_of("Aquitaine")
    kingdom.marriage_points = 5
    await bundle.store.upsert_kingdom(kingdom.to_mongo())

    await bundle.diplomacy.marry("lord-a", "shu")
    # one ACTIVE marriage at a time — never two
    with pytest.raises(AlreadyMarriedError) as exc:
        await bundle.diplomacy.marry("lord-a", "celtes")
    assert "ONE active marriage" in str(exc.value)

    # the defeat breaks the link — D45 relâché: the lord may wed again
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.diplomacy.record_defeat(aquitaine)
    await bundle.diplomacy.recalculate()
    lords = {item.id: item for item in await bundle.kingdoms.lords()}
    assert lords["lord-a"].married_civilization is None

    # a defeat may drop the hand's alliances too — give the ring back
    await bundle.give("Aquitaine", "celtes")
    assert await bundle.diplomacy.marry("lord-a", "celtes") == "celtes"
    lords = {item.id: item for item in await bundle.kingdoms.lords()}
    assert lords["lord-a"].married_civilization == "celtes"
