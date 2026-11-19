"""The 🤝 alliances view (P4.2 — alliances-lisibilite-v1, Drasah 25/10).

One button on the pinned panel, one ephemeral window: the current
hand, the next-cycle projection (kept / arriving / dropping — the
SAME ``_live_hand`` engine as the cycle recalculation, read-only),
the 🎯 near-unlock hints (« à 1 map près ») and the civilizations
locked by another kingdom's active marriage (exclusivity D74).

The cycle recalculation alone decides the truth — this view only
mirrors it without touching a single document.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord

from .common import lord_of, kingdom_by_id, open_unique_ephemeral, strings_for, wiring

logger = logging.getLogger("kingdom.alliances")


def _label(names: dict[str, str], civs: Any) -> str:
    """Render a civilization list with display names (empty → dash)."""
    items = [str(civ) for civ in civs or []]
    if not items:
        return "—"
    return ", ".join(names.get(civ, civ) for civ in items)


def alliances_text(
    strings: dict[str, str],
    kingdom: Any,
    projection: dict[str, Any],
    names: dict[str, str],
) -> str:
    """Compose the alliances window's text (pure, testable)."""
    lines = [f"## {strings['alliances_title'].format(str(getattr(kingdom, 'name', '')))}"]
    lines.append(
        strings["alliances_points"].format(
            int(getattr(kingdom, "marriage_points", 0) or 0),
            int(getattr(kingdom, "arranged_marriage_stock", 0) or 0),
        )
    )
    lines.append(f"### {strings['alliances_hand'].format(len(projection.get('held', [])))}")
    held = list(projection.get("held", []))
    lines.append("• " + _label(names, held) if held else strings["alliances_none"])
    lines.append(f"### {strings['alliances_next_intro']}")
    lines.append(strings["alliances_next_kept"].format(_label(names, projection.get("kept", []))))
    lines.append(
        strings["alliances_next_arriving"].format(_label(names, projection.get("arriving", [])))
    )
    lines.append(
        strings["alliances_next_dropping"].format(_label(names, projection.get("dropping", [])))
    )
    elsewhere = _label(names, projection.get("married_elsewhere", []))
    lines.append(strings["alliances_next_elsewhere"].format(elsewhere))
    near = list(projection.get("near_unlocks", []))
    if near:
        lines.append(f"### {strings['alliances_near_title']}")
        for hint in near:
            lines.append(
                strings["alliances_near_line"].format(
                    names.get(str(hint.get("civ")), str(hint.get("civ"))), str(hint.get("hint"))
                )
            )
    return "\n".join(lines)


class AlliancesButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:alliances$",
):
    """The 🤝 « Alliances » button of the declare panel."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:attack:alliances",
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
    ) -> AlliancesButton:
        return cls(strings_for(interaction)["alliances_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Render the kingdom's alliances projection (read-only)."""
        strings = strings_for(interaction)
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, strings["plan_no_service"])
            return
        lord = await lord_of(stack.kingdoms, str(interaction.user.id), interaction)
        if lord is None or getattr(lord, "kingdom_id", None) is None:
            await open_unique_ephemeral(interaction, strings["not_a_lord"])
            return
        kingdom = await kingdom_by_id(stack.kingdoms, str(lord.kingdom_id))
        if kingdom is None:
            await open_unique_ephemeral(interaction, strings["not_a_lord"])
            return
        try:
            projection = await stack.diplomacy.alliance_projection(str(kingdom.id))
        except Exception:
            logger.warning("kingdom: alliance projection failed", exc_info=True)
            await open_unique_ephemeral(interaction, strings["alliances_no_data"])
            return
        catalog = getattr(stack.config, "civilizations", ()) or ()
        names = {str(civ.key): str(getattr(civ, "display_name", civ.key)) for civ in catalog}
        from .common import surface_footer

        await open_unique_ephemeral(
            interaction,
            alliances_text(strings, kingdom, projection, names)
            + "\n"
            + surface_footer("panel:mod:kingdom:alliances"),
        )
