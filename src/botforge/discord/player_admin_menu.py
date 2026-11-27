"""The players forum's admin menu - the displayed player's accounts.

The post's card carries one \u2699\ufe0f Admin button (the entity-card
contract, owner 2026-11-26): the click opens an EPHEMERAL menu whose
buttons are the profile panel's own add/remove - aoe2-focused, no
rename (a rename floods, the retitle rides the identity service's own
hooks). The gate (owner's word): a GLOBAL bot operator (BOT_ADMINS)
or the DISPLAYED player himself; a guild admin of the day, a random
member, nobody else.

The bar's view id is the player's own panel (owner 2026-11-26:
"le panel admin n'a pas le bon id, mets : panel:player:aoe2:1234") -
the admin menu speaks the SAME id as the card it manages.
"""

from __future__ import annotations

import re
from typing import Any

import discord

_NS = "panel:admin:player"


class PlayerAdminButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:(?P<uid>\d+)",
):
    """The player card's single \u2699\ufe0f Admin button (persistent)."""

    def __init__(self, user_id: str) -> None:
        self.user_id = str(user_id)
        super().__init__(
            discord.ui.Button(
                label="Admin",
                emoji="\u2699\ufe0f",
                style=discord.ButtonStyle.secondary,
                custom_id=f"{_NS}:{self.user_id}"[:100],
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> PlayerAdminButton:
        """Rebuild the button from the wire."""
        del interaction, item
        return cls(match.group("uid"))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard, then open the displayed player's account menu (ephemeral)."""
        from botforge.discord.home import _player_menu_bar, _player_menu_guard

        if not await _player_menu_guard(interaction, self.user_id):
            return
        view = await _player_menu_bar(interaction, self.user_id)
        # the menu answers as a NEW EPHEMERAL message - never an edit of
        # the public post it rides on (the entity-menu rule)
        await interaction.response.send_message(view=view, ephemeral=True)


def register_player_admin_items(bot: discord.Client) -> None:
    """Register the player admin wire items."""
    bot.add_dynamic_items(PlayerAdminButton)


__all__ = ["PlayerAdminButton", "register_player_admin_items"]
