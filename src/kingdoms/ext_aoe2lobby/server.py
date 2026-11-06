"""ext-aoe2lobby process entrypoint (kingdoms.v1.Game live provider)."""

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
                logging.getLogger("kingdoms.ext_aoe2lobby.stream").warning(
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
    from kingdoms.core.models.game import MatchEvent
    from kingdoms.core_process.ext_server import serve_game_provider
    from kingdoms.ext_aoe2lobby import DECLARED_CAPABILITIES, PROVIDER_ID
    from kingdoms.ext_aoe2lobby.adapter import Aoe2LobbyAdapter

    adapter = Aoe2LobbyAdapter(
        ws_url=os.environ.get("AOE2LOBBY_WS_URL", "") or "wss://data.aoe2lobby.com/ws/",
        refresh_s=float(os.environ.get("AOE2LOBBY_REFRESH_S", "5")),
    )

    hub = _StreamHub(adapter)

    async def match_events() -> AsyncIterator[MatchEvent]:
        """Yield the current world, then the live transitions.

        The handshake first: a fresh consumer receives the CURRENT
        state (every enrolled profile's live lobby/game), then the
        live transitions from its OWN broadcast queue — the boot task
        owns the single WS stream, the consumers never carry its life.
        """
        for frame in adapter.current_state_events():
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
                yield MatchEvent(
                    match_ref=frame["match_ref"],
                    type=frame["type"],
                    occurred_at=frame["occurred_at"],
                    profile_ids=tuple(frame["profile_ids"]),
                    metadata=tuple(sorted(frame["metadata"].items())),
                )
        finally:
            hub.unsubscribe(queue)

    async def update_subscriptions(profile_ids: list[str]) -> bool:
        """Reconcile the upstream players subscription in place (one session)."""
        return await adapter.set_subscribed_profiles(profile_ids)

    async def _boot() -> None:
        asyncio.get_running_loop().create_task(hub.run_forever())
        await serve_game_provider(
            DECLARED_CAPABILITIES,
            PROVIDER_ID,
            match_events=match_events,
            update_subscriptions=update_subscriptions,
        )

    asyncio.run(_boot())


if __name__ == "__main__":
    main()
