"""liaison-roless-saison-v1 — the season's Discord roles (Drasah 24/11).

The live incident : Blanc ENGAGED in season saw neither the battlefields
nor Kingdom-Gaïa — the salons unlock through « Kingdom King » /
« Kingdom Lord » (declared view roles) and NOTHING granted them. The
sync reads the engaged realms, hands the King his crown, the members
their sword, and collects the orphans — converged, zero API call.
"""

from __future__ import annotations

import logging
from typing import Any

from .common import wiring

logger = logging.getLogger("kingdom.season_roles")

MOD = "kingdom"
KING_ROLE_KEY = "kingdom_king"
LORD_ROLE_KEY = "kingdom_lord"
_ROLE_KEYS = (KING_ROLE_KEY, LORD_ROLE_KEY)


def _carries(member: Any, role_id: str) -> bool:
    """Whether a member already wears the resolved role id."""
    for role in getattr(member, "roles", None) or []:
        if str(getattr(role, "id", "")) == role_id:
            return True
    return False


async def sync_season_roles(bot: Any, guild: Any) -> int:
    """Converge the season's King/Lord roles on one guild; the transitions, never a raise.

    Reads the ENGAGED realms (engagement set, not archived), expects the
    King on ``kingdom_king`` and the members on ``kingdom_lord``, grants
    the missing, removes the orphans (a member no longer in an engaged
    realm loses the role — the cycle's ejection rule). A guild already
    converged costs ZERO Discord API calls.
    """
    guild_id = str(getattr(guild, "id", "") or "")
    if not guild_id.isdigit():
        return 0
    roles_service = getattr(bot, "mod_roles_service", None)
    if roles_service is None:
        return 0
    role_ids = await _resolved_role_ids(roles_service, guild_id)
    if not role_ids:
        return 0
    expected = await _expected_carriers()
    grants = await _grant_missing(roles_service, guild, guild_id, role_ids, expected)
    revoked = await _revoke_orphans(roles_service, guild, guild_id, role_ids, expected)
    if grants or revoked:
        logger.info(
            "kingdom: season roles synced (guild %s) — %d grant(s), %d revoke(s)",
            guild_id,
            grants,
            revoked,
        )
    return grants + revoked


async def _resolved_role_ids(roles_service: Any, guild_id: str) -> dict[str, str]:
    """Return the two declared role keys resolved to ids (a miss skips)."""
    role_ids: dict[str, str] = {}
    for key in _ROLE_KEYS:
        try:
            role_id = await roles_service.resolve_role_id(guild_id, MOD, key)
        except Exception:
            logger.warning("kingdom: the %s role unreadable — skipped", key, exc_info=True)
            continue
        if role_id and str(role_id).isdigit():
            role_ids[key] = str(role_id)
    return role_ids


async def _expected_carriers() -> dict[str, str]:
    """Return the players who SHOULD wear a role — the ENGAGED realms only."""
    expected: dict[str, str] = {}
    service = getattr(wiring() or None, "realms", None)
    if service is None:
        return expected
    try:
        realms = await service.realms()
    except Exception:
        logger.warning("kingdom: the realms read failed — the roles wait", exc_info=True)
        return expected
    for realm in realms or ():
        if getattr(realm, "archived_at", 0):
            continue
        if not getattr(realm, "engagement", None):
            continue
        king = str(getattr(realm, "king_id", "") or "")
        if king:
            expected[king] = KING_ROLE_KEY
        for member_id in getattr(realm, "member_ids", ()) or ():
            uid = str(member_id)
            if uid != king:
                expected[uid] = LORD_ROLE_KEY
    return expected


async def _grant_missing(
    roles_service: Any, guild: Any, guild_id: str, role_ids: dict[str, str], expected: dict[str, str]
) -> int:
    """Hand the missing roles to the engaged realms' members."""
    grants = 0
    for uid, key in expected.items():
        role_id = role_ids.get(key)
        if not role_id:
            continue
        member = getattr(guild, "get_member", lambda _mid: None)(int(uid))
        if member is None:
            # unresolvable members skip loudly (the 2026-10-18 lesson)
            logger.warning(
                "kingdom: member %s unresolved in guild %s — the %s role waits",
                uid,
                guild_id,
                key,
            )
            continue
        if _carries(member, role_id):
            continue
        try:
            await roles_service.assign_platform_role(guild_id, uid, role_id, MOD, key)
            grants += 1
        except Exception:
            logger.warning(
                "kingdom: the %s role grant failed (%s) — best-effort", key, uid, exc_info=True
            )
    return grants


async def _revoke_orphans(
    roles_service: Any, guild: Any, guild_id: str, role_ids: dict[str, str], expected: dict[str, str]
) -> int:
    """Collect the orphan roles — a carrier outside the engaged realms goes home."""
    revoked = 0
    for member in list(getattr(guild, "members", None) or ()):
        uid = str(getattr(member, "id", ""))
        for key, role_id in role_ids.items():
            if not _carries(member, role_id):
                continue
            if expected.get(uid) == key:
                continue
            try:
                await roles_service.remove_platform_role(guild_id, uid, role_id, MOD, key)
                revoked += 1
            except Exception:
                logger.warning(
                    "kingdom: the %s role revoke failed (%s) — best-effort",
                    key,
                    uid,
                    exc_info=True,
                )
    return revoked
