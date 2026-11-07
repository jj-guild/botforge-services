"""The Liquipedia parse against REAL page wikitexts — no fetch, no fakes.

The fixtures under ``tests/fixtures/liquipedia/`` are the raw wikitexts
of the game's permanent pool (Arabia, Black Forest, Arena, Nomad) plus
Budapest, dumped by the provider probe from the live API (the run's
log). The REAL parser runs on those bytes, so the
labels (image, gallery icon, tags, overview) are checked against the
actual pages — never against assumptions, and never with a network
call: the import is tested offline, exactly as the user asked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kingdoms.ext_liquipedia.liquipedia import LiquipediaMapsProvider, query_tags

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "liquipedia"


def _parse(page: str):
    slug = page.strip().lower().replace(" ", "_")
    wikitext = (FIXTURES / f"{slug}.wikitext").read_text(encoding="utf-8")
    provider = LiquipediaMapsProvider("test-contact https://github.com/merlin-pinpin-org/kingdoms")
    return provider._info_from_wikitext(page, wikitext)


def test_budapest_keeps_its_infobox_and_gallery_icon() -> None:
    """Budapest: the full infobox (image, type, tc) and the Gallery icon."""
    info = _parse("Budapest")
    assert info.name == "Budapest"
    assert info.image_file == "Budapest_Map.png", "the infobox image"
    assert info.gallery_icon == "Budapest_AoE2DE.png", "the Gallery's in-game icon"
    assert info.map_type == "Hybrid"
    assert info.tc == "2"
    assert info.walls == "None"
    assert info.nomad == "No"
    assert info.player_capacity == "Up to 8"
    assert info.creator == "Forgotten Empires"
    tags = query_tags(info)
    assert "type:hybrid" in tags and "water" in tags and "tc:2" in tags, tags
    assert "walls:no" in tags, f"the English walls vocabulary — got {tags}"


def test_budapest_keeps_its_whole_overview() -> None:
    """Budapest: BOTH overview paragraphs — the 2026-11-07 half-overview bug."""
    info = _parse("Budapest")
    assert "two Town Centers not far from each other" in info.description
    assert "tempered area" in info.description, "the second paragraph rides too"


def test_arabia_keeps_its_infobox_and_the_de_description() -> None:
    """Arabia: the infobox image, the land type and the DE description line."""
    info = _parse("Arabia")
    assert info.name == "Arabia"
    assert info.image_file == "Arabia AoE2DE.png"
    assert info.map_type == "Land"
    assert "most balanced and competitive map" in info.description
    assert "Arid desert with strategic elevations" in info.description
    assert "type:land" in query_tags(info)
    assert "walls:no" in query_tags(info), "Arabia's infobox says walls=None"


def test_arena_keeps_its_infobox_and_stops_at_the_subsection() -> None:
    """Arena: the infobox, the icon, and the overview stops at Notable Features."""
    info = _parse("Arena")
    assert info.name == "Arena"
    assert info.image_file == "Arena Map.png"
    assert info.gallery_icon == "Arena_AoE2DE.png"
    assert info.map_type == "Land"
    assert info.walls == "Stone Walls"
    assert "pre-built stone walls" in info.description
    assert "Notable Features" not in info.description, "the subsection header never leaks in"
    tags = query_tags(info)
    assert "walls:stone" in tags, f"the English walls vocabulary — got {tags}"
    assert "tc:1" in tags, "the TC count tags from 1 — got {tags}"


@pytest.mark.parametrize("page", ["Arabia", "Arena", "Black Forest", "Budapest", "Nomad"])
def test_every_fixture_page_yields_an_image_and_tags(page: str) -> None:
    """Every dumped page carries its image, its icon and at least one tag."""
    info = _parse(page)
    assert info.image_file, f"{page}: the infobox image must parse"
    assert info.gallery_icon, f"{page}: the Gallery icon must parse"
    assert query_tags(info), f"{page}: the tags must parse"
    assert info.description.strip(), f"{page}: the overview must parse"


@pytest.mark.parametrize("page", ["Arabia", "Arena", "Black Forest", "Budapest", "Nomad"])
def test_every_map_type_is_casing_normalized(page: str) -> None:
    """The type's display casing is consistent: first letter upper (owner
    direction 2026-11-07 — 'Land' and 'hybrid' on the same catalog was
    inconsistent).
    """
    info = _parse(page)
    if info.map_type:
        assert info.map_type == f"{info.map_type[:1].upper()}{info.map_type[1:]}", (
            f"{page}: the map type must be display-cased — got {info.map_type!r}"
        )


@pytest.mark.parametrize("page", ["Arabia", "Arena", "Black Forest", "Budapest", "Nomad"])
def test_every_fixture_page_carries_its_raw_wikitext(page: str) -> None:
    """The raw provider payload rides the info — the sync's raw-data store."""
    wikitext = _parse(page).raw_wikitext
    on_disk = (
        FIXTURES / f"{page.strip().lower().replace(' ', '_')}.wikitext"
    ).read_text(encoding="utf-8")
    assert wikitext == on_disk, f"{page}: the raw wikitext must ride the info"
    assert "{{Infobox map" in wikitext, f"{page}: the raw payload is the page itself"


def test_nomad_keeps_its_infobox_and_nomad_tag() -> None:
    """Nomad: the nomad-start map — nomad=Yes, walls=No, tc=No (no digit).

    The live-probe facts (2026-11-07): ``tc=No`` in the infobox is not a
    digit, so no ``tc:<n>`` tag; ``walls=No`` tags ``walls:no``; the
    hybrid type derives the water tag.
    """
    info = _parse("Nomad")
    assert info.name == "Nomad"
    assert info.map_type == "Hybrid", (
        "the infobox says 'hybrid' — the display value is normalized to 'Hybrid'"
    )
    assert info.image_file == "Nomad_Map.png"
    assert info.gallery_icon == "Nomad AoE2 DE.png", "the Gallery's File: icon"
    assert info.walls == "No"
    assert info.nomad == "Yes"
    assert info.tc == "No"
    assert info.player_capacity == "Up to 8"
    assert info.creator == "Ensemble Studios", (
        "the empty |caption= must not swallow the next line — the creator rides"
    )
    tags = query_tags(info)
    assert "nomad" in tags, f"the nomad map tags nomad — got {tags}"
    assert "walls:no" in tags, f"walls=No tags walls:no — got {tags}"
    assert "type:hybrid" in tags and "water" in tags, tags
    assert not any(t.startswith("tc:") for t in tags), "tc=No is not a count"


def test_black_forest_keeps_its_infobox_and_default_walls() -> None:
    """Black Forest: the pool's permanent map — no walls field in the infobox.

    The live-probe facts (2026-11-07): the infobox carries NO ``walls``
    field at all — an absent field defaults to the ``walls:no`` tag,
    never a missing walls tag.
    """
    info = _parse("Black Forest")
    assert info.name == "Black Forest"
    assert info.image_file == "Black_Forest_Map.png"
    assert info.gallery_icon == "black-forest_AoE2DE.png"
    assert info.map_type == "Land"
    assert info.walls == "", "the infobox has no walls field"
    assert info.nomad == "No"
    assert info.tc == "1"
    assert info.player_capacity == "Up to 8"
    assert info.creator == "Ensemble Studios"
    tags = query_tags(info)
    assert "type:land" in tags, tags
    assert "walls:no" in tags, f"an absent walls field defaults to walls:no — got {tags}"
    assert "tc:1" in tags, tags


def test_walls_vocabulary_is_english_and_total() -> None:
    """The walls tags: no/wood/stone/partial — English, always present."""
    from kingdoms.ext_liquipedia.liquipedia import walls_vocabulary

    assert walls_vocabulary("") == "no"
    assert walls_vocabulary("None") == "no"
    assert walls_vocabulary("No") == "no"
    assert walls_vocabulary("Stone Walls") == "stone"
    assert walls_vocabulary("Palisade") == "wood"
    assert walls_vocabulary("Wooden Walls") == "wood"
    assert walls_vocabulary("Partial") == "partial"
    assert walls_vocabulary("Yes") == "stone"
