"""The 🍺 Taverne & the 🗡️ Chef Mercenaire (P4.4, #368).

The Taverne is the lords' purse-and-drinks window (taverne-v1): one
purse line, one select of the catalog's drinks (the price and the
combat lock are DATA), one confirm card — the engine debits and poses
the locks, the surface only renders. The Chef Mercenaire stands in
the same Taverne (chef-mercenaire-v1): the live market's lots with
their current highest bid, one bid ladder (the amount strictly above
the highest, capped by the purse — the escrow debits at once), one
withdraw (the escrow refunds). Every engine refusal is a note.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord

from .common import lord_of, open_unique_ephemeral, strings_for, surface, wiring

logger = logging.getLogger("kingdom.tavern")


def _civ_names(stack: Any) -> dict[str, str]:
    catalog = getattr(stack.config, "civilizations", ()) or ()
    return {str(civ.key): str(getattr(civ, "display_name", civ.key)) for civ in catalog}


def _error_note(exc: Exception, strings: dict[str, str]) -> str:
    """Every engine refusal is a note — the strings carry the common ones."""
    from botforge.mods.kingdom.mercenary import (
        MercenaryAlreadyHeldError,
        MercenaryBidTooLowError,
        MercenaryInsufficientPurseError,
        MercenaryMarketClosedError,
        MercenaryNotOpenYetError,
        MercenarySeasonClosedError,
    )
    from botforge.mods.kingdom.service import NoSeasonError
    from botforge.mods.kingdom.tavern import (
        TavernCooldownError,
        TavernInsufficientPurseError,
        TavernSeasonClosedError,
    )

    if isinstance(exc, NoSeasonError):
        return str(strings["tavern_no_season"])
    if isinstance(exc, (TavernSeasonClosedError, MercenarySeasonClosedError)):
        return str(strings["tavern_season_closed"])
    if isinstance(exc, TavernCooldownError):
        return str(strings["tavern_cooldown_note"])
    if isinstance(exc, (TavernInsufficientPurseError, MercenaryInsufficientPurseError)):
        return str(strings["tavern_no_purse"])
    if isinstance(exc, MercenaryBidTooLowError):
        return str(strings["mercenary_bid_too_low"])
    if isinstance(exc, MercenaryNotOpenYetError):
        return str(strings["mercenary_not_open_yet"])
    if isinstance(exc, MercenaryMarketClosedError):
        return str(strings["mercenary_closed_note"])
    if isinstance(exc, MercenaryAlreadyHeldError):
        return str(strings["mercenary_already_held"])
    return str(strings["tavern_error"]).format(str(exc)[:150])


# ---------------------------------------------------------------------------
# The Taverne (the purse + the drinks)
# ---------------------------------------------------------------------------


def _drinks_options(stack: Any, strings: dict[str, str]) -> list[discord.SelectOption]:
    catalog = getattr(getattr(stack.config, "tavern", None), "drinks", ()) or ()
    return [
        discord.SelectOption(
            label=str(strings["tavern_drink_line"]).format(drink.label, drink.price)[:100],
            value=str(drink.key)[:100],
            description=str(strings["tavern_lock_line"]).format(int(drink.lock_minutes))[:100],
        )
        for drink in catalog
    ][:25]


def _tavern_view(stack: Any, lord: Any, strings: dict[str, str]) -> discord.ui.LayoutView:
    """The Taverne window — purse, cooldown state, one select of drinks."""
    from botforge.mods.kingdom.game_clock import game_now

    now_ts = int(game_now().timestamp())
    purse = int(getattr(lord, "purse", 0) or 0)
    lines = [f"## {strings['tavern_title']}", str(strings["tavern_purse"]).format(purse)]
    cooldown = getattr(lord, "tavern_next_drink_at", None)
    if cooldown is not None and int(cooldown) > now_ts:
        lines.append(str(strings["tavern_cooldown"]).format(int(cooldown)))
    locked = getattr(lord, "tavern_locked_until", None)
    if locked is not None and int(locked) > now_ts:
        lines.append(str(strings["tavern_locked"]).format(int(locked)))
    select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id="kingdom:attack:tavernpick",
        placeholder=str(strings["tavern_select"])[:100],
        options=_drinks_options(stack, strings),
    )

    async def on_pick(target: discord.Interaction) -> None:
        values = getattr(target, "data", None) or {}
        chosen = [str(v) for v in values.get("values", [])]
        if not chosen:
            return
        drink = next(
            (
                drink
                for drink in (getattr(getattr(stack.config, "tavern", None), "drinks", ()) or ())
                if str(drink.key) == chosen[0]
            ),
            None,
        )
        if drink is None:
            return
        body = (
            f"## {strings['tavern_confirm_title']}\n"
            f"**{drink.label}**\n"
            f"{str(strings['tavern_confirm_sub']).format(drink.price, drink.lock_minutes)}"
        )
        yes: discord.ui.Button[Any] = discord.ui.Button(
            label=str(strings["tavern_yes"])[:80],
            custom_id="kingdom:attack:taveryes",
            style=discord.ButtonStyle.success,
        )
        async def on_yes(target: discord.Interaction) -> None:
            await target.response.defer()
            try:
                lord_after, drink_after = await stack.tavern.buy_drink(
                    str(target.user.id), chosen[0]
                )
            except Exception as exc:  # noqa: BLE001 — every refusal is a note
                await target.followup.send(_error_note(exc, strings), ephemeral=True)
                return
            note = str(strings["tavern_drunk"]).format(
                drink_after.label, int(lord_after.purse)
            )
            try:
                await target.edit_original_response(content=note, view=None)
            except Exception:
                await target.followup.send(note, ephemeral=True)

        yes.callback = on_yes  # type: ignore[method-assign, assignment]
        from .common import surface

        view = surface(
            "panel:mod:kingdom:tavern:confirm",
            discord.ui.TextDisplay(body),
            discord.ui.ActionRow(yes),
        )
        await target.response.edit_message(content=None, view=view)

    select.callback = on_pick  # type: ignore[method-assign, assignment]
    from .common import surface

    return surface(
        "panel:mod:kingdom:tavern",
        discord.ui.TextDisplay("\n".join(lines)),
        discord.ui.ActionRow(select),
    )


# ---------------------------------------------------------------------------
# The Chef Mercenaire (the lots + the bid ladder)
# ---------------------------------------------------------------------------


def _highest(lot: dict[str, Any]) -> int:
    return max((int(bid.get("amount", 0) or 0) for bid in lot.get("bids", [])), default=0)


def _market_lines(doc: dict[str, Any], lord_id: str, strings: dict[str, str], names: dict[str, str]) -> list[str]:
    """The live market's lots — the highest bid and the clicker's own line."""
    lines = [f"## {strings['mercenary_title']}"]
    for lot in doc.get("lots", []):
        civ = names.get(str(lot.get("civ")), str(lot.get("civ")))
        highest = _highest(lot)
        line = str(strings["mercenary_lot_line"]).format(civ, int(lot.get("uses", 0) or 0), highest)
        mine = next(
            (b for b in lot.get("bids", []) if str(b.get("lord")) == lord_id), None
        )
        if mine is not None:
            line += " " + str(strings["mercenary_own_bid"]).format(int(mine.get("amount", 0)))
        lines.append(line)
    if doc.get("closed", False):
        winners = [
            names.get(str(lot.get("civ")), str(lot.get("civ")))
            for lot in doc.get("lots", [])
            if lot.get("winner")
        ]
        if winners:
            lines.append(str(strings["mercenary_winners"]).format(" · ".join(winners)))
        else:
            lines.append(str(strings["mercenary_no_winner"]))
    return lines


def _mercenary_view(
    stack: Any,
    doc: dict[str, Any],
    lord: Any,
    strings: dict[str, str],
) -> discord.ui.LayoutView:
    """The market window — the lots, a bid ladder, a withdraw button."""
    names = _civ_names(stack)
    lord_id = str(lord.id)
    from .common import surface

    lines = _market_lines(doc, lord_id, strings, names)
    from .tavern_art import taverne_art_item

    merc_art = taverne_art_item("mercenaire")
    head: list[Any] = [discord.ui.MediaGallery(merc_art)] if merc_art is not None else []
    if bool(doc.get("closed", False)):
        return surface(
            "panel:mod:kingdom:mercenary",
            *head,
            discord.ui.TextDisplay("\n".join(lines)),
        )

    options = [
        discord.SelectOption(
            label=str(names.get(str(lot.get("civ")), str(lot.get("civ"))))[:100],
            value=str(lot.get("civ"))[:100],
        )
        for lot in doc.get("lots", [])
    ][:25]
    select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id="kingdom:attack:mercenarylot",
        placeholder=str(strings["mercenary_select_lot"])[:100],
        options=options,
    )

    async def on_lot(target: discord.Interaction) -> None:
        values = getattr(target, "data", None) or {}
        chosen = [str(v) for v in values.get("values", [])]
        if not chosen:
            return
        civ = chosen[0]
        lot = next((lot for lot in doc.get("lots", []) if str(lot.get("civ")) == civ), None)
        if lot is None:
            return
        floor = max(
            int(getattr(getattr(stack.config, "mercenary", None), "starting_bid", 1) or 1),
            _highest(lot) + 1,
        )
        purse = int(getattr(lord, "purse", 0) or 0)
        amounts = [a for a in range(floor, floor + 8) if a <= purse]
        if not amounts:
            await target.response.edit_message(
                content=str(strings["tavern_no_purse"]), view=None
            )
            return
        amount_select: discord.ui.Select[Any] = discord.ui.Select(
            custom_id="kingdom:attack:mercenaryamount",
            placeholder=str(strings["mercenary_select_amount"])[:100],
            options=[
                discord.SelectOption(label=f"{a} 🪙", value=str(a)) for a in amounts
            ][:25],
        )

        async def on_amount(target: discord.Interaction) -> None:
            vals = getattr(target, "data", None) or {}
            picked = [str(v) for v in vals.get("values", [])]
            if not picked:
                return
            await target.response.defer()
            try:
                await stack.mercenary.place_bid(str(target.user.id), civ, int(picked[0]))
            except Exception as exc:  # noqa: BLE001 — every refusal is a note
                await target.followup.send(_error_note(exc, strings), ephemeral=True)
                return
            note = str(strings["mercenary_bid_placed"]).format(
                names.get(civ, civ), int(picked[0])
            )
            try:
                await target.edit_original_response(content=note, view=None)
            except Exception:
                await target.followup.send(note, ephemeral=True)

        amount_select.callback = on_amount  # type: ignore[method-assign, assignment]
        from .common import surface as _surface

        ladder = _surface(
            "panel:mod:kingdom:mercenary:ladder",
            discord.ui.ActionRow(amount_select),
        )
        await target.response.edit_message(content=None, view=ladder)

    select.callback = on_lot  # type: ignore[method-assign, assignment]
    withdraw: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["mercenary_withdraw"])[:80],
        custom_id="kingdom:attack:mercenwithdraw",
        style=discord.ButtonStyle.secondary,
    )

    async def on_withdraw(target: discord.Interaction) -> None:
        await target.response.defer()
        try:
            result = await stack.mercenary.withdraw_bid(str(target.user.id))
        except Exception as exc:  # noqa: BLE001 — every refusal is a note
            await target.followup.send(_error_note(exc, strings), ephemeral=True)
            return
        if result is None:
            await target.followup.send(strings["mercenary_withdraw_none"], ephemeral=True)
            return
        try:
            await target.edit_original_response(
                content=strings["mercenary_withdraw_done"], view=None
            )
        except Exception:
            await target.followup.send(strings["mercenary_withdraw_done"], ephemeral=True)

    withdraw.callback = on_withdraw  # type: ignore[method-assign, assignment]
    from .common import surface

    return surface(
        "panel:mod:kingdom:mercenary",
        *head,
        discord.ui.TextDisplay("\n".join(lines)),
        discord.ui.ActionRow(select, withdraw),
    )


# ---------------------------------------------------------------------------
# The panel buttons
# ---------------------------------------------------------------------------


class TavernButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:tavern$",
):
    """The 🍺 « Taverne » button of the declare panel."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:attack:tavern",
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
    ) -> TavernButton:
        return cls(strings_for(interaction)["tavern_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        # Affaire 39 : le bouton du panneau d'attaque et le pin de la
        # Taverne partagent LE MÊME corps (un seul code, deux surfaces).
        await _open_tavern_menu(interaction)


class MercenaryButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:mercenary$",
):
    """The 🗡️ « Mercenaires » button of the declare panel."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:attack:mercenary",
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
    ) -> MercenaryButton:
        return cls(strings_for(interaction)["mercenary_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        strings = strings_for(interaction)
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, strings["plan_no_service"])
            return
        lord = await lord_of(stack.kingdoms, str(interaction.user.id), interaction)
        if lord is None or getattr(lord, "kingdom_id", None) is None:
            await open_unique_ephemeral(interaction, strings["not_a_lord"])
            return
        try:
            doc = await stack.mercenary.market()
        except Exception:  # noqa: BLE001 — a read failure is a note, never a crash
            doc = None
        if not doc:
            await open_unique_ephemeral(interaction, strings["mercenary_none"])
            return
        await open_unique_ephemeral(
            interaction, view=_mercenary_view(stack, doc, lord, strings)
        )


# ---------------------------------------------------------------------------
# The pinned Taverne panel (Affaire 39 — the salon's own surface)
# ---------------------------------------------------------------------------


async def build_tavern_panel(guild_id: str) -> discord.ui.LayoutView:
    """The pinned Taverne panel (deployed by the static-pin core seam).

    La référence portait le message épinglé du salon 🍺 taverne : le
    comptoir (règles + boutons), le menu à boire et le renseignement.
    Le portage réutilise LES MÊMES fenêtres éphémères que les boutons
    du panneau d'attaque (la fenêtre unique) — zéro duplication : le
    pin ne fait qu'ouvrir les surfaces existantes, le Chef Mercenaire
    reste le bouton enregistré (un seul DynamicItem, deux surfaces).
    """
    from .panel import _guild_locale
    from .strings import strings
    from .tavern_art import taverne_art_item

    locale = await _guild_locale(guild_id)
    strings_map = strings(locale[:2])
    # taverne-v1 (Drasah 28/11) : le pin porte l'art du COMPTOIR en tête
    # + le bouton 🍺 « Entrer dans la Taverne » (la porte, l'art de
    # l'entrée et l'intro RP vivent dans la fenêtre éphémère du bouton).
    items: list[Any] = []
    art = taverne_art_item("comptoir")
    if art is not None:
        items.append(discord.ui.MediaGallery(art))
    items.extend(
        [
            discord.ui.TextDisplay(f"# {strings_map['tavern_pin_title']}"),
            discord.ui.TextDisplay(
                f"{strings_map['tavern_pin_intro']}\n\n{strings_map['tavern_pin_rules']}"
            ),
            discord.ui.Separator(),
            discord.ui.ActionRow(
                TavernEnterButton(strings_map["tavern_enter_button"]),
                TavernMenuButton(strings_map["tavern_menu_button"]),
                MercenaryButton(strings_map["mercenary_button"]),
            ),
            discord.ui.ActionRow(
                TavernInfoButton(strings_map["tavern_info_button"]),
                TavernPurseButton(strings_map["tavern_purse_button"]),
            ),
        ]
    )
    return surface("panel:mod:kingdom:tavern:pin", *items)


async def _open_tavern_menu(interaction: discord.Interaction) -> None:
    """The shared « Demander à boire » body (pin + attack panel button)."""
    strings = strings_for(interaction)
    stack = wiring()
    if stack is None:
        await open_unique_ephemeral(interaction, strings["plan_no_service"])
        return
    lord = await lord_of(stack.kingdoms, str(interaction.user.id), interaction)
    if lord is None or getattr(lord, "kingdom_id", None) is None:
        await open_unique_ephemeral(interaction, strings["not_a_lord"])
        return
    await open_unique_ephemeral(
        interaction, view=_tavern_view(stack, lord, strings)
    )


class TavernMenuButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:tavern:menu$",
):
    """The 🍺 « Demander à boire » button of the pinned Taverne panel."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:tavern:menu",
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
    ) -> TavernMenuButton:
        return cls(strings_for(interaction)["tavern_menu_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await _open_tavern_menu(interaction)


class TavernInfoButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:tavern:info$",
):
    """The 🗣️ « Demander un renseignement » button — what each drink does."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:tavern:info",
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
    ) -> TavernInfoButton:
        return cls(strings_for(interaction)["tavern_info_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        strings = strings_for(interaction)
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, strings["plan_no_service"])
            return
        lines = [strings["tavern_info_rp"], "", strings["tavern_info_header"]]
        for drink in getattr(getattr(stack.config, "tavern", None), "drinks", ()) or ():
            effect = strings.get(f"tavern_effect_{drink.key}", strings["tavern_effect_generic"])
            lines.append(
                str(strings["tavern_info_line"]).format(
                    drink.label, effect, int(drink.lock_minutes)
                )
            )
        await open_unique_ephemeral(
            interaction, view=surface("panel:mod:kingdom:tavern:info", discord.ui.TextDisplay("\n".join(lines)))
        )


class TavernPurseButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:tavern:purse$",
):
    """The 💰 « Regarder sa bourse » button — the live purse note."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:tavern:purse",
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
    ) -> TavernPurseButton:
        return cls(strings_for(interaction)["tavern_purse_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        strings = strings_for(interaction)
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, strings["plan_no_service"])
            return
        lord = await lord_of(stack.kingdoms, str(interaction.user.id), interaction)
        if lord is None:
            await open_unique_ephemeral(interaction, strings["not_a_lord"])
            return
        await open_unique_ephemeral(
            interaction, content=str(strings["tavern_purse_line"]).format(int(getattr(lord, "purse", 0) or 0))
        )


class TavernEnterButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:tavern:enter$",
):
    """taverne-v1 (Drasah 28/11) : le 🍺 « Entrer dans la Taverne » du pin.

    La porte s'ouvre sur une fenêtre éphémère unique : l'art de
    l'ENTRÉE (MediaGallery), l'intro RP, puis les MÊMES boutons que le
    pin (menu / mercenaire / info / bourse) — zéro duplication, la
    fenêtre ne fait qu'assembler les surfaces existantes.
    """

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id="kingdom:tavern:enter",
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
    ) -> TavernEnterButton:
        return cls(strings_for(interaction)["tavern_enter_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        strings = strings_for(interaction)
        from .tavern_art import taverne_art_item

        art = taverne_art_item("entree")
        items: list[Any] = []
        if art is not None:
            items.append(discord.ui.MediaGallery(art))
        items.extend(
            [
                discord.ui.TextDisplay(str(strings["tavern_enter_intro"])),
                discord.ui.Separator(),
                discord.ui.ActionRow(
                    TavernMenuButton(strings["tavern_menu_button"]),
                    MercenaryButton(strings["mercenary_button"]),
                ),
                discord.ui.ActionRow(
                    TavernInfoButton(strings["tavern_info_button"]),
                    TavernPurseButton(strings["tavern_purse_button"]),
                ),
            ]
        )
        await open_unique_ephemeral(
            interaction, view=surface("panel:mod:kingdom:tavern:enter", *items)
        )


def tavern_dynamic_items() -> tuple:
    """The module's restart-proof items (registered by the cog)."""
    return (
        TavernButton,
        TavernEnterButton,
        MercenaryButton,
        TavernMenuButton,
        TavernInfoButton,
        TavernPurseButton,
    )
