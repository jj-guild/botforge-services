"""The stats enrichments of the existing views (#404 T6).

The surfaces stay as they are — these helpers only ENRICH their lines
with the stats the providers now serve (the per-account elo status,
the per-user unification, the criteria results). Every helper is
best-effort: an unreachable game service renders nothing, never
crashes the view (the panels degrade quietly).
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("botforge.discord.stats_views")


def stats_client() -> Any | None:
    """Return the game service's stats client; None when unconfigured."""
    uri = os.environ.get("GAME_AOE2_URI", "")
    if not uri:
        return None
    try:
        from botforge.game_aoe2.client import GameDataClient

        return GameDataClient(uri)
    except Exception:
        logger.warning("STATS VIEWS: the client build failed", exc_info=True)
        return None


async def user_stats_line(bot: Any, user_id: str) -> str:
    """Render the user's unified elo head line (best board).

    ``" — 1400 elo (max 1500)"`` on the player's best leaderboard;
    empty when the stats are unknown — the roster line stays as it was.
    """
    del bot
    client = stats_client()
    if client is None:
        return ""
    try:
        stats = await client.get_user_stats(user_id)
    except Exception:
        logger.warning("STATS VIEWS: the user stats fetch failed", exc_info=True)
        return ""
    if stats is None or not stats.leaderboards:
        return ""
    best = max(stats.leaderboards, key=lambda b: int(b.current))
    if not int(best.current):
        return ""
    label = best.name or best.leaderboard_id
    peak = f" (max {int(best.max)})" if int(best.max) > int(best.current) else ""
    return f" — {int(best.current)} elo {label}{peak}".replace("  ", " ")


BOARD_LABELS = {
    "rm_1v1": "1v1 RM",
    "rm_team": "TG RM",
    "unranked": "unranked",
    "dm_1v1": "1v1 DM",
    "dm_team": "TG DM",
}
"""The human face of the provider's leaderboard keys (display only)."""


async def account_elo_by_profile(bot: Any, profile_ids: list[str]) -> dict[str, str]:
    """Render the per-account 1v1 elo lines, keyed by profile id.

    ``"1185 elo 1v1 (max 1210)"`` per account \u2014 the 1v1 RM rating the
    player actually reads (the request of 2026-11-20: the profile page
    shows the 1v1 elo of every aoe2 account, not the best board); the
    accounts without stored 1v1 stats map to "".
    """
    del bot
    if not profile_ids:
        return {}
    client = stats_client()
    if client is None:
        return {}
    try:
        accounts = await client.get_account_stats([str(p) for p in profile_ids])
    except Exception:
        logger.warning("STATS VIEWS: the account stats fetch failed", exc_info=True)
        return {}
    lines: dict[str, str] = {}
    for account in accounts:
        if not account.known or not account.leaderboards:
            continue
        board = next((b for b in account.leaderboards if str(b.name) == "rm_1v1"), None)
        if board is None or not int(board.current):
            continue
        peak = f" (max {int(board.max)})" if int(board.max) > int(board.current) else ""
        lines[str(account.profile_id)] = f"{int(board.current)} elo 1v1{peak}"
    return lines


async def recent_match_lines(bot: Any, profile_ids: list[str], limit: int = 10) -> list[str]:
    """Render the accounts' last matches, newest first (<= limit lines).

    One line per match: the date, the map, the board, the outcome and
    the elo delta of the player's account. Best-effort \u2014 an
    unreachable game service or an empty history renders nothing.
    """
    del bot
    wanted = {str(p) for p in profile_ids if str(p)}
    if not wanted:
        return []
    client = stats_client()
    if client is None:
        return []
    try:
        entries = await client.get_match_history(sorted(wanted), limit=50)
    except Exception:
        logger.warning("STATS VIEWS: the match history fetch failed", exc_info=True)
        return []
    lines: list[str] = []
    ordered = sorted(entries, key=lambda e: int(e.finished_at or e.started_at or 0), reverse=True)
    for entry in ordered:
        mine = [p for p in (getattr(entry, "profile_ids", ()) or []) if str(p) in wanted]
        if not mine:
            continue
        won = any(str(p) in set(getattr(entry, "winners", ()) or ()) for p in mine)
        before = int(getattr(entry, "rating_before", {}).get(mine[0], 0) or 0)
        after = int(getattr(entry, "rating_after", {}).get(mine[0], 0) or 0)
        delta = f"{after - before:+d} elo" if before and after else ""
        board_key = str(getattr(entry, "leaderboard_id", ""))
        board = BOARD_LABELS.get(board_key, board_key)
        played_at = int(entry.finished_at or entry.started_at or 0)
        stamp = f"<t:{played_at}:R>" if played_at else "?"
        outcome = "\u2705" if won else "\u274c"
        map_name = str(getattr(entry, "map_name", "") or "?")
        lines.append(f"{outcome} {stamp} \u2014 {map_name} ({board}) {delta}".strip())
        if len(lines) >= limit:
            break
    return lines


def criteria_lines(application: Any) -> list[str]:
    """Render the application's criteria results (stats vs criteria).

    One line per evaluated criterion — passed ✓, failed ✗, unknown ❔
    (the manual-review marker of T5) — so the admin announce shows WHY
    the queue holds the candidate. Empty when no criterion ran.
    """
    lines: list[str] = []
    for result in getattr(application, "criteria_results", ()) or ():
        mark = "❔" if getattr(result, "unknown", False) else ("✓" if result.passed else "✗")
        lines.append(f"{mark} `{result.key}` — {result.reason}")
    return lines
