"""ext-librematch process entrypoint (botforge.v1.Game provider)."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any

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
        """
        if store is not None:
            await store.upsert_bindings(profile_ids, user_ids)
            task = asyncio.get_running_loop().create_task(_sync_quietly(syncer, profile_ids))
            _BACKGROUND_TASKS.add(task)
            task.add_done_callback(_BACKGROUND_TASKS.discard)
        return True

    async def _boot() -> None:
        if syncer is not None:
            task = asyncio.get_running_loop().create_task(_daily_sync_loop(syncer))
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
        """Serve the on-demand sync (T4): the given accounts, or all."""
        if syncer is None:
            return False, 0, "stats store not configured (MONGO_URI unset)"
        if wait:
            try:
                synced = await syncer.sync_accounts(profile_ids)
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
        return entries

    async def account_stats(profile_ids: list[str]) -> list[AccountEloStatus]:
        """Serve the per-account status: current + max elo (T1)."""
        if syncer is None:
            return []
        statuses: list[AccountEloStatus] = await syncer.account_stats(profile_ids)
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
    """Run one sync in the background; failures log, never crash."""
    if syncer is None:
        return
    try:
        await syncer.sync_accounts(profile_ids)
    except Exception:
        logging.getLogger("botforge.ext_librematch.sync").warning(
            "background stats sync failed", exc_info=True
        )


async def _daily_sync_loop(syncer: MatchHistorySyncer) -> None:
    """Run the periodic sync (T4): every known account, once a day."""
    period_s = float(os.environ.get("LIBREMATCH_SYNC_PERIOD_S", "86400"))
    while True:
        await asyncio.sleep(period_s)
        await _sync_quietly(syncer, [])


if __name__ == "__main__":
    main()
