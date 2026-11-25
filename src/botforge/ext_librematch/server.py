"""ext-librematch process entrypoint (botforge.v1.Game provider)."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any

logger = logging.getLogger("botforge.ext_librematch.server")

if TYPE_CHECKING:
    from botforge.ext_librematch.adapter import LibrematchAdapter
    from botforge.ext_librematch.history import MatchHistorySyncer
    from botforge.ext_librematch.store import LibrematchStore

_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


def main() -> None:
    """Run the ext-librematch gRPC provider server."""
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    from botforge.core_process.ext_server import serve_game_provider
    from botforge.ext_librematch import DECLARED_CAPABILITIES, PROVIDER_ID

    adapter, store, syncer = _build_stack()
    stats_handlers = _stats_handlers(syncer)

    async def update_subscriptions(profile_ids: list[str], user_ids: list[str]) -> bool:
        """Record the known accounts (+ owners) and refresh them now.

        The core pushes the platform's enrolled profiles; the store
        keeps the profile -> user mapping (the unification's key) and
        an on-demand sync runs in the background (T4) — the history is
        fresh right after a profile binding or an application.

        Observable BY DESIGN: a silent no-op of this handler once cost
        a whole debugging session (merlin, 2026-11-20) — every call
        logs what it did, store present or not.
        """
        logger.info(
            "SUBSCRIPTIONS push received: %s profile(s), %s user id(s) — store %s",
            len(profile_ids),
            len(user_ids),
            "ONLINE" if store is not None else "OFFLINE (no MONGO_URI)",
        )
        if store is not None:
            await store.upsert_bindings(profile_ids, user_ids)
            task = asyncio.get_running_loop().create_task(_sync_quietly(syncer, profile_ids))
            _BACKGROUND_TASKS.add(task)
            task.add_done_callback(_BACKGROUND_TASKS.discard)
        return True

    async def _boot() -> None:
        if store is not None:
            await store.ensure_indexes()
        if syncer is not None:
            task = asyncio.get_running_loop().create_task(_daily_sync_loop(syncer))
            _BACKGROUND_TASKS.add(task)
            task.add_done_callback(_BACKGROUND_TASKS.discard)
            task = asyncio.get_running_loop().create_task(_elo_refresh_loop(syncer))
            _BACKGROUND_TASKS.add(task)
            task.add_done_callback(_BACKGROUND_TASKS.discard)
        await serve_game_provider(
            DECLARED_CAPABILITIES,
            PROVIDER_ID,
            match_details=adapter.match_details,
            list_maps=adapter.list_maps,
            player_stats=adapter.player_stats,
            match_result=adapter.recent_match_result,
            update_subscriptions=update_subscriptions,
            search_profiles=adapter.search_profiles,
            **stats_handlers,
        )

    asyncio.run(_boot())


def _build_stack() -> tuple[LibrematchAdapter, LibrematchStore | None, MatchHistorySyncer | None]:
    """Build the adapter, the stats store and the syncer from the env.

    The community leaderboard endpoint is PUBLIC — no API key gates
    player_stats (the 2026-10-16 lesson: the key gate rejected every
    profile while GetPersonalStat answers anyone). The declared
    capabilities stand as-is.

    The stats store (#404 T1) is the provider's OWN database — the raw
    history and the per-account status live here, never in another
    service's collections. No MONGO_URI means no stats layer: the
    stats RPCs answer degraded empties and the core falls back to
    manual review.
    """
    import redis.asyncio as redis

    from botforge.core.rpc.rate_limit import ProviderRateLimiter
    from botforge.ext_librematch.adapter import DEFAULT_BASE_URL, LibrematchAdapter
    from botforge.ext_librematch.history import MatchHistorySyncer
    from botforge.ext_librematch.store import LibrematchStore

    redis_uri = os.environ.get("REDIS_URI", "")
    rate_limiter = None
    if redis_uri:
        rate_limiter = ProviderRateLimiter(
            redis.from_url(redis_uri, decode_responses=True),
            game_key="aoe2",
            max_calls=int(os.environ.get("LIBREMATCH_RATE_MAX_CALLS", "60")),
            window_s=int(os.environ.get("LIBREMATCH_RATE_WINDOW_S", "60")),
        )
    adapter = LibrematchAdapter(
        base_url=os.environ.get("LIBREMATCH_API_URL", "") or DEFAULT_BASE_URL,
        rate_limiter=rate_limiter,
    )
    if not os.environ.get("MONGO_URI", ""):
        return adapter, None, None
    from botforge.core.models.db import get_async_database

    store = LibrematchStore(get_async_database())
    return adapter, store, MatchHistorySyncer(adapter, store)


def _sync_stats_handler(
    syncer: MatchHistorySyncer | None,
) -> Any:
    """Build the on-demand sync callable; None syncer degrades."""

    async def sync_stats(profile_ids: list[str], wait: bool) -> tuple[bool, int, str]:
        """Serve the on-demand sync (T4): the given accounts, or all.

        The CLICK owns its freshness but never twice in a row
        (owner 2026-11-25: "tu dois d\u00e9j\u00e0 avoir la data - le
        chargement est beaucoup trop lent"): a profile synced within
        the freshness window answers straight from the store, only
        the STALE ones wait for the upstream pass.
        """
        if syncer is None:
            return False, 0, "stats store not configured (MONGO_URI unset)"
        if wait:
            try:
                targets = [str(p) for p in profile_ids]
                if targets:
                    stale_s = int(os.environ.get("LIBREMATCH_SYNC_STALE_S", "120"))
                    targets = await syncer.stale_sync_targets(targets, stale_s)
                if not targets:
                    return True, 0, ""  # all warm: the store IS the truth
                synced = await syncer.sync_accounts(targets)
                return True, synced, ""
            except Exception as exc:  # a functional error, not a crash
                return False, 0, f"{type(exc).__name__}: {exc}"[:400]
        task = asyncio.get_running_loop().create_task(_sync_quietly(syncer, profile_ids))
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)
        return True, 0, ""

    return sync_stats


def _stats_handlers(syncer: MatchHistorySyncer | None) -> dict[str, Any]:
    """Build the stats RPC callables; None syncer degrades to empties."""
    from botforge.core.models.game import AccountEloStatus, MatchHistoryEntry, UserEloStats

    async def match_history(
        profile_ids: list[str], limit: int, since_s: int, leaderboard_id: str
    ) -> list[MatchHistoryEntry]:
        """Serve the stored history of the known accounts (T1)."""
        if syncer is None:
            return []
        entries: list[MatchHistoryEntry] = await syncer.match_history(
            profile_ids, limit, since_s, leaderboard_id
        )
        # Observable BY DESIGN (the 2026-11-20 bare-lines hunt): every
        # served reply samples its newest entries \u2014 the id, the map,
        # the lobby title and the players count the VIEW will read.
        if entries:
            import json as _json

            def _seat_count(entry: Any) -> int:
                try:
                    return len(_json.loads(entry.players_json or "[]"))
                except Exception:
                    return 0

            sample = ", ".join(
                "{} : {} joueur(s) · carte {} · lobby {}".format(
                    e.match_id,
                    _seat_count(e),
                    e.map_name or "?",
                    (e.description or "").strip() or "\u2014",
                )
                for e in entries[:3]
            )
            logger.info("SERVE history: %s entr\u00e9e(s) pour %s \u2014 %s", len(entries), profile_ids, sample)
        return entries

    async def account_stats(profile_ids: list[str], at_s: int = 0) -> list[AccountEloStatus]:
        """Serve the per-account status: current + max elo (T1).

        ``at_s > 0`` answers the elo AS OF that moment (owner
        2026-11-25) - the seat lines render the match's day.
        """
        if syncer is None:
            return []
        statuses: list[AccountEloStatus] = await syncer.account_stats(profile_ids, at_s)
        return statuses

    async def user_stats(user_id: str, window_days: int) -> UserEloStats | None:
        """Serve the per-user unified view over the user's accounts (T1)."""
        if syncer is None:
            return None
        stats: UserEloStats | None = await syncer.user_stats(user_id, window_days)
        return stats

    return {
        "sync_stats": _sync_stats_handler(syncer),
        "match_history": match_history,
        "account_stats": account_stats,
        "user_stats": user_stats,
    }


async def _sync_quietly(syncer: MatchHistorySyncer | None, profile_ids: list[str]) -> None:
    """Run one sync in the background; failures log, never crash.

    Observable BY DESIGN (same lesson): the outcome is logged — how
    many accounts synced and how many matches landed in the store.
    """
    if syncer is None:
        logger.warning("SYNC skipped: no store wired in this process")
        return
    try:
        synced = await syncer.sync_accounts(profile_ids)
        logger.info("SYNC done: %s account(s) synced", synced)
    except Exception:
        logging.getLogger("botforge.ext_librematch.sync").warning(
            "background stats sync failed", exc_info=True
        )


async def _daily_sync_loop(syncer: MatchHistorySyncer) -> None:
    """Run the periodic HISTORY sync (T4): every known account, once a day.

    The fetch is INCREMENTAL (the quick window): the first sync of an
    account pulls deep, every later one appends the new matches only —
    a finished match is immutable.
    """
    period_s = float(os.environ.get("LIBREMATCH_SYNC_PERIOD_S", "86400"))
    while True:
        # Sync FIRST, then sleep: a boot pass must run immediately. The
        # core only pushes UpdateEnrollments when the roster CHANGES, so
        # a store purge (or a silent boot) would otherwise leave the
        # accounts unsynced for a full period with nothing to wake us
        # up. The pass is cheap when the store is already warm (quick
        # window, appends only — a finished match is immutable).
        await _sync_quietly(syncer, [])
        await asyncio.sleep(period_s)


async def _elo_refresh_loop(syncer: MatchHistorySyncer) -> None:
    """Refresh every known account's elo hourly — the light loop.

    The elo the criteria and the views read must stay fresh without
    re-pulling histories: only the per-board stats fetch here (the
    account document merges — the max never drops).
    """
    period_s = float(os.environ.get("LIBREMATCH_ELO_PERIOD_S", "3600"))
    while True:
        # Refresh FIRST, then sleep: same lesson as the history loop —
        # the first pass belongs at boot, not one period later, so a
        # purged or fresh store fills without waiting on a roster push.
        if syncer is not None:
            try:
                refreshed = await syncer.refresh_statuses([])
                logger.info("elo refresh done: %s account(s)", refreshed)
            except Exception:
                logger.warning("elo refresh loop failed — retrying next tick", exc_info=True)
        await asyncio.sleep(period_s)


if __name__ == "__main__":
    main()
