"""The stats enrichments of the existing views (#404 T6).

The surfaces stay as they are — the helpers only enrich their lines,
and degrade to nothing when the game service is unreachable (the
panels never crash on stats).
"""

from __future__ import annotations

from typing import Any

from botforge.core.models.game import AccountEloStatus, LeaderboardElo, UserEloStats
from botforge.core.services.enrollment import CriterionResult
from botforge.discord.stats_views import (
    account_elo_by_profile,
    criteria_lines,
    user_stats_line,
)


class _Client:
    """The game service's stats client stand-in."""

    def __init__(self, user_stats: Any = None, accounts: Any = None) -> None:
        self.user_stats = user_stats
        self.accounts = accounts or []
        self.asked_profile_ids: list[list[str]] = []

    async def get_user_stats(self, user_id: str, window_days: int = 0) -> Any:
        """Serve the unified stats (or None)."""
        del window_days
        return self.user_stats

    async def get_account_stats(self, profile_ids: list[str]) -> list[AccountEloStatus]:
        """Serve the per-account status."""
        self.asked_profile_ids.append(list(profile_ids))
        return self.accounts


def _wire(monkeypatch: Any, client: _Client | None) -> None:
    """Point the stats client builder at the stand-in."""
    import botforge.discord.stats_views as views

    monkeypatch.setattr(views, "stats_client", lambda: client)


async def test_user_stats_line_renders_the_best_board(monkeypatch: Any) -> None:
    """The roster line carries the best board's current elo + peak."""
    _wire(
        monkeypatch,
        _Client(
            UserEloStats(
                user_id="u1",
                leaderboards=(
                    LeaderboardElo(leaderboard_id="0", name="rm_1v1", current=1200, max=1350),
                    LeaderboardElo(leaderboard_id="3", name="dm_1v1", current=900, max=950),
                ),
                known=True,
            )
        ),
    )
    line = await user_stats_line(None, "u1")
    assert "1200" in line
    assert "rm_1v1" in line
    assert "max 1350" in line


async def test_user_stats_line_degrades_to_empty(monkeypatch: Any) -> None:
    """Unknown or unreachable stats render NOTHING (the line unchanged)."""
    _wire(monkeypatch, None)
    assert await user_stats_line(None, "u1") == ""
    _wire(monkeypatch, _Client(None))
    assert await user_stats_line(None, "u1") == ""


async def test_account_elo_by_profile_renders_per_account(monkeypatch: Any) -> None:
    """The profile view carries each account's elo + stored peak."""
    _wire(
        monkeypatch,
        _Client(
            accounts=[
                AccountEloStatus(
                    profile_id="123",
                    leaderboards=(LeaderboardElo(leaderboard_id="0", name="rm_1v1", current=1100, max=1180),),
                    known=True,
                ),
                AccountEloStatus(profile_id="456", known=False),
            ]
        ),
    )
    lines = await account_elo_by_profile(None, ["123", "456"])
    assert lines == {"123": "1100 Elo 1v1 (max 1180)"}


async def test_criteria_lines_render_the_verdicts() -> None:
    """The candidate sheet renders the criteria: pass, fail, unknown."""
    lines = criteria_lines(
        type(
            "Application",
            (),
            {
                "criteria_results": (
                    CriterionResult("min_elo", True, "rating 1250 ≥ required 1200"),
                    CriterionResult("min_matches", False, "2 matches in 30d < required 5"),
                    CriterionResult("requires_profile", False, "no bound profile", unknown=True),
                )
            },
        )()
    )
    assert lines[0].startswith("✓")
    assert lines[1].startswith("✗")
    assert lines[2].startswith("❔")  # the manual-review marker (T5)
    assert criteria_lines(type("Application", (), {"criteria_results": ()})()) == []


class TestProfileMatchesButton:
    """The matches button renders only when the user owns an aoe2 account."""

    def test_the_button_custom_id_is_registered(self) -> None:
        """The dynamic item template matches its custom id (persistence)."""
        from botforge.discord.home import ProfileMatchesButton

        assert ProfileMatchesButton().item.custom_id == "home:profile:matches"

def test_the_live_lobby_settings_render_through_the_popup_tables() -> None:
    """A live card (no blob at all) renders pairs + booleans (owner 2026-11-23)."""
    from botforge.discord.home import _settings_bool_lines, _settings_named_pairs

    card = {
        "match_id": "523203059",
        # a real live lobby capture (aoe2lobby ws, 2026-11-23): raw named json
        "live_settings_json": (
            '{"mode": 0, "size": 5, "population": 200, "speed": 2, "victory": 5,'
            ' "victory_threshold": 14000, "resources": 0, "reveal_map": 0,'
            ' "starting_age": 0, "ending_age": 2, "ai_difficulty": 1, "treaty_length": 0,'
            ' "cheats": false, "lock_speed": true, "lock_teams": false,'
            ' "team_together": true, "team_positions": false,'
            ' "shared_exploration": false, "full_tech_tree": false, "turbo_mode": false}'
        ),
    }
    pairs = _settings_named_pairs(card)
    by_label = dict(pairs)
    assert by_label["Mode"] == "Random Map"
    assert by_label["Taille"] == "Immense"
    assert by_label["Pop"] == "200"
    assert by_label["Vitesse"] == "Normale"
    assert by_label["Victoire"] == "Personnalisée (14000)"
    assert by_label["Ressources"] == "Standard"
    assert "Traité" not in by_label  # a zero treaty reads better than "0 min"
    lines = _settings_bool_lines(card, {
        "setting_bools_live": {
            "cheats": "Cheats", "lock_speed": "Vitesse verrouillée",
            "lock_teams": "Équipes verrouillées", "full_tech_tree": "Arbre complet",
            "record": "Partie enregistrée", "shared_exploration": "Exploration partagée",
            "team_positions": "Positions d'équipe", "team_together": "Équipes ensemble",
            "turbo_mode": "Mode Turbo",
        }
    })
    assert "✅ Vitesse verrouillée" in lines
    assert "✅ Équipes ensemble" in lines
    assert "⬜ Équipes verrouillées" in lines
    assert "⬜ Cheats" in lines
    # the settings view of a live card answers the same shape as a finished one
    assert pairs and lines
