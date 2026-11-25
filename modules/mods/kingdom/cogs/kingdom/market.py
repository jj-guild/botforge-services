"""The 💰 Marché & the 🏛️ Chambre des comptes (P4.3, #368 T7, Affaires 24-25).

The Marché is the reference merchant stall (marche-reference-v1):
one pinned panel, the banner, FOUR shelves in Drasah's order (his
taxonomy, NOT a flat select), one purchase button per article wearing
its price — a click reveals the article CARD (the TCG art streamed
from the reference assets, the full fiche: effect, cost, live treasury,
per-season remainder) with its ✅ Acheter / ❌ Annuler row. Only the
King buys; the engine owns every check, this surface only renders,
reports and never grants anything on its own.

The Chambre des comptes keeps its ported roles (chambre-utiliser-v1:
one stock view, one use-wizard per card) and gains the reference
ledger: the season balance, the purchase registry in reverse
chronology, the CARDS IN HAND with their remaining stocks, and the
held-cards mosaic — one composite image, X<stock> painted per tile.
"""

from __future__ import annotations

import io
import logging
import re
import time
from datetime import datetime
from typing import Any, cast
from zoneinfo import ZoneInfo

import discord

from .common import (
    close_previous_ephemeral,
    lord_of,
    open_unique_ephemeral,
    strings_for,
    surface,
    wiring,
)

logger = logging.getLogger("kingdom.market")

# (item key, buy method suffix) — the consumable cards of the stall.
_CONSUMABLE_ITEMS: tuple[tuple[str, str], ...] = (
    ("mariage_arrange", "arranged_marriage_token"),
    ("explorateur", "explorateur_token"),
    ("corruption", "corruption_token"),
    ("jeu_d_armes", "jeu_d_armes_token"),
    ("garde_royale", "royal_guard"),
)
_COMBAT_TECHNOLOGIES = ("embuscade", "traquenard", "contre_espionnage", "sabotage")
_PATROUILLE_HOURS = tuple(range(0, 24, 2))

# marche-reference-v1: the four shelves of the merchant stall —
# Drasah's own taxonomy and order (the reference MARKET_SECTIONS).
MARKET_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("market_section_ia", ("traquenard", "jeu_d_armes")),
    ("market_section_defense", ("patrouille", "garde_royale")),
    ("market_section_attaque", ("sabotage", "contre_espionnage", "embuscade")),
    ("market_section_speciales", ("explorateur", "mariage_arrange", "corruption")),
)

# The card keys of the CARDS IN HAND section: the stock counter each
# one reads (the buys ride the article counter, the remaining stock
# under its own — the pattern of the reference _LEDGER_CARD_KEYS).
_LEDGER_CARD_STOCK_KEYS = {
    "explorateur": "explorateur_stock",
    "corruption": "corruption_stock",
    "jeu_d_armes": "jeu_d_armes_stock",
    "garde_royale": "garde_royale_stock",
}


def _cost(stack: Any, action: str) -> int:
    """The configured cost of one special action (D9)."""
    return int(getattr(stack.config.technologies, action, 0))


async def _kingdom_of(stack: Any, lord: Any) -> Any | None:
    return next(
        (item for item in await stack.kingdoms.kingdoms() if str(item.id) == str(lord.kingdom_id)),
        None,
    )


def _market_error_note(exc: Exception, strings: dict[str, str]) -> str:
    """Every engine refusal is a note — the strings carry the common ones."""
    from botforge.mods.kingdom.economy import (
        EconomyError,
        EconomyLimitReachedError,
        InsufficientPointsError,
    )

    if isinstance(exc, InsufficientPointsError):
        return strings["market_no_points"]
    if isinstance(exc, EconomyLimitReachedError):
        return strings["market_limit"]
    if isinstance(exc, EconomyError):
        return str(strings["market_error"]).format(str(exc)[:150])
    return str(strings["market_error"]).format(str(exc)[:150])


def _market_label(item: str, strings: dict[str, Any]) -> str:
    """Return the localized article label (tech shelf or action shelf)."""
    tech = strings.get("market_tech") or {}
    action = strings.get("market_action") or {}
    return str(tech.get(item) or action.get(item) or item)


def market_shelf_items(stack: Any, strings: dict[str, Any]) -> list[tuple[str, str, int]]:
    """Return the stall's articles in shelf order (key, label, cost).

    The ONE data seam behind the pinned panel AND the tests: the
    shelves, the labels and the prices carry through a single helper
    (a drift between the render and the rules becomes impossible).
    """
    items: list[tuple[str, str, int]] = []
    for _header_key, keys in MARKET_SECTIONS:
        for key in keys:
            items.append((key, _market_label(key, strings), _cost(stack, key)))
    return items


def _is_king(lord: Any) -> bool:
    """Return True when the lord document holds the KING role."""
    role = getattr(lord, "role", None)
    return str(getattr(role, "name", role or "")).upper().find("KING") >= 0


async def _clicker_kingdom(
    interaction: discord.Interaction, stack: Any, strings: dict[str, str]
) -> tuple[Any, Any] | None:
    """Resolve the clicker's (lord, kingdom), the King gate included."""
    lord = await lord_of(stack.kingdoms, str(interaction.user.id), interaction)
    if lord is None or getattr(lord, "kingdom_id", None) is None:
        await open_unique_ephemeral(interaction, strings["not_a_lord"])
        return None
    if not _is_king(lord):
        await open_unique_ephemeral(interaction, strings["market_not_king"])
        return None
    kingdom = await _kingdom_of(stack, lord)
    if kingdom is None:
        await open_unique_ephemeral(interaction, strings["not_a_lord"])
        return None
    return lord, kingdom


def _market_limit(stack: Any, item: str) -> int:
    """Return the configured per-season purchase limit (0 = unlimited)."""
    limits = getattr(stack.config.technologies, "limits", None) or {}
    return int(limits.get(item, 0) or 0)


async def _market_bought(stack: Any, kingdom_id: str, item: str) -> int:
    """Return the season purchase counter of one article (0 on failure)."""
    try:
        state = await stack.attacks.technology_state(kingdom_id)
        purchases = getattr(state, "purchases", None) or {}
        if item == "jeu_d_armes":
            return int(purchases.get("jeu_d_armes_bought", 0) or 0)
        return int(purchases.get(item, 0) or 0)
    except Exception:
        logger.info("marche: purchase counter read failed (%s)", item, exc_info=True)
        return 0


async def market_fiche(stack: Any, kingdom: Any, item: str, strings: dict[str, Any]) -> str:
    """Build the article sheet: effect, cost, live treasury, limits."""
    kingdom_id = str(kingdom.id)
    wallet = int(kingdom.tech_points_bank)
    try:
        wallet = int(await stack.economy.wallet(kingdom_id))
    except Exception:
        logger.info("marche: wallet read failed", exc_info=True)
    lines = [
        str(strings["market_fiche_effect"]).format((strings.get("market_effect") or {}).get(item, "")),
        str(strings["market_fiche_cost"]).format(_cost(stack, item)),
        str(strings["market_fiche_wallet"]).format(wallet),
    ]
    limit = _market_limit(stack, item)
    if limit > 0:
        bought = await _market_bought(stack, kingdom_id, item)
        lines.append(str(strings["market_fiche_left"]).format(max(0, limit - bought), limit))
    lines.append(str(strings["market_fiche_king_only"]))
    return "\n\n".join(lines)


async def _purchase(stack: Any, kingdom_id: str, item: str) -> None:
    """Run ONE engine purchase — the single dispatch, no ad hoc buys."""
    if item in _COMBAT_TECHNOLOGIES:
        await stack.economy.buy_combat_technology(kingdom_id, item)
    elif item == "patrouille":
        state = await stack.attacks.technology_state(kingdom_id)
        slot = 2 if "patrouille_unlock_1" in state.purchases else 1
        await stack.economy.buy_patrouille_slot(kingdom_id, slot)
    else:
        method = dict(_CONSUMABLE_ITEMS)[item]
        await getattr(stack.economy, f"buy_{method}")(kingdom_id)


async def _success_note(
    stack: Any, kingdom: Any, item: str, strings: dict[str, Any]
) -> str:
    """Build the unique post-purchase echo: bought + treasury + limit."""
    label = _market_label(item, strings)
    wallet = int(kingdom.tech_points_bank)
    try:
        wallet = int(await stack.economy.wallet(str(kingdom.id)))
    except Exception:
        logger.info("marche: wallet read failed", exc_info=True)
    note = str(strings["market_bought"]).format(label, wallet)
    limit = _market_limit(stack, item)
    if limit > 0:
        bought = await _market_bought(stack, str(kingdom.id), item)
        note += str(strings["market_bought_left"]).format(max(0, limit - bought), limit)
    return note


# ---------------------------------------------------------------------------
# The cumulative purchase receipt (achat-recu-v1 — Reference 30/10, Affaire 25)
# ---------------------------------------------------------------------------

_RECEIPT_TTL = 15 * 60
_RECEIPT_WINDOWS: dict[str, dict[str, Any]] = {}


def _receipt_body(title: str, lines: list[str], footer: str = "") -> str:
    """Render one cumulative receipt (title + live lines + the footer).

    The footer is appended ONCE at the bottom (never per purchase
    line); the OLDEST lines fall off past 3400 chars — the ~15-minute
    webhook edit window bounds the growth on its own, the trim is the
    hard stop.
    """
    while sum(len(x) for x in lines) > 3400 and len(lines) > 1:
        lines = lines[1:]
    body = f"{title}\n" + "\n".join(lines)
    if footer:
        body = f"{body}\n\n{footer}"
    return body


async def _realm_ledger_footer(guild: Any, kingdom: Any, strings: dict[str, Any]) -> str:
    """Build the receipt's « where are my purchases » footer.

    Best effort: the clickable mention of HIS kingdom's « le-royaume »
    salon when it resolves, the static fallback text otherwise — a
    failed lookup never breaks the receipt.
    """
    named = str(strings.get("market_receipt_ledger_help_named") or "")
    fallback = str(strings.get("market_receipt_ledger_help") or "")
    if not named and not fallback:
        return ""
    try:
        if guild is not None and kingdom is not None:
            from .realms import _find_realm_category, _slug

            category = _find_realm_category(guild, str(getattr(kingdom, "name", "")))
            channel = next(
                (
                    c
                    for c in getattr(category, "channels", [])
                    if _slug(getattr(c, "name", "")) == "le-royaume"
                ),
                None,
            )
            if channel is not None:
                return named.format(mention=f"<#{channel.id}>")
    except Exception:
        logger.warning("marche: receipt ledger lookup failed", exc_info=True)
    return fallback


async def append_purchase_receipt(
    interaction: discord.Interaction, line: str, kingdom: Any, strings: dict[str, Any]
) -> None:
    """Add one ✅ purchase line to the player's cumulative receipt.

    The receipt is the living trace of the session's purchases — an
    EDIT IN PLACE of the same ephemeral while its ~15-minute webhook
    token lives, a FRESH receipt once that window is dead. It lives in
    its OWN slot (never the fenêtre unique): opening other market cards
    never closes it. Best effort — a failed edit/send never breaks a
    purchase that already happened.
    """
    user_id = str(getattr(interaction.user, "id", "") or "")
    if not user_id:
        return
    title = str(strings["market_receipt_title"])
    receipt = _RECEIPT_WINDOWS.get(user_id)
    if receipt is not None and time.monotonic() - receipt["opened_at"] <= _RECEIPT_TTL:
        receipt["lines"].append(line)
        try:
            await receipt["message"].edit(
                content=_receipt_body(title, receipt["lines"], receipt.get("footer", ""))
            )
            return
        except Exception:
            logger.warning("marche: receipt edit failed — fresh receipt", exc_info=True)
            _RECEIPT_WINDOWS.pop(user_id, None)
    lines = [line]
    footer = await _realm_ledger_footer(interaction.guild, kingdom, strings)
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        message: Any = await interaction.followup.send(  # type: ignore[func-returns-value]
            _receipt_body(title, lines, footer), ephemeral=True
        )
    except Exception:
        logger.warning("marche: receipt send failed (purchase stands)", exc_info=True)
        return
    _RECEIPT_WINDOWS[user_id] = {
        "opened_at": time.monotonic(),
        "message": message,
        "lines": lines,
        "footer": footer,
    }


async def _purchase_line(
    stack: Any, kingdom: Any, item: str, strings: dict[str, Any]
) -> str:
    """Build the item's own ✅ receipt line (never a generic echo)."""
    if item in _COMBAT_TECHNOLOGIES:
        return await _success_note(stack, kingdom, item, strings)
    state = await stack.attacks.technology_state(str(kingdom.id))
    purchases = getattr(state, "purchases", None) or {}
    if item == "patrouille":
        slot = 2 if "patrouille_slot_2" in purchases else 1
        return str(strings["market_patrouille_slot_ok"]).format(slot)
    if item == "mariage_arrange":
        stock = int(getattr(kingdom, "arranged_marriage_stock", 0) or 0)
        return str(strings["market_arranged_token_ok"]).format(stock)
    if item == "garde_royale":
        return str(strings["market_garde_token_ok"]).format(
            int(purchases.get("garde_royale_stock", 0) or 0)
        )
    return str(strings[f"market_{item}_token_ok"]).format(
        int(purchases.get(f"{item}_stock", 0) or 0)
    )


# ---------------------------------------------------------------------------
# The pinned merchant stall (salon market)
# ---------------------------------------------------------------------------


async def build_market_panel(guild_id: str) -> discord.ui.LayoutView:
    """Build the pinned Marché panel — the reference merchant stall.

    The banner rides as a TOP-LEVEL MediaGallery (a pinned CV2 message
    carries no attachments, so the art streams from the reference
    raw URLs), then the four shelves in Drasah's order, one purchase
    button per article wearing its price, and the Chambre des
    comptes row at the bottom.
    """
    from .marche_art import banner_url
    from .panel import _guild_locale
    from .strings import strings as _strings

    locale = await _guild_locale(guild_id)
    strings: dict[str, Any] = _strings(locale[:2])
    items: list[Any] = [
        discord.ui.MediaGallery(discord.MediaGalleryItem(media=banner_url())),
        discord.ui.TextDisplay(f"# {strings['market_title']}"),
        discord.ui.TextDisplay(strings["market_hint_panel"]),
        discord.ui.Separator(),
    ]
    costs_stack = _stack_for_costs()
    for header_key, keys in MARKET_SECTIONS:
        items.append(discord.ui.TextDisplay(f"## {strings[header_key]}"))
        row = discord.ui.ActionRow()
        for key in keys:
            row.add_item(
                MarketItemButton(
                    key, f"{_market_label(key, strings)} — {_cost(costs_stack, key)} ⚙️"
                )
            )
        items.append(row)
    items.append(
        discord.ui.ActionRow(ChamberButton(strings["chamber_button"]))
    )
    return surface("panel:mod:kingdom:market", *items)


def _stack_for_costs() -> Any:
    """Return the wired stack for the pinned render (defaults if absent)."""
    stack = wiring()
    if stack is None:
        from botforge.mods.kingdom.config import TechnologyCosts

        class _Defaults:
            config = type("Config", (), {"technologies": TechnologyCosts()})()

        return _Defaults()
    return stack


# ---------------------------------------------------------------------------
# The stall buttons (restart-proof DynamicItems)
# ---------------------------------------------------------------------------


class MarketItemButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:market:item:(?P<key>[a-z_]+)",
):
    """One article button of a shelf — reveals the ephemeral card."""

    def __init__(self, key: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"kingdom:market:item:{key}",
                style=discord.ButtonStyle.primary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> MarketItemButton:
        """Rebuild the article button from the wire (its shelf label)."""
        strings = strings_for(interaction)
        return cls(match.group("key"), _market_label(match.group("key"), strings))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Reveal the article card: the TCG art plus the full fiche."""
        strings = strings_for(interaction)
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, strings["plan_no_service"])
            return
        resolved = await _clicker_kingdom(interaction, stack, strings)
        if resolved is None:
            return
        _lord, kingdom = resolved
        item = str(getattr(self.item, "custom_id", "")).rsplit(":", 1)[-1]
        from .marche_art import card_url

        view_items: list[Any] = []
        url = card_url(item)
        if url:
            view_items.append(
                discord.ui.MediaGallery(discord.MediaGalleryItem(media=url))
            )
        view_items.append(
            discord.ui.TextDisplay(
                f"## 💰 {_market_label(item, strings)} — {_cost(stack, item)} ⚙️"
            )
        )
        view_items.append(
            discord.ui.TextDisplay(await market_fiche(stack, kingdom, item, strings))
        )
        view_items.append(
            discord.ui.ActionRow(
                MarketBuyButton(item, strings["market_buy_button"]),
                MarketCancelButton(strings["market_cancel_button"]),
            )
        )
        await open_unique_ephemeral(
            interaction, view=surface("panel:mod:kingdom:card", *view_items)
        )


class MarketBuyButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:market:buy:(?P<key>[a-z_]+)",
):
    """The restart-proof ✅ of the revealed article card."""

    def __init__(self, key: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"kingdom:market:buy:{key}",
                style=discord.ButtonStyle.success,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> MarketBuyButton:
        """Rebuild the ✅ of the revealed card from the wire."""
        return cls(
            match.group("key"),
            strings_for(interaction)["market_buy_button"],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Run the purchase the card announced — then grow the receipt.

        One echo, never a grant: the card closes, the cumulative
        receipt gains its line (edit in place while its window lives).
        """
        strings = strings_for(interaction)
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, strings["plan_no_service"])
            return
        resolved = await _clicker_kingdom(interaction, stack, strings)
        if resolved is None:
            return
        _lord, kingdom = resolved
        item = str(getattr(self.item, "custom_id", "")).rsplit(":", 1)[-1]
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            await _purchase(stack, str(kingdom.id), item)
        except Exception as exc:  # noqa: BLE001 — every engine refusal is a note
            await open_unique_ephemeral(interaction, _market_error_note(exc, strings))
            return
        refreshed = await _kingdom_of(stack, resolved[0])
        await close_previous_ephemeral(str(interaction.user.id))
        await append_purchase_receipt(
            interaction,
            await _purchase_line(stack, refreshed or kingdom, item, strings),
            refreshed or kingdom,
            strings,
        )


class MarketCancelButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:market:cancel$",
):
    """The ❌ of the revealed card — the purchase never happened."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id="kingdom:market:cancel",
                style=discord.ButtonStyle.danger,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> MarketCancelButton:
        """Rebuild the ❌ of the revealed card from the wire."""
        return cls(strings_for(interaction)["market_cancel_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Close the revealed card — nothing was bought, nothing spent."""
        await open_unique_ephemeral(interaction, strings_for(interaction)["market_cancelled"])


# ---------------------------------------------------------------------------
# The Chambre des comptes (the stock + use + ledger surface)
# ---------------------------------------------------------------------------


async def chamber_text(stack: Any, kingdom: Any, strings: dict[str, str]) -> str:
    """The wallet, the stocks and the use entries (pure read)."""
    state = await stack.attacks.technology_state(str(kingdom.id))
    p = state.purchases
    lines = [f"## {strings['chamber_title'].format(str(getattr(kingdom, 'name', '')))}"]
    lines.append(str(strings["market_wallet"]).format(int(kingdom.tech_points_bank)))
    lines.append(
        strings["chamber_stock_explorateur"].format(int(p.get("explorateur_stock", 0) or 0))
    )
    lines.append(
        strings["chamber_stock_corruption"].format(int(p.get("corruption_stock", 0) or 0))
    )
    lines.append(
        strings["chamber_stock_jeu_d_armes"].format(int(p.get("jeu_d_armes_stock", 0) or 0))
    )
    lines.append(
        strings["chamber_stock_garde"].format(int(p.get("garde_royale_stock", 0) or 0))
    )
    lines.append(
        strings["chamber_stock_mariage"].format(
            int(getattr(kingdom, "arranged_marriage_stock", 0) or 0)
        )
    )
    slots = [
        f"slot {i + 1} @ {int(p.get(key, -1)):02d}h"
        for i, key in enumerate(("patrouille_slot_1", "patrouille_slot_2"))
        if key in p or f"patrouille_unlock_{i + 1}" in p
    ]
    lines.append(
        strings["chamber_patrouille"].format(" · ".join(slots) or strings["alliances_none"])
    )
    return "\n".join(lines)


async def chamber_ledger_text(stack: Any, kingdom: Any, strings: dict[str, Any]) -> str:
    """Build the season register: balance, limits, purchases."""
    registry = list(getattr(kingdom, "market_registry", None) or [])
    kingdom_id = str(kingdom.id)
    wallet = int(getattr(kingdom, "tech_points_bank", 0) or 0)
    try:
        wallet = int(await stack.economy.wallet(kingdom_id))
    except Exception:
        logger.info("marche: wallet read failed", exc_info=True)
    spent = sum(int(entry.get("cost", 0) or 0) for entry in registry)
    lines = [str(strings["market_ledger_summary"]).format(spent, wallet)]

    limits_parts: list[str] = []
    limits = getattr(stack.config.technologies, "limits", None) or {}
    for item, limit in limits.items():
        item, limit = str(item), int(limit or 0)
        if limit <= 0:
            continue
        bought = await _market_bought(stack, kingdom_id, item)
        limits_parts.append(f"{_market_label(item, strings)} {min(bought, limit)}/{limit}")
    if limits_parts:
        lines.append(str(strings["market_ledger_limits"]).format(" · ".join(limits_parts)))

    lines.append("")
    lines.append(f"## {strings['market_ledger_purchases_title']}")
    if not registry:
        lines.append(str(strings["market_ledger_empty"]))
    else:
        emojis = strings.get("market_ledger_emoji") or {}
        for entry in sorted(registry, key=lambda e: int(e.get("at", 0) or 0), reverse=True):
            item = str(entry.get("item", ""))
            when = datetime.fromtimestamp(
                int(entry.get("at", 0) or 0), tz=ZoneInfo("Europe/Paris")
            ).strftime("%d/%m %H:%M")
            lines.append(
                str(strings["market_ledger_line"]).format(
                    emojis.get(item, "•"),
                    _market_label(item, strings),
                    str(entry.get("detail", "")),
                    int(entry.get("cost", 0) or 0),
                    when,
                )
            )
    return "\n".join(lines)


async def chamber_held_cards(
    stack: Any, kingdom: Any, strings: dict[str, Any]
) -> list[tuple[str, int]]:
    """Return the (card key, remaining stock) pairs of the hand, deduped."""
    state = await stack.attacks.technology_state(str(kingdom.id))
    purchases = dict(getattr(state, "purchases", None) or {})
    held: list[tuple[str, int]] = []
    for key in MARKET_SECTIONS_ORDERED_CARDS:
        stock_key = _LEDGER_CARD_STOCK_KEYS.get(key, key)
        stock = int(purchases.get(stock_key, 0) or 0)
        if key == "mariage_arrange":
            stock = int(getattr(kingdom, "arranged_marriage_stock", 0) or 0)
        if stock <= 0:
            continue
        held.append((key, stock))
    return held


async def _use_wizard(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    card: str,
    kingdom: Any,
) -> None:
    """One use-wizard per card — every path ends on a note, never a crash."""
    kingdom_id = str(kingdom.id)
    if card == "explorateur":
        lords = [
            item
            for item in await stack.kingdoms.lords()
            if not item.left and str(item.kingdom_id or "") == kingdom_id
        ]
        options = [
            discord.SelectOption(
                label=str(getattr(l, "display_name", l.id))[:100], value=str(l.id)[:100]
            )
            for l in lords
        ][:25]

        async def _use_lord(target: discord.Interaction) -> None:
            values = getattr(target, "data", None) or {}
            chosen = [str(v) for v in values.get("values", [])]
            if not chosen:
                return
            await _fire(target, stack, strings, lambda: stack.economy.use_explorateur(kingdom_id, chosen[0]))

        await _wizard_edit(interaction, strings["chamber_select_lord"], options, _use_lord)
        return
    if card == "corruption":
        territories = [
            t for t in await stack.territories.territories() if t.owner_kingdom_id != kingdom_id
        ]
        options = [
            discord.SelectOption(label=str(t.map_key)[:100], value=str(t.id)[:100])
            for t in territories
        ][:25]

        async def _use_territory(target: discord.Interaction) -> None:
            values = getattr(target, "data", None) or {}
            chosen = [str(v) for v in values.get("values", [])]
            if not chosen:
                return
            await _fire(target, stack, strings, lambda: stack.economy.use_corruption(kingdom_id, chosen[0]))

        await _wizard_edit(interaction, strings["chamber_select_territory"], options, _use_territory)
        return
    if card == "jeu_d_armes":
        lord = await lord_of(stack.kingdoms, str(interaction.user.id), interaction)
        if lord is None:
            await interaction.response.edit_message(content=strings["not_a_lord"], view=None)
            return
        await _fire(
            interaction,
            stack,
            strings,
            lambda: stack.economy.use_jeu_d_armes(kingdom_id, str(lord.id)),
        )
        return
    if card == "garde_royale":
        own = [
            t for t in await stack.territories.territories() if t.owner_kingdom_id == kingdom_id
        ]
        options = [
            discord.SelectOption(label=str(t.map_key)[:100], value=str(t.id)[:100])
            for t in own
        ][:25]

        async def _use_guard(target: discord.Interaction) -> None:
            values = getattr(target, "data", None) or {}
            chosen = [str(v) for v in values.get("values", [])]
            if not chosen:
                return
            await _fire(target, stack, strings, lambda: stack.economy.place_royal_guard(kingdom_id, chosen[0]))

        await _wizard_edit(interaction, strings["chamber_select_own_territory"], options, _use_guard)
        return
    if card == "patrouille":
        options = [
            discord.SelectOption(label=f"{hour:02d}h-{hour + 2:02d}h", value=str(hour))
            for hour in _PATROUILLE_HOURS
        ]

        async def _use_hour(target: discord.Interaction) -> None:
            values = getattr(target, "data", None) or {}
            chosen = [str(v) for v in values.get("values", [])]
            if not chosen:
                return
            state = await stack.attacks.technology_state(kingdom_id)
            slot = 1
            if "patrouille_slot_1" in state.purchases:
                slot = 2
            await _fire(
                target,
                stack,
                strings,
                lambda: stack.economy.place_patrouille(kingdom_id, slot, int(chosen[0])),
            )

        await _wizard_edit(interaction, strings["chamber_select_hour"], options, _use_hour)
        return
    await interaction.response.edit_message(content=strings["chamber_no_stock"], view=None)


async def _wizard_edit(
    interaction: discord.Interaction,
    placeholder: str,
    options: list[discord.SelectOption],
    on_pick: Any,
) -> None:
    """Render one select step of a use-wizard (ephemeral, in place)."""
    if not options:
        await interaction.response.edit_message(content=placeholder, view=None)
        return
    select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id=f"kingdom:attack:usepick:{len(options)}",
        placeholder=str(placeholder)[:100],
        options=options,
    )
    select.callback = on_pick  # type: ignore[method-assign, assignment]

    view = surface("panel:mod:kingdom:card", discord.ui.ActionRow(select))
    await interaction.response.edit_message(content=None, view=view)


async def _fire(target: discord.Interaction, stack: Any, strings: dict[str, str], call: Any) -> None:
    """Run one engine call — every refusal is a note, success closes."""
    await target.response.defer()
    try:
        await call()
    except Exception as exc:  # noqa: BLE001 — every engine refusal is a note
        await target.followup.send(_market_error_note(exc, strings), ephemeral=True)
        return
    try:
        await target.edit_original_response(content=strings["chamber_done"], view=None)
    except Exception:
        await target.followup.send(strings["chamber_done"], ephemeral=True)


# ---------------------------------------------------------------------------
# The panel buttons
# ---------------------------------------------------------------------------

# The hand carries the TOKEN cards, in the shelves' own order.
MARKET_SECTIONS_ORDERED_CARDS = tuple(
    key
    for _header_key, keys in MARKET_SECTIONS
    for key in keys
    if key in _LEDGER_CARD_STOCK_KEYS or key == "mariage_arrange"
)


class ChamberButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:chamber$",
):
    """The 🏛️ « Comptes » button of the declare panel & the stall."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:attack:chamber",
                style=discord.ButtonStyle.secondary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> ChamberButton:
        """Rebuild the Comptes button from the wire (its entry label)."""
        return cls(strings_for(interaction)["chamber_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the Chambre des comptes: stocks, use-wizards, the ledger."""
        strings = strings_for(interaction)
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, strings["plan_no_service"])
            return
        lord = await lord_of(stack.kingdoms, str(interaction.user.id), interaction)
        if lord is None or getattr(lord, "kingdom_id", None) is None:
            await open_unique_ephemeral(interaction, strings["not_a_lord"])
            return
        kingdom = await _kingdom_of(stack, lord)
        if kingdom is None:
            await open_unique_ephemeral(interaction, strings["not_a_lord"])
            return
        text = await chamber_text(stack, kingdom, strings)
        ledger = await chamber_ledger_text(stack, kingdom, strings)
        held = await chamber_held_cards(stack, kingdom, strings)
        state = await stack.attacks.technology_state(str(kingdom.id))
        p = state.purchases
        emojis = cast(dict[str, Any], strings.get("market_ledger_emoji") or {})
        items: list[Any] = [
            discord.ui.TextDisplay(text),
            discord.ui.TextDisplay(ledger),
            discord.ui.TextDisplay(f"## {strings['market_ledger_cards_title']}"),
        ]
        card_lines = [
            str(strings["market_ledger_card_line"]).format(
                emojis.get(key, "•"), _market_label(key, strings), stock
            )
            for key, stock in held
        ] or [str(strings["market_ledger_cards_empty"])]
        items.append(discord.ui.TextDisplay("\n".join(card_lines)))
        row: list[discord.ui.Button[Any]] = []
        held_keys = {key for key, _stock in held}
        labels = {
            "explorateur": "chamber_use_explorateur",
            "corruption": "chamber_use_corruption",
            "jeu_d_armes": "chamber_use_jeu_d_armes",
            "garde_royale": "chamber_use_garde",
            "patrouille": "chamber_use_patrouille",
        }
        cards = [
            ("explorateur", int(p.get("explorateur_stock", 0) or 0) > 0 or "explorateur" in held_keys),
            ("corruption", int(p.get("corruption_stock", 0) or 0) > 0 or "corruption" in held_keys),
            ("jeu_d_armes", int(p.get("jeu_d_armes_stock", 0) or 0) > 0 or "jeu_d_armes" in held_keys),
            ("garde_royale", int(p.get("garde_royale_stock", 0) or 0) > 0 or "garde_royale" in held_keys),
            ("patrouille", "patrouille_unlock_1" in p or "patrouille_unlock_2" in p),
        ]
        for card, stock in cards:
            if not stock:
                continue
            button: discord.ui.Button[Any] = discord.ui.Button(
                label=str(strings[labels[card]])[:80],
                custom_id=f"kingdom:attack:usecard:{card}"[:100],
                style=discord.ButtonStyle.success,
            )

            async def on_use(
                target: discord.Interaction, card: str = card, kingdom: Any = kingdom
            ) -> None:
                await _use_wizard(target, stack, strings, card, kingdom)

            button.callback = on_use  # type: ignore[method-assign, assignment]
            row.append(button)
        if row:
            items.append(discord.ui.ActionRow(*row[:5]))
        view = surface("panel:mod:kingdom:chamber", *items)
        files_now = await held_cards_files(held)
        if files_now:
            await open_unique_ephemeral(interaction, view=view, files=files_now)
        else:
            await open_unique_ephemeral(interaction, view=view)


async def held_cards_files(held: list[tuple[str, int]]) -> list[discord.File]:
    """Return the held-cards mosaic as ONE attachment (empty hand = none)."""
    from .marche_art import held_cards_mosaic_png

    png = await held_cards_mosaic_png(held)
    if png is None:
        return []
    try:
        return [discord.File(io.BytesIO(png), filename="cartes_en_main.png")]
    except Exception:
        logger.warning("marche: mosaic attach failed", exc_info=True)
        return []
