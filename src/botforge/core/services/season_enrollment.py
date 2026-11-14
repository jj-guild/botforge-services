"""The seasonal enrollment glue — the per-season roles ride the enrollment (P3).

The owner's spec (2026-11-14): the candidate and member roles are PER
SEASON. A candidate acquires **Candidat <mod> <saison>** at apply,
loses it and gains **Joueur <mod> <saison>** at validation; a refusal
drops the candidate role; a new season starts with fresh roles (the
previous season's candidate roles reset).

The EnrollmentService owns the decisions (criteria, the queue, the
window); the SeasonRolesService owns the per-season roles; this
facade wires the two — the enrollment's states become role
transitions, never a half state.
"""

from __future__ import annotations

import logging
from typing import Any

from botforge.core.services.season_roles import SeasonRolesService

logger = logging.getLogger("botforge.core.services.season_enrollment")


class SeasonEnrollment:
    """The enrollment's decisions wired to the per-season roles."""

    def __init__(
        self,
        enrollment: Any,
        season_roles: SeasonRolesService,
        active_season: Any,
    ) -> None:
        """Bind the enrollment, the season roles and the season resolver.

        ``active_season(guild_id)`` returns the guild's live season id
        (or None — the transitions degrade quietly when no season
        lives: the enrollment still decides, the roles wait).
        """
        self._enrollment = enrollment
        self._season_roles = season_roles
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
        live = season or await self._season_of(guild_id)
        if live and str(getattr(application, "state", "")) == "pending":
            await self._season_roles.sync_candidate_role(guild_id, user_id, live, True)
        return application

    async def accept(self, application_id: str, now: int = 0, reason: str = "") -> Any:
        """Validate: the candidate role is LOST, the member role GAINED."""
        application = await self._enrollment.accept(application_id, now=now, reason=reason)
        await self._promote(application)
        return application

    async def refuse(self, application_id: str, now: int = 0, reason: str = "") -> Any:
        """Refuse: the candidate role goes."""
        application = await self._enrollment.refuse(application_id, now=now, reason=reason)
        live = str(getattr(application, "season", "") or "") or await self._season_of(
            str(getattr(application, "guild_id", ""))
        )
        if live:
            await self._season_roles.sync_candidate_role(
                str(application.guild_id), str(application.user_id), live, False
            )
        return application

    async def _promote(self, application: Any) -> None:
        """Apply the accept transition: -candidat, +joueur, one move."""
        live = str(getattr(application, "season", "") or "") or await self._season_of(
            str(getattr(application, "guild_id", ""))
        )
        if not live:
            return
        await self._season_roles.promote_candidate(
            str(application.guild_id), str(application.user_id), live
        )

    async def reset_candidates(self, guild_id: str, season: str) -> int:
        """Reset a season's candidate roles (the new season starts clean).

        The previous season's candidates lose the role — the new season
        is a fresh enrollment, never a carry-over.
        """
        removed = 0
        for application in await self._enrollment.list_applications(guild_id, state="pending"):
            if str(getattr(application, "season", "") or "") != season:
                continue
            try:
                await self._season_roles.sync_candidate_role(
                    guild_id, str(application.user_id), season, False
                )
                removed += 1
            except Exception:
                logger.warning(
                    "SEASON ENROLLMENT: the candidate reset failed (%s)", application.user_id, exc_info=True
                )
        return removed


__all__ = ["SeasonEnrollment"]
