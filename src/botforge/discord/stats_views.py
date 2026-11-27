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


async def account_elo_by_profile(bot: Any, profile_ids: list[str]) -> dict[str, str]:
    """Render the per-account elo lines, keyed by profile id.

    ``"1250 (max 1300)"`` per account (the best board's current, the
    peak in parens); the accounts without stored stats map to "".
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
        best = max(account.leaderboards, key=lambda b: int(b.current))
        if not int(best.current):
            continue
        peak = f" (max {int(best.max)})" if int(best.max) > int(best.current) else ""
        lines[str(account.profile_id)] = f"{int(best.current)} elo{peak}"
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
