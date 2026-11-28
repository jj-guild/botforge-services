"""discord.py platform seam for dynamic channels (#408).

The gameplay channels — attack salons, battle voice rooms, the FFA
salon — are EPHEMERAL structure: provisioned on demand, purged when
the moment passes. The static structure already lives in declared
data (mod.yaml, seams #264); this seam gives the dynamic half the
same treatment: overwrites as DATA (#221), the Discord objects built
here and only here.

Overwrite keys are logical targets resolved at creation time:
``@everyone``, ``@me`` (the bot itself — the lesson of the channel a
bot locked itself out of), or a role NAME. A role that no longer
exists is skipped with a warning: a missing role must not abort the
provisioning of the channel the game needs.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, cast

import discord

logger = logging.getLogger("botforge.discord.dynamic_channels")

EVERYONE_KEY = "@everyone"
BOT_KEY = "@me"


async def resolve_client_member(guild: Any) -> Any:
    """The bot's OWN member on a guild — cache first, FETCH fallback.

    client-me-v1 (Drasah 28/11, live incident): ``guild.me`` reads the
    member cache and can come back None (an empty cache, the Members
    intent off, a guild resolved outside the cache) — the bot is then
    unable to see ITSELF: every self-permission decision (the @me
    overwrite at creation, the channel-level heal) silently no-ops
    while the server-side role holds every right. The fetch path
    (the client's own user id) always resolves; a refused fetch keeps
    returning None (best effort, never a raise).
    """
    me = getattr(guild, "me", None)
    if me is not None:
        return me
    fetch_member = getattr(guild, "fetch_member", None)
    if fetch_member is None:
        return None
    state = getattr(guild, "_state", None)
    user = getattr(state, "user", None)
    if user is None:
        get_client = getattr(state, "_get_client", None)
        user = getattr(get_client() if callable(get_client) else None, "user", None)
    user_id = int(getattr(user, "id", 0) or 0)
    if not user_id:
        return None
    try:
        me = await fetch_member(user_id)
    except Exception:
        logger.debug(
            "client member fetch refused on guild %s", getattr(guild, "id", "?"), exc_info=True
        )
        return None
    logger.info("client member resolved by fetch on guild %s", getattr(guild, "id", "?"))
    return me


class DiscordDynamicChannelsPlatform:
    """discord.py implementation of the dynamic-channel seam (create/delete)."""

    def __init__(self, bot: discord.Client) -> None:
        """Keep a client reference for guild and channel lookups."""
        self._bot = bot

    async def _guild(self, guild_id: str) -> discord.Guild | None:
        guild = self._bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        if guild is None and guild_id.isdigit():
            try:
                guild = await self._bot.fetch_guild(int(guild_id))
            except Exception:
                return None
        return guild

    def _overwrites(
        self, guild: discord.Guild, data: Mapping[str, Mapping[str, bool]] | None
    ) -> dict[discord.Role | discord.Member, discord.PermissionOverwrite]:
        """Translate the data-form overwrites into Discord objects.

        Duck-typed guild surfaces (test doubles) resolve the same way:
        default_role, me and roles are the guild's whole surface here.
        """
        resolved: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {}
        for key, perms in (data or {}).items():
            target: Any = None
            if key == EVERYONE_KEY:
                target = getattr(guild, "default_role", None)
            elif key == BOT_KEY:
                target = getattr(guild, "me", None)
            else:
                target = discord.utils.get(getattr(guild, "roles", []), name=key)
            if target is None:
                logger.warning("dynamic channel overwrite target missing: %s (skipped)", key)
                continue
            resolved[target] = discord.PermissionOverwrite(**{k: bool(v) for k, v in perms.items()})
        return resolved

    async def create_channel(
        self,
        guild_id: str,
        name: str,
        category_id: str | None = None,
        kind: str = "text",
        overwrites: Mapping[str, Mapping[str, bool]] | None = None,
        position: int | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> discord.abc.GuildChannel:
        """Create the text or voice channel — raises when the guild is unreachable."""
        guild = await self._guild(guild_id)
        if guild is None:
            raise RuntimeError(f"dynamic channel guild unreachable: {guild_id}")
        category = None
        if category_id is not None and str(category_id).isdigit():
            # Whatever the lookup returns IS the category (a wrong id
            # surfaces at the platform call, and the _safe edge owns
            # the degradation) — duck-typed like the rest of the seam.
            category = cast("discord.CategoryChannel | None", self._bot.get_channel(int(category_id)))
        resolved = self._overwrites(guild, overwrites)
        # The bot never locks itself out of the channel it provisions:
        # @me always carries the full bot allow (manage_channels included —
        # purging an ephemeral room needs it), above all inside a private
        # parent category (#413). An explicit @me from the caller is
        # normalized to that allow — view_channel is never denied.
        # client-me-v1: the member resolves through the robust helper
        # (cache first, FETCH fallback) — a bot that cannot see itself
        # in the cache still carries its allow.
        me = await resolve_client_member(guild)
        if me is not None:
            resolved[me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                manage_channels=True,
            )
        # The optional data forms map onto discord.py's call — a position
        # of None means "no hint", not "position zero".
        kwargs: dict[str, Any] = {"category": category}
        if position is not None:
            kwargs["position"] = position
        if resolved:
            kwargs["overwrites"] = resolved
        kwargs.update(options or {})
        if kind == "voice":
            channel = await guild.create_voice_channel(name, **kwargs)
        else:
            channel = await guild.create_text_channel(name, **kwargs)
        # birth-check-v1 (Drasah 28/11): the provisioning's own entry is
        # verified on the LIVE channel the moment it exists — a creation
        # whose @me allow did not land surfaces in the logs at once
        # (✅/⚠️), never as an undeletable ghost discovered mid-game.
        await self._log_birth_check(channel, me)
        return channel

    async def _log_birth_check(self, channel: Any, me: Any) -> None:
        """Verify the bot's allow on the just-created channel, best effort."""
        if me is None:
            logger.warning(
                "birth check: client member unresolved — channel %s created without a verified @me allow",
                getattr(channel, "id", "?"),
            )
            return
        overwrites_for = getattr(channel, "overwrites_for", None)
        if overwrites_for is None:
            return
        try:
            ok = bool(overwrites_for(me).manage_channels)
        except Exception:
            logger.debug("birth check read failed", exc_info=True)
            return
        if ok:
            logger.info(
                "birth check ✅ — channel %s carries the bot's manage_channels allow",
                getattr(channel, "id", "?"),
            )
        else:
            logger.warning(
                "birth check ⚠️ — channel %s does NOT carry the bot's manage_channels allow (Discord refused it)",
                getattr(channel, "id", "?"),
            )

    async def delete_channel(self, channel_id: str) -> None:
        """Delete the channel — best-effort, a miss is never an error."""
        raw = int(channel_id) if str(channel_id).isdigit() else 0
        if not raw:
            return
        channel = self._bot.get_channel(raw)
        if channel is None:
            logger.info("dynamic channel already gone (%s)", channel_id)
            return
        await cast("discord.abc.GuildChannel", channel).delete()
