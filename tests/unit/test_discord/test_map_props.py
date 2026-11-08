"""The map post's subtitle tags: backticked FILTER SLUGS.

English, lowercase, never translated — they are query keys the users
filter on (owner direction 2026-11-08). The valid vocabulary: the
Liquipedia type, the walls, the player count (silent at the nominal
8), nomad (the flag or a TC=0 start), the multi-TC start. The
open/closed/semi-open/chaotic classification is the designers'
vocabulary — delegated to kingdoms-services#348, never shown from
the import.
"""

from __future__ import annotations

from kingdoms.discord.maps_forum import _map_props_lines, _walls_slug


def test_walls_slug_normalizes_to_the_filter_vocabulary() -> None:
    """The walls slugs: stone-walls / palisade-walls / fortified-walls."""
    assert _walls_slug("") == ""
    assert _walls_slug("None") == ""
    assert _walls_slug("No") == ""
    assert _walls_slug("Stone Walls") == "stone-walls"
    assert _walls_slug("Palisade") == "palisade-walls"
    assert _walls_slug("Wooden Walls") == "palisade-walls"
    assert _walls_slug("Fortified Walls") == "fortified-walls"
    assert _walls_slug("Partial") == "partial-walls"
    assert _walls_slug("Yes") == "stone-walls"


def test_props_lines_are_backticked_filter_slugs() -> None:
    """The subtitle tags: backticked, English, lowercase."""
    props = _map_props_lines("Hybrid", "Stone Walls", "No", "2", "Up to 8")
    assert props == [
        "`hybrid`",
        "`stone-walls`",
        "`2 TCs start`",
    ], f"the nominal 8-player capacity stays silent — got {props}"


def test_props_lines_capacity_below_nominal_rides() -> None:
    """A below-nominal capacity rides as a player-count tag."""
    props = _map_props_lines("Land", "None", "Yes", "0", "Up to 4")
    assert "`up to 4 players`" in props
    assert "`nomad`" in props, "the Liquipedia nomad flag rides"
    assert "`land`" in props
    assert not any("walls" in tag for tag in props), "walls=None hides the tag"


def test_props_lines_nomad_from_tc_zero() -> None:
    """A TC=0 start tags nomad even without the Liquipedia flag."""
    props = _map_props_lines("Land", "", "No", "0", "")
    assert "`nomad`" in props, "a TC=0 start is a nomad start"


def test_props_lines_hide_bool_garbage() -> None:
    """The amputation era's True/False residue never renders."""
    props = _map_props_lines("", "True", "False", "2", "")
    assert props == ["`2 TCs start`"], f"only the TC tag survives — got {props}"
