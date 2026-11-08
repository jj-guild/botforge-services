"""The map post's subtitle tags: backticked French strings.

Each tag on the vocabulary (owner direction 2026-11-08): the Liquipedia
type, the walls, the player count (silent at the nominal 8), Nomade
(the flag or a TC=0 start), the multi-TC start. The open/closed/
semi-open/chaotic classification is the designers' vocabulary —
delegated to kingdoms-services#348, never shown from the import.
"""

from __future__ import annotations

from kingdoms.discord.maps_forum import (
    _map_props_lines,
    _type_display,
    _walls_display,
)


def test_walls_display_normalizes_to_french() -> None:
    """The walls vocabulary: Pierre / Bois / Fortifiés / Partiels."""
    assert _walls_display("") == ""
    assert _walls_display("None") == ""
    assert _walls_display("No") == ""
    assert _walls_display("Stone Walls") == "Pierre"
    assert _walls_display("Palisade") == "Bois"
    assert _walls_display("Wooden Walls") == "Bois"
    assert _walls_display("Fortified Walls") == "Fortifiés"
    assert _walls_display("Partial") == "Partiels"
    assert _walls_display("Yes") == "Pierre"


def test_type_display_translates_the_known_vocabulary() -> None:
    """The map types: Hybride/Terrestre/Aquatique..., unknown rides as-is."""
    assert _type_display("Hybrid") == "Hybride"
    assert _type_display("Land") == "Terrestre"
    assert _type_display("Water") == "Aquatique"
    assert _type_display("Custom Weird Type") == "Custom Weird Type"
    assert _type_display("") == ""


def test_props_lines_are_backticked_tags() -> None:
    """The subtitle tags: backticked, one vocabulary each."""
    props = _map_props_lines("Hybrid", "Stone Walls", "No", "2", "Up to 8")
    assert props == [
        "`Hybride`",
        "`Murs : Pierre`",
        "`2 TC au départ`",
    ], f"the nominal 8-player capacity stays silent — got {props}"


def test_props_lines_capacity_below_nominal_rides() -> None:
    """A below-nominal capacity rides as a player-count tag."""
    props = _map_props_lines("Land", "None", "Yes", "0", "Up to 4")
    assert "`Jusqu'à 4 joueurs`" in props
    assert "`Nomade`" in props, "the Liquipedia nomad flag rides"
    assert "`Terrestre`" in props
    assert not any("Murs" in tag for tag in props), "walls=None hides the tag"


def test_props_lines_nomad_from_tc_zero() -> None:
    """A TC=0 start tags Nomade even without the Liquipedia flag."""
    props = _map_props_lines("Land", "", "No", "0", "")
    assert "`Nomade`" in props, "a TC=0 start is a nomad start"


def test_props_lines_hide_bool_garbage() -> None:
    """The amputation era's True/False residue never renders."""
    props = _map_props_lines("", "True", "False", "2", "")
    assert props == ["`2 TC au départ`"], f"only the TC tag survives — got {props}"
