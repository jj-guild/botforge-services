"""ext-aoe2lobby process entrypoint (botforge.v1.Game live provider)."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from typing import Any


class _StreamHub:
    """The boot-owned WS stream + the per-consumer broadcast queues.

    The stream runs from the BOOT (the owner's spec): the state is
    maintained permanently by the subscriptions, INDEPENDENTLY of the
    consumers. The old shape carried the stream's life inside
    match_events — one consumer's ended generator silenced the whole
    provider (the 'my lobby never shows' saga).
    """

    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter
        self._subscribers: list[Any] = []

    async def run_forever(self) -> None:
        """Consume THE ws stream forever, fanning out to every queue."""
        while True:
            try:
                async for frame in self._adapter.stream_events():
                    for queue in list(self._subscribers):
                        queue.put_nowait(frame)
            except Exception:
                logging.getLogger("botforge.ext_aoe2lobby.stream").warning(
                    "the ws stream task ended — restarting", exc_info=True
                )
                await asyncio.sleep(5)

    def subscribe(self) -> Any:
        """Register one consumer's queue (removed on its end)."""
        queue: Any = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: Any) -> None:
        """Remove a consumer's queue so it stops receiving events."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)


def main() -> None:
    """Run the ext-aoe2lobby gRPC provider server."""
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    from botforge.core_process.ext_server import serve_game_provider
    from botforge.ext_aoe2lobby import DECLARED_CAPABILITIES, PROVIDER_ID
    from botforge.ext_aoe2lobby.adapter import Aoe2LobbyAdapter
    from botforge.ext_aoe2lobby.store import STATUS_GAME, STATUS_LOBBY, LobbyStore

    adapter = Aoe2LobbyAdapter(
        ws_url=os.environ.get("AOE2LOBBY_WS_URL", "") or "wss://data.aoe2lobby.com/ws/",
        refresh_s=float(os.environ.get("AOE2LOBBY_REFRESH_S", "5")),
    )

    hub = _StreamHub(adapter)

    # The live store (#404 T3): the provider's OWN database — every
    # interesting match (with at least one known player) is stored as
    # the frames arrive, raw first. No MONGO_URI means no live store:
    # the GetLiveMatches RPC answers UNIMPLEMENTED and the core keeps
    # the in-memory stream it always had.
    store = None
    if os.environ.get("MONGO_URI", ""):
        from botforge.core.models.db import get_async_database

        store = LobbyStore(get_async_database())

    async def _persist(frame: dict[str, Any]) -> None:
        """Store one frame (raw + projection); failures never crash."""
        if store is None:
            return
        try:
            await store.apply_event(frame)
        except Exception:
            logging.getLogger("botforge.ext_aoe2lobby.store").warning(
                "live frame store failed", exc_info=True
            )

    match_events = _match_events(adapter, hub, _persist)

    async def live_matches(limit: int) -> list[dict[str, Any]]:
        """Serve the stored live state (lobby + in-game matches)."""
        if store is None:
            return []
        return await store.list_matches([STATUS_LOBBY, STATUS_GAME], limit)

    async def update_subscriptions(profile_ids: list[str], user_ids: list[str]) -> bool:
        """Reconcile the upstream players subscription in place (one session).

        ``user_ids`` (parallel to profile_ids) ride the wire so the
        stats store can keep the profile -> user mapping; the lobby
        provider itself only subscribes the profile ids.
        """
        del user_ids
        return await adapter.set_subscribed_profiles(profile_ids)

    async def _boot() -> None:
        asyncio.get_running_loop().create_task(hub.run_forever())
        await serve_game_provider(
            DECLARED_CAPABILITIES,
            PROVIDER_ID,
            match_events=match_events,
            update_subscriptions=update_subscriptions,
            live_matches=live_matches,
        )

    asyncio.run(_boot())


def _match_events(
    adapter: Any,
    hub: _StreamHub,
    persist: Any,
) -> Any:
    """Build the events generator: the current world, then the live feed.

    The handshake first: a fresh consumer receives the CURRENT state
    (every enrolled profile's live lobby/game), then the live
    transitions from its OWN broadcast queue — the boot task owns the
    single WS stream, the consumers never carry its life.

    Every frame rides the live store (#404 T3) on its way through: the
    raw frames are kept, the match documents fold the current state —
    the GetLiveMatches RPC answers from the store.
    """
    from botforge.core.models.game import MatchEvent

    async def generator() -> AsyncIterator[MatchEvent]:
        """Yield the stored-then-live frames as MatchEvent models."""
        for frame in adapter.current_state_events():
            await persist(frame)
            yield MatchEvent(
                match_ref=frame["match_ref"],
                type=frame["type"],
                occurred_at=frame["occurred_at"],
                profile_ids=tuple(frame["profile_ids"]),
                metadata=tuple(sorted(frame["metadata"].items())),
            )
        queue = hub.subscribe()
        try:
            while True:
                frame = await queue.get()
                await persist(frame)
                yield MatchEvent(
                    match_ref=frame["match_ref"],
                    type=frame["type"],
                    occurred_at=frame["occurred_at"],
                    profile_ids=tuple(frame["profile_ids"]),
                    metadata=tuple(sorted(frame["metadata"].items())),
                )
        finally:
            hub.unsubscribe(queue)

    return generator()


if __name__ == "__main__":
    main()
