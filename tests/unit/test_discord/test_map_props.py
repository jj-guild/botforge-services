"""The map post's property lines: French labels, French vocabulary.

The stored docs carry Liquipedia's English (the provider's data); the
post is French UI — the labels translate (Type/Murs/Nomade/TCs/Capacité)
and the known vocabulary too (Pierre/Bois/Partiels, Hybride/Terrestre,
Oui/Non). The tags stay English slugs — they are query keys, never
display (owner directions 2026-11-07/08).
"""

from __future__ import annotations

from kingdoms.discord.maps_forum import (
    _map_props_lines,
    _type_display,
    _walls_display,
)


def test_walls_display_normalizes_to_french() -> None:
    """The walls vocabulary: Pierre / Bois / Partiels, empty hides."""
    assert _walls_display("") == ""
    assert _walls_display("None") == ""
    assert _walls_display("No") == ""
    assert _walls_display("Stone Walls") == "Pierre"
    assert _walls_display("Palisade") == "Bois"
    assert _walls_display("Wooden Walls") == "Bois"
    assert _walls_display("Partial") == "Partiels"
    assert _walls_display("Yes") == "Pierre"


def test_type_display_translates_the_known_vocabulary() -> None:
    """The map types: Hybride/Terrestre/Aquatique..., unknown rides as-is."""
    assert _type_display("Hybrid") == "Hybride"
    assert _type_display("Land") == "Terrestre"
    assert _type_display("Water") == "Aquatique"
    assert _type_display("Open") == "Ouverte"
    assert _type_display("Semi-open") == "Semi-ouverte"
    assert _type_display("Closed") == "Fermée"
    assert _type_display("Fortified") == "Fortifiée"
    assert _type_display("Custom Weird Type") == "Custom Weird Type"
    assert _type_display("") == ""


def test_props_lines_are_french() -> None:
    """Type/Murs/Nomade/TCs/Capacité — French labels, French values."""
    props = _map_props_lines("Hybrid", "Stone Walls", "No", "2", "Up to 8")
    assert props == [
        "**Type** : Hybride",
        "**Murs** : Pierre",
        "**Nomade** : Non",
        "**TCs** : 2",
        "**Capacité** : Up to 8",
    ]


def test_props_lines_nomad_yes_and_hidden_walls() -> None:
    """Nomad renders Oui; a walls=None infobox hides the line entirely."""
    props = _map_props_lines("Land", "None", "Yes", "1", "Up to 8")
    assert "**Nomade** : Oui" in props
    assert not any(line.startswith("**Murs**") for line in props), (
        "walls=None must hide the line, never render 'None'"
    )
    assert "**TCs** : 1" in props, "the TC count renders from 1"
    assert "**Capacité** : Up to 8" in props
    assert "**Type** : Terrestre" in props


def test_props_lines_hide_bool_garbage() -> None:
    """The amputation era's True/False residue never renders."""
    props = _map_props_lines("", "True", "False", "2", "")
    assert props == ["**TCs** : 2"], f"only the TC count survives — got {props}"
