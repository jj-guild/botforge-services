"""game-aoe2 client (bot side): the kingdoms.v1.GameData consumer.

Same shape as the LiveClient seam (``watch`` + ``stream_snapshots`` +
``stream_player_events``) so the bot wiring picks whichever process is
configured: the enriched GameData feed when ``GAME_AOE2_URI`` is set,
the plain Live feed otherwise. The GameData feed carries the full
match summaries (map, format, civs, aoe2lobby links, aoe2de deep
link) through ``GamePlayerState.match``.
"""

from __future__ import annotations

from typing import Any

from kingdoms.game_aoe2.rpc import dashboard_from_wire, event_from_wire


class GameDataClient:
    """Typed client for the kingdoms.v1.GameData service (bot side)."""

    def __init__(self, uri: str) -> None:
        """Keep the service address; channels are per-call (ADR-0020)."""
        self._uri = uri

    async def sync_content(
        self, game_key: str, what: str, timeout_s: float = 900.0
    ) -> dict[str, Any]:
        """Ask the game service to run a content sync (civs, maps).

        The service runs it against ITS providers — the caller never
        touches one. The reply carries the counts or a FUNCTIONAL error
        the UI shows as-is. The timeout is long BY DESIGN: the maps
        enrichment rides the Liquipedia pacing (minutes).
        """
        from kingdoms.core.rpc.client import build_channel
        from kingdoms.rpc_generated.kingdoms.v1 import gamedata_pb2, gamedata_pb2_grpc

        async with build_channel(self._uri) as channel:
            stub = gamedata_pb2_grpc.GameDataStub(channel)
            reply = await stub.SyncContent(
                gamedata_pb2.SyncContentRequest(game_key=game_key, what=what),
                timeout=timeout_s,
            )
        return {
            "ok": reply.ok,
            "error": reply.error,
            "counts": dict(reply.counts),
            "new_factions": list(reply.new_factions),
        }

    async def watch(self, game_key: str, timeout_s: float = 5.0) -> dict[str, Any]:
        """Fetch the current dashboard snapshot (first stream frame)."""
        from kingdoms.core.rpc.client import build_channel
        from kingdoms.rpc_generated.kingdoms.v1 import gamedata_pb2, gamedata_pb2_grpc

        async with build_channel(self._uri) as channel:
            stub = gamedata_pb2_grpc.GameDataStub(channel)
            call = stub.WatchDashboard(
                gamedata_pb2.WatchGameDataRequest(game_key=game_key),
                timeout=timeout_s,
            )
            async for frame in call:
                return dashboard_from_wire(frame)
        return {"players": [], "generated_at": 0, "degraded": True}

    async def stream_snapshots(self, game_key: str):
        """Yield dashboard snapshots continuously: one per effective change."""
        from kingdoms.core.rpc.client import build_channel
        from kingdoms.rpc_generated.kingdoms.v1 import gamedata_pb2, gamedata_pb2_grpc

        async with build_channel(self._uri) as channel:
            stub = gamedata_pb2_grpc.GameDataStub(channel)
            call = stub.WatchDashboard(
                gamedata_pb2.WatchGameDataRequest(game_key=game_key)
            )
            async for frame in call:
                yield dashboard_from_wire(frame)

    async def stream_player_events(self, game_key: str = ""):
        """Yield normalized player transitions continuously, forever."""
        import asyncio

        import grpc

        from kingdoms.core.rpc.client import build_channel
        from kingdoms.rpc_generated.kingdoms.v1 import gamedata_pb2, gamedata_pb2_grpc

        while True:
            try:
                async with build_channel(self._uri) as channel:
                    stub = gamedata_pb2_grpc.GameDataStub(channel)
                    call = stub.WatchPlayerEvents(
                        gamedata_pb2.WatchGameDataRequest(game_key=game_key)
                    )
                    async for wire in call:
                        yield event_from_wire(wire)
            except grpc.aio.AioRpcError:
                await asyncio.sleep(5)
