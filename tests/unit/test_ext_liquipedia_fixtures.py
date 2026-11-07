"""The Liquipedia parse against REAL page wikitexts — no fetch, no fakes.

The fixtures under ``tests/fixtures/liquipedia/`` are the raw wikitexts
of Budapest, Arabia and Arena, dumped by the provider probe from the
live API (the run's log). The REAL parser runs on those bytes, so the
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
    wikitext = (FIXTURES / f"{page.lower()}.wikitext").read_text(encoding="utf-8")
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


@pytest.mark.parametrize("page", ["Arabia", "Arena", "Budapest"])
def test_every_fixture_page_yields_an_image_and_tags(page: str) -> None:
    """Every dumped page carries its image, its icon and at least one tag."""
    info = _parse(page)
    assert info.image_file, f"{page}: the infobox image must parse"
    assert info.gallery_icon, f"{page}: the Gallery icon must parse"
    assert query_tags(info), f"{page}: the tags must parse"
    assert info.description.strip(), f"{page}: the overview must parse"


@pytest.mark.parametrize("page", ["Arabia", "Arena", "Budapest"])
def test_every_fixture_page_carries_its_raw_wikitext(page: str) -> None:
    """The raw provider payload rides the info — the sync's raw-data store."""
    wikitext = (FIXTURES / f"{page.lower()}.wikitext").read_text(encoding="utf-8")
    info = _parse(page)
    assert info.raw_wikitext == wikitext, f"{page}: the raw wikitext must ride the info"
    assert "{{Infobox map" in info.raw_wikitext, f"{page}: the raw payload is the page itself"


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
