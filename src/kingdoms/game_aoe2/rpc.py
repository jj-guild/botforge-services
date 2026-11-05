"""game-aoe2 RPC seam — the kingdoms.v1.GameData servicer.

Translates between the GameData contract and the aggregator's
snapshots/transitions. The match summaries ride the wire as the
``GameMatchSummary`` message (map, format, slots, host, players with
civs, aoe2lobby join/spectate URLs, aoe2de deep link).
"""

from __future__ import annotations

import logging
from typing import Any

import grpc

from kingdoms.core.rpc.game import (
    capabilities_to_wire,
    match_result_to_wire,
    player_stats_to_wire,
)
from kingdoms.rpc_generated.kingdoms.v1 import gamedata_pb2, gamedata_pb2_grpc

logger = logging.getLogger("kingdoms.game_aoe2")


def summary_to_wire(summary: dict[str, Any]) -> gamedata_pb2.GameMatchSummary:
    """Translate one match summary dict into the wire message.

    The summary's ``players`` field rides as the compact
    ``Name(Civ),Name(Civ)`` string (the adapter's metadata shape); it is
    parsed into the structured slots here so the wire stays typed, and
    rejoined on the way back (round-trip stable).
    """
    return gamedata_pb2.GameMatchSummary(
        match_ref=str(summary.get("match_ref", "")),
        map_name=str(summary.get("map", "")),
        format=str(summary.get("format", "")),
        status=str(summary.get("status", "")),
        slots_taken=int(summary.get("slots_taken") or 0),
        slots_total=int(summary.get("slots_total") or 0),
        host_name=str(summary.get("host", "")),
        players=_parse_players(str(summary.get("players", ""))),
        lobby_url=str(summary.get("lobby_url", "")),
        spectate_url=str(summary.get("spectate_url", "")),
        deep_link=str(summary.get("deep_link", "")),
        match_type=str(summary.get("match_type", "")),
    )


def _parse_players(compact: str) -> list[gamedata_pb2.GamePlayerSlot]:
    """Parse the summary's players JSON into typed slots.

    The adapter ships the occupied slots as a JSON array
    (profile_id, name, civ, team) — the wire stays typed, the
    consumers (dashboard rendering, mod notifications) never re-parse
    display strings.
    """
    import json

    try:
        entries = json.loads(compact) if compact else []
    except (json.JSONDecodeError, TypeError):
        return []
    slots: list[gamedata_pb2.GamePlayerSlot] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        slots.append(
            gamedata_pb2.GamePlayerSlot(
                profile_id=str(entry.get("profile_id", "")),
                name=str(entry.get("name", "")),
                civilization=str(entry.get("civ", "")),
                team=int(entry.get("team", 0) or 0),
                filled=True,
                avatar_url=str(entry.get("avatar", "")),
                country=str(entry.get("country", "")),
            )
        )
    return slots


def player_state_to_wire(state: dict[str, Any]) -> gamedata_pb2.GamePlayerState:
    """Translate one player state dict into the wire message."""
    summary = state.get("match") or {}
    return gamedata_pb2.GamePlayerState(
        user_id=str(state.get("user_id", "")),
        profile_id=str(state.get("profile_id", "")),
        state=str(state.get("state", "offline")),
        match_ref=str(state.get("match_ref", "")),
        since=int(state.get("since", 0)),
        match=summary_to_wire(summary) if summary else None,
    )


def dashboard_to_wire(snapshot: dict[str, Any]) -> gamedata_pb2.GameDashboard:
    """Translate one aggregator snapshot into the wire message."""
    return gamedata_pb2.GameDashboard(
        players=[player_state_to_wire(p) for p in snapshot.get("players", [])],
        generated_at=int(snapshot.get("generated_at", 0)),
        degraded=bool(snapshot.get("degraded", False)),
    )


def event_to_wire(transition: dict[str, Any], game_key: str = "aoe2") -> gamedata_pb2.GamePlayerEvent:
    """Translate one normalized transition into the wire message."""
    return gamedata_pb2.GamePlayerEvent(
        game_key=game_key,
        profile_id=str(transition.get("profile_id", "")),
        user_id=str(transition.get("user_id", "")),
        old_status=str(transition.get("old_status", "")),
        new_status=str(transition.get("new_status", "")),
        occurred_at=int(transition.get("occurred_at", 0)),
        match=summary_to_wire(transition.get("match") or {}) or None,
    )


def dashboard_from_wire(wire: gamedata_pb2.GameDashboard) -> dict[str, Any]:
    """Translate a wire dashboard back into the plain dict shape."""
    return {
        "players": [
            {
                "user_id": p.user_id,
                "profile_id": p.profile_id,
                "state": p.state,
                "match_ref": p.match_ref,
                "since": p.since,
                "match": summary_from_wire(p.match) if p.HasField("match") else {},
            }
            for p in wire.players
        ],
        "generated_at": wire.generated_at,
        "degraded": wire.degraded,
    }


def event_from_wire(wire: gamedata_pb2.GamePlayerEvent) -> dict[str, Any]:
    """Translate a wire player event back into the plain dict shape."""
    return {
        "game_key": wire.game_key,
        "profile_id": wire.profile_id,
        "user_id": wire.user_id,
        "old_status": wire.old_status,
        "new_status": wire.new_status,
        "occurred_at": wire.occurred_at,
        "match": summary_from_wire(wire.match) if wire.HasField("match") else {},
    }


def summary_from_wire(wire: gamedata_pb2.GameMatchSummary) -> dict[str, Any]:
    """Translate a wire match summary back into the plain dict shape."""
    return {
        "match_ref": wire.match_ref,
        "map": wire.map_name,
        "format": wire.format,
        "status": wire.status,
        "slots_taken": str(wire.slots_taken),
        "slots_total": str(wire.slots_total),
        "host": wire.host_name,
        "players": [
            {
                "profile_id": p.profile_id,
                "name": p.name,
                "civ": p.civilization,
                "avatar": p.avatar_url,
                "country": p.country,
                "team": p.team,
            }
            for p in wire.players
        ],
        "match_type": wire.match_type,
        "lobby_url": wire.lobby_url,
        "spectate_url": wire.spectate_url,
        "deep_link": wire.deep_link,
    }


class GameDataServicer(gamedata_pb2_grpc.GameDataServicer):
    """Serve the kingdoms.v1.GameData contract from the aggregator."""

    def __init__(
        self,
        aggregator: Any,
        poll_interval_s: float = 2.0,
        enrollments: Any = None,
        stats_provider: Any = None,
    ) -> None:
        """Wire the aggregator, the poll interval, the enrollments and the stats proxy."""
        self._aggregator = aggregator
        self._poll_interval_s = poll_interval_s
        self._enrollments = enrollments
        self._stats_provider = stats_provider

    async def GetCoverage(
        self,
        request: gamedata_pb2.CoverageRequest,
        context: grpc.aio.ServicerContext,
    ) -> gamedata_pb2.GameCoverage:
        """Serve the games this process covers and its health."""
        return gamedata_pb2.GameCoverage(
            game_keys=["aoe2"],
            realtime=True,
            degraded=self._aggregator.snapshot()["degraded"],
        )

    async def WatchDashboard(
        self,
        request: gamedata_pb2.WatchGameDataRequest,
        context: grpc.aio.ServicerContext,
    ) -> Any:
        """Stream snapshots: one immediately, then one per effective change.

        The aggregator folds the provider (aoe2lobby) events in the
        background consumer; this stream polls its snapshot, emitting
        only when the payload changed so the channel never spams.
        """
        import asyncio

        last: Any = None
        while True:
            snapshot = self._aggregator.snapshot()
            if last is None or snapshot["players"] != last:
                last = snapshot["players"]
                yield dashboard_to_wire(snapshot)
            await asyncio.sleep(self._poll_interval_s)

    async def WatchPlayerEvents(
        self,
        request: gamedata_pb2.WatchGameDataRequest,
        context: grpc.aio.ServicerContext,
    ) -> Any:
        """Stream the player transitions to every subscriber (fan-out).

        The service subscribes to its provider (aoe2lobby) in its
        background consumer, maintains the coherent player state (the
        aggregator) and serves its subscribers — a mod, the bot: each
        stream owns its queue, one consumer never starves another.
        """
        queue = self._aggregator.subscribe()
        try:
            while True:
                transition = await queue.get()
                if request.game_key and transition.get("game_key") != request.game_key:
                    continue
                if request.since and int(transition.get("occurred_at", 0)) < request.since:
                    continue
                match = transition.get("match") or {}
                yield gamedata_pb2.GamePlayerEvent(
                    game_key=str(transition.get("game_key", "")),
                    profile_id=str(transition.get("profile_id", "")),
                    user_id=str(transition.get("user_id", "")),
                    old_status=str(transition.get("old_status", "")),
                    new_status=str(transition.get("new_status", "")),
                    occurred_at=int(transition.get("occurred_at", 0)),
                    match=summary_to_wire(match) if match else None,
                )
        finally:
            self._aggregator.unsubscribe(queue)

    async def SyncContent(
        self,
        request: gamedata_pb2.SyncContentRequest,
        context: grpc.aio.ServicerContext,
    ) -> gamedata_pb2.SyncContentReply:
        """Run the content sync against the game's providers, in here.

        The civs sync rides the aoe2techtree content provider, the maps
        enrichment rides the liquipedia provider — the game service owns
        both (the bot never touches a provider, it asks this service).
        A provider failure comes back as a FUNCTIONAL error the UI shows
        as-is; it never crashes the servicer.
        """
        from kingdoms.game_aoe2.content_refresh import (
            refresh_aoe2_content,
            refresh_aoe2_maps,
        )

        try:
            if request.what == "factions":
                result = await refresh_aoe2_content()
            elif request.what == "maps":
                result = await refresh_aoe2_maps()
            else:
                await context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    f"unknown sync target: {request.what!r}",
                )
                raise AssertionError  # abort never returns
        except Exception as exc:  # a functional error, not a crash
            logger.warning("SyncContent(%s) failed: %s", request.what, exc)
            return gamedata_pb2.SyncContentReply(
                ok=False,
                error=f"{type(exc).__name__}: {exc}"[:400],
            )
        counts = {
            key: int(value)
            for key, value in result.items()
            if isinstance(value, int)
        }
        raw_new = result.get("new_factions", ())
        new_factions = (
            [str(name) for name in raw_new if isinstance(name, str)]
            if isinstance(raw_new, (list, tuple))
            else []
        )
        return gamedata_pb2.SyncContentReply(
            ok=True,
            counts=counts,
            new_factions=new_factions,
        )

    async def GetProfileStats(
        self,
        request: Any,
        context: grpc.aio.ServicerContext,
    ) -> Any:
        """Proxy the profile stats through the game's stats provider.

        The bot and the mods ask the GAME SERVICE (rule 4); the service
        asks its provider — the caller never sees the provider.
        """
        if self._stats_provider is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "stats provider not wired")
            raise AssertionError
        stats = await self._stats_provider.get_player_stats(request.profile_id)
        if stats is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "no stats for this profile")
            raise AssertionError
        return player_stats_to_wire(stats)

    async def GetMatchResult(
        self,
        request: Any,
        context: grpc.aio.ServicerContext,
    ) -> Any:
        """Proxy a finished match's outcome (the activity feed's cards)."""
        if self._stats_provider is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "stats provider not wired")
            raise AssertionError
        result = await self._stats_provider.get_match_result(
            list(request.profile_ids), int(request.started_after)
        )
        if result is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "no result yet")
            raise AssertionError
        return match_result_to_wire(result)

    async def GetProviderCapabilities(
        self,
        request: Any,
        context: grpc.aio.ServicerContext,
    ) -> Any:
        """Proxy the stats provider's declared capabilities."""
        if self._stats_provider is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "stats provider not wired")
            raise AssertionError
        caps = await self._stats_provider.get_capabilities()
        return capabilities_to_wire(caps)

    async def UpdateEnrollments(
        self,
        request: gamedata_pb2.UpdateEnrollmentsRequest,
        context: grpc.aio.ServicerContext,
    ) -> gamedata_pb2.UpdateEnrollmentsResponse:
        """Forward the platform's enrollments to the realtime provider."""
        if self._enrollments is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "enrollments not wired")
        subscribed, applied = await self._enrollments.apply(
            request.game_key, list(request.profile_ids), list(request.user_ids)
        )
        return gamedata_pb2.UpdateEnrollmentsResponse(subscribed=subscribed, applied=applied)


def add_gamedata_servicer(server: grpc.aio.Server, servicer: GameDataServicer) -> None:
    """Bind the GameData servicer onto the server."""
    gamedata_pb2_grpc.add_GameDataServicer_to_server(servicer, server)
