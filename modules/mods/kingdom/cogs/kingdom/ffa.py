"""The 🧭 Saturday FFA Exploration (P4.5, #368).

Each Saturday the engine draws a random start hour and announces the
Expedition in Géopolitique 2h before the game — the announcement
carries this persistent « Aller explorer » button. Registration is
FREE, capped by the Gaïa free-for-all ceiling, toggle-secured: a
second click before the start RELEASES the slot (a quitter never
blocks a seat). The engine owns every check; this surface only
toggles and reports.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord

from .common import strings_for, wiring

logger = logging.getLogger("kingdom.ffa")


def _ffa_error_note(exc: Exception, strings: dict[str, str]) -> str | None:
    """Map the engine refusals to their notes (None falls back to generic)."""
    from botforge.mods.kingdom.attacks import LordLockedError
    from botforge.mods.kingdom.ffa_exploration import (
        FFAKingdomFullError,
        FFAFullError,
        FFANotOpenError,
    )

    if isinstance(exc, FFANotOpenError):
        return str(strings["ffa_not_open"])
    if isinstance(exc, FFAFullError):
        return str(strings["ffa_full"])  # the {max} placeholder stays free-form
    if isinstance(exc, FFAKingdomFullError):
        return str(strings["ffa_kingdom_full"])
    if isinstance(exc, LordLockedError):
        return str(strings["ffa_locked"])
    return None


def _ffa_join_view(strings: dict[str, str]) -> discord.ui.LayoutView:
    """The persistent join button view riding the Géopolitique announce."""
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.ActionRow(FFAJoinButton(strings["ffa_join_button"])))
    return view


class FFAJoinButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:ffajoin$",
):
    """The restart-proof 🗺️ « Aller explorer » button (ffa-exploration-v1).

    Any lord of the season may click to RESERVE a free slot; a second
    click before the start RELEASES it (the toggle settles the open
    withdrawal point — a quitter never blocks a seat).
    """

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:attack:ffajoin",
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
    ) -> FFAJoinButton:
        return cls(strings_for(interaction)["ffa_join_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Toggle the lord's FFA slot (join/leave), ephemeral note."""
        strings = strings_for(interaction)
        stack = wiring()
        ffa_service = getattr(stack, "ffa", None) if stack is not None else None
        if ffa_service is None:
            await interaction.response.send_message(
                strings["plan_no_service"], ephemeral=True
            )
            return
        from botforge.mods.kingdom.ffa_exploration import FFA_JOINED

        try:
            state, ffa = await ffa_service.enroll(str(interaction.user.id))
        except Exception as exc:  # noqa: BLE001 — every engine refusal is a note
            note = _ffa_error_note(exc, strings)
            if note is None:
                note = str(strings["tavern_error"]).format(str(exc)[:150])
            await interaction.response.send_message(note, ephemeral=True)
            return
        count = len(ffa.participants)
        maximum = int(ffa_service.max_participants())
        if state == FFA_JOINED:
            note = str(strings["ffa_join_note"]).format(
                interaction.user.display_name, count, maximum
            )
        else:
            note = str(strings["ffa_left_note"]).format(
                interaction.user.display_name, count, maximum
            )
        await interaction.response.send_message(note, ephemeral=True)
