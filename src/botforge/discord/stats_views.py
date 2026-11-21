"""The stats enrichments of the existing views (#404 T6).

The surfaces stay as they are — these helpers only ENRICH their lines
with the stats the providers now serve (the per-account elo status,
the per-user unification, the criteria results). Every helper is
best-effort: an unreachable game service renders nothing, never
crashes the view (the panels degrade quietly).
"""

from __future__ import annotations

import json
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

    ``" — 1400 Elo (max 1500)"`` on the player's best leaderboard;
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
    return f" — {int(best.current)} Elo {label}{peak}".replace("  ", " ")


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

    ``"1185 Elo 1v1 (max 1210)"`` per account \u2014 the 1v1 RM rating the
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
        lines[str(account.profile_id)] = f"{int(board.current)} Elo 1v1{peak}"
    return lines


async def recent_match_blocks(
    profile_ids: list[str],
    me_ids: set[str],
    known_ids: set[str],
    labels: dict[str, str],
    limit: int = 10,
) -> list[list[str]]:
    """Render the accounts' last finished matches as bullet blocks.

    One BLOCK per match (newest first, <= limit): the header line (the
    match's own name, the time, the duration, the format) then one
    sub-bullet per team carrying every seat (alias, civ, Elo, the
    rating delta). ``me_ids`` renders bold, the other server-known
    profiles render italic — the highlight contract of the matches
    popup. Best-effort — an unreachable game service renders [].
    """
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
    # ONE block per match id: the legacy per-board store tripled every
    # match (the board param never filtered), so the same game answered
    # as three rows — dedupe, newest first.
    blocks: list[list[str]] = []
    seen: set[str] = set()
    ordered = sorted(entries, key=lambda e: int(e.finished_at or e.started_at or 0), reverse=True)
    for entry in ordered:
        match_id = str(getattr(entry, "match_id", ""))
        if match_id and match_id in seen:
            continue
        mine = [p for p in (getattr(entry, "profile_ids", ()) or []) if str(p) in wanted]
        if not mine:
            continue
        if match_id:
            seen.add(match_id)
        blocks.append(finished_match_block(entry, wanted, known_ids, labels))
        if len(blocks) >= limit:
            break
    return blocks


def finished_match_block(
    entry: Any,
    me_ids: set[str],
    known_ids: set[str],
    labels: dict[str, str],
) -> list[str]:
    """Render one finished match block: the header, then the teams."""
    players = _entry_players(entry)
    winners = tuple(getattr(entry, "winners", ()) or ())
    won = any(str(p) in set(winners) for p in me_ids)
    outcome = "\u2705" if won else ("\u274c" if winners else "\u2b1c")
    team_of_me = _team_of(players, me_ids)
    title = _match_title(entry, labels)
    head = " ".join(bit for bit in [outcome, f"**{title}**"] if bit)
    map_name = str(getattr(entry, "map_name", "") or "").strip()
    if map_name and map_name.lower() != "my map" and map_name != title:
        head += f" \u00b7 *{map_name}*"
    tail = " \u00b7 ".join(
        bit for bit in [_when(entry), _fmt_duration(_duration_of(entry)), _match_kind(players, team_of_me)] if bit
    )
    lines = [f"- {head} \u2014 {tail}".rstrip(" \u2014-")]
    lines.extend(_team_bullets(players, me_ids, known_ids, labels))
    return lines


def live_match_block(
    match: dict[str, Any],
    me_ids: set[str],
    known_ids: set[str],
    labels: dict[str, str],
) -> list[str]:
    """Render one ongoing-match block: header with the live marker, teams.

    ``match`` is the aggregator snapshot's per-player match context
    (aoe2lobby: map, format, per-slot players). No outcome, no delta —
    the seats carry the alias, the civ, the team; the same layout the
    finished blocks render, so both sources read identically.
    """
    players = [dict(p) for p in (match.get("players") or []) if isinstance(p, dict)]
    title = str(match.get("map") or match.get("label") or "")
    fmt = str(match.get("format") or "")
    head = "\U0001f3ae " + (f"**{title}**" if title else "")
    tail = " \u00b7 ".join(bit for bit in [labels.get("ongoing", "in progress"), fmt] if bit)
    lines = [(f"- {head} \u2014 {tail}").rstrip(" \u2014-").rstrip()]
    lines.extend(_team_bullets(players, me_ids, known_ids, labels))
    return lines


def _team_bullets(
    players: list[dict[str, Any]],
    me_ids: set[str],
    known_ids: set[str],
    labels: dict[str, str],
) -> list[str]:
    """One sub-bullet per team: every seat in one line."""
    if not players:
        return []
    by_team: dict[int, list[dict[str, Any]]] = {}
    for player in players:
        by_team.setdefault(int(player.get("team", 0) or 0), []).append(player)
    team_label = labels.get("team", "Team")
    bullets = []
    for index, team in enumerate(sorted(by_team)):
        bullets.append(f"  - **{team_label} {index + 1}**")
        for player in by_team[team]:
            bullets.append(f"      - {_player_token(player, me_ids, known_ids)}")
    return bullets


def _player_token(player: dict[str, Any], me_ids: set[str], known_ids: set[str]) -> str:
    """One seat's readable token: alias, civ, Elo, the rating delta.

    The VIEWED profiles render bold, the other server-known profiles
    render italic (the owner's 2026-11-20 highlight contract) — the
    plain players stay quiet.
    """
    pid = str(player.get("profile_id", ""))
    name = str(player.get("alias") or player.get("name") or pid or "?")
    if pid in me_ids and pid:
        name = f"**{name}**"
    elif pid in known_ids and pid:
        name = f"*{name}*"
    civ = str(player.get("civ") or "").strip()
    elo = int(player.get("rating_after") or player.get("elo") or 0)
    bits: list[str] = [name]
    if civ:
        bits.append(civ)
    if elo:
        bits.append(f"**{elo} Elo**")
    before = int(player.get("rating_before") or 0)
    after = int(player.get("rating_after") or 0)
    delta = ""
    if before and after and before != after:
        delta = f" ({after - before:+d})"
    return " \u00b7 ".join(bits) + delta


def _match_title(entry: Any, labels: dict[str, str]) -> str:
    """Return the match's own name: the lobby title, else the map, else the id.

    A custom lobby names itself (its title); a ranked match rides its
    map; the rare untitled-unknown pair falls back to the match id
    (the owner's 2026-11-20 pick over a lying "my map").
    """
    title = str(getattr(entry, "description", "") or "").strip()
    if title and title.upper() == "AUTOMATCH":
        title = ""
    if title:
        return title
    map_name = str(getattr(entry, "map_name", "") or "").strip()
    if map_name and map_name.lower() != "my map":
        return map_name
    return labels.get("untitled", "Match {id}").format(id=str(getattr(entry, "match_id", "")))


def _when(entry: Any) -> str:
    """Return the played-at stamp (Discord's relative time)."""
    played_at = int(getattr(entry, "finished_at", 0) or getattr(entry, "started_at", 0) or 0)
    return f"<t:{played_at}:R>" if played_at else ""


def _duration_of(entry: Any) -> int:
    """Return the match's duration in seconds (0 when unknown)."""
    started = int(getattr(entry, "started_at", 0) or 0)
    finished = int(getattr(entry, "finished_at", 0) or 0)
    return max(0, finished - started) if started and finished else 0


def _fmt_duration(seconds: int) -> str:
    """Render a duration: ``42 min`` / ``1 h 05``."""
    minutes = seconds // 60
    if minutes <= 0:
        return ""
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d}"


def _team_of(players: list[dict[str, Any]], me_ids: set[str]) -> int:
    """Return the team of the first viewed profile among the seats (0 default)."""
    for player in players:
        if str(player.get("profile_id", "")) in me_ids:
            return int(player.get("team", 0) or 0)
    return 0


def _entry_players(entry: Any) -> list[dict[str, Any]]:
    """Return the decoded players of one stored match ("" when none)."""
    raw = str(getattr(entry, "players_json", "") or "")
    if not raw:
        return []
    try:
        decoded = json.loads(raw)
    except Exception:
        return []
    return [pl for pl in decoded if isinstance(pl, dict)]


def _match_kind(players: list[dict[str, Any]], my_team: int) -> str:
    """Render the readable match type: 1v1, 2v2..., custom."""
    if not players:
        return ""
    mine = sum(1 for pl in players if int(pl.get("team", 0) or 0) == my_team)
    theirs = len(players) - mine
    if mine == 1 and theirs == 1:
        return "1v1"
    if mine and theirs:
        return f"{mine}v{theirs}"
    return "custom"


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
