"""synfoni-v1 (Drasah 06/11) — the beta-tester clarity wave.

The objectives picker finally explains itself (explainer, numbered
slots, named flip buttons, page indicator, alphabetical page ranges),
the attack lines read naturally (relative « when », author + target
kingdom, defense state SECRET), a kingdom acceptance is finally
announced, the postuler panel counts the kingdoms in play, and the
jeu d'armes no-stock note rides the single-window registry.
"""

from __future__ import annotations

from types import SimpleNamespace

import discord

from kingdoms.mods.kingdoms.kingdom_attack_panel import (
    _fmt_when_paris,
    _strings as attack_strings,
)
from kingdoms.mods.kingdoms.kingdom_lieux import (
    _objectif_page_options,
    _objectif_page_range,
    _objectifs_picker,
    _objectifs_display_lines,
    _objectifs_edit_content,
    _objectifs_read_content,
    _strings as lieux_strings,
)
from kingdoms.mods.kingdoms.kingdom_panels import _apply_kingdoms_line
from kingdoms.mods.kingdoms.kingdom_realms import STRINGS as realms_strings


TEST_KINGDOM_ID = "k-test"


def _kingdom(objectives: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=TEST_KINGDOM_ID, name="Nilrem", council_objectives=objectives or {}
    )


# ---------------------------------------------------------------------------
# The objectives picker — explainer, numbering, named flips, ranges
# ---------------------------------------------------------------------------


def test_objectifs_strings_carry_the_explainer_and_flips() -> None:
    for locale in ("fr", "en"):
        lieu = lieux_strings(locale)
        assert "objectif_explainer" in lieu
        # the explainer speaks to the realm, and the goals are free
        assert "indépendants" in lieu["objectif_explainer"] or "independent" in lieu[
            "objectif_explainer"
        ]
        assert lieu["objectif_flip_prev"].startswith("◀️")
        assert lieu["objectif_flip_next"].startswith("▶️")
        assert "{0}/{1}" in lieu["objectif_flip_pages"]
        # the hints mention the flips' page browsing
        assert "Précédent" in lieu["objectif_edit_hint"] or "Previous" in lieu[
            "objectif_edit_hint"
        ]


def test_objectifs_contents_open_with_the_explainer() -> None:
    import asyncio

    lieu_fr = lieux_strings("fr")
    for content in (
        asyncio.run(_objectifs_read_content("fr", _kingdom(), None)),
        _objectifs_edit_content("fr", _kingdom(), {}),
    ):
        assert lieu_fr["objectif_explainer"] in content
        assert "## 🎯" in content


def test_objectifs_lines_are_numbered_slots() -> None:
    import asyncio

    kingdom = _kingdom(
        {
            "target_kingdom": "k-2",
            "target_kingdom_label": "HeN",
            "target_alliance": "c-1",
            "target_alliance_label": "Huns",
        }
    )
    lines = asyncio.run(_objectifs_display_lines("fr", kingdom, None))
    # slot 1 (kingdom) and slot 3 (alliance) keep their fixed numbers
    assert lines[0].startswith("1. ")
    assert lines[1].startswith("3. ")
    assert "HeN" in lines[0] and "Huns" in lines[1]


def test_objectif_page_range_is_alphabetical() -> None:
    catalog = {f"map-{i}": f"Map {i}" for i in range(1, 61)}
    assert _objectif_page_range("fr", {"m-1": "Ile du Pacifique"}, 0) is None
    range_fr = _objectif_page_range("fr", catalog, 0)
    assert range_fr is not None and " à " in range_fr
    assert range_fr == "M à M"  # every label starts with M
    # an EN catalog range reads « to »
    assert " to " in (_objectif_page_range("en", catalog, 0) or "")


def test_objectif_options_are_sorted_alphabetetically() -> None:
    catalog = {
        "z": "Zèbre",
        "a": "Ananas",
        "m": "Mangue",
    }
    options = _objectif_page_options("fr", catalog, "", 0)
    labels = [str(option.label) for option in options]
    assert labels[1:] == ["Ananas", "Mangue", "Zèbre"]


def test_objectif_picker_named_flips_indicator_and_range() -> None:
    lieu = lieux_strings("fr")
    maps_catalog = {f"map-{i}": f"Map {i}" for i in range(1, 60)}
    civs_catalog = {f"civ-{i}": f"Civ {i}" for i in range(1, 40)}
    view = _objectifs_picker(
        SimpleNamespace(kingdoms_service=None),
        _kingdom(),
        "fr",
        {},
        maps_catalog,
        civs_catalog,
        {},
        reveal=("target_territory", "target_alliance"),
    )
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    labels = [str(b.label) for b in buttons]
    assert lieu["objectif_flip_prev"] in labels
    assert lieu["objectif_flip_next"] in labels
    assert "Page 1/3" in labels
    indicators = [b for b in buttons if str(b.label).startswith("Page ")]
    assert all(b.disabled for b in indicators)
    selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
    placeholders = [str(s.placeholder) for s in selects]
    assert any(" — " in p and " à " in p for p in placeholders)


# ---------------------------------------------------------------------------
# The attack lines — relative « when », author + target, secret defense
# ---------------------------------------------------------------------------


def test_fmt_when_paris_reads_today_tomorrow_and_date() -> None:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    strings = attack_strings("fr")
    paris = ZoneInfo("Europe/Paris")
    # a fixed mid-day anchor keeps the date math deterministic
    anchor = datetime.now(tz=paris).replace(hour=12, minute=0, second=0, microsecond=0)
    assert "aujourd'hui" in _fmt_when_paris(anchor + timedelta(hours=2), strings)
    assert "demain" in _fmt_when_paris(anchor + timedelta(days=1, hours=3), strings)
    late = _fmt_when_paris(anchor + timedelta(days=5), strings)
    assert late.startswith("le ") and " à " in late
    # EN locale reads « today at » with a 24h clock
    strings_en = attack_strings("en")
    assert "today at " in _fmt_when_paris(anchor + timedelta(hours=2), strings_en)


def test_plan_manager_declared_row_names_author_and_target() -> None:
    for locale in ("fr", "en"):
        strings = attack_strings(locale)
        row = str(strings["plan_manager_declared_row"])
        # the author and the target kingdom ride the line…
        assert "{kingdom}" in row and "{lord}" in row
        # …the defense state NEVER does (SECRET, Drasah's 06/11 ruling)
        assert "{state}" not in row
        assert "defended" not in row
        # relative time, no « RDV », no « (Paris) »
        assert "{when}" in row
        assert "RDV" not in row and "(Paris)" not in row


def test_attack_and_defense_rows_use_the_relative_when() -> None:
    for locale in ("fr", "en"):
        strings = attack_strings(locale)
        for key in (
            "defense_manager_row",
            "plan_manager_planned_row",
            "attack_line",
            "gaia_line",
        ):
            row = str(strings[key])
            assert "{when}" in row, key
            assert "(Paris)" not in row, key


# ---------------------------------------------------------------------------
# The acceptance announce + the kingdoms counter
# ---------------------------------------------------------------------------


def test_kingdom_accepted_strings_exist_in_both_locales() -> None:
    for locale in ("fr", "en"):
        strings = realms_strings[locale]
        assert "{kingdom}" in str(strings["kingdom_accepted_dm"])
        assert "{kingdom}" in str(strings["kingdom_accepted_note"])


def test_apply_kingdoms_line_pluralizes() -> None:
    assert "Aucun royaume" in _apply_kingdoms_line(0)
    assert _apply_kingdoms_line(1) == "👑 **1** royaume en jeu — rejoins l'aventure !"
    assert "**4** royaumes" in _apply_kingdoms_line(4)
