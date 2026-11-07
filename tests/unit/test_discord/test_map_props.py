"""The map post's property lines: English labels, normalized walls.

Liquipedia only serves English content (owner direction 2026-11-07):
the post's props speak the same vocabulary as the tags — Walls
No/Wood/Stone/Partial, Nomad Yes/No, TCs, Capacity — and the infobox's
``None`` never leaks onto a post.
"""

from __future__ import annotations

from kingdoms.discord.maps_forum import _map_props_lines, _walls_display


def test_walls_display_normalizes_to_english() -> None:
    """The walls vocabulary: No / Wood / Stone / Partial, empty hides."""
    assert _walls_display("") == ""
    assert _walls_display("None") == ""
    assert _walls_display("No") == ""
    assert _walls_display("Stone Walls") == "Stone"
    assert _walls_display("Palisade") == "Wood"
    assert _walls_display("Wooden Walls") == "Wood"
    assert _walls_display("Partial") == "Partial"
    assert _walls_display("Yes") == "Stone"


def test_props_lines_are_english() -> None:
    """Type/Walls/Nomad/TCs/Capacity — English labels, English values."""
    props = _map_props_lines("Hybrid", "Stone Walls", "No", "2", "Up to 8")
    assert props == [
        "**Type** : Hybrid",
        "**Walls** : Stone",
        "**Nomad** : No",
        "**TCs** : 2",
        "**Capacity** : Up to 8",
    ]


def test_props_lines_nomad_yes_and_hidden_walls() -> None:
    """Nomad renders Yes; a walls=None infobox hides the line entirely."""
    props = _map_props_lines("Land", "None", "Yes", "1", "Up to 8")
    assert "**Nomad** : Yes" in props
    assert not any(line.startswith("**Walls**") for line in props), (
        "walls=None must hide the line, never render 'None'"
    )
    assert "**TCs** : 1" in props, "the TC count renders from 1"
    assert "**Capacity** : Up to 8" in props, "never 'Capacité' — English only"


def test_props_lines_hide_bool_garbage() -> None:
    """The amputation era's True/False residue never renders."""
    props = _map_props_lines("", "True", "False", "2", "")
    assert props == ["**TCs** : 2"], f"only the TC count survives — got {props}"
