"""The EnrollmentStats seam over the providers' stats layer (#404 T5).

The seam translates the enrollment's questions (elo, matches window,
bound profile) into the game service's stats answers — the per-user
unified view the providers serve. Degradation is the rule: an
unreachable service reads as unknown stats, the enrollment falls back
to manual review.
"""

from __future__ import annotations

from typing import Any

from botforge.core.models.game import LeaderboardElo, UserEloStats
from botforge.core.services.provider_stats import GrpcEnrollmentStats


class FakeGameClient:
    """The game service's stats client stand-in."""

    def __init__(self, stats: UserEloStats | None) -> None:
        self.stats = stats
        self.calls: list[tuple[str, int]] = []

    async def get_user_stats(self, user_id: str, window_days: int = 0) -> UserEloStats | None:
        """Serve the unified stats (or None when unknown)."""
        self.calls.append((user_id, window_days))
        return self.stats


class FakeBindings:
    """The platform's own bindings seam stand-in."""

    def __init__(self, games_by_user: dict[str, list[str]]) -> None:
        self.games_by_user = games_by_user

    async def find_user_bindings(self, user_id: str) -> list[dict[str, Any]]:
        """List the user's bindings for the bound games."""
        return [
            {"game_key": game, "profile_id": f"{user_id}:{game}"}
            for game in self.games_by_user.get(user_id, [])
        ]


def _stats(boards: list[LeaderboardElo], matches: int = 0) -> UserEloStats:
    return UserEloStats(
        user_id="alice",
        profile_ids=("123", "456"),
        leaderboards=tuple(boards),
        matches_in_window=matches,
        known=True,
    )


async def test_player_elo_serves_the_unified_best_current() -> None:
    """The seam returns the best current elo across the accounts."""
    stats = _stats(
        [
            LeaderboardElo(leaderboard_id="0", name="rm_1v1", current=1000, max=1100),
            LeaderboardElo(leaderboard_id="3", name="dm_1v1", current=1400, max=1500),
        ]
    )
    seam = GrpcEnrollmentStats(FakeGameClient(stats))
    assert await seam.player_elo("alice", "aoe2") == 1400  # the best board
    assert await seam.player_elo("alice", "aoe2", "rm_1v1") == 1000
    assert await seam.player_elo("alice", "aoe2", "0") == 1000  # by provider id
    assert await seam.player_elo("alice", "aoe2", "dm_team") is None


async def test_matches_in_window_counts_the_window() -> None:
    """The matches criterion reads the window count of the unified view."""
    client = FakeGameClient(_stats([], matches=12))
    seam = GrpcEnrollmentStats(client)
    assert await seam.matches_in_window("alice", "aoe2", 30) == 12
    assert client.calls == [("alice", 30)]


async def test_unknown_stats_degrade_to_none_never_raise() -> None:
    """An unreachable service reads as unknown stats (None)."""
    class ExplodingClient:
        async def get_user_stats(self, user_id: str, window_days: int = 0) -> None:
            raise RuntimeError("game service unreachable")

    seam = GrpcEnrollmentStats(ExplodingClient())
    assert await seam.player_elo("alice", "aoe2") is None
    assert await seam.matches_in_window("alice", "aoe2", 30) is None


async def test_has_profile_reads_the_platform_bindings() -> None:
    """The bound-profile criterion reads the platform's own truth."""
    seam = GrpcEnrollmentStats(
        FakeGameClient(_stats([])), bindings=FakeBindings({"alice": ["aoe2"]})
    )
    assert await seam.has_profile("alice", "aoe2") is True
    assert await seam.has_profile("alice", "aoe4") is False
    assert await seam.has_profile("bob", "aoe2") is False


async def test_has_profile_falls_back_to_the_unified_stats() -> None:
    """Without a bindings seam, the unified stats answer the profile."""
    seam = GrpcEnrollmentStats(FakeGameClient(_stats([])))
    assert await seam.has_profile("alice", "aoe2") is True
    seam_unknown = GrpcEnrollmentStats(FakeGameClient(None))
    assert await seam_unknown.has_profile("alice", "aoe2") is False
