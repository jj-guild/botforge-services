"""The 🛒 Marché & the 🏛️ Chambre des comptes (P4.3, #368 T7).

The Marché sells the CARDS (D9/D36): the King pays from the kingdom's
single tech-point wallet, payment first — a refused purchase never
grants anything. The Chambre des comptes is where the bought tokens
live and fire (chambre-utiliser-v1): one stock view, one use-wizard
per card (Explorateur → a lord, Corruption → a foreign territory,
Jeu d'armes → the clicker, Garde Royale → an owned map, Patrouille
→ a daily 2h tranche). The ledger (purchases + uses) rides the
kingdom documents, best effort.

The engine owns every check; this surface only renders and reports.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord

from .common import lord_of, open_unique_ephemeral, strings_for, wiring

logger = logging.getLogger("kingdom.market")

# (item key, buy method suffix, description string key)
_CONSUMABLE_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("mariage_arrange", "arranged_marriage_token", "market_item_mariage_arrange"),
    ("explorateur", "explorateur_token", "market_item_explorateur"),
    ("corruption", "corruption_token", "market_item_corruption"),
    ("jeu_d_armes", "jeu_d_armes_token", "market_item_jeu_d_armes"),
    ("garde_royale", "royal_guard", "market_item_garde_royale"),
)
_COMBAT_TECHNOLOGIES = ("embuscade", "traquenard", "contre_espionnage", "sabotage")
_PATROUILLE_HOURS = tuple(range(0, 24, 2))


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


# ---------------------------------------------------------------------------
# The Marché (the card shop)
# ---------------------------------------------------------------------------


def _market_options(stack: Any, strings: dict[str, str]) -> list[discord.SelectOption]:
    """The purchasable cards with their price (combat techs + consumables)."""
    options: list[discord.SelectOption] = []
    for tech in _COMBAT_TECHNOLOGIES:
        options.append(
            discord.SelectOption(
                label=str(strings["market_item_technology"]).format(tech)[:100],
                value=f"tech:{tech}",
                description=f"{_cost(stack, tech)} ⚙️",
            )
        )
    for key, _method, label_key in _CONSUMABLE_ITEMS:
        options.append(
            discord.SelectOption(
                label=str(strings[label_key])[:100],
                value=f"item:{key}",
                description=f"{_cost(stack, key)} ⚙️",
            )
        )
    options.append(
        discord.SelectOption(
            label=str(strings["market_item_patrouille"])[:100],
            value="item:patrouille",
            description=f"{_cost(stack, 'patrouille')} ⚙️",
        )
    )
    return options[:25]


def _market_view(stack: Any, wallet: int, strings: dict[str, str], kingdom_id: str) -> discord.ui.LayoutView:
    """The market window — wallet, rules, one select of the cards."""
    select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id="kingdom:attack:marketpick",
        placeholder=str(strings["market_intro"])[:100],
        options=_market_options(stack, strings),
    )

    async def on_pick(target: discord.Interaction) -> None:
        values = getattr(target, "data", None) or {}
        chosen = [str(v) for v in values.get("values", [])]
        if not chosen:
            return
        label = next(
            (
                opt.label
                for opt in _market_options(stack, strings)
                if opt.value == chosen[0]
            ),
            chosen[0],
        )
        await _confirm_purchase(target, stack, strings, chosen[0], label, kingdom_id)

    select.callback = on_pick  # type: ignore[method-assign, assignment]
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(
        discord.ui.TextDisplay(f"## {strings['market_title']}\n{strings['market_rules']}")
    )
    view.add_item(discord.ui.TextDisplay(str(strings["market_wallet"]).format(wallet)))
    view.add_item(discord.ui.ActionRow(select))
    return view


async def _confirm_purchase(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    value: str,
    label: str,
    kingdom_id: str,
) -> None:
    """The confirm card — one Yes + one Change (back to the select)."""
    cost = _cost(stack, value.split(":", 1)[1])
    body = (
        f"## {strings['market_confirm_title']}\n"
        f"**{label}**\n{strings['market_confirm_sub'].format(cost)}"
    )
    yes: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["market_yes"])[:80],
        custom_id="kingdom:attack:marketyes",
        style=discord.ButtonStyle.success,
    )
    edit: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["market_edit"])[:80],
        custom_id="kingdom:attack:marketedit",
        style=discord.ButtonStyle.secondary,
    )

    async def on_yes(target: discord.Interaction) -> None:
        await target.response.defer()
        kind, key = value.split(":", 1)
        try:
            if kind == "tech":
                await stack.economy.buy_combat_technology(kingdom_id, key)
            elif key == "patrouille":
                state = await stack.attacks.technology_state(kingdom_id)
                slot = 2 if "patrouille_unlock_1" in state.purchases else 1
                await stack.economy.buy_patrouille_slot(kingdom_id, slot)
            else:
                method = dict((k, m) for k, m, _ in _CONSUMABLE_ITEMS)[key]
                await getattr(stack.economy, f"buy_{method}")(kingdom_id)
        except Exception as exc:  # noqa: BLE001 — every engine refusal is a note
            await target.followup.send(_market_error_note(exc, strings), ephemeral=True)
            return
        try:
            await target.edit_original_response(
                content=str(strings["market_bought"]).format(label), view=None
            )
        except Exception:
            await target.followup.send(
                str(strings["market_bought"]).format(label), ephemeral=True
            )

    async def on_edit(target: discord.Interaction) -> None:
        try:
            wallet = int(await stack.economy.wallet(kingdom_id))
        except Exception:
            wallet = 0
        await target.response.edit_message(
            content=None, view=_market_view(stack, wallet, strings, kingdom_id)
        )

    yes.callback = on_yes  # type: ignore[method-assign, assignment]
    edit.callback = on_edit  # type: ignore[method-assign, assignment]
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.TextDisplay(body))
    view.add_item(discord.ui.ActionRow(yes, edit))
    await interaction.response.edit_message(content=None, view=view)


# ---------------------------------------------------------------------------
# The Chambre des comptes (the stock + use surface)
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
    slots = [
        f"slot {i + 1} @ {int(p.get(key, -1)):02d}h"
        for i, key in enumerate(("patrouille_slot_1", "patrouille_slot_2"))
        if key in p or f"patrouille_unlock_{i + 1}" in p
    ]
    lines.append(
        strings["chamber_patrouille"].format(" · ".join(slots) or strings["alliances_none"])
    )
    return "\n".join(lines)


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
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.ActionRow(select))
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


class MarketButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:market$",
):
    """The 🛒 « Marché » button of the declare panel."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:attack:market",
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
    ) -> MarketButton:
        return cls(strings_for(interaction)["market_button"])

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
        kingdom = await _kingdom_of(stack, lord)
        if kingdom is None:
            await open_unique_ephemeral(interaction, strings["not_a_lord"])
            return
        await open_unique_ephemeral(
            interaction,
            view=_market_view(stack, int(kingdom.tech_points_bank), strings, str(kingdom.id)),
        )


class ChamberButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:chamber$",
):
    """The 🏛️ « Comptes » button of the declare panel."""

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
        return cls(strings_for(interaction)["chamber_button"])

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
        kingdom = await _kingdom_of(stack, lord)
        if kingdom is None:
            await open_unique_ephemeral(interaction, strings["not_a_lord"])
            return
        text = await chamber_text(stack, kingdom, strings)
        state = await stack.attacks.technology_state(str(kingdom.id))
        p = state.purchases
        cards: list[tuple[str, bool]] = [
            ("explorateur", int(p.get("explorateur_stock", 0) or 0) > 0),
            ("corruption", int(p.get("corruption_stock", 0) or 0) > 0),
            ("jeu_d_armes", int(p.get("jeu_d_armes_stock", 0) or 0) > 0),
            ("garde_royale", int(p.get("garde_royale_stock", 0) or 0) > 0),
            ("patrouille", "patrouille_unlock_1" in p or "patrouille_unlock_2" in p),
        ]
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(discord.ui.TextDisplay(text))
        row: list[discord.ui.Button[Any]] = []
        labels = {
            "explorateur": "chamber_use_explorateur",
            "corruption": "chamber_use_corruption",
            "jeu_d_armes": "chamber_use_jeu_d_armes",
            "garde_royale": "chamber_use_garde",
            "patrouille": "chamber_use_patrouille",
        }
        for card, held in cards:
            if not held:
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
            view.add_item(discord.ui.ActionRow(*row[:5]))
        await open_unique_ephemeral(interaction, content=text, view=view if row else None)
