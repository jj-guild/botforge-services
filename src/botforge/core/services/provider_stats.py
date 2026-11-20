"""The EnrollmentStats seam over the providers' stats layer (#404 T5).

The generic enrollment (``EnrollmentService``) evaluates its automatic
criteria against the ``EnrollmentStats`` protocol; this module
implements the protocol over the REAL data — the game service's stats
proxies (the per-user unified view: current/max elo per leaderboard,
the matches of the last N days), never the external API, never a
provider's database.

Degradation is the rule: an unreachable service reads as "unknown
stats" (None) — the enrollment falls back to manual review, never a
crash, never a silent refusal.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger("botforge.core.provider_stats")


class UserBindings(Protocol):
    """The platform's own profile-bindings seam (the registration DB)."""

    async def find_user_bindings(self, user_id: str) -> list[dict[str, Any]]:
        """List the game-profile bindings of a user (all games)."""
        ...


class GrpcEnrollmentStats:
    """EnrollmentStats served by the game service's stats layer."""

    def __init__(self, game_client: Any, bindings: UserBindings | None = None) -> None:
        """Wire the GameData client and (optionally) the bindings seam.

        ``game_client`` is the game service's client (GameDataClient)
        — the stats RPCs it serves are the providers' own answers,
        cached by the service (T4). ``bindings`` answers
        ``has_profile`` from the platform's own truth when wired.
        """
        self._client = game_client
        self._bindings = bindings

    async def player_elo(
        self, user_id: str, game_key: str, leaderboard: str = ""
    ) -> int | None:
        """Return the player's current rating; None when unknown.

        The per-user unification keeps the BEST current rating across
        the user's accounts; the leaderboard narrows it (by logical
        name — ``rm_1v1`` — or by the provider's own id).
        """
        del game_key
        stats = await self._stats(user_id)
        if stats is None:
            return None
        board = _pick_board(stats.leaderboards, leaderboard)
        if board is None:
            return None
        return int(board.current) or None

    async def matches_in_window(
        self, user_id: str, game_key: str, days: int, leaderboard: str = ""
    ) -> int | None:
        """Return the matches played in the last N days; None unknown."""
        del game_key, leaderboard
        stats = await self._stats(user_id, window_days=days)
        if stats is None:
            return None
        return int(stats.matches_in_window)

    async def has_profile(self, user_id: str, game_key: str) -> bool:
        """Whether the player has a bound, validated game profile."""
        if self._bindings is not None:
            try:
                bindings = await self._bindings.find_user_bindings(user_id)
            except Exception:
                logger.warning("bindings lookup failed (user %s)", user_id, exc_info=True)
                return False
            return any(str(b.get("game_key", "")) == game_key for b in bindings)
        stats = await self._stats(user_id)
        return stats is not None and stats.known

    async def _stats(self, user_id: str, window_days: int = 0) -> Any | None:
        """Fetch the unified stats; degrade to None, never raise."""
        try:
            return await self._client.get_user_stats(user_id, window_days)
        except Exception:
            logger.warning("user stats fetch failed (user %s)", user_id, exc_info=True)
            return None


def _pick_board(boards: Any, leaderboard: str) -> Any | None:
    """Select one leaderboard's status by name or provider id.

    An empty selector returns the player's best board (the highest
    current rating) — the unification's own head line.
    """
    ordered = sorted(boards, key=lambda b: int(b.current), reverse=True)
    if not leaderboard:
        return ordered[0] if ordered else None
    for board in boards:
        if leaderboard in (board.name, board.leaderboard_id):
            return board
    return None
