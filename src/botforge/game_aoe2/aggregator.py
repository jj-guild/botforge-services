"""game-aoe2 aggregator: provider events → enriched player states.

The game service consumes the providers' ``StreamMatchEvents``
(ext-aoe2lobby realtime layer; ext-librematch the source of truth),
folds them into per-profile states, and keeps the full match summary
carried by the events' metadata (map, format, civs, host, join and
spectate links, aoe2de deep link) so the dashboard and the mod
notifications render rich context without any extra provider call.

Ownership (developer direction): this service owns the AoE2 domain
state; svc-core and the bot only see what the GameData contract serves.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Protocol

from botforge.aoe2.known_ids import KnownIds, log_match_event
from botforge.game_aoe2 import GAME_KEY

logger = logging.getLogger("botforge.game_aoe2.aggregator")

STATE_OFFLINE = "offline"
STATE_IN_LOBBY = "in_lobby"
STATE_IN_GAME = "in_game"

STATUS_LOBBY = "lobby"
STATUS_GAME = "game"

_EVENT_STATE = {
    "lobby_opened": STATE_IN_LOBBY,
    "game_started": STATE_IN_GAME,
    "lobby_closed": STATE_OFFLINE,
    "game_ended": STATE_OFFLINE,
}

GRACE_MS = 15_000
SNAPSHOT_KEYS = (
    "map",
    "format",
    "status",
    "slots_taken",
    "slots_total",
    "host",
    "players",
    "lobby_url",
    "spectate_url",
    "deep_link",
    "match_url",
)


class ProviderEvents(Protocol):
    """One provider's live event stream (GameProviderClient.stream_match_events)."""

    provider_id: str

    def stream_match_events(self, since: int) -> Any:
        """Async iterator of MatchEvent from the provider."""
        ...


class GameAoe2Aggregator:
    """Fold provider events into enriched per-player dashboard states.

    The enrolled roster (pushed by svc-core through UpdateEnrollments)
    is the dashboard's baseline: an enrolled player never seen in a
    match renders OFFLINE — the dashboard shows every enrolled player,
    not only those whose transitions already fired.
    """

    def __init__(self) -> None:
        """Start with an empty state; the first snapshot resolves it."""
        self._players: dict[str, dict[str, Any]] = {}
        # WatchPlayerEvents subscribers: every stream gets its OWN queue
        # (a fan-out — one consumer must never starve another), cleaned
        # up when the stream ends.
        self._subscribers: set[Any] = set()
        self._roster: dict[str, str] = {}
        self._known = KnownIds()
        self._degraded = True
        self._transitions: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def set_roster(self, entries: list[Any]) -> None:
        """Record the enrolled roster (the dashboard's baseline + known ids).

        Entries are the enrollment records — dicts with profile_id and
        user_id (the UpdateEnrollments push), an optional name (the
        binding's display name), or bare profile id strings (tests,
        degraded paths). Newly enrolled profiles become known from this
        point on (botforge-services#423).
        """
        roster: dict[str, str] = {}
        for entry in entries:
            if isinstance(entry, dict):
                roster[str(entry.get("profile_id", ""))] = str(entry.get("user_id", ""))
            else:
                roster[str(entry)] = ""
        self._roster = roster
        self._known.set_entries(entries)

    def snapshot(self) -> dict[str, Any]:
        """Build the current dashboard snapshot (every enrolled player)."""
        players = []
        for profile_id, user_id in sorted(self._roster.items()):
            state = self._players.get(profile_id)
            if state is None:
                state = _offline_state(profile_id)
                state["user_id"] = user_id
            elif user_id and not state.get("user_id"):
                state = {**state, "user_id": user_id}
            players.append(dict(state))
        for profile_id, state in self._players.items():
            if profile_id not in self._roster:
                players.append(dict(state))
        players.sort(key=lambda p: str(p.get("profile_id", "")))
        return {"players": players, "generated_at": _now_ms(), "degraded": self._degraded}

    async def _persist_player_state(self, profile_id: str, state: dict[str, Any]) -> None:
        """Persist one player's current state to Mongo (best-effort).

        The ``player_state`` collection holds the LIVE truth per
        profile — maintained by the subscriptions' events (in/out of
        lobby, in/out of game, the settings' changes), read as a
        snapshot by every panel. A store failure never breaks the
        stream (the in-memory state stays authoritative for the
        live readers).
        """
        import os

        uri = os.environ.get("MONGO_URI", "")
        if not uri:
            return
        try:
            from botforge.core.models.db import get_async_database

            database = get_async_database()
            await database["player_state"].update_one(
                {"profile_id": profile_id},
                {"$set": {**state, "updated_at": _now_ms()}},
                upsert=True,
            )
        except Exception:
            logger.debug("player state persist skipped (profile %s) — best-effort", profile_id, exc_info=True)

    async def apply_event(self, event: Any) -> None:
        """Fold one provider MatchEvent into the player states.

        botforge-services#423: an event is folded only when it concerns
        known ids — an enrolled profile id, a profile already tracked,
        or a match ref already referenced by a tracked player. Events
        about strangers are dropped before any INFO log, state write,
        transition fan-out or Mongo persist; receiving the event still
        proves provider liveness, so the degraded flag clears first.
        """
        self._degraded = False
        filtered = self._known_filter(event)
        if filtered is None:
            logger.debug(
                "gamedata EVENT dropped (strangers only): profiles=%s match=%s type=%s",
                ",".join(str(p) for p in getattr(event, "profile_ids", ()) or ()),
                getattr(event, "match_ref", ""),
                getattr(event, "type", "?"),
            )
            return
        relevant, concerned = filtered
        log_match_event(
            logger,
            "gamedata EVENT",
            str(getattr(event, "type", "?")),
            str(getattr(event, "match_ref", "") or ""),
            concerned,
            self._known,
            dict(getattr(event, "metadata", ()) or {}),
        )
        if event.type == "match_updated":
            await self._apply_match_updated(event, relevant)
            return
        target_state = _EVENT_STATE.get(event.type)
        if target_state is None:
            return
        for profile_id in relevant:
            await self._apply_transition(event, profile_id, target_state)

    async def _apply_match_updated(self, event: Any, relevant: list[str]) -> None:
        """Refresh the stored match payload of known profiles on that match.

        A live setup change (civ, map, settings, slots): no state
        transition, no noise — and unknown profiles are never
        persisted (botforge-services#423).
        """
        summary = _summary_of(event)
        for profile_id in relevant:
            current = self._players.get(profile_id)
            if current is not None and current.get("match_ref") == event.match_ref:
                current["match"] = summary
                # the settings' live change persists with the state
                await self._persist_player_state(profile_id, current)

    async def _apply_transition(self, event: Any, profile_id: str, target_state: str) -> None:
        """Fold one profile's state transition (persist + fan-out)."""
        current = self._players.get(profile_id)
        if target_state == STATE_OFFLINE and current is not None and current["state"] == STATE_IN_GAME:
            if event.type == "lobby_closed" and event.occurred_at - current["since"] < GRACE_MS:
                return
        summary = _summary_of(event)
        new_state = {
            "profile_id": profile_id,
            "state": target_state,
            "match_ref": event.match_ref if target_state != STATE_OFFLINE else "",
            "since": event.occurred_at,
            "match": summary if target_state != STATE_OFFLINE else {},
        }
        old_state = current["state"] if current else STATE_OFFLINE
        self._players[profile_id] = new_state
        # the state persists (owner spec 2026-11-01): the panels
        # read snapshots from the store; the requests NEVER query
        # the providers — the subscriptions maintain the truth.
        await self._persist_player_state(profile_id, new_state)
        if old_state != target_state:
            transition = {
                "game_key": GAME_KEY,
                "profile_id": profile_id,
                "user_id": self._roster.get(profile_id, ""),
                "old_status": old_state,
                "new_status": target_state,
                "match_ref": new_state["match_ref"],
                "occurred_at": event.occurred_at,
                "match": summary,
            }
            self._transitions.put_nowait(transition)
            # the fan-out: every subscriber's queue gets its own copy
            for queue in list(self._subscribers):
                queue.put_nowait(transition)

    def _known_filter(self, event: Any) -> tuple[list[str], list[str]] | None:
        """Apply the #423 known-id filter to one event.

        Return ``(to_process, to_log)`` — the relevant profile ids to
        fold and the ids the INFO line names — or None when the event
        concerns strangers only and must be dropped before any side
        effect. An empty ``profile_ids`` on a tracked match_ref is a
        match-level update for the players on that match.
        """
        profile_ids = [str(p) for p in getattr(event, "profile_ids", ()) or ()]
        match_ref = str(getattr(event, "match_ref", "") or "")
        known_ids = set(self._roster) | set(self._players)
        relevant = [p for p in profile_ids if p in known_ids]
        match_players = [
            profile_id
            for profile_id, state in self._players.items()
            if match_ref and state.get("match_ref") == match_ref
        ]
        if not relevant and not match_players:
            return None
        if not profile_ids and match_players:
            relevant = match_players
        return relevant, relevant or match_players

    async def next_transition(self) -> dict[str, Any]:
        """Await the next normalized transition (WatchPlayerEvents)."""
        return await self._transitions.get()

    def subscribe(self) -> Any:
        """Register a WatchPlayerEvents subscriber; it gets its own queue.

        The service maintains the state (this aggregator) and streams
        every transition to ALL its subscribers (a mod, the bot) — a
        fan-out, never a competition for one queue.
        """
        import asyncio

        queue: Any = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: Any) -> None:
        """Drop a subscriber (its stream ended); its queue goes with it."""
        self._subscribers.discard(queue)

    def pending_transitions(self) -> int:
        """Report the number of queued transitions (diagnostics, tests)."""
        return self._transitions.qsize()

    def mark_degraded(self) -> None:
        """Flag the state provider-less (all offline)."""
        self._degraded = True

    def mark_healthy(self) -> None:
        """Clear the degraded flag once a provider stream is live."""
        self._degraded = False


def _summary_of(event: Any) -> dict[str, Any]:
    """Extract the match summary an event's metadata carries."""
    metadata = dict(getattr(event, "metadata", ()) or {})
    return {key: str(metadata.get(key, "")) for key in SNAPSHOT_KEYS if metadata.get(key) not in (None, "")}


def _now_ms() -> int:
    """Epoch milliseconds, the repo's timestamp convention."""
    return int(time.time() * 1000)


def _offline_state(profile_id: str) -> dict[str, Any]:
    """Build the offline baseline of an enrolled player never seen in a match."""
    return {
        "profile_id": profile_id,
        "state": STATE_OFFLINE,
        "match_ref": "",
        "since": 0,
        "match": {},
    }
