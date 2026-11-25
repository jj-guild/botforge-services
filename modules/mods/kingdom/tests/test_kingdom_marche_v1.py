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


# ---------------------------------------------------------------------------
# achat-recu-v1 (Affaire 25) — the cumulative purchase receipt
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self) -> None:
        self.done = False
        self.deferred = 0

    def is_done(self) -> bool:
        return self.done

    async def defer(self, ephemeral: bool = True) -> None:
        self.done = True
        self.deferred += 1


class _FakeMessage:
    def __init__(self) -> None:
        self.edits: list[str] = []
        self.dead = False

    async def edit(self, content: str) -> None:
        if self.dead:
            raise RuntimeError("webhook token expired")
        self.edits.append(content)

    async def delete(self) -> None:
        self.dead = True


class _FakeFollowup:
    def __init__(self, sent: list[Any]) -> None:
        self._sent = sent

    async def send(self, content: str, ephemeral: bool = False) -> Any:
        message = _FakeMessage()
        self._sent.append(content)
        return message


class _FakeInteraction:
    def __init__(self, user_id: str = "u-1", guild: Any = None) -> None:
        self.user = type("U", (), {"id": user_id})()
        self.guild = guild
        self.response = _FakeResponse()
        self.followup = _FakeFollowup([])
        self.sent_contents: list[str] = self.followup._sent


@pytest.mark.asyncio
async def test_the_receipt_edits_the_same_window_until_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """A living receipt = ONE ephemeral edited in place, line by line."""
    import botforge.mods.kingdom.cogs.market as market
    from botforge.mods.kingdom.cogs.strings import strings

    monkeypatch.setattr(market, "_RECEIPT_WINDOWS", {})
    interaction = _FakeInteraction("u-9")
    kingdom = type("K", (), {"id": "k-1", "name": "Aegis"})()

    await market.append_purchase_receipt(interaction, "achat 1", kingdom, strings("fr"))
    first = market._RECEIPT_WINDOWS["u-9"]["message"]
    await market.append_purchase_receipt(interaction, "achat 2", kingdom, strings("fr"))
    await market.append_purchase_receipt(interaction, "achat 3", kingdom, strings("fr"))

    assert market._RECEIPT_WINDOWS["u-9"]["message"] is first, "one window per player"
    assert len(first.edits) == 2, "the 2nd and 3rd purchases EDIT, never re-send"
    assert "achat 1" in first.edits[-1] and "achat 3" in first.edits[-1]
    assert first.edits[-1].count("achats de la session") == 1, "the title never duplicates"


@pytest.mark.asyncio
async def test_a_dead_receipt_opens_a_fresh_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """An expired window (TTL or dead webhook token) = a NEW receipt."""
    import time as _time

    import botforge.mods.kingdom.cogs.market as market
    from botforge.mods.kingdom.cogs.strings import strings

    monkeypatch.setattr(market, "_RECEIPT_WINDOWS", {})
    interaction = _FakeInteraction("u-8")
    kingdom = type("K", (), {"id": "k-1", "name": "Aegis"})()

    await market.append_purchase_receipt(interaction, "achat 1", kingdom, strings("fr"))
    # TTL expiry: the tracked window turns stale
    market._RECEIPT_WINDOWS["u-8"]["opened_at"] = _time.monotonic() - (
        market._RECEIPT_TTL + 1
    )
    await market.append_purchase_receipt(interaction, "achat 2", kingdom, strings("fr"))
    assert "achat 2" in interaction.sent_contents[-1], "a stale window re-opens"
    assert "achat 1" not in interaction.sent_contents[-1], "the dead receipt dies alone"

    # a failed edit (dead webhook token) also re-opens a fresh receipt
    interaction2 = _FakeInteraction("u-7")
    await market.append_purchase_receipt(interaction2, "achat A", kingdom, strings("fr"))
    market._RECEIPT_WINDOWS["u-7"]["message"].dead = True
    await market.append_purchase_receipt(interaction2, "achat B", kingdom, strings("fr"))
    assert "achat B" in interaction2.sent_contents[-1]


def test_the_receipt_body_trims_and_footers_once() -> None:
    """Old lines fall off past 3400 chars; the footer rides ONCE at the bottom."""
    from botforge.mods.kingdom.cogs.market import _receipt_body

    lines = [f"L{i} {'x' * 900}" for i in range(10)]
    body = _receipt_body("TITRE", lines, "FOOTER")
    assert len(body) < 4000
    assert body.startswith("TITRE\nL7"), (
        "the OLDEST lines fall off first (only the newest ones stay)"
    )
    assert body.endswith("\n\nFOOTER") and body.count("FOOTER") == 1


@pytest.mark.asyncio
async def test_each_article_gets_its_own_receipt_line() -> None:
    """The line is the article's own echo (never a generic « acheté »)."""
    from botforge.mods.kingdom.cogs.market import _purchase_line
    from botforge.mods.kingdom.cogs.strings import strings

    stack = _Stack(
        {
            "garde_royale_stock": 2,
            "corruption_stock": 4,
            "jeu_d_armes_stock": 1,
            "explorateur_stock": 3,
            "patrouille_slot_2": 6,
        },
        wallet=10,
    )
    kingdom = type(
        "K", (), {"id": "k-1", "tech_points_bank": 10, "arranged_marriage_stock": 5}
    )()
    s = strings("fr")
    assert "en réserve : 2" in await _purchase_line(stack, kingdom, "garde_royale", s)
    assert "en réserve : 4" in await _purchase_line(stack, kingdom, "corruption", s)
    assert "en réserve : 1" in await _purchase_line(stack, kingdom, "jeu_d_armes", s)
    assert "en réserve : 3" in await _purchase_line(stack, kingdom, "explorateur", s)
    assert "stock : 5" in await _purchase_line(stack, kingdom, "mariage_arrange", s)
    assert "Emplacement de patrouille 2" in await _purchase_line(
        stack, kingdom, "patrouille", s
    )
    assert "✅ Acheté : **🥷 Embuscade**" in await _purchase_line(
        stack, kingdom, "embuscade", s
    )


@pytest.mark.asyncio
async def test_the_receipt_footer_mentions_le_royaume_or_falls_back() -> None:
    """The footer: the clickable salon mention, else the static text."""
    from botforge.mods.kingdom.cogs.strings import strings

    s = strings("fr")

    channel = type("C", (), {"id": 555, "name": "Le-Royaume"})()
    category = type("Cat", (), {"channels": [channel]})()

    import unittest.mock as mock

    import botforge.mods.kingdom.cogs.market as market
    import botforge.mods.kingdom.cogs.realms as realms

    with mock.patch.object(realms, "_find_realm_category", lambda g, n: category):
        footer = await market._realm_ledger_footer(
            object(), type("K", (), {"name": "Aegis"})(), s
        )
    assert "<#555>" in footer, "the resolved salon becomes a clickable mention"

    fallback = await market._realm_ledger_footer(None, None, s)
    assert fallback == s["market_receipt_ledger_help"], "no salon = static fallback"


def test_sabotage_reveal_views_are_always_awaited() -> None:
    """Affaire 25 contract: `sabotage_dm_view(...)` is async — a bare
    (un-awaited) call ships a coroutine as the view and the reveal DM
    dies silently (the 25/11 live incident). Lock EVERY call site to
    an await."""
    import ast
    import inspect
    from pathlib import Path

    from botforge.mods.kingdom.cogs import pickban

    source = Path(str(inspect.getsourcefile(pickban) or pickban.__file__)).read_text()
    tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "sabotage_dm_view"
    ]
    awaited = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call)
    }
    bare = [node for node in calls if id(node) not in awaited]
    assert not bare, f"{len(bare)} bare sabotage_dm_view call(s) — the reveal dies"
    assert len(calls) >= 2, "the two reveal call sites must stay awaited"
