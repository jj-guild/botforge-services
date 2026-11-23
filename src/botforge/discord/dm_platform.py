"""discord.py platform seam for interactive DMs (#407).

The contract (``IPlatform.send_dm/edit_dm/delete_dm``) carries opaque
view handles (#221); this is where they become real Discord payloads.
The seam resolves users and messages lazily, exactly like every
platform seam: a user id is looked up in the cache first, then fetched,
so a restart that lost its cache still finds the player.

Message references: callers keep DM messages under two shapes — the
message itself (``IMessage``) or a persisted ref
(``{"channel_id": …, "message_id": …}`` — the mod's stored form, the one
that survives a restart). Both are accepted everywhere a message is
expected; a ref is resolved to the live message on demand, and a
resolution miss raises like the contract says (the ``_safe`` wrappers
at the caller's edge swallow, the seam stays honest).
"""

from __future__ import annotations

import logging
from typing import Any, cast

import discord

logger = logging.getLogger("botforge.discord.dm_platform")

UserLike = Any  # IUser, a raw id (str/int) or a discord.User
MessageLike = Any  # IMessage, a {"channel_id", "message_id"} ref or a discord.Message


class DiscordDMPlatform:
    """discord.py implementation of the DM seam (send/edit/delete, with views)."""

    def __init__(self, bot: discord.Client) -> None:
        """Keep a client reference for user and channel lookups."""
        self._bot = bot

    async def _user(self, user: UserLike) -> discord.abc.User | None:
        """Resolve the target user: object, cached id, then fetched id."""
        if isinstance(user, discord.abc.User):
            return user
        raw = getattr(user, "id", user)
        user_id = str(raw)
        if not user_id.isdigit():
            return None
        found = self._bot.get_user(int(user_id))
        if found is not None:
            return found
        try:
            return await self._bot.fetch_user(int(user_id))
        except Exception:
            logger.warning("DM user unreachable (%s)", user_id, exc_info=True)
            return None

    async def _message(self, message: MessageLike) -> discord.Message | None:
        """Resolve a DM message: the object, or a persisted channel/message ref."""
        if isinstance(message, discord.Message):
            return message
        channel_id = getattr(message, "channel_id", None)
        message_id = getattr(message, "message_id", None)
        if channel_id is None and isinstance(message, dict):
            channel_id = message.get("channel_id")
            message_id = message.get("message_id")
        channel_raw = int(channel_id or 0)
        message_raw = int(message_id or 0)
        if not channel_raw or not message_raw:
            return None
        channel = self._bot.get_channel(channel_raw)
        if channel is None:
            channel = await self._bot.fetch_channel(channel_raw)
        # Duck-typed on purpose (ADR-0011): any messageable channel —
        # a real DMChannel or a test double — fetches the same way.
        if not hasattr(channel, "fetch_message"):
            return None
        return await cast("discord.abc.Messageable", channel).fetch_message(message_raw)

    async def send_dm(
        self, user: UserLike, content: str, view: Any | None = None
    ) -> discord.Message:
        """Send the DM (optionally interactive) — raises when unreachable."""
        target = await self._user(user)
        if target is None:
            raise RuntimeError(f"DM user unreachable: {getattr(user, 'id', user)}")
        messageable = cast("discord.abc.Messageable", target)
        if view is None:
            return await messageable.send(content)
        return await messageable.send(content, view=cast("discord.ui.View", view))

    async def edit_dm(
        self, message: MessageLike, content: str, view: Any | None = None
    ) -> discord.Message:
        """Edit a sent DM in place — raises when the message is gone."""
        resolved = await self._message(message)
        if resolved is None:
            raise RuntimeError("DM message unresolvable")
        return await resolved.edit(content=content, view=cast("discord.ui.View | None", view))

    async def delete_dm(self, message: MessageLike) -> None:
        """Delete a sent DM — a miss is a no-op, never an error."""
        try:
            resolved = await self._message(message)
        except Exception:
            logger.info("DM delete resolution failed (ignored)", exc_info=True)
            return
        if resolved is None:
            return
        try:
            await resolved.delete()
        except Exception:
            logger.info("DM delete failed (ignored)", exc_info=True)
