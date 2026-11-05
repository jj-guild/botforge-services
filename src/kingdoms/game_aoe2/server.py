"""game-aoe2 process entrypoint (kingdoms.v1.GameData server).

The single consumer of the AoE2 providers (developer direction):
consumes their ``StreamMatchEvents`` (ext-aoe2lobby realtime,
ext-librematch source of truth), folds them into the enriched
per-player state, and serves the GameData contract (dashboard,
player events, enrollments) to svc-core and the bot.

``UpdateEnrollments`` (pushed by svc-core) is reconciled down to the
realtime provider through its own ``UpdateSubscriptions`` — svc-core
never talks to the providers directly, in either direction.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from kingdoms.core.upstream_stats import StatsRegistry

# The process-wide upstream call stats — the provider streams this
# process consumes, served over the Status contract.
STATS = StatsRegistry()

logger = logging.getLogger("kingdoms.game_aoe2")


def main() -> None:
    """Run the game-aoe2 gRPC GameData server."""
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(_serve())


async def _serve() -> None:
    from kingdoms import __version__
    from kingdoms.core.rpc.status import CoreStatus, build_status_server_with_stats
    from kingdoms.game_aoe2 import GAME_KEY, PROCESS_LABEL
    from kingdoms.game_aoe2.aggregator import GameAoe2Aggregator
    from kingdoms.game_aoe2.rpc import GameDataServicer, add_gamedata_servicer

    aggregator = GameAoe2Aggregator()
    enrollments = _EnrollmentPusher(aggregator)
    server = build_status_server_with_stats(
        lambda: CoreStatus(version=__version__, process=PROCESS_LABEL),
        stats_provider=_aggregate_provider_stats,
    )
    add_gamedata_servicer(server, GameDataServicer(aggregator, enrollments=enrollments))

    consumer = asyncio.ensure_future(_consume_providers(aggregator))
    # The active prober is GONE (owner direction 2026-11-04): a synthetic
    # ping every minute was indistinguishable from real traffic for the
    # rate-limited upstreams. The providers panel reads each provider's
    # OWN call statistics (GetUpstreamStats on the Status contract) —
    # the provider process is the only place that sees the calls.

    port = os.environ.get("GAME_GRPC_PORT", "50071")
    bind = f"[::]:{port}"
    server.add_insecure_port(bind)
    await server.start()
    logger.info("GAME_AOE2_READY port=%s version=%s game=%s", port, __version__, GAME_KEY)
    try:
        await server.wait_for_termination()
    finally:
        consumer.cancel()


class _EnrollmentPusher:
    """Reconcile the platform's enrollments: roster + provider subscription.

    The enrollments carry the roster (profile ids + their platform
    users) — the dashboard's baseline, so every enrolled player
    renders even before any transition fired — and the realtime
    provider's ``UpdateSubscriptions`` (in-place deltas on its single
    WebSocket session, no teardown).
    """

    def __init__(self, aggregator: Any) -> None:
        self._aggregator = aggregator
        self._last_ids: list[str] | None = None
        self._client: Any = None

    async def apply(
        self, game_key: str, profile_ids: list[str], user_ids: list[str] | None = None
    ) -> tuple[int, bool]:
        """Record the roster, then push the subscription down."""
        self._aggregator.set_roster(
            [
                {"profile_id": pid, "user_id": uid}
                for pid, uid in zip(profile_ids, user_ids or [], strict=False)
            ]
            or profile_ids
        )
        """Push one enrollment list to the realtime provider for the game."""
        if game_key != "aoe2":
            return 0, False
        uri = os.environ.get("EXT_AOE2LOBBY_URI", "")
        if not uri:
            self._last_ids = None
            return len(profile_ids), False
        try:
            from kingdoms.core.rpc.game_client import GameProviderClient

            if self._client is None:
                self._client = GameProviderClient(uri, "ext-aoe2lobby", "aoe2")
            applied = await self._client.update_subscriptions(profile_ids)
            if applied:
                self._last_ids = list(profile_ids)
            return len(profile_ids), applied
        except Exception:
            logger.warning("enrollment push to the realtime provider failed", exc_info=True)
            return len(profile_ids), False


async def _aggregate_provider_stats() -> list[dict[str, Any]]:
    """Fetch the game service's providers' stats on demand.

    The game service OWNS its providers (owner direction 2026-11-05):
    the bot never interrogates them. When the panel asks, this process
    fetches each provider's own call statistics over the Status
    contract and merges its own stream-consumption stats — one answer,
    every provider.
    """
    from kingdoms.core.rpc.status import fetch_upstream_stats

    providers = [
        ("ext-librematch", os.environ.get("EXT_LIBREMATCH_URI", "")),
        ("ext-aoe2lobby", os.environ.get("EXT_AOE2LOBBY_URI", "")),
        ("ext-aoe2techtree", os.environ.get("EXT_AOE2TECHTREE_URI", "")),
        ("ext-liquipedia", os.environ.get("EXT_LIQUIPEDIA_URI", "")),
    ]
    entries: list[dict[str, Any]] = []
    for provider_id, uri in providers:
        if not uri:
            entries.append(
                {"provider_id": provider_id, "upstream": provider_id,
                 "never_called": True, "detail": "not deployed"}
            )
            continue
        try:
            stats = await fetch_upstream_stats(uri, timeout_s=5.0)
        except Exception as exc:
            entries.append(
                {"provider_id": provider_id, "upstream": provider_id,
                 "never_called": True, "detail": f"unreachable: {type(exc).__name__}"}
            )
            continue
        if not stats:
            entries.append(
                {"provider_id": provider_id, "upstream": provider_id,
                 "never_called": True, "detail": "no calls yet"}
            )
            continue
        for entry in stats:
            entry["provider_id"] = provider_id
        entries.extend(stats)
    return entries


async def _consume_providers(aggregator: Any) -> None:
    """Fold every configured provider's event stream into the aggregator."""
    providers = [
        ("ext-aoe2lobby", os.environ.get("EXT_AOE2LOBBY_URI", "")),
        ("ext-librematch", os.environ.get("EXT_LIBREMATCH_URI", "")),
    ]
    tasks = [
        _consume_one(aggregator, provider_id, uri)
        for provider_id, uri in providers
        if uri
    ]
    if not tasks:
        aggregator.mark_degraded()
        return
    await asyncio.gather(*tasks)


async def _consume_one(aggregator: Any, provider_id: str, uri: str) -> None:
    """Consume one provider stream forever, degrading on silence."""
    from kingdoms.core.rpc.game_client import GameProviderClient

    client = GameProviderClient(uri, provider_id, "aoe2")
    health = asyncio.ensure_future(_watch_provider_health(aggregator, client))
    stats = STATS.register(f"provider:{provider_id}")
    try:
        while True:
            established = False
            try:
                async for event in client.stream_match_events(since=0):
                    if not established:
                        # RECORD AT ESTABLISHMENT: a long-lived session
                        # must count as a live call the moment it exists,
                        # not when it eventually closes.
                        stats.record(True, 0)
                        established = True
                    await aggregator.apply_event(event)
            except Exception as exc:
                stats.record(False, 0, f"{type(exc).__name__}: {exc}")
                logger.warning("provider %s stream lost; retrying in 5s", provider_id)
                await asyncio.sleep(5)
            await asyncio.sleep(1)
    finally:
        health.cancel()


async def _watch_provider_health(aggregator: Any, client: Any) -> None:
    """Ping one provider periodically; a reply clears the degraded flag."""
    interval_s = float(os.environ.get("PROVIDER_HEALTH_INTERVAL_S", "30"))
    while True:
        try:
            await client.get_capabilities()
            aggregator.mark_healthy()
        except Exception:
            aggregator.mark_degraded()
        await asyncio.sleep(interval_s)

if __name__ == "__main__":
    main()
