"""The aoe2lobby live store tests (#404 T3).

The lobby provider covers the PRESENT: every interesting match is
stored as the frames arrive — the raw frames first, the exploited
projection (status, summary, the elo changes riding the frames) after.
"""

from __future__ import annotations

from typing import Any

from botforge.ext_aoe2lobby.store import (
    STATUS_ENDED,
    STATUS_GAME,
    STATUS_LOBBY,
    LobbyStore,
)


class FakeCollection:
    """An in-memory Mongo collection (the store's query subset)."""

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}
        self.order: list[str] = []

    async def insert_one(self, doc: dict[str, Any]) -> None:
        self.docs[str(doc["_id"])] = doc
        self.order.append(str(doc["_id"]))

    async def replace_one(
        self, query: dict[str, Any], doc: dict[str, Any], upsert: bool = False
    ) -> None:
        del upsert
        self.docs[str(query.get("_id", ""))] = doc

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        return self.docs.get(str(query.get("_id", "")))

    def find(self, query: dict[str, Any]) -> Any:
        return FakeCursor([d for d in self.docs.values() if _match(query, d)])


class FakeSortCursor:
    """A cursor stub carrying the sort/limit chain."""

    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    def sort(self, key: str, direction: int) -> FakeSortCursor:
        self._docs = sorted(self._docs, key=lambda d: d.get(key, 0), reverse=direction < 0)
        return self

    def limit(self, count: int) -> FakeSortCursor:
        self._docs = self._docs[:count]
        return self

    def __aiter__(self):
        self._iter = iter(self._docs)
        return self

    async def __anext__(self) -> dict[str, Any]:
        try:
            return dict(next(self._iter))
        except StopIteration as exc:
            raise StopAsyncIteration from exc


FakeCursor = FakeSortCursor


def _match(query: dict[str, Any], doc: dict[str, Any]) -> bool:
    for key, condition in query.items():
        value = doc.get(key)
        if isinstance(condition, dict) and "$in" in condition:
            if value not in condition["$in"]:
                return False
        elif value != condition:
            return False
    return True


class FakeDb:
    """database[collection] stand-in."""

    def __init__(self) -> None:
        self._collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self._collections.setdefault(name, FakeCollection())


def _frame(
    match_ref: str,
    event_type: str,
    occurred_at: int,
    profile_ids: list[str],
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "match_ref": match_ref,
        "type": event_type,
        "occurred_at": occurred_at,
        "profile_ids": profile_ids,
        "metadata": metadata or {},
    }


async def test_frames_fold_into_match_documents() -> None:
    """Each frame lands raw in the events, folded into the match doc."""
    db = FakeDb()
    store = LobbyStore(db)
    await store.apply_event(
        _frame("abc", "lobby_opened", 1000, ["123"], {"map": "Arabia", "format": "1v1"})
    )
    await store.apply_event(
        _frame("abc", "game_started", 2000, ["123"], {"map": "Arabia"})
    )

    events = db["aoe2lobby:events"].docs
    assert len(events) == 2  # the raw frames, kept verbatim
    match = db["aoe2lobby:matches"].docs["abc"]
    assert match["status"] == STATUS_GAME
    assert match["map_name"] == "Arabia"
    assert match["profile_ids"] == ["123"]
    assert match["updated_at"] == 2000


async def test_ended_matches_leave_the_live_list() -> None:
    """The live list serves lobby + game; the ended ones leave it."""
    db = FakeDb()
    store = LobbyStore(db)
    await store.apply_event(_frame("live1", "lobby_opened", 1000, ["123"]))
    await store.apply_event(_frame("live2", "game_started", 1100, ["456"]))
    await store.apply_event(_frame("done", "game_ended", 1200, ["789"]))

    live = await store.list_matches([STATUS_LOBBY, STATUS_GAME])
    assert sorted(m["match_ref"] for m in live) == ["live1", "live2"]
    ended = await store.list_matches([STATUS_ENDED])
    assert [m["match_ref"] for m in ended] == ["done"]


async def test_elo_changes_ride_the_frames() -> None:
    """The elo deltas carried by a frame land on the match document."""
    db = FakeDb()
    store = LobbyStore(db)
    import json

    await store.apply_event(
        _frame(
            "abc",
            "game_ended",
            3000,
            ["123", "456"],
            {"elo_json": json.dumps({"123": {"before": 1000, "after": 1012}})},
        )
    )
    match = db["aoe2lobby:matches"].docs["abc"]
    assert match["elo_changes"] == {"123": {"before": 1000, "after": 1012}}

    # the per-key form carries too
    await store.apply_event(_frame("def", "game_ended", 3100, ["999"], {"elo_999": "1200"}))
    assert db["aoe2lobby:matches"].docs["def"]["elo_changes"] == {"999": {"after": 1200, "before": 0}}


async def test_event_audit_trail_lists_oldest_first() -> None:
    """The raw frames of one match list oldest first (the audit trail)."""
    db = FakeDb()
    store = LobbyStore(db)
    await store.apply_event(_frame("abc", "lobby_opened", 1000, ["123"]))
    await store.apply_event(_frame("abc", "game_started", 2000, ["123"]))
    await store.apply_event(_frame("abc", "game_ended", 3000, ["123"]))

    events = await store.list_events("abc")
    assert [e["type"] for e in events] == ["lobby_opened", "game_started", "game_ended"]
