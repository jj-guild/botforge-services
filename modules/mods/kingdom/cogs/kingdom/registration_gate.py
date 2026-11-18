"""The registration's salon gate (salon-parcours-v2, Drasah 18/11).

The parcours is TWO salons: « register » is public, « apply » (the
Postuler salon) denies @everyone and opens ONLY to the players whose
project account exists. The access rule is a ROLE — « Kingdom
Enregistré » — granted the moment the platform binds an AoE2 profile
(the core's ``profile.bound`` event, fanned out by the Discord sink),
revoked when the last binding goes.

The mod owns the SHAPE (which role, which salons read it — all data in
``mod.yaml``); the platform owns the MECHANICS (the bind, the event,
the sink). Never a local re-read of the platform's database: the event
carries everything.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("kingdom.registration_gate")

MOD = "kingdom"
ROLE_KEY = "enregistre"


async def _resolve_role_id(bot: Any, guild_id: str) -> int | None:
    """The « Kingdom Enregistré » role id (the persisted ids resolver)."""
    roles_service = getattr(bot, "mod_roles_service", None)
    if roles_service is None:
        return None
    role_id = await roles_service.resolve_role_id(guild_id, MOD, ROLE_KEY)
    if role_id and str(role_id).isdigit():
        return int(role_id)
    return None


async def _toggle_role(bot: Any, guild_id: str, user_id: str, *, grant: bool, reason: str) -> None:
    """Grant or revoke the access role on one member (best-effort)."""
    guild = bot.get_guild(int(guild_id)) if str(guild_id).isdigit() else None
    if guild is None:
        return
    role_id = await _resolve_role_id(bot, guild_id)
    role = guild.get_role(role_id) if role_id else None
    member = guild.get_member(int(user_id)) if str(user_id).isdigit() else None
    if role is None or member is None:
        logger.info("kingdom: the register gate skipped (guild %s role %s member %s)", guild_id, role_id, user_id)
        return
    try:
        if grant and role not in member.roles:
            await member.add_roles(role, reason=reason)
        if not grant and role in member.roles:
            await member.remove_roles(role, reason=reason)
    except Exception:
        logger.warning("kingdom: the register gate role toggle failed", exc_info=True)


async def profile_event_handler(intent: str, payload: dict[str, Any]) -> None:
    """React to the platform's registration events (the gate's rule)."""
    from .panel import current_bot

    bot = current_bot()
    if bot is None:
        return
    guild_id = str(payload.get("guild_id", "") or "")
    user_id = str(payload.get("user_id", "") or "")
    if not guild_id or not user_id:
        return
    if intent == "profile.bound":
        await _toggle_role(
            bot, guild_id, user_id, grant=True, reason="botforge: the account exists — the Postuler salon opens"
        )
    elif intent == "profile.unbound":
        # the gate closes ONLY when the LAST binding goes (multi-profile)
        if payload.get("remaining"):
            return
        await _toggle_role(
            bot, guild_id, user_id, grant=False, reason="botforge: no account left — the Postuler salon closes"
        )


def subscribe_profile_gate(bot: Any) -> None:
    """Register the gate on the bot's registration-event subscribers."""
    from botforge.discord.registration_events import subscribe_registration_events

    subscribe_registration_events(bot, profile_event_handler)
