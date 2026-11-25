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

import json
import logging
import re
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
from botforge.ext_librematch.reference import civ_name_of, map_name_of
from botforge.ext_librematch.store import DEFAULT_HISTORY_LIMIT, LibrematchStore

#: The capture era of the CURRENT revision (the repair gate).
#: Every stored match carries its era; a capture of an older era \u2014
#: or written by a revision before the era existed \u2014 repairs once,
#: then never again: whatever the upstream genuinely failed to carry
#: (RANDOM seats, unknown civ ids) stops the loop by construction.
CAPTURE_ERA = 5

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


def _map_name(raw_map: Any) -> str:
    """Normalize the upstream map filename into a readable map name.

    The upstream sends the map's file name (``FrigidLake.rms``, the
    community ``megarandom.rms2``, scenario files) and the literal
    ``my map`` for custom lobbies — the readable name of a custom
    lobby rides the lobby's own title. Strip the script extension
    whatever its trailing digit is (``.rms`` and ``.rms2`` both live
    in the wild).
    """
    name = str(raw_map or "").strip()
    if not name:
        return ""
    return re.sub(r"\.rms\d*$", "", name, flags=re.IGNORECASE)


#: the options blob's own key for the selected map (the community id
#: tables' ``10`` — 'location' in the ustacode option-key table)
OPTION_LOCATION = "10"


def _map_label(raw_map: Any, options_json: str) -> str:
    """Return the readable map name, crossing the upstream data sources.

    The options blob's location key (``10``) carries the REAL map id
    the provider's ``maps_aoe2.json`` reference table names — the
    authoritative source (verified live 2026-11-20: a custom lobby's
    ``FrigidLake.rms`` file name answered while the match played on
    the table's ``Enclosed``; a ``my map`` lobby answered ``Murkwood``).
    Fall back to the normalized file name (``Arena.rms``) when the
    blob or the table stays silent, "" never.
    """
    try:
        options = json.loads(options_json) if options_json else {}
    except json.JSONDecodeError:
        options = {}
    named = map_name_of(options.get(OPTION_LOCATION))
    if named:
        return named
    name = _map_name(raw_map)
    if name.lower() == "my map":
        return ""
    return name


def _member_civ(match: dict[str, Any], profile_id: str) -> Any:
    """Return the raw civilization id of one member of the raw payload.

    The history payload names it ``civilization_id`` (verified live
    2026-11-20 — the older ``race_id`` key lives in other upstream
    replies, both stay accepted).
    """
    for member in match.get("matchhistorymember") or []:
        if not isinstance(member, dict) or str(member.get("profile_id", "")) != profile_id:
            continue
        return member.get("civilization_id", member.get("race_id"))
    return None


def _int(value: Any) -> int:
    """Coerce an upstream field to int, 0 on garbage."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0



def _seen_board_updates(documents: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, int]]]:
    """Fold the freshly fetched matches into per-SEEN-PLAYER boards.

    Every member of every fetched match is a player the bot's users
    MET \u2014 the payload already carries his elo through that match
    (oldrating/newrating), so the encounter itself is the stat: no
    extra upstream call (owner 2026-11-22). The newest encounter on
    a board carries the current; the max never drops.

    RANKED matches only (owner 2026-11-22): a custom lobby's rating
    semantics are the lobby's own \u2014 the "test"/"Murkwood 1200"
    bot lobbies reported TG elo with one player per team, which the
    team-size heuristic folded into rm_1v1 and poisoned the panels'
    1v1 lines. AUTOMATCH (the ranked label) bounds the harvest.
    """
    updates: dict[str, dict[str, dict[str, int]]] = {}
    for doc in documents:
        if str(doc.get("lobby_title") or "").strip().upper() != "AUTOMATCH":
            continue
        # the match's OWN leaderboard read - the SAME keys as the
        # authority (GetPersonalStat boards are the WE leaderboard
        # ids: 3 = RM 1v1, 4 = RM team). The team-size HEURISTIC
        # folded an Empire Wars automatch (boards 13/14) into the RM
        # TG line and the panels read the EW elo (owner 2026-11-25)
        board = str(doc.get("leaderboard_id") or "")
        if board not in ("3", "4"):
            continue  # an EW/dm automatch never feeds the RM ladders
        ts = int(doc.get("finished_at") or doc.get("started_at") or 0)
        for player in doc.get("players") or []:
            pid = str((player or {}).get("profile_id", ""))
            if not pid:
                continue
            before = int((player or {}).get("rating_before") or 0)
            after = int((player or {}).get("rating_after") or 0)
            if not before and not after:
                continue
            entry = updates.setdefault(pid, {}).setdefault(
                board, {"current": 0, "max": 0, "ts": 0}
            )
            entry["max"] = max(entry["max"], before, after)
            if ts >= entry["ts"]:
                entry["current"] = after or before
                entry["ts"] = ts
    return updates


#: The option columns the footer displays (verified live 2026-11-22
#: against aoe2insights' rendering of match 517022737): the population
#: cap, the map size in TILES (the labels ride the game's own
#: OptionsMapSize enum — tiles ARE the enum values, see
#: https://aoe2control.github.io/game-options/#option-enums), the
#: game speed, the victory condition and the cheats flag. Unknown
#: values render raw, missing keys render nothing.
_MAP_SIZE_LABELS = {
    120: "Minuscule",
    144: "Petite",
    168: "Moyenne",
    200: "Normale",
    220: "Grande",
    240: "Immense",
    480: "Colossale",
}
_GAME_MODE_LABELS = {
    0: "Random Map",
    1: "R\u00e9gicide",
    2: "Death Match",
    3: "Sc\u00e9nario",
    5: "King of the Hill",
    6: "Course \u00e0 la Merveille",
    7: "D\u00e9fendre la Merveille",
    8: "Turbo Random Map",
    10: "Capture du Relique",
    11: "Sudden Death",
    12: "Battle Royale",
    13: "Empire Wars",
}
_SETTINGS_KEYS = {
    "5": ("Mode", _GAME_MODE_LABELS),
    "8": ("Taille", None),
    "28": ("Pop", None),
    "21": ("Vitesse", {50: "Lente", 60: "Normale", 80: "Rapide", 120: "Turbo"}),
    "81": ("Victoire", {1: "Conqu\u00eate", 9: "Standard", 7: "Temps", 8: "Score", 11: "Dernier debout"}),
    "1": ("Cheats", {"n": "non", "y": "oui",
                   "0": "non", "1": "oui"}),
}


def _setting_value(table: dict[Any, str] | None, raw: Any) -> str:
    """Look up a settings label tolerantly (the blob keys are strings)."""
    if table is None:
        return str(raw)
    for probe in (raw, str(raw), _int(raw)):
        if probe in table:
            return table[probe]
    return str(raw)


def _settings_of(options_json: str) -> list[list[str]]:
    """Extract the compact, human settings line from the options blob."""
    try:
        options = json.loads(options_json) if options_json else {}
    except Exception:
        return []
    if not isinstance(options, dict):
        return []
    out: list[list[str]] = []
    for key, (label, table) in _SETTINGS_KEYS.items():
        raw = options.get(key)
        if raw is None or raw == "":
            continue
        value = _setting_value(table, raw)
        if key == "8":
            # the map size, in tiles — the OptionsMapSize enum's own
            # numbers carry the label
            size = _setting_value(table, raw)
            value = f"{size} \u00d7 {size}"
            size_label = _MAP_SIZE_LABELS.get(_int(raw))
            if size_label:
                value = f"{value} ({size_label})"
        out.append([label, value])
    return out


def _players_with_ai(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the doc's seats - the AI seats ride along when the ingest missed them.

    An old capture folds its players BEFORE the AI rule (owner
    2026-11-24: his 1v1v1 against two computers served one seat);
    the slotinfo carries the computers anyway - re-fold at read time.
    """
    players = list(doc.get("players") or [])
    if any(bool((p or {}).get("ai")) for p in players):
        return players
    return [*players, *_ai_seats(str(doc.get("slots_json") or ""), doc.get("teams") or {})]


def _int_of_slot(value: Any) -> int:
    """Coerce a slot field to int (-1 on garbage)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _is_computer_slot(slot: dict[str, Any]) -> bool:
    """Whether a normalised slot is a computer seat.

    One grammar for every capture AGE (owner 2026-11-24): the WE
    slotinfo answers a NEGATIVE profile id for a computer (verified
    live, matches 518232462/523338329); the old decode stored those
    seats as filled humans. The truth: NO profile (pid <= 0) with a
    civ is a computer; a closed slot carries neither.
    """
    if str(slot.get("slot_kind") or "") == "ai":
        return True
    pid = _int_of_slot(slot.get("profile_id"))
    civ = _int_of_slot(slot.get("civ"))
    return pid <= 0 and civ >= 0


def _ai_seats(slots_json: str, teams: dict[str, int]) -> list[dict[str, Any]]:
    """Build the AI seats the slotinfo carries (owner 2026-11-23).

    A filled slot without a profile is a computer - it never joined
    the members walk, but it PLAYED; no elo lines, the civ speaks.
    """
    try:
        slots = json.loads(slots_json) if slots_json else []
    except Exception:
        return []
    if not isinstance(slots, list):
        return []
    seats: list[dict[str, Any]] = []
    for slot in slots:
        if not isinstance(slot, dict) or not _is_computer_slot(slot):
            continue
        if str((slot or {}).get("profile_id", "")) in teams:
            continue
        seats.append(
            {
                "profile_id": "",
                "alias": str(slot.get("ai_name") or "IA"),
                "civ": civ_name_of(slot.get("civ")),
                "team": int(slot.get("team") or 0),
                "slot": int(slot.get("slot_index") or 0),
                "ai": True,
                "rating_before": 0,
                "rating_after": 0,
            }
        )
    return seats


def _board_complete(doc: dict[str, Any] | None, board_ids: tuple[str, ...]) -> bool:
    """Return True when every wanted board is known (a value, a peak, or the absence)."""
    boards = (doc or {}).get("leaderboards") or {}
    for board_id in board_ids:
        board = boards.get(board_id) or {}
        if not (
            int(board.get("current") or 0)
            or int(board.get("max") or 0)
            or board.get("none")
        ):
            return False
    return True


def _needs_repair(candidate_docs: list[dict[str, Any]]) -> bool:
    """Return True when older-era captures wait for their repair pass.

    The candidates come from the store's ERA GATE (see
    ``find_incomplete_docs``): a capture of an older era repairs once
    whatever its content \u2014 the rebuilt capture carries the current
    era and never loops, even when the upstream honestly lacks a
    field (RANDOM seats, civ ids the reference cannot name).
    """
    return bool(candidate_docs)


class MatchHistorySyncer:
    """Pull the known accounts' history into the store, exploit it after."""

    def _ladder_of_doc(self, doc: dict[str, Any]) -> str:
        """Infer the doc's RATED board (owner 2026-11-25).

        The upstream carries NO per-match leaderboard (verified live
        - ``leaderboard_id`` reads empty on every sync payload), so
        the rated matches infer their board: ``AUTOMATCH`` only (a
        rated row never rides a custom lobby), the game's own MODE
        key splits Empire Wars (13/14) from Random Map, then exactly
        two rated seats read RM 1v1 (3), a team game reads RM TG (4).
        """
        if str(doc.get("leaderboard_id") or ""):
            return str(doc.get("leaderboard_id"))  # a legacy board rides
        ratings = doc.get("rating_after") or {}
        if not ratings or str(doc.get("description") or "").strip().upper() != "AUTOMATCH":
            return ""
        mode = ""
        try:
            options = json.loads(str(doc.get("options_json") or "") or "{}")
            mode = str(options.get("5", "")).strip()
        except Exception:
            mode = ""
        if mode in ("13", "14"):
            return mode  # Empire Wars: its own series, never the RM ladders
        rated = [p for p in (doc.get("players") or []) if str((p or {}).get("profile_id", "")) in ratings]
        return "3" if len(rated) == 2 else "4"

    async def _fold_elo_points(self, documents: list[dict[str, Any]]) -> None:
        """Record one dated elo point per (profile, board) of the fold.

        Each RATED match carries the players' after-ratings - one
        point at the match's own end (owner 2026-11-25): the seat
        lines read the match's day, not the card's.
        """
        try:
            for doc in documents:
                board = self._ladder_of_doc(doc)
                point_at = _int(doc.get("finished_at")) or _int(doc.get("started_at"))
                if not board or not point_at:
                    continue
                for pid, after in (doc.get("rating_after") or {}).items():
                    if _int(after) > 0 and str(pid):
                        await self._store.record_elo_points(str(pid), board, [(point_at, _int(after))])
        except Exception:
            logger.debug("the elo series fold failed", exc_info=True)

    async def backfill_elo_series(self) -> int:
        """Fold the STORED matches into the elo timeseries (once).

        The series starts empty; the matches already carry every
        after-rating with its date (owner 2026-11-25) - one pass over
        the store rebuilds the whole history retroactively, the
        regular fold keeps it alive afterwards. Idempotent: the
        points deduplicate on the upsert.
        """
        if not await self._store.elo_series_is_empty():
            return 0
        try:
            docs = await self._store.find_matches([], limit=0, include_invalid=True)
        except Exception:
            logger.warning("the elo backfill read failed", exc_info=True)
            return 0
        written = 0
        for doc in docs:
            board = self._ladder_of_doc(doc)
            point_at = _int(doc.get("finished_at")) or _int(doc.get("started_at"))
            if not board or not point_at:
                continue
            for pid, after in (doc.get("rating_after") or {}).items():
                if _int(after) > 0 and str(pid):
                    written += 1
                    await self._store.record_elo_points(str(pid), board, [(point_at, _int(after))])
        logger.info("elo series backfill: %d doc(s), %d point(s)", len(docs), written)
        return written

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
        self._last_seal_s = 0.0

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
        # AN INCOMPLETE CAPTURE heals like an empty store: the raw of
        # an old-revision document may lack the members/description
        # fields, so the decode heal cannot reconstruct what was never
        # captured — the account re-pulls its DEEP window and REPLACES
        # the incomplete captures with the full upstream payload (the
        # match facts stay what they are; only the capture completes).
        repair_docs = await self._store.find_incomplete_docs(profile_id)
        incomplete = _needs_repair(repair_docs)
        deep = (
            await self._store.count_matches_of_profile(profile_id) == 0
            or incomplete
        )
        if incomplete:
            logger.info(
                "SYNC repair: %d incomplete stored capture(s) for %s \u2014 deep refetch",
                len(repair_docs),
                profile_id,
            )
        count = self._sync_count if deep else self._quick_count
        # ONE history fetch: the upstream's ``leaderboard_id`` param does NOT
        # filter (verified live 2026-11-20 — the same matches answer under
        # every board), so the per-board loop only tripled the upstream
        # calls and stored every match three times.
        raw_matches = await self._adapter.fetch_match_history_raw(profile_id, "", count)
        if raw_matches:
            documents = [self._match_doc(m) for m in raw_matches]
            if incomplete:
                # the repair DELETES the poisoned captures first (the
                # old era suffixed every id with a board \u2014 the bare-id
                # inserts never overwrote them, and the marker looped),
                # then re-inserts complete captures of the SAME facts
                await self._store.delete_matches(
                    [str(doc.get("_id", "")) for doc in repair_docs]
                )
                await self._store.insert_matches_new_only(documents)
                stored_any = True
            else:
                # the steady state: a finished match is immutable, a
                # known id is never rewritten \u2014 insert-only
                inserted = await self._store.insert_matches_new_only(documents)
                stored_any = stored_any or inserted > 0
            # the elo TIMESERIES rides the fold (owner 2026-11-25)
            await self._fold_elo_points(documents)
            # every seat met becomes a known player: his boards ride
            # the encounter itself (no extra upstream call), and the
            # seats lacking a 1v1 elo get probed once (owner 2026-11-22)
            await self._store.upsert_seen_accounts(_seen_board_updates(documents))
            met = sorted({str(pid) for doc in documents for pid in doc.get("profile_ids") or []})
            await self.refresh_missing_1v1(met, cap=10)
            # The decode step (T2) rides the ingest now: the history
            # payload ITSELF carries the encoded ``options``/``slotinfo``
            # blobs (the LibreMatch wiki, community/leaderboard/
            # getRecentMatchHistory), so exploiting them needs NO
            # second endpoint call — the match-details fetch the earlier
            # revision made 400s on World's Edge, every single time.
        # ONE stats fetch answers EVERY board at once: the reply joins
        # ``leaderboardStats[].statgroup_id`` with ``members[].
        # personal_statgroup_id`` (the same join the alias search rides).
        stat = await self._adapter.fetch_personal_stat_raw(profile_id, "")
        boards = self._boards_from_stat(stat, profile_id)
        if boards:
            stored_any = True
        await self._store.upsert_account(self._account_doc(profile_id, boards, previous))
        # the freshness stamp rides the ACCOUNT (owner 2026-11-25):
        # the next listing click within the window reads the store,
        # no upstream wait
        try:
            await self._store.stamp_synced([profile_id])
        except Exception:
            logger.debug("the sync stamp failed", exc_info=True)
        # The catch-up decode for documents stored by an older revision
        # (their blobs sit verbatim in ``raw``): no network, no re-fetch.
        await self.decode_stored([profile_id])
        # Seal the never-played captures: a match started long ago
        # with no result is an abandoned lobby, not a game (owner
        # 2026-11-23 - the served "test" lobbies never went away).
        await self._seal_stale_when_due()
        return stored_any

    async def _seal_stale_when_due(self) -> None:
        """Run the never-played sweep THROTTLED - never per click.

        The seal sweeps the WHOLE matches collection (owner
        2026-11-25): one pass every ten minutes, then silence.
        """
        import os
        import time

        if time.time() - self._last_seal_s > float(os.environ.get("LIBREMATCH_SEAL_INTERVAL_S", "600")):
            self._last_seal_s = time.time()
            try:
                stale = await self._store.invalidate_stale_matches()
                if stale:
                    logger.info("stale matches invalidated: %d", stale)
            except Exception:
                logger.debug("the stale-match seal failed", exc_info=True)

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
        # the timeseries wants the refresh too (owner 2026-11-25): a
        # board the matches never carried still tracks its current
        try:
            import time

            now = int(time.time())
            for board, entry in (boards or {}).items():
                cur = _int((entry or {}).get("current"))
                if cur > 0:
                    await self._store.record_elo_points(profile_id, str(board), [(now, cur)])
        except Exception:
            logger.debug("the elo series refresh failed", exc_info=True)
        return True

    async def refresh_statuses(self, profile_ids: list[str]) -> int:
        """Run the light elo refresh (every BOUND account when empty).

        The MET players never join the loop: their boards ride the
        encounter fold, a scheduled stat call for every stranger ever
        met would hammer the upstream for data the store already has
        (owner 2026-11-22 \u2014 the post-purge boot walked thousands of
        unrelated profiles).
        """
        targets = [str(p) for p in profile_ids] or await self._store.list_bound_profiles()
        refreshed = 0
        for profile_id in targets:
            try:
                if await self.refresh_status(profile_id):
                    refreshed += 1
            except Exception:
                logger.warning("elo refresh failed (%s)", profile_id, exc_info=True)
        return refreshed

    async def stale_sync_targets(self, profile_ids: list[str], window_s: int = 120) -> list[str]:
        """Return the profiles whose sync stamp is OLDER than the window.

        The on-demand listing gate (owner 2026-11-25): the profile
        synced seconds ago already owns the match that just ended
        upstream - re-fetching it only added seconds to the click.
        """
        try:
            fresh = await self._store.recently_synced(profile_ids, window_s)
        except Exception:
            return [str(p) for p in profile_ids]
        return [str(p) for p in profile_ids if str(p) not in fresh]

    async def sync_accounts(self, profile_ids: list[str]) -> int:
        """Sync the given accounts (every BOUND one when empty). T4 rides.

        The met players stay OUT of the walk (list_bound_profiles)
        \u2014 the encounter fold already harvests their boards (see
        refresh_statuses).
        """
        targets = [str(p) for p in profile_ids] or await self._store.list_bound_profiles()
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
        # the listing shows the SEALED matches too - with their status
        # (owner 2026-11-24: his never-decided test read as a hole in
        # the five); the panel reads the entry's own invalid flag
        docs = await self._store.find_matches(
            profile_ids, limit or DEFAULT_HISTORY_LIMIT, since_s, leaderboard_id, include_invalid=True
        )
        return [self._entry_of(doc) for doc in docs]

    async def refresh_missing_1v1(self, profile_ids: list[str], cap: int = 30) -> list[str]:
        """Probe the missing 1v1 AND TG boards of the MET players - once each.

        The seen harvest only folds the boards the matches carried
        (a player met through NOTHING but custom lobbies never gets
        his TG board either): every board the panels read, 3 (RM 1v1)
        and 4 (RM team), probes once when absent \u2014 found is
        stored, an honest absence marks the board so the probe never
        repeats (owners 2026-11-22/23: the missing TG elo).
        """
        if not profile_ids:
            return []
        docs = await self._store.find_accounts([str(p) for p in profile_ids])
        by_id = {str(doc.get("_id", "")): doc for doc in docs}
        probed: list[str] = []
        missing_boards = ("3", "4")  # the WE ids: RM 1v1, RM team
        for profile_id in profile_ids:
            str_pid = str(profile_id)
            if _board_complete(by_id.get(str_pid), missing_boards):
                continue
            if len(probed) >= max(0, cap):
                break
            probed.append(str_pid)
        if not probed:
            return []
        fresh, absent = await self._probe_boards(probed, missing_boards)
        if fresh:
            await self._store.upsert_seen_accounts(fresh)
        if absent:
            for profile_id, board_id in absent:
                await self._store.mark_missing_board(profile_id, board_id)
        return probed

    async def _probe_boards(
        self, profile_ids: list[str], board_ids: tuple[str, ...] = ("3",)
    ) -> tuple[dict[str, dict[str, dict[str, int]]], list[tuple[str, str]]]:
        """Fetch the wanted boards of each profile once, found/absent.

        ONE stat call answers EVERY board (the statgroup join), so
        probing several boards costs nothing extra.
        """
        fresh: dict[str, dict[str, dict[str, int]]] = {}
        absent: list[tuple[str, str]] = []
        for profile_id in profile_ids:
            try:
                # the adapter's signature takes (profile_id, leaderboard_id):
                # the probe passes an empty board - ONE call answers every
                # board (the statgroup join)
                stat = await self._adapter.fetch_personal_stat_raw(profile_id, "")
            except Exception:
                logger.debug("the 1v1 probe failed (%s)", profile_id, exc_info=True)
                continue
            boards = self._boards_from_stat(stat, profile_id) if isinstance(stat, dict) else {}
            found: dict[str, dict[str, int]] = {}
            for board_id in board_ids:
                board = boards.get(board_id) or {}
                if int(board.get("current") or 0) or int(board.get("max") or 0):
                    found[board_id] = board
                else:
                    absent.append((profile_id, board_id))
            if found:
                fresh[profile_id] = found
        return fresh, absent

    async def account_stats(
        self, profile_ids: list[str], at_s: int = 0
    ) -> list[AccountEloStatus]:
        """Serve the per-account status (current + max elo per board).

        Store-only, NEVER a probe on the serve path (owner
        2026-11-23): a batch of 8 seats probing the missing 1v1/TG
        boards walked the upstream and the gRPC reply ran past its
        deadline - the panels then rendered NO elo lines at all
        (DEADLINE_EXCEEDED, merlin 14:27). The probes ride the SYNC
        flow (sync_account probes the met players, capped); the
        serve answers what the store already knows.

        ``at_s > 0`` serves the ELO AS OF THAT MOMENT (owner
        2026-11-25): the seat lines render the match's day, not the
        card's - the timeseries (librematch:elo) answers the last
        point at or before it; before the first point the status
        reads UNKNOWN, never a guess.
        """
        if not profile_ids:
            return []
        if at_s > 0:
            series = await self._store.elo_as_of([str(p) for p in profile_ids], int(at_s))
            return [
                self._as_of_status(str(profile_id), series.get(str(profile_id)) or {})
                for profile_id in profile_ids
            ]
        docs = await self._store.find_accounts([str(p) for p in profile_ids])
        by_id = {str(doc["_id"]): doc for doc in docs}
        statuses: list[AccountEloStatus] = []
        for profile_id in profile_ids:
            doc = by_id.get(str(profile_id))
            statuses.append(self._status_of(str(profile_id), doc))
        return statuses

    def _as_of_status(self, profile_id: str, boards: dict[str, tuple[int, int]]) -> AccountEloStatus:
        """Build the as-of account status from the timeseries row."""
        from botforge.core.models.game import LeaderboardElo

        if not boards:
            return AccountEloStatus(profile_id=profile_id, known=False)
        names = {"3": "rm_1v1", "4": "rm_team"}
        return AccountEloStatus(
            profile_id=profile_id,
            leaderboards=tuple(
                LeaderboardElo(
                    leaderboard_id=board, name=names.get(board, board), current=cur, max=peak
                )
                for board, (cur, peak) in sorted(boards.items())
            ),
            known=True,
        )

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

        The blobs ride the stored ``raw`` payload verbatim — the history
        fetch already returned them (the upstream's own fields,
        base64+zlib per the LibreMatch wiki); the match-details
        endpoint played that role earlier but World's Edge 400s it,
        so the decode re-fetches NOTHING. It also RE-DERIVES every
        projection field from the raw payload — a document stored by
        an older revision heals itself (the labels the reference
        tables now name), without a purge and without touching the
        immutable raw. Returns the number of documents patched.
        """
        decoded = 0
        pending = await self._store.find_undecoded_matches(profile_ids, batch)
        for doc in pending:
            raw = doc.get("raw")
            if not isinstance(raw, dict):
                continue
            options_json, slots_json = decode_match_payload(raw)
            rebuilt = self._match_doc(raw)
            await self._store.update_match_fields(
                str(doc["_id"]),
                {
                    "map_name": rebuilt["map_name"],
                    "lobby_title": rebuilt["lobby_title"],
                    "description": rebuilt["description"],
                    "players": rebuilt["players"],
                    "teams": rebuilt["teams"],
                    "winners": rebuilt["winners"],
                    "profile_ids": rebuilt["profile_ids"],
                    "options_json": options_json,
                    "slots_json": slots_json,
                    "decoded_at": _now_ms() if (options_json or slots_json) else 0,
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
        # SLOTINFO carries the truth (owner 2026-11-22): the slot index
        # AND the team both come from it in ranked games (teams split
        # by slot parity 1-3-5-7 vs 2-4-6-8) - the member's teamid
        # has led cards wrong; slotinfo's word is final. It decodes
        # FIRST so the members walk can already read it.
        options_json, slots_json = decode_match_payload(match)
        seat_slots: dict[str, int] = {}
        seat_teams: dict[str, int] = {}
        if slots_json:
            try:
                for slot in json.loads(slots_json) or []:
                    pid = str((slot or {}).get("profile_id", ""))
                    if not pid:
                        continue
                    seat_teams[pid] = int((slot or {}).get("team") or 0)
                    seat_slots[pid] = int((slot or {}).get("slot_index", 0) or 0)
            except Exception:
                seat_slots = {}
                seat_teams = {}
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
            teams[pid] = seat_teams.get(pid, _int(member.get("teamid")))
            if member.get("outcome") == 1:
                winners.append(pid)
            old = _int(member.get("oldrating"))
            new = _int(member.get("newrating"))
            if old or new:
                rating_before[pid] = old
                rating_after[pid] = new
        aliases = match.get("profile_aliases") or {}
        civs = {
            pid: civ_name_of(_member_civ(match, pid)) for pid in profile_ids
        }
        players = [
            {
                "profile_id": pid,
                "alias": str(aliases.get(pid, "")),
                "civ": civs.get(pid, ""),
                "team": teams.get(pid, 0),
                "slot": seat_slots.get(pid, 0),
                "rating_before": rating_before.get(pid, 0),
                "rating_after": rating_after.get(pid, 0),
            }
            for pid in profile_ids
        ]
        # the AI seats ride the slotinfo too (owner 2026-11-23)
        players.extend(_ai_seats(slots_json, teams))
        board = str(match.get("leaderboard") or "")
        lobby = str(match.get("description") or "").strip()
        return {
            "_id": f"{match.get('id', '')}:{board}" if board else f"{match.get('id', '')}",
            "match_id": str(match.get("id", "")),
            "leaderboard_id": board,
            "started_at": _int(match.get("startgametime")),
            "finished_at": _int(match.get("completiontime")),
            "map_name": _map_label(match.get("mapname"), options_json),
            "lobby_title": lobby,
            "profile_ids": profile_ids,
            "rating_before": rating_before,
            "rating_after": rating_after,
            "teams": teams,
            "winners": winners,
            "description": lobby,
            "players": players,
            "settings": _settings_of(options_json),
            "options_json": options_json,
            "slots_json": slots_json,
            "raw": match,
            "capture_era": CAPTURE_ERA,
            "decoded_at": _now_ms() if (options_json or slots_json) else 0,
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
            description=str(doc.get("description", "")),
            players_json=json.dumps(_players_with_ai(doc), ensure_ascii=False),
            invalid=bool(doc.get("invalid") or False),
            settings_json=json.dumps(doc.get("settings") or [], ensure_ascii=False),
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
