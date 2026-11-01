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


def test_canary_hub_carries_the_castle_above_the_panel() -> None:
    # live crash 01/11 (Nilrem's Le-Royaume empty): the illustration-top
    # rewrite mistyped the item class (discord.ui.MediaGalleryItem, which
    # the deployed discord.py does not expose) — every media-bearing view
    # died at build. The castle must ride ABOVE the panel, first child.
    strings = _strings("fr")
    view = _build_overview(
        strings,
        _kingdom(TEST_KINGDOM_ID),
        {"members": [], "wallet": 3, "territories": [], "purchases": {}, "parish": {}},
    )
    assert view.children
    assert isinstance(view.children[0], discord.MediaGallery)
    assert view.children[0].items[0].media == "attachment://royaume.png"


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


# ---------------------------------------------------------------------------
# lieux-rows-v1 (Drasah 01/11) — the button rules of every lieu view.
# ---------------------------------------------------------------------------


def _action_rows(children: Any) -> list[discord.ui.ActionRow]:
    rows: list[discord.ui.ActionRow] = []
    for child in children:
        if isinstance(child, discord.ui.ActionRow):
            rows.append(child)
        rows.extend(_action_rows(getattr(child, "children", []) or []))
    return rows


def _merged_fr() -> dict[str, str]:
    from kingdoms.mods.kingdoms.kingdom_realm_content import _strings as _realm

    return _realm("fr")


def _minimal_state(purchases: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "members": [],
        "wallet": 0,
        "territories": [],
        "purchases": purchases or {},
        "parish": {"tier": 1, "max_tier": 3, "next_name": "Église", "cost": 2},
    }


def test_sortir_button_registered_and_red() -> None:
    from kingdoms.mods.kingdoms.kingdom_lieux import KingdomLieuSortirButton

    bot = _FakeBot()
    register_kingdom_lieux_items(bot)
    assert KingdomLieuSortirButton in bot._dynamic_items
    sortir = KingdomLieuSortirButton("🚪 Sortir")
    assert sortir.item.style == discord.ButtonStyle.danger
    assert sortir.item.custom_id == "kingdoms:lieux:sortir"


def test_conseil_rows_follow_the_button_rules() -> None:
    from kingdoms.mods.kingdoms.kingdom_lieux import build_conseil_view

    strings = _merged_fr()
    wiring = SimpleNamespace(kingdoms_service=None)
    view, _files = build_conseil_view(
        strings, _kingdom(TEST_KINGDOM_ID), _minimal_state(), wiring, "fr"
    )
    rows = _action_rows(view.children)
    assert len(rows) == 2
    first = list(rows[0].children)
    second = list(rows[1].children)
    # line 1: default action GREEN + Sortir RED last
    assert first[0].style == discord.ButtonStyle.success
    assert first[-1].label == _strings("fr")["sortir_button"]
    assert first[-1].style == discord.ButtonStyle.danger
    # line 2: the cards stay VISIBLE, gray+disabled while out of stock
    assert len(second) == 2
    for button in second:
        assert button.disabled is True
        assert button.style == discord.ButtonStyle.secondary


def test_conseil_cards_green_while_held() -> None:
    from kingdoms.mods.kingdoms.kingdom_lieux import build_conseil_view

    strings = _merged_fr()
    wiring = SimpleNamespace(kingdoms_service=None)
    state = _minimal_state({"explorateur_stock": 1, "traquenard": 2})
    view, _files = build_conseil_view(
        strings, _kingdom(TEST_KINGDOM_ID), state, wiring, "fr"
    )
    rows = _action_rows(view.children)
    for button in rows[1].children:
        assert button.disabled is False
        assert button.style == discord.ButtonStyle.success


def test_remparts_rows_follow_the_button_rules() -> None:
    from kingdoms.mods.kingdoms.kingdom_lieux import _remparts_rows

    strings = _merged_fr()
    wiring = SimpleNamespace(kingdoms_service=None)
    rows = _remparts_rows(strings, _minimal_state(), wiring, "fr")
    assert len(rows) == 2
    first, second = (list(row) for row in rows)
    # line 1: the war actions GREEN + Sortir RED last
    for button in first[:-1]:
        assert button.item.style == discord.ButtonStyle.success
    assert first[-1].item.label == _strings("fr")["sortir_button"]
    assert first[-1].item.style == discord.ButtonStyle.danger
    # line 2: Garde + Patrouille 1/2 gray+disabled without stock, and
    # the Jeu d'armes card lives HERE (moved out of the Council).
    labels = [str(button.item.label) for button in second]
    assert any("Jeu d'armes" in label for label in labels)
    for button in second:
        assert button.item.disabled is True
        assert button.item.style == discord.ButtonStyle.secondary
    # with everything held, line 2 turns green
    green_state = _minimal_state(
        {
            "garde_royale_stock": 1,
            "patrouille_unlock_1": 1,
            "patrouille_unlock_2": 1,
        }
    )
    green_state["wallet"] = 999  # the Jeu d'armes card turns green too
    rows_green = _remparts_rows(
        strings,
        green_state,
        SimpleNamespace(kingdoms_service=SimpleNamespace(config=None)),
        "fr",
    )
    for button in rows_green[1]:
        assert button.item.disabled is False
        assert button.item.style == discord.ButtonStyle.success


def test_paroisse_rows_follow_the_button_rules() -> None:
    from kingdoms.mods.kingdoms.kingdom_lieux import _paroisse_rows

    strings = _merged_fr()
    kingdom = SimpleNamespace(
        id=TEST_KINGDOM_ID, name="Nilrem", arranged_marriage_stock=0
    )
    rows = _paroisse_rows(strings, kingdom, _minimal_state(), "fr")
    assert len(rows) == 2
    first, second = (list(row) for row in rows)
    # line 1: the parish actions GREEN + Sortir RED last
    assert first[-1].item.label == _strings("fr")["sortir_button"]
    assert first[-1].item.style == discord.ButtonStyle.danger
    # line 2: Mariage arrangé ALWAYS visible, gray at tier 1
    assert len(second) == 1
    assert second[0].item.disabled is True
    assert second[0].item.style == discord.ButtonStyle.secondary
    # from the Église palier with a token held, it turns green
    kingdom2 = SimpleNamespace(
        id=TEST_KINGDOM_ID, name="Nilrem", arranged_marriage_stock=1
    )
    state2 = _minimal_state()
    state2["parish"] = {"tier": 2, "max_tier": 3, "next_name": "Cathédrale", "cost": 4}
    rows2 = _paroisse_rows(strings, kingdom2, state2, "fr")
    arrange = list(rows2[1])[0]
    assert arrange.item.disabled is False
    assert arrange.item.style == discord.ButtonStyle.success
