"""Game provider RPC seam — server side (botforge.v1.Game).

A game provider process builds its gRPC
server from these servicers, backed by its own adapters to the external
APIs. The seam keeps provider code out of the core: it only translates
between the wire contract and plain core models.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import grpc

from botforge.core.models.game import (
    AccountEloStatus,
    GameMap,
    LeaderboardElo,
    MatchDetails,
    MatchEvent,
    MatchHistoryEntry,
    MatchResult,
    PlayerStats,
    ProviderCapabilities,
    Slot,
    StatsBlock,
    StatsEntry,
    UserEloStats,
)
from botforge.rpc_generated.botforge.v1 import game_pb2, game_pb2_grpc


def capabilities_to_wire(caps: ProviderCapabilities) -> game_pb2.Capabilities:
    """Translate a core capability declaration into the wire message."""
    return game_pb2.Capabilities(
        provider_id=caps.provider_id,
        game_key=caps.game_key,
        realtime=caps.realtime,
        reliable_results=caps.reliable_results,
        check_map=caps.check_map,
        player_stats=caps.player_stats,
    )


def capabilities_from_wire(wire: game_pb2.Capabilities) -> ProviderCapabilities:
    """Translate a wire capability message into the core model."""
    return ProviderCapabilities(
        provider_id=wire.provider_id,
        game_key=wire.game_key,
        realtime=wire.realtime,
        reliable_results=wire.reliable_results,
        check_map=wire.check_map,
        player_stats=wire.player_stats,
    )


def slot_to_wire(slot: Slot) -> game_pb2.Slot:
    """Translate a core slot model into the wire message."""
    return game_pb2.Slot(
        slot_index=slot.slot_index,
        profile_id=slot.profile_id,
        faction_key=slot.faction_key,
        team=slot.team,
        filled=slot.filled,
        slot_kind=slot.slot_kind,
    )


def slot_from_wire(wire: game_pb2.Slot) -> Slot:
    """Translate a wire slot message into the core model."""
    return Slot(
        slot_index=wire.slot_index,
        profile_id=wire.profile_id,
        faction_key=wire.faction_key,
        team=wire.team,
        filled=wire.filled,
        slot_kind=wire.slot_kind,
    )


def match_details_to_wire(details: MatchDetails) -> game_pb2.MatchDetails:
    """Translate a core match-details model into the wire message."""
    return game_pb2.MatchDetails(
        match_ref=details.match_ref,
        map_name=details.map_name,
        slots=[slot_to_wire(s) for s in details.slots],
        options=dict(details.options),
        started_at=details.started_at,
        match_kind=details.match_kind,
    )


def match_details_from_wire(wire: game_pb2.MatchDetails) -> MatchDetails:
    """Translate a wire match-details message into the core model."""
    return MatchDetails(
        match_ref=wire.match_ref,
        map_name=wire.map_name,
        slots=tuple(slot_from_wire(s) for s in wire.slots),
        options=tuple(sorted(wire.options.items())),
        started_at=wire.started_at,
        match_kind=wire.match_kind,
    )


def game_map_to_wire(game_map: GameMap) -> game_pb2.GameMap:
    """Translate a core game-map model into the wire message."""
    return game_pb2.GameMap(
        map_key=game_map.map_key,
        name=game_map.name,
        map_type=game_map.map_type,
        resource_url=game_map.resource_url,
    )


def game_map_from_wire(wire: game_pb2.GameMap) -> GameMap:
    """Translate a wire game-map message into the core model."""
    return GameMap(
        map_key=wire.map_key,
        name=wire.name,
        map_type=wire.map_type,
        resource_url=wire.resource_url,
    )


def match_event_to_wire(event: MatchEvent) -> game_pb2.MatchEvent:
    """Translate a core match-event model into the wire message."""
    return game_pb2.MatchEvent(
        match_ref=event.match_ref,
        type=event.type,
        occurred_at=event.occurred_at,
        profile_ids=list(event.profile_ids),
        metadata=dict(event.metadata),
    )


def match_event_from_wire(wire: game_pb2.MatchEvent) -> MatchEvent:
    """Translate a wire match-event message into the core model."""
    return MatchEvent(
        match_ref=wire.match_ref,
        type=wire.type,
        occurred_at=wire.occurred_at,
        profile_ids=tuple(wire.profile_ids),
        metadata=tuple(sorted(wire.metadata.items())),
    )


def match_result_to_wire(result: MatchResult) -> game_pb2.MatchResult:
    """Translate a finished match's outcome into the wire message."""
    return game_pb2.MatchResult(
        winner_profile_id=result.winner_profile_id,
        loser_profile_ids=list(result.loser_profile_ids),
        map_name=result.map_name,
        duration_ms=result.duration_ms,
        ended_at=result.ended_at,
        factions=dict(result.factions),
        found=result.found,
        teams=dict(result.teams),
        old_rating={pid: old for pid, (old, _new) in result.ratings.items()},
        new_rating={pid: new for pid, (_old, new) in result.ratings.items()},
    )


def match_result_from_wire(wire: game_pb2.MatchResult) -> MatchResult:
    """Translate a wire match-result message into the core model.

    The ratings ride the wire as two maps (old/new); the model carries
    the pairs. ``match_ref`` is the platform's own reference and never
    crosses the provider wire — it stays empty for the caller to fill.
    """
    return MatchResult(
        match_ref="",
        winner_profile_id=wire.winner_profile_id,
        loser_profile_ids=tuple(wire.loser_profile_ids),
        map_name=wire.map_name,
        duration_ms=wire.duration_ms,
        ended_at=wire.ended_at,
        factions=dict(wire.factions),
        found=wire.found,
        ratings={
            pid: (wire.old_rating[pid], wire.new_rating[pid])
            for pid in wire.old_rating
            if pid in wire.new_rating
        },
        teams=dict(wire.teams),
    )


def player_stats_to_wire(stats: PlayerStats) -> game_pb2.PlayerStats:
    """Translate a core player-stats model into the wire message."""
    return game_pb2.PlayerStats(
        blocks=[
            game_pb2.StatsBlock(
                name=block.name,
                entries=[game_pb2.StatsEntry(key=e.key, value=e.value) for e in block.entries],
            )
            for block in stats.blocks
        ]
    )


def player_stats_from_wire(wire: game_pb2.PlayerStats) -> PlayerStats:
    """Translate a wire player-stats message into the core model."""
    return PlayerStats(
        profile_id="",
        blocks=tuple(
            StatsBlock(
                name=block.name,
                entries=tuple(StatsEntry(key=e.key, value=e.value) for e in block.entries),
            )
            for block in wire.blocks
        ),
    )


def leaderboard_elo_to_wire(elo: LeaderboardElo) -> game_pb2.LeaderboardElo:
    """Translate a core leaderboard-elo model into the wire message."""
    return game_pb2.LeaderboardElo(
        leaderboard_id=elo.leaderboard_id,
        name=elo.name,
        current=elo.current,
        max=elo.max,
        rank=elo.rank,
        wins=elo.wins,
        losses=elo.losses,
    )


def leaderboard_elo_from_wire(wire: game_pb2.LeaderboardElo) -> LeaderboardElo:
    """Translate a wire leaderboard-elo message into the core model."""
    return LeaderboardElo(
        leaderboard_id=wire.leaderboard_id,
        name=wire.name,
        current=wire.current,
        max=wire.max,
        rank=wire.rank,
        wins=wire.wins,
        losses=wire.losses,
    )


def account_stats_to_wire(status: AccountEloStatus) -> game_pb2.AccountStats:
    """Translate a core account-status model into the wire message."""
    return game_pb2.AccountStats(
        profile_id=status.profile_id,
        leaderboards=[leaderboard_elo_to_wire(e) for e in status.leaderboards],
        last_synced_at=status.last_synced_at,
        known=status.known,
    )


def account_stats_from_wire(wire: game_pb2.AccountStats) -> AccountEloStatus:
    """Translate a wire account-status message into the core model."""
    return AccountEloStatus(
        profile_id=wire.profile_id,
        leaderboards=tuple(leaderboard_elo_from_wire(e) for e in wire.leaderboards),
        last_synced_at=wire.last_synced_at,
        known=wire.known,
    )


def user_stats_to_wire(stats: UserEloStats) -> game_pb2.UserStats:
    """Translate a core user-stats model into the wire message."""
    return game_pb2.UserStats(
        user_id=stats.user_id,
        profile_ids=list(stats.profile_ids),
        leaderboards=[leaderboard_elo_to_wire(e) for e in stats.leaderboards],
        matches_in_window=stats.matches_in_window,
        known=stats.known,
    )


def user_stats_from_wire(wire: game_pb2.UserStats) -> UserEloStats:
    """Translate a wire user-stats message into the core model."""
    return UserEloStats(
        user_id=wire.user_id,
        profile_ids=tuple(wire.profile_ids),
        leaderboards=tuple(leaderboard_elo_from_wire(e) for e in wire.leaderboards),
        matches_in_window=wire.matches_in_window,
        known=wire.known,
    )


def match_history_to_wire(entry: MatchHistoryEntry) -> game_pb2.MatchHistoryEntry:
    """Translate a core match-history model into the wire message."""
    return game_pb2.MatchHistoryEntry(
        match_id=entry.match_id,
        leaderboard_id=entry.leaderboard_id,
        started_at=entry.started_at,
        finished_at=entry.finished_at,
        map_name=entry.map_name,
        profile_ids=list(entry.profile_ids),
        rating_before=entry.rating_before,
        rating_after=entry.rating_after,
        teams=entry.teams,
        winners=list(entry.winners),
        description=entry.description,
        players_json=entry.players_json,
        options_json=entry.options_json,
        slots_json=entry.slots_json,
    )


def match_history_from_wire(wire: game_pb2.MatchHistoryEntry) -> MatchHistoryEntry:
    """Translate a wire match-history message into the core model."""
    return MatchHistoryEntry(
        match_id=wire.match_id,
        leaderboard_id=wire.leaderboard_id,
        started_at=wire.started_at,
        finished_at=wire.finished_at,
        map_name=wire.map_name,
        profile_ids=tuple(wire.profile_ids),
        rating_before=dict(wire.rating_before),
        rating_after=dict(wire.rating_after),
        teams=dict(wire.teams),
        winners=tuple(wire.winners),
        options_json=wire.options_json,
        description=wire.description,
        players_json=wire.players_json,
        slots_json=wire.slots_json,
    )


class GameServicer(game_pb2_grpc.GameServicer):
    """Serve the botforge.v1.Game contract from provider-backed callables.

    Providers register plain async callables; this servicer adapts them to
    gRPC. Providers that do not support a capability raise
    ``UnsupportedCapability`` in the backing callable, mapped to
    UNIMPLEMENTED on the wire so the core degrades cleanly.
    """

    def __init__(
        self,
        capabilities: Callable[[], ProviderCapabilities],
        match_details: Callable[[str], Awaitable[MatchDetails | None]] | None = None,
        list_maps: Callable[[], Awaitable[list[GameMap]]] | None = None,
        match_events: Callable[[], AsyncIterator[MatchEvent]] | None = None,
        player_stats: Callable[[str], Awaitable[PlayerStats | None]] | None = None,
        update_subscriptions: Callable[[list[str], list[str]], Awaitable[bool]] | None = None,
        match_result: Callable[[list[str], int], Awaitable[MatchResult | None]] | None = None,
        sync_stats: Callable[[list[str], bool], Awaitable[tuple[bool, int, str]]] | None = None,
        match_history: Callable[[list[str], int, int, str], Awaitable[list[MatchHistoryEntry]]] | None = None,
        account_stats: Callable[[list[str]], Awaitable[list[AccountEloStatus]]] | None = None,
        user_stats: Callable[[str, int], Awaitable[UserEloStats | None]] | None = None,
        live_matches: Callable[[int], Awaitable[list[dict[str, Any]]]] | None = None,
        search_profiles: Callable[[str], Awaitable[list[dict[str, str]]]] | None = None,
    ) -> None:
        self._capabilities = capabilities
        self._match_details = match_details
        self._list_maps = list_maps
        self._match_events = match_events
        self._player_stats = player_stats
        self._update_subscriptions = update_subscriptions
        self._match_result = match_result
        self._sync_stats = sync_stats
        self._match_history = match_history
        self._account_stats = account_stats
        self._user_stats = user_stats
        self._live_matches = live_matches
        self._search_profiles = search_profiles
    async def GetCapabilities(
        self,
        request: game_pb2.CapabilitiesRequest,
        context: grpc.aio.ServicerContext,
    ) -> game_pb2.Capabilities:
        """Serve the provider's declared capabilities as the wire message."""
        return capabilities_to_wire(self._capabilities())

    async def GetMatchDetails(
        self,
        request: game_pb2.GetMatchDetailsRequest,
        context: grpc.aio.ServicerContext,
    ) -> game_pb2.MatchDetails:
        """Serve a match's slotinfo and raw game options when known."""
        if self._match_details is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "match details not available")
        details = await self._match_details(request.match_ref)
        if details is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "unknown match_ref")
        return match_details_to_wire(details)

    async def ListMaps(
        self,
        request: game_pb2.ListMapsRequest,
        context: grpc.aio.ServicerContext,
    ) -> game_pb2.GameMaps:
        """Serve the provider's known map catalog for its game."""
        if self._list_maps is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "map catalog not available")
        maps = await self._list_maps()
        return game_pb2.GameMaps(maps=[game_map_to_wire(m) for m in maps])

    async def GetPlayerStats(
        self,
        request: game_pb2.GetPlayerStatsRequest,
        context: grpc.aio.ServicerContext,
    ) -> game_pb2.PlayerStats:
        """Serve a profile's named stats blocks when the provider has them."""
        if self._player_stats is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "player stats not available")
        stats = await self._player_stats(request.profile_id)
        if stats is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "unknown profile_id")
        return player_stats_to_wire(stats)

    async def GetMatchResult(
        self,
        request: game_pb2.GetMatchResultRequest,
        context: grpc.aio.ServicerContext,
    ) -> game_pb2.MatchResult:
        """Serve a finished match's outcome when the provider has it.

        The correlation rides the profile ids and the time window
        (the upstream's match id is not the platform's ref). The
        provider answers None while the upstream has not recorded
        the match yet — ``found=False`` on the wire, the caller
        retries with a backoff.
        """
        if self._match_result is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "match result not available")
        result = await self._match_result(list(request.profile_ids), int(request.started_after))
        if result is None:
            return game_pb2.MatchResult(found=False)
        return match_result_to_wire(result)

    async def UpdateSubscriptions(
        self,
        request: game_pb2.UpdateSubscriptionsRequest,
        context: grpc.aio.ServicerContext,
    ) -> game_pb2.UpdateSubscriptionsResponse:
        """Push the subscribed profile ids; the provider reconciles in place."""
        if self._update_subscriptions is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "subscriptions not available")
        user_ids = list(request.user_ids) if request.user_ids else [""] * len(request.profile_ids)
        applied = await self._update_subscriptions(list(request.profile_ids), user_ids)
        return game_pb2.UpdateSubscriptionsResponse(
            subscribed=len(request.profile_ids),
            applied=applied,
        )

    async def StreamMatchEvents(
        self,
        request: game_pb2.StreamMatchEventsRequest,
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[game_pb2.MatchEvent]:
        """Stream live match lifecycle events from the provider."""
        if self._match_events is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "live events not available")
        async for event in self._match_events():
            if event.occurred_at < request.since:
                continue
            yield match_event_to_wire(event)

    async def SyncStats(
        self,
        request: game_pb2.SyncStatsRequest,
        context: grpc.aio.ServicerContext,
    ) -> game_pb2.SyncStatsReply:
        """Trigger the provider's history sync (on-demand, #404 T4)."""
        if self._sync_stats is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "stats sync not available")
        ok, synced, error = await self._sync_stats(list(request.profile_ids), bool(request.wait))
        return game_pb2.SyncStatsReply(ok=ok, synced=synced, error=error)

    async def GetMatchHistory(
        self,
        request: game_pb2.MatchHistoryRequest,
        context: grpc.aio.ServicerContext,
    ) -> game_pb2.MatchHistoryReply:
        """Serve the stored match history of the known accounts (#404 T1)."""
        if self._match_history is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "match history not available")
        entries = await self._match_history(
            list(request.profile_ids), int(request.limit), int(request.since_s), request.leaderboard_id
        )
        return game_pb2.MatchHistoryReply(matches=[match_history_to_wire(e) for e in entries])

    async def GetAccountStats(
        self,
        request: game_pb2.AccountStatsRequest,
        context: grpc.aio.ServicerContext,
    ) -> game_pb2.AccountStatsReply:
        """Serve the per-account elo status (current + max, #404 T1)."""
        if self._account_stats is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "account stats not available")
        accounts = await self._account_stats(list(request.profile_ids))
        return game_pb2.AccountStatsReply(accounts=[account_stats_to_wire(a) for a in accounts])

    async def GetUserStats(
        self,
        request: game_pb2.UserStatsRequest,
        context: grpc.aio.ServicerContext,
    ) -> game_pb2.UserStatsReply:
        """Serve the per-user unified stats view (#404 T1)."""
        if self._user_stats is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "user stats not available")
        stats = await self._user_stats(request.user_id, int(request.window_days))
        if stats is None:
            return game_pb2.UserStatsReply(stats=game_pb2.UserStats(user_id=request.user_id))
        return game_pb2.UserStatsReply(stats=user_stats_to_wire(stats))

    async def GetLiveMatches(
        self,
        request: game_pb2.LiveMatchesRequest,
        context: grpc.aio.ServicerContext,
    ) -> game_pb2.LiveMatchesReply:
        """Serve the live matches the provider currently sees (#404 T3)."""
        if self._live_matches is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "live matches not available")
        matches = await self._live_matches(int(request.limit))
        return game_pb2.LiveMatchesReply(
            matches=[
                game_pb2.LiveMatch(
                    match_ref=str(m.get("match_ref", "")),
                    status=str(m.get("status", "")),
                    map_name=str(m.get("map_name", "")),
                    format=str(m.get("format", "")),
                    profile_ids=[str(p) for p in m.get("profile_ids") or ()],
                    players_json=str(m.get("players_json", "")),
                    lobby_url=str(m.get("lobby_url", "")),
                    spectate_url=str(m.get("spectate_url", "")),
                    updated_at=int(m.get("updated_at", 0)),
                    metadata={str(k): str(v) for k, v in (m.get("metadata") or {}).items()},
                )
                for m in matches
            ]
        )

    async def SearchProfiles(
        self,
        request: game_pb2.SearchProfilesRequest,
        context: grpc.aio.ServicerContext,
    ) -> game_pb2.ProfileSearchReply:
        """Serve the alias search (the #402 name resolution path)."""
        if self._search_profiles is None:
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "profile search not available")
        candidates = await self._search_profiles(request.alias)
        return game_pb2.ProfileSearchReply(
            candidates=[
                game_pb2.ProfileCandidate(
                    profile_id=str(c.get("profile_id", "")),
                    alias=str(c.get("alias", "")),
                    steam_name=str(c.get("steam_name", "")),
                    country=str(c.get("country", "")),
                    clan=str(c.get("clan", "")),
                    elo_1v1=int(c.get("elo_1v1", 0)),
                    elo_tg=int(c.get("elo_tg", 0)),
                    matches=[
                        game_pb2.MatchPreview(
                            map_name=str(m.get("map_name", "")),
                            description=str(m.get("description", "")),
                            completed_at=int(m.get("completed_at", 0)),
                            opponents=[str(o) for o in m.get("opponents") or ()],
                        )
                        for m in c.get("matches") or ()
                    ],
                )
                for c in candidates
            ]
        )
