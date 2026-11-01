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
    import asyncio

    from kingdoms.mods.kingdoms.kingdom_lieux import build_conseil_view

    strings = _merged_fr()
    wiring = SimpleNamespace(kingdoms_service=None)
    view, _files = asyncio.run(
        build_conseil_view(
            strings, _kingdom(TEST_KINGDOM_ID), _minimal_state(), wiring, "fr"
        )
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
    import asyncio

    from kingdoms.mods.kingdoms.kingdom_lieux import build_conseil_view

    strings = _merged_fr()
    wiring = SimpleNamespace(kingdoms_service=None)
    state = _minimal_state({"explorateur_stock": 1, "traquenard": 2})
    view, _files = asyncio.run(
        build_conseil_view(
            strings, _kingdom(TEST_KINGDOM_ID), state, wiring, "fr"
        )
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


# ---------------------------------------------------------------------------
# comptes-rows-v1 (Drasah 01/11) — the canary Chambre des comptes.
# ---------------------------------------------------------------------------


def _ledger_kingdom(kid: str) -> Any:
    return SimpleNamespace(
        id=kid,
        name="Nilrem",
        tech_points_bank=3,
        market_registry=[{"item": "traquenard", "detail": "", "cost": 2, "at": 1730000000}],
        market_actions=[{"item": "corruption", "detail": "map alpha", "at": 1730000100}],
    )


def _ledger_wiring() -> Any:
    return SimpleNamespace(kingdoms_service=None, attacks_service=None)


def _view_buttons(view: Any) -> list[Any]:
    return list(getattr(view, "children", []) or [])


def test_canary_comptes_strip_removes_the_purchases_section() -> None:
    from kingdoms.mods.kingdoms.kingdom_lieux import _strip_purchases

    strings = _merged_fr()
    content = (
        "# Chambre des comptes\n\n"
        "Bilan — dépensé : 0 ⚙️ · trésor : 1 ⚙️\n\n"
        f"## {strings['market_ledger_purchases_title']}\n"
        "🪤 Traquenard — · 0 ⚙️ · 31/10 13:16\n\n"
        f"## {strings['market_ledger_cards_title']}\n"
        "🪤 Traquenard — ×1"
    )
    stripped = _strip_purchases(content, strings)
    # the base window keeps the balance + the cards in hand ONLY
    assert strings["market_ledger_purchases_title"] not in stripped
    assert "Traquenard — · 0 ⚙️" not in stripped
    assert strings["market_ledger_cards_title"] in stripped
    assert "Traquenard — ×1" in stripped
    assert "trésor" in stripped


def test_canary_comptes_view_hides_purchases_and_adds_history_buttons() -> None:
    from kingdoms.mods.kingdoms.kingdom_lieux import _comptes_canary_view

    strings = _merged_fr()
    held = [
        ("traquenard", "🪤 Traquenard — ×1", 1),
        ("explorateur", "🛡️ Explorateur — ×3", 3),
    ]
    view = _comptes_canary_view(strings, "fr", held, None)
    buttons = _view_buttons(view)
    labels = [str(b.label) for b in buttons]
    custom_ids = [str(b.custom_id) for b in buttons]
    # line 1: the two history buttons + the red Sortir (no Utiliser —
    # no card is selected on the base window)
    assert strings["market_hist_achats_button"] in labels
    assert strings["market_hist_actions_button"] in labels
    assert "kingdoms:lieux:hist:achats" in custom_ids
    assert "kingdoms:lieux:hist:actions" in custom_ids
    assert "kingdoms:lieux:sortir" in custom_ids
    assert not any(cid.startswith("kingdoms:market:use:") for cid in custom_ids)
    for cid in ("kingdoms:lieux:hist:achats", "kingdoms:lieux:hist:actions", "kingdoms:lieux:sortir"):
        assert [b for b in buttons if str(b.custom_id) == cid][0].row == 0
    # the cards ride the rows below, one canary cardinfo button each
    assert "kingdoms:lieux:cardinfo:traquenard" in custom_ids
    assert "kingdoms:lieux:cardinfo:explorateur" in custom_ids
    card_rows = sorted(
        b.row for b in buttons if str(b.custom_id).startswith("kingdoms:lieux:cardinfo:")
    )
    assert card_rows[0] >= 1


def test_canary_comptes_utiliser_rides_line_one_for_a_usable_card() -> None:
    from kingdoms.mods.kingdoms.kingdom_lieux import _comptes_canary_view

    strings = _merged_fr()
    held = [("traquenard", "🪤 Traquenard — ×1", 1)]
    view = _comptes_canary_view(strings, "fr", held, "traquenard")
    buttons = _view_buttons(view)
    custom_ids = [str(b.custom_id) for b in buttons]
    use = [b for b in buttons if str(b.custom_id) == "kingdoms:market:use:traquenard"]
    assert use, "the selected usable card adds the Utiliser button"
    assert use[0].style == discord.ButtonStyle.success
    assert use[0].row == 0
    # Utiliser is the FIRST button of the view (line 1, slot 1)
    assert custom_ids[0] == "kingdoms:market:use:traquenard"


def test_history_button_labels_styles_and_registration() -> None:
    from kingdoms.mods.kingdoms.kingdom_lieux import (
        KingdomLieuCardInfoButton,
        KingdomLieuHistButton,
    )

    strings = _merged_fr()
    achats = KingdomLieuHistButton("achats", strings, row=0)
    actions = KingdomLieuHistButton("actions", strings, row=0)
    assert achats.item.label == strings["market_hist_achats_button"]
    assert actions.item.label == strings["market_hist_actions_button"]
    for button in (achats, actions):
        assert button.item.style == discord.ButtonStyle.success
    card = KingdomLieuCardInfoButton("traquenard", strings, row=1)
    assert card.item.custom_id == "kingdoms:lieux:cardinfo:traquenard"
    # the canary buttons ride the lieu register
    bot = _FakeBot()
    register_kingdom_lieux_items(bot)
    assert KingdomLieuHistButton in bot._dynamic_items
    assert KingdomLieuCardInfoButton in bot._dynamic_items


# ---------------------------------------------------------------------------
# conseil-objectif-v2 (Drasah 01/11) — dropdown goals + the council sheet.
# ---------------------------------------------------------------------------


def test_conseil_base_carries_intro_rank_stats_and_goals(monkeypatch) -> None:
    import asyncio

    from kingdoms.mods.kingdoms import civ_crests
    from kingdoms.mods.kingdoms.kingdom_lieux import build_conseil_view

    async def _fake_crest_files(civ_keys: Any) -> list[Any]:
        return [SimpleNamespace(filename=f"{civ_keys[0]}.png")]

    monkeypatch.setattr(civ_crests, "civ_crest_files", _fake_crest_files)

    strings = _merged_fr()
    lieu = _strings("fr")
    kingdom = SimpleNamespace(
        id=TEST_KINGDOM_ID,
        name="Nilrem",
        civilizations=["azteques", "britons"],
        council_objectives={
            "target_kingdom": "k-2",
            "target_kingdom_label": "HeN",
            "target_territory": "arabia",
            "target_territory_label": "Arabie",
            "target_alliance": "francs",
            "target_alliance_label": "Francs",
        },
    )
    state = _minimal_state()
    state["wallet"] = 4
    state["territories"] = [SimpleNamespace(), SimpleNamespace(), SimpleNamespace()]
    view, files = asyncio.run(
        build_conseil_view(
            strings,
            kingdom,
            state,
            SimpleNamespace(kingdoms_service=None),
            "fr",
            rank=(2, 5),
            viewer_is_king=True,
        )
    )
    text = _walk_text(view.children)
    assert lieu["conseil_intro_l1"] in text
    assert lieu["conseil_intro_l2"] in text
    assert lieu["conseil_intro_l3"] in text
    assert lieu["conseil_classement"].format("2/5") in text
    assert lieu["conseil_stats"].format(4, 3, 2) in text
    assert lieu["conseil_classement_hint"] in text
    # the old overview block left the base sheet
    assert strings["members"] not in text
    # the goals ride the sheet — one line EACH (conseil-objectif-
    # lignes-fix: the pipe line read badly)
    goals = "\n".join(
        [
            lieu["conseil_objectif_kingdom"].format("HeN"),
            lieu["conseil_objectif_map"].format("Arabie"),
            lieu["conseil_objectif_alliance"].format("Francs"),
        ]
    )
    assert goals in text
    # the targeted alliance's blason rides as a REFERENCED attachment
    galleries = [
        child
        for child in view.children
        if isinstance(child, discord.ui.MediaGallery)
    ]
    assert any(
        getattr(item, "media", "") == "attachment://francs.png"
        for gallery in galleries
        for item in getattr(gallery, "items", [])
    )
    assert any(getattr(f, "filename", "") == "francs.png" for f in files)
    # the empty state keeps the sheet clean — no crest, just the note
    empty = SimpleNamespace(
        id=TEST_KINGDOM_ID,
        name="Nilrem",
        civilizations=[],
        council_objectives={},
    )
    view_empty, files_empty = asyncio.run(
        build_conseil_view(
            strings,
            empty,
            _minimal_state(),
            SimpleNamespace(kingdoms_service=None),
            "fr",
        )
    )
    assert lieu["conseil_objectifs_none"] in _walk_text(view_empty.children)
    assert len(files_empty) == 1


def test_objectif_button_follows_the_crown() -> None:
    import asyncio

    from kingdoms.mods.kingdoms.kingdom_lieux import (
        KingdomLieuObjectifButton,
        build_conseil_view,
        register_kingdom_lieux_items,
    )

    strings = _merged_fr()
    wiring = SimpleNamespace(kingdoms_service=None)
    kingdom = _kingdom(TEST_KINGDOM_ID)
    view, _ = asyncio.run(
        build_conseil_view(
            strings, kingdom, _minimal_state(), wiring, "fr", viewer_is_king=True
        )
    )
    line_one = list(_action_rows(view.children)[0].children)
    labels = [str(button.label) for button in line_one]
    assert labels == [
        strings["seigneurie_open_button"],
        _strings("fr")["objectif_button"],
        _strings("fr")["sortir_button"],
    ]
    assert line_one[1].style == discord.ButtonStyle.success
    assert line_one[1].disabled is False
    # a subject sees the SAME button, red+disabled (never hidden)
    view_subject, _ = asyncio.run(
        build_conseil_view(
            strings, kingdom, _minimal_state(), wiring, "fr", viewer_is_king=False
        )
    )
    line_subject = list(_action_rows(view_subject.children)[0].children)
    assert line_subject[1].style == discord.ButtonStyle.danger
    assert line_subject[1].disabled is True
    # restart-proof registration
    bot = _FakeBot()
    register_kingdom_lieux_items(bot)
    assert KingdomLieuObjectifButton in bot._dynamic_items


def test_objectif_read_view_offers_edit_and_quit() -> None:
    from kingdoms.mods.kingdoms.kingdom_lieux import (
        _objectifs_read_content,
        _objectifs_read_view,
    )

    lieu = _strings("fr")
    kingdom = SimpleNamespace(
        id=TEST_KINGDOM_ID,
        name="Nilrem",
        council_objectives={"target_kingdom": "k-2", "target_kingdom_label": "HeN"},
    )
    view = _objectifs_read_view(
        SimpleNamespace(kingdoms_service=None), kingdom, "fr", {"k-2": "HeN"}, {}, {}
    )
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    labels = [str(b.label) for b in buttons]
    assert labels == [lieu["objectif_edit_button"], lieu["objectif_quit_button"]]
    content = _objectifs_read_content("fr", kingdom)
    assert lieu["objectif_picker_title"].format("Nilrem") in content
    assert lieu["conseil_objectif_kingdom"].format("HeN") in content
    assert lieu["objectif_read_hint"] in content


def test_objectif_picker_pages_and_options() -> None:
    from kingdoms.mods.kingdoms.kingdom_lieux import _objectifs_picker

    lieu = _strings("fr")
    wiring = SimpleNamespace(kingdoms_service=None)
    kingdom = SimpleNamespace(
        id=TEST_KINGDOM_ID,
        name="Nilrem",
        council_objectives={
            "target_territory": "map-7",
            "target_territory_label": "Map 7",
        },
    )
    staged = dict(kingdom.council_objectives)
    kingdoms_catalog = {"k-2": "HeN", "k-3": "Gwen"}
    maps_catalog = {f"map-{i}": f"Map {i}" for i in range(1, 61)}
    civs_catalog = {f"civ-{i}": f"Civ {i}" for i in range(1, 41)}
    # a STAGED goal rides as a « ✏️ change » button — its dropdown
    # comes back through « changer » (the reveal below)
    view = _objectifs_picker(
        wiring, kingdom, "fr", kingdoms_catalog, maps_catalog, civs_catalog, staged
    )
    selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
    assert len(selects) == 2  # kingdom + civ — the map is a change button
    change = [
        c
        for c in view.children
        if isinstance(c, discord.ui.Button) and c.label and "Map 7" in str(c.label)
    ]
    assert len(change) == 1
    assert "✏️" in str(change[0].label)
    # revealed, the map dropdown leads with the pinned goal
    view_revealed = _objectifs_picker(
        wiring,
        kingdom,
        "fr",
        kingdoms_catalog,
        maps_catalog,
        civs_catalog,
        staged,
        reveal=("target_territory",),
    )
    selects = [
        c for c in view_revealed.children if isinstance(c, discord.ui.Select)
    ]
    assert len(selects) == 3
    for select in selects:
        assert len(select.options) <= 25  # the Discord cap, always
    # Discord requires a select option value of 1-100 characters —
    # the « Aucun » sentinel rides "none" on the wire (NEVER "").
    assert all(select.options[0].value == "none" for select in selects)
    assert all(
        option.value for select in selects for option in select.options
    )
    map_select = selects[1]
    assert map_select.options[1].value == "map-7"
    assert "Map 7" in map_select.options[1].label
    # a select is ALWAYS alone in its action row (Discord) — the
    # flips ride their OWN rows (2 = maps, 4 = civs + Valider/Quitter)
    rows_used: dict[int, int] = {}
    for child in view_revealed.children:
        rows_used[child.row or 0] = rows_used.get(child.row or 0, 0) + 1
    assert rows_used[0] == 1  # kingdom select
    assert rows_used[1] == 1  # map select
    assert rows_used[2] == 2  # maps ◀️▶️
    assert rows_used[3] == 1  # civ select
    assert rows_used[4] == 4  # civs ◀️▶️ + Valider + Quitter
    buttons = [
        c for c in view_revealed.children if isinstance(c, discord.ui.Button)
    ]
    labels = [str(b.label) for b in buttons]
    assert labels[-2:] == [
        lieu["objectif_validate_button"],
        lieu["objectif_quit_button"],
    ]
    flips = [b for b in buttons if b.label is None]
    assert len(flips) == 4
    assert flips[0].disabled is True  # maps ◀ on page 0
    assert flips[1].disabled is False
    assert flips[2].disabled is True  # civs ◀ on page 0
    assert flips[3].disabled is False
    # page two serves the NEXT slice of maps, the goal stays pinned
    view_two = _objectifs_picker(
        wiring,
        kingdom,
        "fr",
        kingdoms_catalog,
        maps_catalog,
        civs_catalog,
        staged,
        map_page=1,
        reveal=("target_territory",),
    )
    selects_two = [c for c in view_two.children if isinstance(c, discord.ui.Select)]
    page_one_values = {o.value for o in selects_two[1].options}
    assert "map-25" in page_one_values
    assert "map-1" not in page_one_values
    assert selects_two[1].options[1].value == "map-7"


def test_objectif_picker_choice_becomes_a_change_button() -> None:
    import asyncio

    from kingdoms.mods.kingdoms.kingdom_lieux import _objectifs_picker

    wiring = SimpleNamespace(kingdoms_service=None)
    kingdom = SimpleNamespace(id=TEST_KINGDOM_ID, name="Nilrem", council_objectives={})
    view = _objectifs_picker(
        wiring,
        kingdom,
        "fr",
        {"k-2": "HeN"},
        {"m-1": "Ile du Pacifique"},
        {"c-1": "Huns"},
        {},
    )
    kingdom_select = next(c for c in view.children if isinstance(c, discord.ui.Select))
    kingdom_select.values = ["k-2"]
    edited: dict[str, Any] = {}

    class _Response:
        async def edit_message(self, **kwargs: Any) -> None:
            edited.update(kwargs)

    asyncio.run(kingdom_select.callback(SimpleNamespace(response=_Response())))
    # the chosen goal STAGES (never saves on the spot) and the dropdown
    # transforms into a « ✏️ change » button carrying the chosen value
    assert "view" in edited and "content" in edited
    new_selects = [c for c in edited["view"].children if isinstance(c, discord.ui.Select)]
    assert len(new_selects) == 2  # the kingdom dropdown is GONE
    change_buttons = [
        c
        for c in edited["view"].children
        if isinstance(c, discord.ui.Button) and c.label and "HeN" in str(c.label)
    ]
    assert len(change_buttons) == 1
    assert "✏️" in str(change_buttons[0].label)
    labels = [
        str(c.label)
        for c in edited["view"].children
        if isinstance(c, discord.ui.Button) and c.label
    ]
    assert labels[-2:] == [
        _strings("fr")["objectif_validate_button"],
        _strings("fr")["objectif_quit_button"],
    ]
    assert "HeN" in edited["content"]


def test_objectif_picker_sentinel_and_change_round_trip() -> None:
    import asyncio

    from kingdoms.mods.kingdoms.kingdom_lieux import _objectifs_picker

    wiring = SimpleNamespace(kingdoms_service=None)
    kingdom = SimpleNamespace(id=TEST_KINGDOM_ID, name="Nilrem", council_objectives={})
    staged = {"target_kingdom": "k-2", "target_kingdom_label": "HeN"}
    view = _objectifs_picker(
        wiring, kingdom, "fr", {"k-2": "HeN"}, {}, {}, staged
    )
    # a staged goal rides as a change button — « changer » reveals it
    change = next(
        c
        for c in view.children
        if isinstance(c, discord.ui.Button) and c.label and "HeN" in str(c.label)
    )
    edited: dict[str, Any] = {}

    class _Response:
        async def edit_message(self, **kwargs: Any) -> None:
            edited.update(kwargs)

    asyncio.run(change.callback(SimpleNamespace(response=_Response())))
    select = next(
        c for c in edited["view"].children if isinstance(c, discord.ui.Select)
    )
    assert select.options[1].value == "k-2"  # the staged goal stays pinned ✅
    select.values = [select.options[0].value]  # the « Aucun » sentinel
    cleared: dict[str, Any] = {}

    class _Response2:
        async def edit_message(self, **kwargs: Any) -> None:
            cleared.update(kwargs)

    asyncio.run(select.callback(SimpleNamespace(response=_Response2())))
    # choosing the sentinel CLEARS the staged goal — back to a dropdown
    cleared_selects = [
        c for c in cleared["view"].children if isinstance(c, discord.ui.Select)
    ]
    assert len(cleared_selects) == 3
    assert cleared_selects[0].options[0].value == "none"  # no pinned goal anymore
    assert "— non défini" in cleared["content"]


def test_objectif_validate_saves_all_and_returns_to_read() -> None:
    import asyncio

    from kingdoms.mods.kingdoms.kingdom_lieux import _objectifs_picker

    saved: list[Any] = []

    class _Service:
        async def save_kingdom(self, kingdom: Any) -> Any:
            saved.append(kingdom)
            return kingdom

    wiring = SimpleNamespace(kingdoms_service=_Service())
    kingdom = SimpleNamespace(id=TEST_KINGDOM_ID, name="Nilrem", council_objectives={})
    staged = {
        "target_kingdom": "k-2",
        "target_kingdom_label": "HeN",
        "target_territory": "m-1",
        "target_territory_label": "Ile du Pacifique",
        "target_alliance": "",
        "target_alliance_label": "",
    }
    view = _objectifs_picker(
        wiring,
        kingdom,
        "fr",
        {"k-2": "HeN"},
        {"m-1": "Ile du Pacifique"},
        {"c-1": "Huns"},
        staged,
    )
    validate = next(
        c
        for c in view.children
        if isinstance(c, discord.ui.Button)
        and str(c.label) == _strings("fr")["objectif_validate_button"]
    )
    edited: dict[str, Any] = {}

    class _Response:
        async def edit_message(self, **kwargs: Any) -> None:
            edited.update(kwargs)

    asyncio.run(validate.callback(SimpleNamespace(response=_Response())))
    # ONE save commits ALL three kinds, empty choices included
    assert saved == [kingdom]
    assert kingdom.council_objectives["target_kingdom"] == "k-2"
    assert kingdom.council_objectives["target_territory"] == "m-1"
    assert kingdom.council_objectives["target_alliance"] == ""
    assert "updated_at" in kingdom.council_objectives
    # back to the READ sheet — Modifier + Quitter only
    labels = [
        str(c.label)
        for c in edited["view"].children
        if isinstance(c, discord.ui.Button) and c.label
    ]
    assert labels == [
        _strings("fr")["objectif_edit_button"],
        _strings("fr")["objectif_quit_button"],
    ]
    assert _strings("fr")["objectif_read_hint"] in edited["content"]


def test_objectif_save_failure_never_crashes_the_picker() -> None:
    import asyncio

    from kingdoms.mods.kingdoms.kingdom_lieux import _save_objectives

    class _Broken:
        async def save_kingdom(self, kingdom: Any) -> Any:
            raise RuntimeError("boom")

    kingdom = SimpleNamespace(id=TEST_KINGDOM_ID, council_objectives={})
    staged = {"target_alliance": "c-1", "target_alliance_label": "Huns"}
    assert (
        asyncio.run(
            _save_objectives(
                SimpleNamespace(kingdoms_service=_Broken()), kingdom, staged
            )
        )
        is False
    )
    # the staged values still landed on the in-memory kingdom
    assert kingdom.council_objectives["target_alliance"] == "c-1"


def test_objectif_click_keeps_the_council_sheet_alive() -> None:
    # objectif-fenetre-coexist-v1: the 🎯 Objectif picker opens
    # ALONGSIDE the council sheet — a send_message window (a 2-tuple
    # registry entry) is NEVER replaced by the click, only a previous
    # PICKER (a defer+followup 3-tuple) is.
    from kingdoms.mods.kingdoms.kingdom_lieux import _objectif_replaces_previous

    assert _objectif_replaces_previous(None) is False
    assert _objectif_replaces_previous((object(), 1.0)) is False  # the sheet
    assert _objectif_replaces_previous((object(), 1.0, object())) is True  # a picker
