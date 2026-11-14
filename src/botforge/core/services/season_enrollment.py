"""The seasonal enrollment glue — the per-season roles ride the enrollment (P3).

The owner's spec (2026-11-14, refined): the candidate and member
roles are THE MOD'S standard roles (``<Mod> Candidate`` /
``<Mod> Member`` — the registry's trio, no season suffix); what
resets at each new season is the MEMBERSHIP (the roles empty out, a
fresh enrollment fills them). A candidate acquires the candidate
role at apply, loses it and gains the member role at validation; a
refusal drops the candidate role.

The EnrollmentService owns the decisions (criteria, the queue, the
window); the SeasonRolesService owns the per-season roles; this
facade wires the two — the enrollment's states become role
transitions, never a half state.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("botforge.core.services.season_enrollment")


class SeasonEnrollment:
    """The enrollment's decisions wired to the per-season roles."""

    def __init__(
        self,
        enrollment: Any,
        mod_roles: Any,
        active_season: Any,
    ) -> None:
        """Bind the enrollment, the mod's roles service and the season resolver.

        ``active_season(guild_id)`` returns the guild's live season id
        (or None — the transitions degrade quietly when no season
        lives: the enrollment still decides, the roles wait). The
        roles are the MOD'S standard candidate/member keys — resolved
        through the persisted mappings (renamable, never a name
        lookup).
        """
        self._enrollment = enrollment
        self._mod_roles = mod_roles
        self._active_season = active_season

    async def _season_of(self, guild_id: str) -> str:
        try:
            season = await self._active_season(guild_id)
            return str(season) if season else ""
        except Exception:
            logger.warning("SEASON ENROLLMENT: the active season unreadable", exc_info=True)
            return ""

    async def apply(
        self,
        guild_id: str,
        user_id: str,
        display_name: str,
        season: str | None = None,
        now: int = 0,
        season_start: int | None = None,
    ) -> Any:
        """Apply for enrollment; a PENDING application wears the candidate role."""
        application = await self._enrollment.apply(
            guild_id, user_id, display_name, season=season, now=now, season_start=season_start
        )
        del season, season_start
        if str(getattr(application, "state", "")) == "pending":
            await self._assign_role(guild_id, user_id, "candidate", True)
        return application

    async def accept(self, application_id: str, now: int = 0, reason: str = "") -> Any:
        """Validate: the candidate role is LOST, the member role GAINED."""
        application = await self._enrollment.accept(application_id, now=now, reason=reason)
        await self._promote(application)
        return application

    async def refuse(self, application_id: str, now: int = 0, reason: str = "") -> Any:
        """Refuse: the candidate role goes."""
        application = await self._enrollment.refuse(application_id, now=now, reason=reason)
        await self._assign_role(
            str(application.guild_id), str(application.user_id), "candidate", False
        )
        return application

    async def _promote(self, application: Any) -> None:
        """Apply the accept transition: -candidate, +member, one move."""
        guild_id = str(application.guild_id)
        user_id = str(application.user_id)
        await self._assign_role(guild_id, user_id, "candidate", False)
        await self._assign_role(guild_id, user_id, "member", True)

    async def _assign_role(self, guild_id: str, user_id: str, key: str, grant: bool) -> None:
        """Grant or drop one of the mod's standard roles (by stored id)."""
        if self._mod_roles is None:
            return
        try:
            role_id = await self._mod_roles.resolve_role_id(guild_id, self._enrollment._mod, key)
        except Exception:
            logger.warning("SEASON ENROLLMENT: the %s role unresolved", key, exc_info=True)
            return
        if not role_id:
            return
        try:
            if grant:
                await self._mod_roles.assign_platform_role(guild_id, user_id, role_id, "", key)
            else:
                await self._mod_roles.remove_platform_role(guild_id, user_id, role_id, "", key)
        except Exception:
            logger.warning("SEASON ENROLLMENT: the %s role transition failed", key, exc_info=True)

    async def reset_candidates(self, guild_id: str, season: str) -> int:
        """Reset the season's MEMBERSHIP (the new season starts clean).

        The mod's candidate and member roles EMPTY OUT — every
        candidate loses the candidate role, every member the member
        role; a fresh enrollment fills them again. The roles stay (a
        rename keeps its mapping), the membership resets.
        """
        del season
        removed = 0
        for application in await self._enrollment.list_applications(guild_id):
            try:
                state = str(getattr(application, "state", ""))
                if state == "pending":
                    await self._assign_role(
                        guild_id, str(application.user_id), "candidate", False
                    )
                    removed += 1
                elif state == "accepted":
                    await self._assign_role(
                        guild_id, str(application.user_id), "member", False
                    )
                    removed += 1
            except Exception:
                logger.warning(
                    "SEASON ENROLLMENT: the reset failed (%s)", application.user_id, exc_info=True
                )
        return removed


__all__ = ["SeasonEnrollment"]
