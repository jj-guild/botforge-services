"""libre:match history syncer — store first, exploit after (#404 T1).

The syncer pulls, for every known account and every kept leaderboard
(0, 3, 4 — rm_1v1, dm_1v1, dm_team):

- the FULL recent match history (raw documents, stored verbatim);
- the personal stat (the account's current elo per leaderboard);

then EXPLOITS the stored data: the per-account status (current elo +
MAX elo per leaderboard — the max rides the history's rating_after
values), and the per-USER unification (multiple accounts aggregated
into one view).

Never a re-fetch at read time: the queries answer from the store; the
sync (periodic + on-demand, T4) keeps the store fresh.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from botforge.core.models.game import (
    AccountEloStatus,
    LeaderboardElo,
    MatchHistoryEntry,
    UserEloStats,
)
from botforge.ext_librematch.adapter import LEADERBOARD_KEYS
from botforge.ext_librematch.decode import DECODE_BATCH, decode_match_payload
from botforge.ext_librematch.store import DEFAULT_HISTORY_LIMIT, LibrematchStore

logger = logging.getLogger("botforge.ext_librematch.history")

STATS_LEADERBOARDS = ("0", "3", "4")
DEFAULT_SYNC_COUNT = 1000
# The INCREMENTAL fetch window: the periodic sync reads the last
# matches only, and inserts just the unknown ones — a finished match is
# immutable and never rewritten. The DEEP fetch (the full count) runs
# once per account: on its first sync.
DEFAULT_QUICK_COUNT = 25
_DAY_S = 86_400


def _now_ms() -> int:
    """Epoch milliseconds, the repo's timestamp convention."""
    return int(time.time() * 1000)


def _int(value: Any) -> int:
    """Coerce an upstream field to int, 0 on garbage."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


class MatchHistorySyncer:
    """Pull the known accounts' history into the store, exploit it after."""

    def __init__(
        self,
        adapter: Any,
        store: LibrematchStore,
        leaderboards: tuple[str, ...] = STATS_LEADERBOARDS,
        sync_count: int = DEFAULT_SYNC_COUNT,
        quick_count: int = DEFAULT_QUICK_COUNT,
    ) -> None:
        self._adapter = adapter
        self._store = store
        self._leaderboards = leaderboards
        self._sync_count = sync_count
        self._quick_count = quick_count

    async def sync_account(self, profile_id: str) -> bool:
        """Sync one account: raw history + status, then the elo max.

        The SMART fetch (the #404 T4 rule): the account's FIRST sync
        pulls the deep window (``sync_count``), every later one reads
        the incremental window (``quick_count``) and inserts ONLY the
        unknown matches — a finished match is immutable, never
        rewritten, never re-counted.

        Returns True when anything was stored. Failures degrade to
        False — the provider keeps serving the previous store, the
        periodic sync retries later.
        """
        profile_id = str(profile_id)
        stored_any = False
        previous = await self._find_status(profile_id)
        deep = await self._store.count_matches_of_profile(profile_id) == 0
        count = self._sync_count if deep else self._quick_count
        # ONE history fetch: the upstream's ``leaderboard_id`` param does NOT
        # filter (verified live 2026-11-20 — the same matches answer under
        # every board), so the per-board loop only tripled the upstream
        # calls and stored every match three times.
        raw_matches = await self._adapter.fetch_match_history_raw(profile_id, "", count)
        if raw_matches:
            inserted = await self._store.insert_matches_new_only(
                [self._match_doc(m) for m in raw_matches]
            )
            stored_any = stored_any or inserted > 0
        # ONE stats fetch answers EVERY board at once: the reply joins
        # ``leaderboardStats[].statgroup_id`` with ``members[].
        # personal_statgroup_id`` (the same join the alias search rides).
        stat = await self._adapter.fetch_personal_stat_raw(profile_id, "")
        boards = self._boards_from_stat(stat, profile_id)
        if boards:
            stored_any = True
        await self._store.upsert_account(self._account_doc(profile_id, boards, previous))
        # The decode step (T2): the stored documents are exploited AFTER
        # the ingestion — no history re-fetch, only the details endpoint.
        await self.decode_stored([profile_id])
        return stored_any

    async def refresh_status(self, profile_id: str) -> bool:
        """Refresh ONE account's elo status — no history fetch at all.

        The light path of the hourly loop: only the per-board stats
        (current elo, rank, wins/losses); the MAX never drops (the
        account document merges with the stored max).
        """
        profile_id = str(profile_id)
        previous = await self._find_status(profile_id)
        # ONE stats fetch answers every board (the statgroup join).
        stat = await self._adapter.fetch_personal_stat_raw(profile_id, "")
        boards = self._boards_from_stat(stat, profile_id)
        if not boards:
            return False
        await self._store.upsert_account(self._account_doc(profile_id, boards, previous))
        return True

    async def refresh_statuses(self, profile_ids: list[str]) -> int:
        """Run the light elo refresh (every known account when empty)."""
        targets = [str(p) for p in profile_ids] or await self._store.list_known_profiles()
        refreshed = 0
        for profile_id in targets:
            try:
                if await self.refresh_status(profile_id):
                    refreshed += 1
            except Exception:
                logger.warning("elo refresh failed (%s)", profile_id, exc_info=True)
        return refreshed

    async def sync_accounts(self, profile_ids: list[str]) -> int:
        """Sync the given accounts (every known one when empty). T4 rides."""
        targets = [str(p) for p in profile_ids] or await self._store.list_known_profiles()
        synced = 0
        for profile_id in targets:
            try:
                if await self.sync_account(profile_id):
                    synced += 1
            except Exception:
                logger.warning("account sync failed (%s)", profile_id, exc_info=True)
        return synced

    async def match_history(
        self,
        profile_ids: list[str],
        limit: int = 0,
        since_s: int = 0,
        leaderboard_id: str = "",
    ) -> list[MatchHistoryEntry]:
        """Serve the stored history as the exploited projection."""
        docs = await self._store.find_matches(profile_ids, limit or DEFAULT_HISTORY_LIMIT, since_s, leaderboard_id)
        return [self._entry_of(doc) for doc in docs]

    async def account_stats(self, profile_ids: list[str]) -> list[AccountEloStatus]:
        """Serve the per-account status (current + max elo per board)."""
        if not profile_ids:
            return []
        docs = await self._store.find_accounts([str(p) for p in profile_ids])
        by_id = {str(doc["_id"]): doc for doc in docs}
        statuses: list[AccountEloStatus] = []
        for profile_id in profile_ids:
            doc = by_id.get(str(profile_id))
            statuses.append(self._status_of(str(profile_id), doc))
        return statuses

    async def user_stats(self, user_id: str, window_days: int = 0) -> UserEloStats | None:
        """Serve the per-USER unified view over the user's accounts.

        None when the user owns no known account — the caller reads it
        as "unknown stats" and degrades to manual review (never a crash,
        never a silent refusal).
        """
        profiles = await self._store.find_profiles_of_user(user_id)
        if not profiles:
            return None
        statuses = await self.account_stats(profiles)
        unified: dict[str, LeaderboardElo] = {}
        for status in statuses:
            if not status.known:
                continue
            for board in status.leaderboards:
                merged = unified.get(board.leaderboard_id)
                if merged is None:
                    unified[board.leaderboard_id] = board
                    continue
                unified[board.leaderboard_id] = LeaderboardElo(
                    leaderboard_id=board.leaderboard_id,
                    name=board.name or merged.name,
                    current=max(merged.current, board.current),
                    max=max(merged.max, board.max),
                    rank=merged.rank if merged.rank and merged.current >= board.current else board.rank,
                    wins=merged.wins + board.wins,
                    losses=merged.losses + board.losses,
                )
        matches = 0
        if window_days > 0:
            since = int(time.time()) - window_days * _DAY_S
            matches = await self._store.count_matches_since(profiles, since)
        known = any(s.known for s in statuses)
        return UserEloStats(
            user_id=user_id,
            profile_ids=tuple(profiles),
            leaderboards=tuple(unified.values()),
            matches_in_window=matches,
            known=known,
        )

    def _history_peak(self, matches: list[dict[str, Any]], profile_id: str) -> int:
        """Return the profile's highest rating_after across the raw history."""
        peak = 0
        for match in matches:
            for member in match.get("matchhistorymember") or []:
                if not isinstance(member, dict) or str(member.get("profile_id")) != profile_id:
                    continue
                peak = max(peak, _int(member.get("newrating")), _int(member.get("oldrating")))
        return peak

    async def decode_stored(self, profile_ids: list[str], batch: int = DECODE_BATCH) -> int:
        """Decode the stored matches' encoded fields (#288, T2).

        The blobs ride the match-details endpoint of an already-stored
        match id — the history itself is never re-fetched. A decode or
        transport failure leaves the document untouched: the next sync
        retries. Returns the number of decoded matches.
        """
        decoded = 0
        pending = await self._store.find_undecoded_matches(profile_ids, batch)
        for doc in pending:
            match_id = str(doc.get("match_id", ""))
            if not match_id:
                continue
            raw = await self._adapter.fetch_match_details_raw(match_id)
            if not raw:
                continue
            options_json, slots_json = decode_match_payload(raw)
            if not options_json and not slots_json:
                continue
            await self._store.update_match_fields(
                str(doc["_id"]),
                {
                    "options_json": options_json,
                    "slots_json": slots_json,
                    "decoded_at": _now_ms(),
                },
            )
            decoded += 1
        return decoded

    async def _find_status(self, profile_id: str) -> dict[str, Any] | None:
        """Return the account's previously stored status document."""
        docs = await self._store.find_accounts([profile_id])
        return docs[0] if docs else None

    def _account_doc(
        self, profile_id: str, boards: dict[str, dict[str, int]], previous: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Merge the fresh status into the account's document.

        The MAX elo never drops: the fresh board's max starts from the
        previously stored max (the history window may have slid past
        the all-time peak), then takes the fresh current and the
        history's peaks (computed at ingestion by ``_board_status``).
        """
        old_boards = (previous or {}).get("leaderboards") or {}
        merged: dict[str, dict[str, Any]] = dict(old_boards)
        for leaderboard_id, board in boards.items():
            old = old_boards.get(leaderboard_id) or {}
            merged[leaderboard_id] = {
                "current": board.get("current", 0),
                "max": max(
                    _int(old.get("max")),
                    _int(board.get("max")),
                    _int(board.get("current")),
                ),
                "rank": board.get("rank", 0),
                "wins": board.get("wins", 0),
                "losses": board.get("losses", 0),
            }
        return {
            "_id": profile_id,
            "leaderboards": merged,
            "last_synced_at": _now_ms(),
        }

    def _boards_from_stat(self, stat: dict[str, Any], profile_id: str) -> dict[str, dict[str, int]]:
        """Extract the account's PER-BOARD statuses from one raw reply.

        The REAL World's Edge shape (verified live 2026-11-20): the
        identity lives in ``statGroups[].members[]`` (with
        ``personal_statgroup_id``), the per-board stats in
        ``leaderboardStats[]`` (joined by ``statgroup_id`` — there is NO
        profile_id there; the shape this extractor used to expect never
        existed, so no board ever populated). One reply, every board.

        The MAX starts at the highest of the upstream-declared peak and
        the current rating; the account doc's merge keeps the stored
        all-time max (never drops).
        """
        member = _matching_member(stat, profile_id)
        if member is None:
            return {}
        statgroup = _int(member.get("personal_statgroup_id"))
        boards: dict[str, dict[str, int]] = {}
        for entry in stat.get("leaderboardStats") or []:
            if not isinstance(entry, dict) or _int(entry.get("statgroup_id")) != statgroup:
                continue
            board_id = str(entry.get("leaderboard_id", ""))
            if not board_id:
                continue
            current = _int(entry.get("rating", entry.get("elo")))
            wins = _int(entry.get("wins"))
            losses = _int(entry.get("losses"))
            if not current and not wins and not losses:
                continue  # an empty row reads as "unranked here", not a fake 0
            boards[board_id] = {
                "current": current,
                "max": max(current, _int(entry.get("highestrating"))),
                "rank": _int(entry.get("rank")),
                "wins": wins,
                "losses": losses,
            }
        return boards

    def _match_doc(self, match: dict[str, Any]) -> dict[str, Any]:
        """Build one stored match document from the RAW upstream payload.

        The document id is the bare match id: the upstream carries NO
        per-match leaderboard (the board suffix tripled every match).
        The raw payload rides verbatim (``raw``); the projection fields
        (participants, elo deltas, outcome) are extracted for the
        queries — the store never drops the source document.
        """
        members = match.get("matchhistorymember") or []
        profile_ids: list[str] = []
        rating_before: dict[str, int] = {}
        rating_after: dict[str, int] = {}
        teams: dict[str, int] = {}
        winners: list[str] = []
        for member in members:
            if not isinstance(member, dict):
                continue
            pid = str(member.get("profile_id", ""))
            if not pid:
                continue
            profile_ids.append(pid)
            teams[pid] = _int(member.get("teamid"))
            if member.get("outcome") == 1:
                winners.append(pid)
            old = _int(member.get("oldrating"))
            new = _int(member.get("newrating"))
            if old or new:
                rating_before[pid] = old
                rating_after[pid] = new
        board = str(match.get("leaderboard") or "")
        return {
            "_id": f"{match.get('id', '')}:{board}" if board else f"{match.get('id', '')}",
            "match_id": str(match.get("id", "")),
            "leaderboard_id": board,
            "started_at": _int(match.get("startgametime")),
            "finished_at": _int(match.get("completiontime")),
            "map_name": str(match.get("mapname") or "").removesuffix(".rms"),
            "profile_ids": profile_ids,
            "rating_before": rating_before,
            "rating_after": rating_after,
            "teams": teams,
            "winners": winners,
            "options_json": "",
            "slots_json": "",
            "raw": match,
            "fetched_at": _now_ms(),
        }

    def _entry_of(self, doc: dict[str, Any]) -> MatchHistoryEntry:
        """Build the served projection from one stored document."""
        return MatchHistoryEntry(
            match_id=str(doc.get("match_id", "")),
            leaderboard_id=str(doc.get("leaderboard_id", "")),
            started_at=_int(doc.get("started_at")),
            finished_at=_int(doc.get("finished_at")),
            map_name=str(doc.get("map_name", "")),
            profile_ids=tuple(str(p) for p in doc.get("profile_ids") or ()),
            rating_before={str(k): _int(v) for k, v in (doc.get("rating_before") or {}).items()},
            rating_after={str(k): _int(v) for k, v in (doc.get("rating_after") or {}).items()},
            teams={str(k): _int(v) for k, v in (doc.get("teams") or {}).items()},
            winners=tuple(str(w) for w in doc.get("winners") or ()),
            options_json=str(doc.get("options_json", "")),
            slots_json=str(doc.get("slots_json", "")),
        )

    def _status_of(self, profile_id: str, doc: dict[str, Any] | None) -> AccountEloStatus:
        """Build the served account status from the stored document."""
        if doc is None:
            return AccountEloStatus(profile_id=profile_id, known=False)
        boards = doc.get("leaderboards") or {}
        return AccountEloStatus(
            profile_id=profile_id,
            leaderboards=tuple(
                LeaderboardElo(
                    leaderboard_id=board_id,
                    name=LEADERBOARD_KEYS.get(board_id, board_id),
                    current=_int(board.get("current")),
                    max=_int(board.get("max")),
                    rank=_int(board.get("rank")),
                    wins=_int(board.get("wins")),
                    losses=_int(board.get("losses")),
                )
                for board_id, board in sorted(boards.items())
            ),
            last_synced_at=_int(doc.get("last_synced_at")),
            known=True,
        )


def _matching_member(stat: dict[str, Any], profile_id: str) -> dict[str, Any] | None:
    """Find the profile's identity member in the statGroups of a reply."""
    for group in stat.get("statGroups") or []:
        for member in (group or {}).get("members") or []:
            if isinstance(member, dict) and str(member.get("profile_id")) == profile_id:
                return member
    return None
