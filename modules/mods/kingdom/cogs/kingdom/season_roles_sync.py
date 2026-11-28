"""The season's King/Lord roles converge from the season data.

saisons-roles-v1 (Drasah 24/11) — l'incident Blanc : la saison était
ENGAGÉE mais le Roi et ses membres ne voyaient ni Kingdom-Gaïa ni les
champs de bataille. Les salons de ces catégories s'ouvrent par les
rôles « Kingdom King » / « Kingdom Lord »... que RIEN ne distribuait :
l'acceptation enrôlait côté moteur, la clé existait, personne ne la
posait dans la serrure (la liaison perdue de la divergence — l'ancienne
version avait ce geste, le portage ne l'a jamais branché).

Le choix d'architecture n'est PAS une copie de l'ancien geste-événement
mais une CONVERGENCE : les rôles attendus se calculent à chaque passe
depuis les données de la saison (les royaumes ENGAGÉS : le Roi, ses
membres), puis Discord suit — les manquants sont posés, les en trop
retirés. Une seule mécanique couvre l'acceptation, le RATTRAPAGE des
saisons déjà lancées, l'éjection d'un membre ou d'un royaume, et la FIN
DE SAISON (plus d'engagement = état attendu vide = retour à l'origine,
gratuitement). Strictement limitée aux DEUX rôles du mod : aucun autre
rôle du serveur n'est touché ; les ids se résolvent par le mapping
persisté (renommable), jamais par nom.
"""

from __future__ import annotations

import logging
from typing import Any

from .common import wiring

logger = logging.getLogger("kingdom.season_roles_sync")

MOD = "kingdom"
# role keys per conf/mod.yaml — King wears the crown, Lords follow
ROLE_KING = "kingdom_king"
ROLE_LORD = "kingdom_lord"


async def _resolve_role(bot: Any, guild: Any, role_key: str) -> Any:
    """Return the live Discord role by its PERSISTED id (never a name)."""
    roles_service = getattr(bot, "mod_roles_service", None)
    if roles_service is None:
        return None
    gid = str(getattr(guild, "id", "") or "")
    try:
        resolved = await roles_service.resolve_role_id(gid, MOD, role_key)
    except Exception:  # a missing role skips, never a raise
        logger.warning("kingdom: the season role read failed (%s)", role_key, exc_info=True)
        return None
    if not resolved or not str(resolved).isdigit():
        return None
    get_role = getattr(guild, "get_role", None)
    return get_role(int(resolved)) if get_role is not None else None


async def _expected_holders(bot: Any) -> tuple[set[str], set[str]]:
    """Return the season's truth : kings first, lords after (never both)."""
    stack = wiring()
    service = getattr(stack, "realms", None) if stack is not None else None
    if service is None:
        return set(), set()
    try:
        realms = await service.realms()
    except Exception:  # a read, never a crash
        logger.warning("kingdom: the season roles read failed", exc_info=True)
        return set(), set()
    kings: set[str] = set()
    lords: set[str] = set()
    for realm in realms or []:
        if getattr(realm, "archived_at", 0):
            continue  # archivé : plus de saison, plus de rôle
        if not bool(getattr(realm, "engagement", None)):
            continue  # dormant : la saison n'est pas engagée
        kings.add(str(getattr(realm, "king_id", "") or ""))
        lords.update(str(m) for m in (getattr(realm, "member_ids", []) or []))
    kings.discard("")
    lords.discard("")
    lords -= kings  # le rang le plus haut gagne, jamais les deux
    return kings, lords


async def _member_of(guild: Any, member_id: str) -> Any:
    """Return the live member (cache then fetch, best-effort)."""
    try:
        member = guild.get_member(int(member_id))
    except (TypeError, ValueError):
        member = None
    if member is not None:
        return member
    fetch = getattr(guild, "fetch_member", None)
    if fetch is None:
        return None
    try:
        return await fetch(int(member_id))
    except Exception:
        return None


async def _one_role_converge(guild: Any, role: Any, expected: set[str]) -> int:
    """Add the missing holders, drop the leftovers — ONE role, best-effort."""
    holders = {
        str(getattr(member, "id", ""))
        for member in (getattr(role, "members", None) or [])
    }
    if holders == expected:
        return 0  # converged — zero Discord API call
    moved = 0
    for member_id in sorted(expected - holders):
        member = await _member_of(guild, member_id)
        if member is None:
            logger.warning("kingdom: season role target unresolvable (%s)", member_id)
            continue
        try:
            await member.add_roles(role, reason="kingdom: the season's rank")
            moved += 1
        except Exception:
            logger.warning("kingdom: season role grant failed (%s)", member_id, exc_info=True)
    for member in list(getattr(role, "members", None) or []):
        if str(getattr(member, "id", "")) in expected:
            continue
        try:
            await member.remove_roles(role, reason="kingdom: the season moved on")
            moved += 1
        except Exception:
            logger.warning(
                "kingdom: season role revoke failed (%s)", getattr(member, "id", "?"), exc_info=True
            )
    return moved


async def sync_season_roles(bot: Any, guild_id: str = "") -> int:
    """Assert the season's King/Lord roles — the report, never a raise."""
    guilds = (
        [bot.get_guild(int(guild_id))]
        if str(guild_id).isdigit()
        else list(getattr(bot, "guilds", []) or [])
    )
    kings, lords = await _expected_holders(bot)
    moved = 0
    for guild in guilds:
        if guild is None:
            continue
        for role_key, expected in ((ROLE_KING, kings), (ROLE_LORD, lords)):
            role = await _resolve_role(bot, guild, role_key)
            if role is None:
                continue  # rôle non provisionné : la passe reste muette
            try:
                moved += await _one_role_converge(guild, role, expected)
            except Exception:  # never a raise
                logger.warning(
                    "kingdom: the season role pass failed (%s, guild %s)",
                    role_key,
                    getattr(guild, "id", "?"),
                    exc_info=True,
                )
    if moved:
        logger.info("kingdom: season roles converged (%d member-grade change(s))", moved)
    return moved


__all__ = ["sync_season_roles"]
