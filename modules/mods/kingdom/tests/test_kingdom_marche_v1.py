"""marche-reference-v1 (Affaire 24) — the merchant stall, ported.

The reference Marché comes back as ONE pinned stall: the streamed
banner, the four shelves in Drasah's order, one purchase button per
article wearing its price, the revealed TCG card (art + fiche), and
the Chambre des comptes gaining the season ledger and the held-cards
mosaic. These tests lock the portable seams: the card resolver
(local-first, URL fallback), the shelf data, the fiche, the ledger,
the hand, and the restart-proof dynamic buttons.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import discord
import pytest


@pytest.mark.asyncio
async def test_card_resolver_is_local_first_with_url_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A local PNG wins; a missing card still streams its raw URL."""
    from botforge.mods.kingdom.cogs import marche_art

    assert marche_art.card_filename("jeu_d_armes") == "Jeu_darme.png"
    assert marche_art.card_filename("unknown") == "unknown.png"
    assert marche_art.card_url("sabotage").endswith("/assets/marche/Sabotage.png")
    assert marche_art.card_url("not_a_card") is None
    assert marche_art.banner_url().endswith("march%C3%A9.jpg")
    assert marche_art.resolve_card_path("sabotage") is None, "not local by default"

    monkeypatch.setattr(marche_art, "_ASSET_DIR", tmp_path)
    local = tmp_path / "Sabotage.png"
    local.write_bytes(b"\x89PNG-fake")
    assert marche_art.resolve_card_path("sabotage") == local
    assert await marche_art.card_bytes("sabotage") == b"\x89PNG-fake"


@pytest.mark.asyncio
async def test_held_cards_mosaic_encodes_and_caches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """One hand, ONE mosaic PNG, decoded + cached per fingerprint."""
    from botforge.mods.kingdom.cogs import marche_art
    from botforge.mods.kingdom.cogs.civ_crests import (
        _decode_png_rgba,
        _encode_png_rgba,
    )

    monkeypatch.setattr(marche_art, "_ASSET_DIR", tmp_path)
    marche_art._HELD_CACHE.clear()
    marche_art._HELD_ART_CACHE.clear()
    png = _encode_png_rgba(16, 20, bytes(16 * 20 * 4))
    (tmp_path / "Corruption.png").write_bytes(png)
    (tmp_path / "Explorateur.png").write_bytes(png)

    assert await marche_art.held_cards_mosaic_png([]) is None
    held = [("corruption", 2), ("corruption", 2), ("explorateur", 1)]
    mosaic = await marche_art.held_cards_mosaic_png(held)
    assert mosaic is not None and mosaic[:8] == b"\x89PNG\r\n\x1a\n"
    width, height, _pixels = _decode_png_rgba(mosaic)
    assert (width, height) == (marche_art.HELD_COLS * marche_art.HELD_CARD_W, marche_art.HELD_TILE_H)
    assert await marche_art.held_cards_mosaic_png(held) is mosaic, "the fingerprint caches"
    assert await marche_art.held_cards_mosaic_png([("corruption", 3)]) is not mosaic


class _Tech:
    embuscade = 2
    traquenard = 1
    patrouille = 2
    contre_espionnage = 2
    sabotage = 1
    explorateur = 2
    jeu_d_armes = 1
    mariage_arrange = 3
    corruption = 4
    garde_royale = 2
    limits: ClassVar[dict[str, int]] = {"explorateur": 1, "sabotage": 0}


class _Config:
    technologies = _Tech()


class _State:
    def __init__(self, purchases: dict[str, int]) -> None:
        self.purchases = purchases


class _Stack:
    config = _Config()

    def __init__(self, purchases: dict[str, int], wallet: int = 12) -> None:
        self._purchases = purchases
        self._wallet = wallet
        self.economy = self
        self.attacks = self

    async def wallet(self, kingdom_id: str) -> int:
        return self._wallet

    async def technology_state(self, kingdom_id: str) -> _State:
        return _State(dict(self._purchases))


def test_market_shelves_carry_drasahs_order_and_costs() -> None:
    """The four shelves, his taxonomy, every article with its price."""
    from botforge.mods.kingdom.cogs.market import MARKET_SECTIONS, market_shelf_items
    from botforge.mods.kingdom.cogs.strings import strings

    items = market_shelf_items(_Stack({}), strings("fr"))
    keys = [key for key, _label, _cost in items]
    assert keys == [
        "traquenard", "jeu_d_armes",
        "patrouille", "garde_royale",
        "sabotage", "contre_espionnage", "embuscade",
        "explorateur", "mariage_arrange", "corruption",
    ]
    assert len(keys) == sum(len(k) for _h, k in MARKET_SECTIONS)
    by_key = {key: cost for key, _label, cost in items}
    assert by_key["embuscade"] == 2 and by_key["corruption"] == 4


@pytest.mark.asyncio
async def test_market_fiche_carries_effect_cost_wallet_and_left() -> None:
    """The article sheet: effect, cost, live treasury, the remainder."""
    from botforge.mods.kingdom.cogs.market import market_fiche
    from botforge.mods.kingdom.cogs.strings import strings

    kingdom = type("K", (), {"id": "k-1", "tech_points_bank": 12})()
    stack = _Stack({"explorateur": 1}, wallet=9)
    fiche = await market_fiche(stack, kingdom, "explorateur", strings("fr"))
    assert "EFFET" in fiche and "jeton Explorateur" in fiche
    assert "**__COÛT :__** 2 ⚙️" in fiche
    assert "**__TRÉSORERIE ACTUELLE :__** 9 ⚙️" in fiche
    assert "**__RESTE CETTE SAISON :__** 0/1" in fiche
    assert "Réservé au Roi" in fiche
    # an unlimited article never shows the remainder line
    fiche = await market_fiche(stack, kingdom, "garde_royale", strings("fr"))
    assert "RESTE CETTE SAISON" not in fiche


@pytest.mark.asyncio
async def test_chamber_ledger_orders_balance_limits_purchases() -> None:
    """The season register: balance, the limits, reverse chronology."""
    from botforge.mods.kingdom.cogs.market import chamber_ledger_text
    from botforge.mods.kingdom.cogs.strings import strings

    kingdom = type(
        "K",
        (),
        {
            "id": "k-1",
            "name": "Aegis",
            "tech_points_bank": 5,
            "market_registry": [
                {"item": "embuscade", "detail": "", "cost": 2, "at": 100},
                {"item": "explorateur", "detail": "jeton", "cost": 2, "at": 200},
            ],
        },
    )()
    ledger = await chamber_ledger_text(_Stack({"explorateur": 1}), kingdom, strings("fr"))
    assert "dépensé : 4 ⚙️ · trésor : 12 ⚙️" in ledger
    assert "🧭 Explorateur 1/1" in ledger
    assert "Achats" in ledger and "🧭 Explorateur" in ledger
    newest = ledger.find("Achats")
    assert ledger.find("🧭 Explorateur", newest) < ledger.find("🥷 Embuscade", newest), (
        "the newest purchase comes first"
    )


@pytest.mark.asyncio
async def test_chamber_held_cards_read_the_remaining_stocks() -> None:
    """The hand lists the TOKEN cards with their remaining stock."""
    from botforge.mods.kingdom.cogs.market import chamber_held_cards
    from botforge.mods.kingdom.cogs.strings import strings

    kingdom = type("K", (), {"id": "k-1", "arranged_marriage_stock": 3})()
    stack = _Stack(
        {
            "explorateur_stock": 1,
            "corruption_stock": 2,
            "jeu_d_armes_bought": 5,
            "garde_royale_stock": 0,
        }
    )
    held = await chamber_held_cards(stack, kingdom, strings("fr"))
    keys = [key for key, _stock in held]
    assert "explorateur" in keys and "corruption" in keys and "mariage_arrange" in keys
    assert ("mariage_arrange", 3) in held
    assert "garde_royale" not in keys, "an empty stock stays out of the hand"


@pytest.mark.asyncio
async def test_the_pinned_stall_renders_banner_shelves_and_buttons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pin: the streamed banner, four shelves, priced buttons, Comptes."""
    import botforge.mods.kingdom.cogs.market as market
    import botforge.mods.kingdom.cogs.panel as panel

    async def _fr(guild_id: str) -> str:
        return "fr"

    monkeypatch.setattr(panel, "_guild_locale", _fr)
    monkeypatch.setattr(market, "wiring", lambda: None)

    view = await market.build_market_panel("123")
    assert isinstance(view, discord.ui.LayoutView)
    media: list[str] = []
    texts: list[str] = []
    buttons: list[str] = []
    labels: list[str] = []

    def _walk(item: Any) -> None:
        if isinstance(item, discord.ui.MediaGallery):
            media.extend(str(entry.media.url or "") for entry in item.items)
        content = getattr(item, "content", None)
        if isinstance(content, str):
            texts.append(content)
        cid = getattr(item, "custom_id", None)
        if cid:
            buttons.append(str(cid))
        label = getattr(item, "label", None) or getattr(getattr(item, "item", None), "label", None)
        if label:
            labels.append(str(label))
        for child in getattr(item, "children", None) or []:
            _walk(child)

    for child in getattr(view, "children", None) or []:
        _walk(child)

    assert any("march%C3%A9.jpg" in url for url in media), "the banner streams"
    assert any("Marché du Royaume" in text for text in texts)
    assert any("Actions spéciales" in text for text in texts)
    item_buttons = [cid for cid in buttons if cid.startswith("kingdom:market:item:")]
    assert len(item_buttons) == 10, "one priced button per article"
    assert any("— 4 ⚙️" in label for label in labels), "the price rides the label"
    assert "kingdom:attack:chamber" in buttons


def test_setup_hook_lands_every_stall_button() -> None:
    """A stalled DynamicItem = a click into the void (« n'a pas répondu à
    temps ») — the register loop must land every stall button."""
    from botforge.mods.kingdom.cogs import setup_hook
    from botforge.mods.kingdom.cogs.market import (
        MarketBuyButton,
        MarketCancelButton,
        MarketItemButton,
    )

    landed: list[object] = []

    class _RecordingBot:
        def add_dynamic_items(self, item: object) -> None:
            landed.append(item)

    setup_hook(_RecordingBot())
    missing = {MarketItemButton, MarketBuyButton, MarketCancelButton} - set(landed)
    assert not missing, (
        "register() never landed these stall buttons — their clicks "
        f"silently die: {sorted(c.__name__ for c in missing)}"
    )
