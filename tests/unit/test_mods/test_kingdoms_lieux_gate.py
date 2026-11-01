"""lieux-et-conseil-v1 (Drasah 01/11) — the canary gate around the castle hub.

Nilrem (``k-nilrem``) is the only canary realm while the beta runs: it
renders the CASTLE HUB (five doors, no stats on the sheet, the council
salon renamed « Discussions »). The player kingdoms keep the classic
Le-Royaume sheet — removing the gate generalises the rework
(canary-gate-v1: the declaration wins, never the live state).
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import discord

from kingdoms.mods.kingdoms.kingdom_lieux import (
    KingdomLieuComptesButton,
    KingdomLieuConseilButton,
    KingdomLieuEntreeButton,
    KingdomLieuParoisseButton,
    KingdomLieuRempartsButton,
    KingdomLieuVoliereButton,
    _strings,
    canary_salon_display,
    entree_view,
    hub_buttons,
    is_canary_realm,
    register_kingdom_lieux_items,
)
from kingdoms.mods.kingdoms.kingdom_realm_content import _build_overview
from kingdoms.mods.kingdoms.service import TEST_KINGDOM_ID


class _FakeBot:
    def __init__(self) -> None:
        self._dynamic_items: set[type] = set()

    def add_dynamic_items(self, *items: type) -> None:
        self._dynamic_items.update(items)


def _kingdom(kid: str) -> Any:
    return SimpleNamespace(id=kid, name="Nilrem" if kid == TEST_KINGDOM_ID else "A")


def _walk_text(children: Any) -> str:
    chunks: list[str] = []
    for child in children:
        if isinstance(child, discord.ui.TextDisplay):
            chunks.append(str(getattr(child, "content", "") or ""))
        chunks.append(_walk_text(getattr(child, "children", []) or []))
    return "\n".join(chunks)


def _walk_buttons(children: Any) -> list[str]:
    labels: list[str] = []
    for child in children:
        if isinstance(child, discord.ui.Button):
            labels.append(str(child.label))
        for sub in getattr(child, "children", []) or []:
            labels.extend(_walk_buttons([sub]))
    return labels


def test_gate_is_declaration_only() -> None:
    assert is_canary_realm(_kingdom(TEST_KINGDOM_ID)) is True
    assert is_canary_realm(_kingdom("k-3")) is False
    assert is_canary_realm(None) is False


def test_items_registered_on_bot() -> None:
    bot = _FakeBot()
    register_kingdom_lieux_items(bot)
    expected = {
        KingdomLieuEntreeButton,
        KingdomLieuConseilButton,
        KingdomLieuRempartsButton,
        KingdomLieuComptesButton,
        KingdomLieuParoisseButton,
        KingdomLieuVoliereButton,
    }
    assert expected <= bot._dynamic_items


def test_hub_buttons_are_the_five_doors() -> None:
    labels = [type(b).__name__ for b in hub_buttons("fr")]
    assert labels == [
        "KingdomLieuConseilButton",
        "KingdomLieuRempartsButton",
        "KingdomLieuComptesButton",
        "KingdomLieuParoisseButton",
        "KingdomLieuVoliereButton",
    ]
    strings = _strings("fr")
    for key in (
        "conseil_button",
        "remparts_button",
        "comptes_button",
        "paroisse_button",
        "voliere_button",
    ):
        assert strings[key]


def test_canary_hub_shows_one_entree_door() -> None:
    strings = _strings("fr")
    kingdom = _kingdom(TEST_KINGDOM_ID)
    view = _build_overview(
        strings,
        kingdom,
        {"members": [], "wallet": 3, "territories": [], "purchases": {}, "parish": {}},
    )
    labels = _walk_buttons(view.children)
    # entree-v1: the hub carries the ONE 🏰 Entrée door — the five
    # places moved into its ephemeral chooser.
    assert strings["entree_button"] in labels
    for key in (
        "conseil_button",
        "remparts_button",
        "comptes_button",
        "paroisse_button",
        "voliere_button",
    ):
        assert strings[key] not in labels
    # the stats block left the hub (it moved into the Council)
    assert strings["treasury"] not in _walk_text(view.children)


def test_entree_chooser_holds_the_five_doors() -> None:
    strings = _strings("fr")
    view = entree_view("fr")
    assert strings["entree_title"] in _walk_text(view.children)
    labels = _walk_buttons(view.children)
    for key in (
        "conseil_button",
        "remparts_button",
        "comptes_button",
        "paroisse_button",
        "voliere_button",
    ):
        assert strings[key] in labels


def test_player_kingdom_keeps_classic_sheet() -> None:
    strings = _strings("fr")
    view = _build_overview(
        strings,
        _kingdom("k-3"),
        {"members": [], "wallet": 3, "territories": [], "purchases": {}, "parish": {}},
    )
    labels = _walk_buttons(view.children)
    assert strings["conseil_button"] not in labels
    assert strings["treasury"] in _walk_text(view.children)


def test_council_salon_renamed_for_canary_only() -> None:
    assert (
        canary_salon_display(
            "salle-du-conseil", "💬 salle du conseil", _kingdom(TEST_KINGDOM_ID)
        )
        == "💬 discussions"
    )
    assert (
        canary_salon_display(
            "salle-du-conseil", "💬 salle du conseil", _kingdom("k-3")
        )
        == "💬 salle du conseil"
    )
    assert (
        canary_salon_display("territoire", "🗺️ territoire", _kingdom(TEST_KINGDOM_ID))
        == "🗺️ territoire"
    )
