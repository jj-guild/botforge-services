"""The registration's salon gate (salon-parcours-v2, Drasah 18/11).

The parcours is TWO salons: « register » is public, « apply » (the
Postuler salon) denies @everyone and opens ONLY to the players whose
project account exists. The access rule is a ROLE — « Kingdom
Enregistré » — granted the moment the platform binds an AoE2 profile
(the core's ``profile.bound`` event, fanned out by the Discord sink),
revoked when the last binding goes.

salon-parcours-v2-fix (Drasah 18/11, live incident): the bind ALONE is
not enough — (1) ``guild.get_member`` returns None without the members
intent, so the grant silently skipped (the 27/10 lesson: never trust a
best-effort live member cache); (2) accounts bound BEFORE this gate
existed never fire ``profile.bound`` again. The member resolution now
falls back to ``fetch_member`` (one API call, allowed), every skip is
a LOUD warning (nothing may fail silently), and ``on_ready`` runs a
self-heal that re-grants the role from the DECLARED truth (the
bindings' guild_id, rule 5), so a boot converges the parcours by
itself.

The mod owns the SHAPE (which role, which salons read it — all data in
``mod.yaml``); the platform owns the MECHANICS (the bind, the event,
the sink). Never a local re-read of the platform's database: the event
carries everything, and the heal reads the service's seam.
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


async def _resolve_member(guild: Any, user_id: str) -> Any:
    """One guild member, cache first, fetch fallback (no members intent)."""
    if not str(user_id).isdigit():
        return None
    member = guild.get_member(int(user_id))
    if member is not None:
        return member
    try:
        return await guild.fetch_member(int(user_id))
    except Exception:
        # LOUD: a skipped grant means a registered player stares at an
        # invisible salon — this may never fail silently (27/10 lesson).
        logger.warning(
            "kingdom: the register gate could not resolve member %s in guild %s",
            user_id,
            getattr(guild, "id", "?"),
            exc_info=True,
        )
        return None


async def _toggle_role(bot: Any, guild_id: str, user_id: str, *, grant: bool, reason: str) -> None:
    """Grant or revoke the access role on one member (best-effort)."""
    guild = bot.get_guild(int(guild_id)) if str(guild_id).isdigit() else None
    if guild is None:
        logger.warning("kingdom: the register gate skipped — guild %s not in cache", guild_id)
        return
    role_id = await _resolve_role_id(bot, guild_id)
    role = guild.get_role(role_id) if role_id else None
    if role is None:
        # the role is provisioned at install/Repair; a bind before that
        # moment would silently lose the grant — the boot heal catches
        # up, but the operator must hear it now.
        logger.warning(
            "kingdom: the register gate SKIPPED — the « Kingdom Enregistré » role is not "
            "provisioned yet (guild %s, resolved id %r); run the mod's Repair",
            guild_id,
            role_id,
        )
        return
    member = await _resolve_member(guild, user_id)
    if member is None:
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
        logger.warning(
            "kingdom: the register gate ignored a %s without guild/user context (%r)",
            intent,
            payload,
        )
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


async def reconcile_guild_access(bot: Any) -> None:
    """Boot self-heal: every registered player carries the access role.

    The DECLARED truth wins (the bindings' guild_id read through the
    registration service's seam — rule 5, never the raw database): each
    guild's registrants are re-granted the role, so an account bound
    before the role existed (or a Discord hiccup at bind time) opens
    the Postuler salon at the next boot anyway. Grants only — revokes
    ride the ``profile.unbound`` event; a stale role holder would merely
    see the salon (no write path), and pruning the whole roster per
    boot would abuse the API (rate-limit lesson 27/10).
    """
    registration = getattr(bot, "registration_service", None)
    list_registrants = getattr(registration, "list_guild_registrant_ids", None)
    if list_registrants is None:
        logger.warning(
            "kingdom: the register gate self-heal is DEAD — no registration seam with "
            "list_guild_registrant_ids on the bot (registration_service=%r)",
            registration,
        )
        return
    for guild in list(getattr(bot, "guilds", None) or []):
        guild_id = str(guild.id)
        role_id = await _resolve_role_id(bot, guild_id)
        if role_id is None:
            logger.warning(
                "kingdom: the register gate self-heal SKIPPED guild %s — the « Kingdom "
                "Enregistré » role is not provisioned; run the mod's Repair",
                guild_id,
            )
            continue
        users = await list_registrants(guild_id)
        granted = 0
        for user_id in users:
            member = await _resolve_member(guild, user_id)
            role = guild.get_role(role_id)
            if member is None or role is None:
                continue
            try:
                if role not in member.roles:
                    await member.add_roles(
                        role, reason="botforge: the register gate self-heal (boot reconcile)"
                    )
                    granted += 1
            except Exception:
                logger.warning("kingdom: the register gate self-heal failed for user %s", user_id, exc_info=True)
        logger.info(
            "kingdom: the register gate self-heal ran (guild %s, %d registrant(s), %d grant(s))",
            guild_id,
            len(users),
            granted,
        )


def subscribe_profile_gate(bot: Any) -> None:
    """Register the gate on the bot's registration-event subscribers."""
    from botforge.discord.registration_events import subscribe_registration_events

    subscribe_registration_events(bot, profile_event_handler)
    # the one-shot boot heal (on_ready fires per (re)connect; the flag
    # keeps the reconcile to the boot that matters)
    if getattr(bot, "_kingdom_gate_reconciled", False):
        return

    async def _on_ready_gate() -> None:
        if getattr(bot, "_kingdom_gate_reconciled", False):
            return
        bot._kingdom_gate_reconciled = True
        try:
            await reconcile_guild_access(bot)
        except Exception:
            logger.exception("kingdom: the register gate self-heal crashed at boot (best-effort)")

    bot.add_listener(_on_ready_gate, "on_ready")
