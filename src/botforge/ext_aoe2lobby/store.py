"""aoe2lobby live store — the provider's OWN live-state database (#404 T3).

The lobby provider covers the PRESENT: every interesting match (with at
least one known player) is stored here, in the provider's namespaced
collections — the raw frames first, the exploited projection (status,
summary, elo changes riding the frames) after. libre:match covers the
past; the two stores never merge, the consumers compose.

Collections:

- ``aoe2lobby:matches`` — one document per match_ref: the last known
  payload, the status (lobby | game | ended), the known participants,
  the summary metadata and the elo deltas seen on the frames;
- ``aoe2lobby:events`` — the raw transition frames, append-only (the
  audit trail of the live world).
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("botforge.ext_aoe2lobby.store")

MATCHES_COLLECTION = "aoe2lobby:matches"
EVENTS_COLLECTION = "aoe2lobby:events"

DEFAULT_LIVE_LIMIT = 50

STATUS_LOBBY = "lobby"
STATUS_GAME = "game"
STATUS_ENDED = "ended"

_EVENT_STATUS = {
    "lobby_opened": STATUS_LOBBY,
    "match_updated": STATUS_LOBBY,
    "game_started": STATUS_GAME,
    "lobby_closed": STATUS_ENDED,
    "game_ended": STATUS_ENDED,
}


def _now_ms() -> int:
    """Epoch milliseconds, the repo's timestamp convention."""
    return int(time.time() * 1000)


class LobbyStore:
    """The provider's own persistence seam over async MongoDB."""

    def __init__(self, database: Any) -> None:
        """Wrap the provider's async Mongo database."""
        self._db = database

    def _matches(self) -> Any:
        """Return the live match documents collection."""
        return self._db[MATCHES_COLLECTION]

    def _events(self) -> Any:
        """Return the raw frames collection."""
        return self._db[EVENTS_COLLECTION]

    async def apply_event(self, event: dict[str, Any]) -> None:
        """Store one transition frame and fold it into the match doc.

        The raw frame lands in ``aoe2lobby:events`` verbatim
        (append-only); the match document upserts with the event's
        status, participants and summary metadata. Best-effort: a
        store failure logs, never crashes the stream.
        """
        match_ref = str(event.get("match_ref", ""))
        if not match_ref:
            return
        occurred_at = int(event.get("occurred_at") or _now_ms())
        try:
            await self._events().insert_one(
                {
                    "_id": f"{match_ref}:{occurred_at}:{event.get('type', '')}",
                    "match_ref": match_ref,
                    "type": str(event.get("type", "")),
                    "occurred_at": occurred_at,
                    "profile_ids": list(event.get("profile_ids") or ()),
                    "metadata": dict(event.get("metadata") or {}),
                    "raw": event,
                }
            )
        except Exception:
            # a duplicate frame id (same ms) is expected on replays —
            # the raw frame is already stored, the fold continues
            logger.debug("frame insert skipped (duplicate replay)", exc_info=True)
        status = _EVENT_STATUS.get(str(event.get("type", "")), STATUS_LOBBY)
        metadata = dict(event.get("metadata") or {})
        profile_ids = sorted({str(p) for p in event.get("profile_ids") or ()})
        doc = {
            "_id": match_ref,
            "match_ref": match_ref,
            "status": status,
            "map_name": metadata.get("map", ""),
            "format": metadata.get("format", ""),
            "profile_ids": profile_ids,
            "players_json": metadata.get("players", ""),
            "lobby_url": metadata.get("lobby_url", ""),
            "spectate_url": metadata.get("spectate_url", ""),
            "metadata": metadata,
            "updated_at": occurred_at,
        }
        elo = _elo_changes(metadata)
        if elo:
            doc["elo_changes"] = elo
        await self._matches().replace_one({"_id": match_ref}, doc, upsert=True)

    async def list_matches(
        self, statuses: list[str] | None = None, limit: int = 0
    ) -> list[dict[str, Any]]:
        """List the stored matches, newest first, optionally by status."""
        query: dict[str, Any] = {}
        if statuses:
            query["status"] = {"$in": statuses}
        cursor = self._matches().find(query)
        cursor = cursor.sort("updated_at", -1)
        return [dict(doc) async for doc in cursor.limit(limit or DEFAULT_LIVE_LIMIT)]

    async def find_match(self, match_ref: str) -> dict[str, Any] | None:
        """Return one stored match document; None when unknown."""
        doc = await self._matches().find_one({"_id": str(match_ref)})
        return dict(doc) if doc is not None else None

    async def list_events(self, match_ref: str, limit: int = 0) -> list[dict[str, Any]]:
        """List the raw frames of one match, oldest first (the audit trail)."""
        cursor = self._events().find({"match_ref": str(match_ref)})
        cursor = cursor.sort("occurred_at", 1)
        return [dict(doc) async for doc in cursor.limit(limit or 100)]


def _elo_changes(metadata: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Extract the elo deltas riding one frame's metadata, if any.

    The live frames carry the rating changes on the ended matches (the
    upstream's own fields, when present): ``elo_<profile_id>`` /
    ``rating_<profile_id>`` keys, or the compact ``elo_json`` payload.
    Absent fields mean no elo change on this frame — an empty dict.
    """
    changes: dict[str, dict[str, int]] = {}
    compact = metadata.get("elo_json") or metadata.get("ratings_json")
    if compact:
        import json

        try:
            parsed = json.loads(compact)
        except (TypeError, ValueError):
            parsed = {}
        if isinstance(parsed, dict):
            for pid, delta in parsed.items():
                if isinstance(delta, dict):
                    changes[str(pid)] = {
                        "before": int(delta.get("before", 0)),
                        "after": int(delta.get("after", 0)),
                    }
    for key, value in metadata.items():
        if not key.startswith("elo_"):
            continue
        pid = key.removeprefix("elo_")
        try:
            changes[pid] = {"after": int(value), "before": 0}
        except (TypeError, ValueError):
            continue
    return changes
