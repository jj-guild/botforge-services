"""The 💍 marriage wizard (P4.2 — paroisse-v1, Drasah 06/11).

One button on the pinned panel, one ephemeral window: the wizard lists
the kingdom's hand as PRINCESSES (the seeded ``_pick_promise`` — never
a raw civilization), the confirm card carries the rings, the palier's
combat lock and its indicative Paris end, and the sealed marriage
announces itself in Géopolitique (the royal pattern — EVERY marriage
is announced, paroisse-v1).

The exclusivity is D74 (a civilization already claimed by ANY active
marriage is never listed) and the cost is D59 (one marriage point —
two for a King's royal marriage, D45/D60). The engine owns every
check; this surface only renders and reports.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

import discord

from .common import lord_of, open_unique_ephemeral, strings_for, wiring

logger = logging.getLogger("kingdom.marry")

_PARIS = ZoneInfo("Europe/Paris")


def _marry_cost(lord: Any, kingdom: Any, tier: Any) -> tuple[int, int, bool]:
    """The (rings, lock_hours, royal) triple of the clicker's marriage."""
    royal = str(getattr(lord, "role", "")) == "king"
    rings = 2 if royal else 1
    hours = int(getattr(tier, "marriage_lock_hours", 24)) * (2 if royal else 1)
    return rings, hours, royal


def _princess_label(
    strings: dict[str, str], lord_id: str, civ_key: str, civ_names: dict[str, str]
) -> str:
    """Name the PRINCESS, never a raw civilization (paroisse-retours-v1).

    The promise is seeded (``lord:civ``) — stable across every view
    and restart-proof, exactly like the ref's Les Fidèles badge.
    """
    from botforge.mods.kingdom.diplomacy import _pick_promise

    civ_display = civ_names.get(civ_key, civ_key)
    promise = _pick_promise(f"{lord_id}:{civ_display}", civ_display)
    named = f"{promise} ({civ_display})" if promise else civ_display
    return str(strings["church_marry_princess"]).format(named)[:100]


def _fmt_marriage_lock_end(hours: int, strings: dict[str, str]) -> str:
    """The INDICATIVE end of the combat lock — a Discord <t:..:R> epoch.

    The discord-ui norm (#381): a user-facing instant never renders as a
    formatted string — the epoch localizes per viewer, never a timezone.
    """
    from botforge.mods.kingdom.game_clock import game_now

    now = game_now()
    end_epoch = int((now + timedelta(hours=int(hours or 0))).timestamp())
    return str(strings["church_marry_lock"]).format(end_epoch)


def _marry_error_note(exc: Exception, strings: dict[str, str]) -> str:
    """Map a diplomacy engine error to a player-facing note."""
    from botforge.mods.kingdom.diplomacy import (
        AlreadyMarriedError,
        CivilizationNotInHandError,
        MarriageError,
        NoMarriagePointsError,
        RoyalMarriagePointsError,
    )

    if isinstance(exc, AlreadyMarriedError):
        return strings["church_marry_already"]
    if isinstance(exc, NoMarriagePointsError):
        return strings["church_marry_no_points"]
    if isinstance(exc, RoyalMarriagePointsError):
        return strings["church_marry_no_points_royal"]
    if isinstance(exc, CivilizationNotInHandError):
        return strings["church_marry_not_in_hand"]
    if isinstance(exc, MarriageError):
        return str(strings["marry_error"]).format(str(exc)[:150])
    return str(strings["marry_error"]).format(str(exc)[:150])


def _civ_names(stack: Any) -> dict[str, str]:
    catalog = getattr(stack.config, "civilizations", ()) or ()
    return {str(civ.key): str(getattr(civ, "display_name", civ.key)) for civ in catalog}


async def _announce_wedding_safe(guild: Any, strings: dict[str, str], text: str) -> None:
    """Publish the wedding in Géopolitique (best effort, zero spam)."""
    from .battle import _geopolitics_channel

    try:
        channel = _geopolitics_channel(guild)
        if channel is not None:
            await channel.send(text)
    except Exception:
        logger.info("kingdom: wedding announcement skipped", exc_info=True)


async def _wizard_view(
    stack: Any, lord: Any, kingdom: Any, strings: dict[str, str]
) -> discord.ui.LayoutView | None:
    """Build the role-adapted 💍 Se marier view (None when nothing to wed).

    The view ADAPTS to the clicker: a lord sees ONE ring and the
    palier's lock, the King sees TWO rings and the doubled royal lock
    with the MARIAGE ROYAL badge. The select lists the kingdom's
    playable hand minus every civilization already claimed by an
    active marriage (exclusivity D74, all kingdoms).
    """
    tier = stack.config.parish.tier(getattr(kingdom, "parish_tier", 1))
    rings, hours, royal = _marry_cost(lord, kingdom, tier)
    lords = await stack.kingdoms.lords()
    married = {
        str(item.married_civilization)
        for item in lords
        if getattr(item, "married_civilization", None) is not None
    }
    names = _civ_names(stack)
    options = [
        discord.SelectOption(
            label=_princess_label(strings, str(lord.id), str(civ), names),
            value=str(civ)[:100],
        )
        for civ in kingdom.civilizations
        if str(civ) not in married
    ][:25]
    if not options:
        return None

    header = f"## {strings['church_marry_view_title'].format(str(getattr(lord, 'display_name', lord.id)))}"
    if royal:
        header += f" — `{strings['church_marry_badge']}`"
    rules = strings["church_marry_rules"].format(rings, hours, _fmt_marriage_lock_end(hours, strings))
    if royal:
        rules += "\n" + strings["church_marry_rules_royal"]

    select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id=f"kingdom:attack:marryciv:{str(lord.id)[:60]}",
        placeholder=str(strings["church_marry_intro"])[:100],
        options=options,
    )

    async def on_choose(target: discord.Interaction) -> None:
        values = getattr(target, "data", None) or {}
        chosen = [str(v) for v in values.get("values", [])]
        if not chosen:
            return
        civ_key = chosen[0]
        confirm = _confirm_view(stack, strings, lord, kingdom, civ_key, names, rings, hours)
        await target.response.edit_message(view=confirm)

    select.callback = on_choose  # type: ignore[method-assign, assignment]
    from .common import surface

    return surface(
        "panel:mod:kingdom:church:marry",
        discord.ui.TextDisplay(header),
        discord.ui.TextDisplay(rules),
        discord.ui.ActionRow(select),
    )


def _confirm_view(
    stack: Any,
    strings: dict[str, str],
    lord: Any,
    kingdom: Any,
    civ_key: str,
    names: dict[str, str],
    rings: int,
    hours: int,
) -> discord.ui.LayoutView:
    """The confirmation card — the select is OVERWRITTEN in place."""
    princess = _princess_label(strings, str(lord.id), civ_key, names)
    body = (
        f"## {strings['church_marry_confirm_title']}\n"
        f"**{princess}**\n"
        f"{strings['church_marry_confirm_sub'].format(rings, hours)}"
    )
    yes: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["church_marry_yes_button"])[:80],
        custom_id=f"kingdom:attack:marryyes:{str(lord.id)[:50]}",
        style=discord.ButtonStyle.success,
    )
    edit: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["church_marry_edit_button"])[:80],
        custom_id=f"kingdom:attack:marryedit:{str(lord.id)[:50]}",
        style=discord.ButtonStyle.secondary,
    )

    async def on_yes(target: discord.Interaction) -> None:
        await target.response.defer()
        try:
            await stack.diplomacy.marry(str(lord.id), civ_key)
        except Exception as exc:  # noqa: BLE001 — every engine refusal is a note
            await target.followup.send(_marry_error_note(exc, strings), ephemeral=True)
            return
        tier = stack.config.parish.tier(getattr(kingdom, "parish_tier", 1))
        offering = int(getattr(tier, "offering", 0) or 0)
        lord_name = str(getattr(lord, "display_name", str(lord.id)))
        kingdom_name = str(getattr(kingdom, "name", ""))
        await _announce_wedding_safe(
            target.guild,
            strings,
            str(strings["church_wedding_announce"]).format(
                lord_name, kingdom_name, princess, hours, offering
            ),
        )
        sealed = (
            f"## {strings['church_marry_sealed_title'].format(names.get(civ_key, civ_key))}\n"
            f"{strings['church_marry_sealed_note']}"
        )
        try:
            await target.edit_original_response(content=sealed, view=None)
        except Exception:
            await target.followup.send(sealed, ephemeral=True)
        # alliances-evenementiel-v1 (Drasah 23/11) : le mariage ajoute
        # la civilisation à la main IMMÉDIATEMENT (diplomacy.marry) —
        # LE déclencheur du panneau 🏆, rafraîchi sur l'événement (le
        # moteur a déjà écrit la main : le rendu lit le document vivant).
        try:
            from .realm_content import refresh_alliance_panels

            await refresh_alliance_panels(target.client, [str(getattr(kingdom, "id", ""))])
        except Exception:  # noqa: BLE001 — the panel never blocks the wedding
            logger.warning("kingdom: alliances event refresh (marriage) failed", exc_info=True)

    async def on_edit(target: discord.Interaction) -> None:
        fresh = await _wizard_view(stack, lord, kingdom, strings)
        if fresh is None:
            await target.response.edit_message(
                content=strings["church_marry_no_options"], view=None
            )
            return
        await target.response.edit_message(content=None, view=fresh)

    yes.callback = on_yes  # type: ignore[method-assign, assignment]
    edit.callback = on_edit  # type: ignore[method-assign, assignment]
    from .common import surface

    return surface(
        "panel:mod:kingdom:church:confirm",
        discord.ui.TextDisplay(body),
        discord.ui.ActionRow(yes, edit),
    )


class MarryButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:marry$",
):
    """The 💍 « Se marier » button of the declare panel."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:attack:marry",
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
    ) -> MarryButton:
        return cls(strings_for(interaction)["marry_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the marriage wizard (one ephemeral window)."""
        strings = strings_for(interaction)
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, strings["plan_no_service"])
            return
        lord = await lord_of(stack.kingdoms, str(interaction.user.id), interaction)
        if lord is None or getattr(lord, "kingdom_id", None) is None:
            await open_unique_ephemeral(interaction, strings["not_a_lord"])
            return
        if getattr(lord, "married_civilization", None) is not None:
            await open_unique_ephemeral(interaction, strings["church_marry_already"])
            return
        kingdom = next(
            (
                item
                for item in await stack.kingdoms.kingdoms()
                if str(item.id) == str(lord.kingdom_id)
            ),
            None,
        )
        if kingdom is None:
            await open_unique_ephemeral(interaction, strings["not_a_lord"])
            return
        view = await _wizard_view(stack, lord, kingdom, strings)
        if view is None:
            await open_unique_ephemeral(interaction, strings["church_marry_no_options"])
            return
        await open_unique_ephemeral(interaction, view=view)
