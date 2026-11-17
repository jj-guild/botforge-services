"""The kingdom mod's Discord cog (§7): commands and views.

The cog is the mod's ONLY Discord layer. It calls the mod's service
through the contract (``mod_service``) and builds its UI through the
botforge UI SDK — never the service's internals.
"""

from __future__ import annotations

import discord

from botforge.core.services.mod_entrypoint import mod_service
from botforge.discord.ui import BLURPLE, Container, Text, UILayout


async def status_view(guild_id: str) -> discord.ui.LayoutView:
    """Render the service's status through the UI SDK."""
    service = mod_service("kingdom")
    status = await service.KingdomServiceImpl().status(guild_id)
    from botforge.discord.ui.view_footer import add_view_footer

    body = (
        UILayout()
        .add(
            Container(accent=BLURPLE).add(
                Text("# Kingdom"),
                Text(f"state: {status.get('state', 'unknown')}"),
            )
        )
        .build()
    )
    # the declared-surface footer rides the built layout (#381 ruling 1)
    return add_view_footer(body, "surface:mod:kingdom:status")
