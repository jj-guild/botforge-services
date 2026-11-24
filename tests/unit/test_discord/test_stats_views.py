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

def test_the_live_dashboard_cards_come_from_the_snapshot_with_settings() -> None:
    """The /live cards share the panel card shape (owner 2026-11-23)."""
    from botforge.discord.home import _cards_from_live_snapshot

    snapshot = {
        "players": [
            {
                "profile_id": "17190369",
                "user_id": "10",
                "state": "in_lobby",
                "match_ref": "523203059",
                "match": {
                    "match_ref": "523203059",
                    "map": "Coastal",
                    "match_type": "Random Map",
                    "status": "lobby",
                    "players": (
                        '[{"profile_id": "17190369", "name": "Merlin Pinpin",'
                        ' "civ": "Franks", "team": 1}]'
                    ),
                    "lobby_url": "https://www.aoe2lobby.com/j/523203059",
                    "spectate_url": "https://www.aoe2lobby.com/w/523203059",
                    "settings_json": '{"speed": 2, "lock_teams": true}',
                },
            },
            {
                "profile_id": "848567",
                "user_id": "10",
                "state": "offline",
                "match_ref": "",
                "match": {},
            },
        ]
    }
    cards = _cards_from_live_snapshot(snapshot)
    assert len(cards) == 1, "the offline profile renders no card"
    card = cards[0]
    assert card["status"] == "lobby"
    assert card["map_name"] == "Coastal"
    assert card["lobby_url"].endswith("/j/523203059")
    assert card["live_settings_json"] == '{"speed": 2, "lock_teams": true}'
    # the viewer-scoped cut keeps ONLY the scoped seats' matches
    scoped = _cards_from_live_snapshot(snapshot, keep_ids={"848567"})
    assert scoped == [], "a profile outside the scope renders no card"
    # the card renders through the very same parts builder as the panels
    from botforge.discord.home import _match_card_parts

    blocks, buttons, match_id, accent = _match_card_parts(
        card, {"civ_urls": {}, "civ_images": {}, "map_urls": {}, "map_images": {},
         "map_display": {}, "civ_display": {}, "ladder": {}},
        set(), {"team": "Team"},
    )
    assert match_id == "523203059"
    assert blocks and buttons and accent, "the card renders the full panel shape"

def test_the_settings_checkboxes_read_the_games_order_with_a_separator() -> None:
    """The checkbox block follows the game's own order (owner 2026-11-24)."""
    from botforge.discord.home import _settings_bool_lines

    card = {
        "live_settings_json": (
            '{"lock_teams": true, "team_together": true, "team_positions": false,'
            ' "shared_exploration": false, "lock_speed": true, "cheats": false,'
            ' "turbo_mode": false, "full_tech_tree": false, "ew_mode": false,'
            ' "sudden_death_mode": false, "regicide_mode": false,'
            ' "antiquity_mode": false, "record": true}'
        ),
    }
    names = {
        "lock_teams": "Équipes verrouillées", "team_together": "Équipes ensemble",
        "team_positions": "Positions d'équipe", "shared_exploration": "Exploration partagée",
        "lock_speed": "Vitesse verrouillée", "cheats": "Cheats",
        "turbo_mode": "Mode Turbo", "full_tech_tree": "Arbre technologique complet",
        "ew_mode": "Mode Empire Wars", "sudden_death_mode": "Mort subite",
        "regicide_mode": "Mode Régicide", "antiquity_mode": "Mode Antiquité",
        "record": "Partie enregistrée",
    }
    lines = _settings_bool_lines(card, {
        "setting_bools_live": names,
        "checkbox_names": {
            "profile.matches_setting_handicap": "Handicap",
            "profile.matches_setting_ew": "Mode Empire Wars",
        },
    })
    # the game's own order: teams group, the "?" handicap, the separator, the rest
    assert lines[0] == "✅ Équipes verrouillées"
    assert lines[1] == "✅ Équipes ensemble"
    assert lines[2] == "⬜ Positions d'équipe"
    assert lines[3] == "⬜ Exploration partagée"
    assert lines[4] == "❓ Handicap"
    assert lines[5].startswith("──────────")
    assert lines[6] == "✅ Vitesse verrouillée"
    assert lines[-1] == "✅ Partie enregistrée"
    assert "⬜ Mode Empire Wars" in lines  # the payload answers it: a checkbox, never a "?"


def test_the_seat_ladder_lines_name_lb3_and_lb4_only() -> None:
    """An Empire Wars TG automatch never dresses its board as the TG line."""
    from botforge.discord.home import _seat_text

    card = {
        "status": "finished",
        "match_id": "523338329",
        "lobby_title": "AUTOMATCH",
        # an Empire Wars TG match rides leaderboard 14 (owner 2026-11-24)
        "leaderboard_id": "14",
        "players": [{"profile_id": "848567", "alias": "Merlin", "team": 1, "slot": 1,
                     "rating_before": 1499, "rating_after": 1511}],
    }
    ctx = {"civ_urls": {}, "civ_images": {}, "map_urls": {}, "map_images": {},
           "civ_display": {}, "map_display": {},
           "ladder": {"848567": {"rm_1v1": (1015, 1120), "rm_team": (1180, 1300)}}}
    text, _ = _seat_text(card["players"][0], card, ctx, {})
    # the RM TG board renders (plain, no board-14 bold masquerade)
    assert "TG : 1180 - 1300" in text
    assert "**1499**" not in text, "the EW board's own elo never dresses as TG"
