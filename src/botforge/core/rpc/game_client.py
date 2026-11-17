"""Game provider RPC seam — client side (botforge.v1.Game).

svc-core consumes game providers through these typed helpers. Every call
degrades cleanly: an unreachable provider declares zero capabilities and
the core keeps running on the manual path; an explicitly unsupported
capability surfaces as ``UnsupportedCapabilityError`` for the caller to catch.
"""

from __future__ import annotations

from typing import Any

import grpc

from botforge.core.models.game import (
    AccountEloStatus,
    GameMap,
    MatchDetails,
    MatchHistoryEntry,
    MatchResult,
    PlayerStats,
    ProviderCapabilities,
    UserEloStats,
)
from botforge.core.rpc.client import build_channel, call_with_retry
from botforge.core.rpc.game import (
    account_stats_from_wire,
    game_map_from_wire,
    match_details_from_wire,
    match_event_from_wire,
    match_history_from_wire,
    player_stats_from_wire,
    user_stats_from_wire,
)
from botforge.rpc_generated.botforge.v1 import game_pb2, game_pb2_grpc

_RETRYABLE_CODES: tuple[grpc.StatusCode, ...] = (
    grpc.StatusCode.UNAVAILABLE,
    grpc.StatusCode.DEADLINE_EXCEEDED,
)


class UnsupportedCapabilityError(RuntimeError):
    """The provider does not support this capability (clean degradation)."""


class GameProviderClient:
    """Typed client for a botforge.v1.Game provider process."""

    def __init__(self, provider_uri: str, provider_id: str, game_key: str) -> None:
        self._provider_uri = provider_uri
        self._provider_id = provider_id
        self._game_key = game_key

    @property
    def provider_id(self) -> str:
        """Provider identity used in logs and audit trails."""
        return self._provider_id

    async def get_capabilities(self) -> ProviderCapabilities:
        """Fetch the provider's declared capabilities, degrading to zero."""
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            try:
                reply = await call_with_retry(
                    stub.GetCapabilities,
                    game_pb2.CapabilitiesRequest(),
                )
            except grpc.aio.AioRpcError as exc:
                if exc.code() == grpc.StatusCode.UNIMPLEMENTED:
                    raise UnsupportedCapabilityError(self._provider_id) from exc
                # An unreachable provider declares nothing: the core keeps
                # running on the degraded (manual) path.
                return ProviderCapabilities.none(self._provider_id, self._game_key)
        return ProviderCapabilities(
            provider_id=reply.provider_id,
            game_key=reply.game_key,
            realtime=reply.realtime,
            reliable_results=reply.reliable_results,
            check_map=reply.check_map,
            player_stats=reply.player_stats,
        )

    async def get_match_details(self, match_ref: str) -> MatchDetails | None:
        """Fetch a match's slotinfo and raw options, degrading to None.

        A provider that cannot serve match details (unsupported or
        unknown match) yields None: callers fall back to what the match
        already knows instead of failing the workflow.
        """
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            try:
                reply = await call_with_retry(
                    stub.GetMatchDetails,
                    game_pb2.GetMatchDetailsRequest(match_ref=match_ref),
                )
            except grpc.aio.AioRpcError as exc:
                if exc.code() in (
                    grpc.StatusCode.UNIMPLEMENTED,
                    grpc.StatusCode.NOT_FOUND,
                ):
                    return None
                raise
        return match_details_from_wire(reply)

    async def list_maps(self) -> list[GameMap]:
        """Fetch the provider's map catalog, degrading to an empty list."""
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            try:
                reply = await call_with_retry(
                    stub.ListMaps,
                    game_pb2.ListMapsRequest(),
                )
            except grpc.aio.AioRpcError as exc:
                if exc.code() == grpc.StatusCode.UNIMPLEMENTED:
                    return []
                raise
        return [game_map_from_wire(m) for m in reply.maps]

    async def get_player_stats(self, profile_id: str) -> PlayerStats | None:
        """Fetch a profile's stats blocks, degrading to None (no stats)."""
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            try:
                reply = await call_with_retry(
                    stub.GetPlayerStats,
                    game_pb2.GetPlayerStatsRequest(profile_id=profile_id),
                )
            except grpc.aio.AioRpcError as exc:
                if exc.code() in (
                    grpc.StatusCode.UNIMPLEMENTED,
                    grpc.StatusCode.NOT_FOUND,
                ):
                    return None
                raise
        stats = player_stats_from_wire(reply)
        return PlayerStats(profile_id=profile_id, blocks=stats.blocks)

    async def get_match_result(
        self, profile_ids: list[str], started_after: int
    ) -> MatchResult | None:
        """Fetch a finished match's outcome, degrading to None.

        The correlation rides the profile ids and the time window;
        None while the upstream has not recorded the match yet — the
        caller retries with a backoff.
        """
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            try:
                reply = await call_with_retry(
                    stub.GetMatchResult,
                    game_pb2.GetMatchResultRequest(
                        profile_ids=profile_ids, started_after=started_after
                    ),
                )
            except grpc.aio.AioRpcError as exc:
                if exc.code() in (
                    grpc.StatusCode.UNIMPLEMENTED,
                    grpc.StatusCode.NOT_FOUND,
                ):
                    return None
                raise
        if not reply.found:
            return None
        return MatchResult(
            match_ref="",
            winner_profile_id=reply.winner_profile_id,
            loser_profile_ids=tuple(reply.loser_profile_ids),
            map_name=reply.map_name,
            duration_ms=reply.duration_ms,
            ended_at=reply.ended_at,
            factions=dict(reply.factions),
            found=True,
            ratings={
                pid: (reply.old_rating.get(pid, 0), reply.new_rating.get(pid, 0))
                for pid in set(reply.old_rating) | set(reply.new_rating)
            },
            teams={pid: int(reply.teams.get(pid, 0)) for pid in reply.teams},
        )

    async def update_subscriptions(
        self, profile_ids: list[str], user_ids: list[str] | None = None
    ) -> bool:
        """Push the subscribed profile ids (+ owners), degrading to False.

        The provider reconciles its upstream subscriptions in place;
        ``user_ids`` (parallel to profile_ids) carry the platform owner
        of each profile so the stats store keeps the profile -> user
        mapping (#404). False means the push was not applied (provider
        offline or without the capability) and the caller should retry
        later — the provider re-syncs the full list on its next
        reconnect.
        """
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            try:
                reply = await call_with_retry(
                    stub.UpdateSubscriptions,
                    game_pb2.UpdateSubscriptionsRequest(
                        profile_ids=profile_ids,
                        user_ids=user_ids or [],
                    ),
                )
            except grpc.aio.AioRpcError as exc:
                if exc.code() in (
                    grpc.StatusCode.UNIMPLEMENTED,
                    grpc.StatusCode.UNAVAILABLE,
                ):
                    return False
                raise
        return bool(reply.applied)

    def stream_match_events(self, since: int):
        """Stream live match events from the provider, degrading to silence.

        The generator yields MatchEvent models as they arrive; on a
        lost stream it yields nothing and returns — the caller (the
        live aggregator loop) retries with backoff.
        """
        return self._stream_match_events(since)

    async def _stream_match_events(self, since: int):
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            try:
                call = stub.StreamMatchEvents(
                    game_pb2.StreamMatchEventsRequest(since=since),
                )
                async for wire in call:
                    yield match_event_from_wire(wire)
            except grpc.aio.AioRpcError as exc:
                if exc.code() in (
                    grpc.StatusCode.UNIMPLEMENTED,
                    grpc.StatusCode.UNAVAILABLE,
                ):
                    return
                raise

    async def sync_stats(self, profile_ids: list[str], wait: bool = False) -> tuple[bool, int, str]:
        """Trigger the provider's history sync (on-demand, #404 T4).

        Degrades to (False, 0, error) — an unreachable provider never
        fails the caller; the periodic sync catches up later.
        """
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            try:
                reply = await call_with_retry(
                    stub.SyncStats,
                    game_pb2.SyncStatsRequest(profile_ids=profile_ids, wait=wait),
                )
            except grpc.aio.AioRpcError as exc:
                if exc.code() in (
                    grpc.StatusCode.UNIMPLEMENTED,
                    grpc.StatusCode.UNAVAILABLE,
                ):
                    return False, 0, f"provider unreachable: {exc.code()}"
                raise
        return bool(reply.ok), int(reply.synced), reply.error

    async def get_match_history(
        self,
        profile_ids: list[str],
        limit: int = 0,
        since_s: int = 0,
        leaderboard_id: str = "",
    ) -> list[MatchHistoryEntry]:
        """Fetch the stored match history of the accounts (#404 T1)."""
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            try:
                reply = await call_with_retry(
                    stub.GetMatchHistory,
                    game_pb2.MatchHistoryRequest(
                        profile_ids=profile_ids,
                        limit=limit,
                        since_s=since_s,
                        leaderboard_id=leaderboard_id,
                    ),
                )
            except grpc.aio.AioRpcError as exc:
                if exc.code() in (
                    grpc.StatusCode.UNIMPLEMENTED,
                    grpc.StatusCode.UNAVAILABLE,
                ):
                    return []
                raise
        return [match_history_from_wire(e) for e in reply.matches]

    async def get_account_stats(self, profile_ids: list[str]) -> list[AccountEloStatus]:
        """Fetch the per-account elo status (current + max, #404 T1)."""
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            try:
                reply = await call_with_retry(
                    stub.GetAccountStats,
                    game_pb2.AccountStatsRequest(profile_ids=profile_ids),
                )
            except grpc.aio.AioRpcError as exc:
                if exc.code() in (
                    grpc.StatusCode.UNIMPLEMENTED,
                    grpc.StatusCode.UNAVAILABLE,
                ):
                    return []
                raise
        return [account_stats_from_wire(a) for a in reply.accounts]

    async def get_user_stats(self, user_id: str, window_days: int = 0) -> UserEloStats | None:
        """Fetch the per-user unified stats view (#404 T1).

        Degrades to None — an unreachable provider reads as "unknown
        stats", never as a failure of the caller (the enrollment's
        manual-review fallback).
        """
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            try:
                reply = await call_with_retry(
                    stub.GetUserStats,
                    game_pb2.UserStatsRequest(user_id=user_id, window_days=window_days),
                )
            except grpc.aio.AioRpcError as exc:
                if exc.code() in (
                    grpc.StatusCode.UNIMPLEMENTED,
                    grpc.StatusCode.UNAVAILABLE,
                ):
                    return None
                raise
        stats = user_stats_from_wire(reply.stats)
        return stats if stats.known else None

    # ---- The stats layer, wire-shaped helpers (#404) ---------------------
    # The GameData proxy caches and forwards the provider's own wire
    # messages (rule 4: one shape, no copy) — these helpers return the
    # wire replies directly.

    async def get_match_history_wire(self, request: Any) -> Any:
        """Fetch the stored match history as the wire reply."""
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            return await call_with_retry(stub.GetMatchHistory, request)

    async def get_account_stats_wire(self, request: Any) -> Any:
        """Fetch the per-account status as the wire reply."""
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            return await call_with_retry(stub.GetAccountStats, request)

    async def get_user_stats_wire(self, request: Any) -> Any:
        """Fetch the per-user unified stats as the wire reply."""
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            return await call_with_retry(stub.GetUserStats, request)

    async def get_live_matches(self, limit: int = 0) -> list[dict[str, Any]]:
        """Fetch the live matches the provider sees (#404 T3).

        Degrades to an empty list — an unreachable provider reads as
        "nothing live right now".
        """
        async with build_channel(self._provider_uri) as channel:
            stub = game_pb2_grpc.GameStub(channel)
            try:
                reply = await call_with_retry(
                    stub.GetLiveMatches,
                    game_pb2.LiveMatchesRequest(limit=limit),
                )
            except grpc.aio.AioRpcError as exc:
                if exc.code() in (
                    grpc.StatusCode.UNIMPLEMENTED,
                    grpc.StatusCode.UNAVAILABLE,
                ):
                    return []
                raise
        return [
            {
                "match_ref": m.match_ref,
                "status": m.status,
                "map_name": m.map_name,
                "format": m.format,
                "profile_ids": list(m.profile_ids),
                "players_json": m.players_json,
                "lobby_url": m.lobby_url,
                "spectate_url": m.spectate_url,
                "updated_at": m.updated_at,
                "metadata": dict(m.metadata),
            }
            for m in reply.matches
        ]
