"""The libre:match stats layer tests (#404 T1).

The provider is the source of truth of its perimeter: the syncer
STORES the raw history first, then EXPLOITS it (per-account status
with current + MAX elo, per-user unification) — these tests pin the
store-first-then-exploit order and the unification's rules.
"""

from __future__ import annotations

from typing import Any

from botforge.ext_librematch.history import MatchHistorySyncer
from botforge.ext_librematch.store import LibrematchStore


class FakeCursor:
    """An in-memory Mongo cursor (filter, sort, limit)."""

    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    def sort(self, key: str, direction: int) -> FakeCursor:
        self._docs = sorted(self._docs, key=lambda d: d.get(key, 0), reverse=direction < 0)
        return self

    def limit(self, count: int) -> FakeCursor:
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


def _matches(query: dict[str, Any], docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The Mongo query subset the store uses ($in, $gte)."""
    out = []
    for doc in docs:
        ok = True
        for key, condition in query.items():
            value = doc.get(key)
            if isinstance(condition, dict) and "$in" in condition:
                if isinstance(value, list):
                    ok = ok and any(v in condition["$in"] for v in value)
                else:
                    ok = ok and value in condition["$in"]
            elif isinstance(condition, dict) and "$gte" in condition:
                ok = ok and value is not None and value >= condition["$gte"]
            else:
                ok = ok and value == condition
        if ok:
            out.append(doc)
    return out


class FakeCollection:
    """An in-memory Mongo collection (the store's query subset)."""

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    async def replace_one(
        self, query: dict[str, Any], doc: dict[str, Any], upsert: bool = False
    ) -> None:
        del upsert
        self.docs[str(query.get("_id", ""))] = doc

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        found = _matches(query, list(self.docs.values()))
        return dict(found[0]) if found else None

    def find(self, query: dict[str, Any], projection: dict[str, Any] | None = None) -> FakeCursor:
        del projection
        return FakeCursor(_matches(query, list(self.docs.values())))

    async def count_documents(self, query: dict[str, Any]) -> int:
        return len(_matches(query, list(self.docs.values())))

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> None:
        doc = self.docs.get(str(query.get("_id", "")))
        if doc is None:
            return
        doc.update(update.get("$set", {}))


class FakeDb:
    """database[collection] stand-in."""

    def __init__(self) -> None:
        self._collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self._collections.setdefault(name, FakeCollection())


class FakeAdapter:
    """The live adapter stand-in: raw payloads, verbatim."""

    def __init__(self) -> None:
        self.history: dict[str, list[dict[str, Any]]] = {}
        self.stats: dict[str, dict[str, Any]] = {}
        self.details: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[str, str]] = []

    async def fetch_match_details_raw(self, match_id: str) -> dict[str, Any]:
        self.calls.append(("details", match_id))
        return self.details.get(match_id, {})

    async def fetch_match_history_raw(
        self, profile_id: str, leaderboard_id: str = "", count: int = 1000
    ) -> list[dict[str, Any]]:
        del count
        self.calls.append(("history", profile_id))
        return self.history.get(f"{profile_id}:{leaderboard_id}", [])

    async def fetch_personal_stat_raw(
        self, profile_id: str, leaderboard_id: str
    ) -> dict[str, Any]:
        self.calls.append(("stat", profile_id))
        return self.stats.get(f"{profile_id}:{leaderboard_id}", {})


def _match(
    match_id: str,
    board: str,
    started: int,
    finished: int,
    members: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": match_id,
        "leaderboard": board,
        "startgametime": started,
        "completiontime": finished,
        "mapname": "arabia.rms",
        "matchhistorymember": members,
    }


def _member(
    profile_id: str, outcome: int, team: int, old: int, new: int
) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "outcome": outcome,
        "teamid": team,
        "oldrating": old,
        "newrating": new,
    }


def _stat(profile_id: str, rating: int, rank: int, wins: int, losses: int) -> dict[str, Any]:
    return {
        "statGroups": [{"members": [{"profile_id": profile_id, "alias": "Someone"}]}],
        "leaderboardStats": [
            {
                "profile_id": profile_id,
                "rating": rating,
                "rank": rank,
                "wins": wins,
                "losses": losses,
            }
        ],
    }


def _syncer(db: FakeDb, adapter: FakeAdapter) -> MatchHistorySyncer:
    return MatchHistorySyncer(adapter, LibrematchStore(db))


async def test_sync_stores_raw_and_status() -> None:
    """The sync stores the RAW match docs and the account status."""
    db, adapter = FakeDb(), FakeAdapter()
    adapter.history["123:0"] = [
        _match("m1", "0", 100, 200, [_member("123", 1, 1, 1000, 1024)])
    ]
    adapter.stats["123:0"] = _stat("123", 1024, 55, 10, 2)
    syncer = _syncer(db, adapter)

    assert await syncer.sync_account("123") is True
    matches = db["librematch:matches"].docs
    assert "m1:0" in matches
    assert matches["m1:0"]["raw"]["id"] == "m1"  # the raw payload, verbatim
    account = db["librematch:accounts"].docs["123"]
    assert account["leaderboards"]["0"]["current"] == 1024
    # the MAX elo rides the history's peaks (1024) and the current (1024)
    assert account["leaderboards"]["0"]["max"] == 1024
    assert account["leaderboards"]["0"]["rank"] == 55


async def test_max_elo_never_drops() -> None:
    """The stored MAX survives a lower fresh sync (the window slid)."""
    db, adapter = FakeDb(), FakeAdapter()
    adapter.history["123:0"] = [
        _match("m1", "0", 100, 200, [_member("123", 1, 1, 1200, 1250)])
    ]
    adapter.stats["123:0"] = _stat("123", 1250, 10, 30, 5)
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")

    # a later sync: the peak match slid out of the history window
    adapter.history["123:0"] = []
    adapter.stats["123:0"] = _stat("123", 1100, 12, 31, 6)
    await syncer.sync_account("123")
    account = db["librematch:accounts"].docs["123"]
    assert account["leaderboards"]["0"]["current"] == 1100
    assert account["leaderboards"]["0"]["max"] == 1250


async def test_account_stats_serves_known_and_unknown() -> None:
    """The status answers per account; unknown accounts read known=False."""
    db, adapter = FakeDb(), FakeAdapter()
    adapter.stats["123:0"] = _stat("123", 1024, 55, 10, 2)
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")

    statuses = await syncer.account_stats(["123", "999"])
    assert [s.profile_id for s in statuses] == ["123", "999"]
    assert statuses[0].known is True
    board = statuses[0].leaderboards[0]
    assert board.name == "rm_1v1"
    assert board.current == 1024
    assert statuses[1].known is False


async def test_user_unification_best_elo_and_matches_window() -> None:
    """Multiple accounts aggregate into ONE per-user view."""
    db, adapter = FakeDb(), FakeAdapter()
    store = LibrematchStore(db)
    await store.upsert_bindings(["123", "456"], ["alice", "alice"])
    adapter.stats["123:0"] = _stat("123", 1000, 100, 10, 2)
    adapter.stats["456:0"] = _stat("456", 1200, 40, 20, 4)
    now = 2_000_000_000
    adapter.history["123:0"] = [
        _match("m1", "0", now - 100, now, [_member("123", 1, 1, 990, 1000)]),
        _match("m2", "0", now - 200, now - 150, [_member("123", 1, 1, 980, 990)]),
    ]
    adapter.history["456:0"] = [
        _match("m3", "0", now - 50, now, [_member("456", 1, 1, 1190, 1200)])
    ]
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")
    await syncer.sync_account("456")

    stats = await syncer.user_stats("alice", window_days=30)
    assert stats is not None
    assert stats.profile_ids == ("123", "456")
    board = next(b for b in stats.leaderboards if b.leaderboard_id == "0")
    assert board.current == 1200  # the BEST current across the accounts
    assert board.max == 1200  # the BEST max across the accounts
    assert board.wins == 30  # summed
    assert stats.matches_in_window == 3  # every stored match of the window


async def test_user_stats_unknown_user_is_none() -> None:
    """A user with no known account reads as unknown (None)."""
    db, adapter = FakeDb(), FakeAdapter()
    syncer = _syncer(db, adapter)
    assert await syncer.user_stats("nobody") is None


async def test_match_history_query_filters() -> None:
    """The history answers from the store: leaderboard + window filters."""
    db, adapter = FakeDb(), FakeAdapter()
    adapter.history["123:0"] = [
        _match("m1", "0", 100, 200, [_member("123", 1, 1, 1000, 1024)]),
        _match("m2", "0", 300, 400, [_member("123", 1, 1, 1024, 1030)]),
    ]
    adapter.history["123:3"] = [
        _match("m3", "3", 500, 600, [_member("123", 1, 1, 900, 910)])
    ]
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")

    entries = await syncer.match_history(["123"], leaderboard_id="0")
    assert [e.match_id for e in entries] == ["m2", "m1"]  # newest first
    assert entries[0].rating_after["123"] == 1030
    assert entries[0].winners == ("123",)

    only_recent = await syncer.match_history(["123"], since_s=350)
    assert [e.match_id for e in only_recent] == ["m3", "m2"]  # newest first

    limited = await syncer.match_history(["123"], limit=1)
    assert len(limited) == 1


async def test_sync_accounts_targets_given_or_all() -> None:
    """The batch sync covers the given accounts, or every known one."""
    db, adapter = FakeDb(), FakeAdapter()
    store = LibrematchStore(db)
    await store.upsert_bindings(["123", "456"], ["alice", "bob"])
    syncer = _syncer(db, adapter)

    assert await syncer.sync_accounts(["123"]) == 0  # nothing stored, no stat
    adapter.stats["123:0"] = _stat("123", 1000, 1, 1, 0)
    adapter.stats["456:0"] = _stat("456", 1100, 1, 1, 0)
    assert await syncer.sync_accounts([]) == 2  # every known account
    assert set(db["librematch:accounts"].docs) == {"123", "456"}


def _slotinfo(slots: list[dict[str, Any]]) -> str:
    """Build a real-shape slotinfo blob: base64(zlib("<N>,<json>"))."""
    import base64
    import json as _json
    import zlib

    payload = f"{len(slots)},{_json.dumps(slots)}"
    return base64.b64encode(zlib.compress(payload.encode())).decode()


def _options(pairs: list[tuple[str, str]]) -> str:
    """Build a real-shape options blob (the codecs test's recipe)."""
    import base64
    import struct
    import zlib

    records = b"".join(
        struct.pack("<I", len(k.encode()) + 1 + len(v.encode())) + f"{k}:{v}".encode()
        for k, v in pairs
    )
    inner = base64.b64encode(bytes([len(pairs)]) + records).decode()
    return base64.b64encode(zlib.compress(inner.encode())).decode()


async def test_decode_exploits_stored_matches_without_refetch() -> None:
    """T2: the encoded fields decode AFTER the storage, no history re-fetch."""
    db, adapter = FakeDb(), FakeAdapter()
    adapter.history["123:0"] = [
        _match("m1", "0", 100, 200, [_member("123", 1, 1, 1000, 1024)])
    ]
    adapter.details["m1"] = {
        "id": "m1",
        "options": _options([("MAP_SIZE", "3"), ("SPEED", "2")]),
        "slotinfo": _slotinfo(
            [{"profileInfo": {"id": 123}, "factionID": 1, "teamID": 1, "status": 3}]
        ),
    }
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")

    doc = db["librematch:matches"].docs["m1:0"]
    import json

    assert json.loads(doc["options_json"]) == {"MAP_SIZE": "3", "SPEED": "2"}
    slots = json.loads(doc["slots_json"])
    assert slots[0]["profile_id"] == "123"
    assert slots[0]["civ"] == 1
    assert slots[0]["team"] == 1
    assert slots[0]["slot_kind"] == "human"
    # the served projection carries the decoded fields (T2)
    entries = await syncer.match_history(["123"])
    assert entries[0].options_json == doc["options_json"]
    assert entries[0].slots_json == doc["slots_json"]
    # no history re-fetch: only the details endpoint was called
    assert ("details", "m1") in adapter.calls
    assert ("history", "123") in adapter.calls


async def test_decode_failure_leaves_the_document_untouched() -> None:
    """T2: an undecodable blob degrades — the raw stays, fields stay empty."""
    db, adapter = FakeDb(), FakeAdapter()
    adapter.history["123:0"] = [
        _match("m1", "0", 100, 200, [_member("123", 1, 1, 1000, 1024)])
    ]
    adapter.details["m1"] = {"id": "m1", "options": "not-a-blob", "slotinfo": "!!!"}
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")

    doc = db["librematch:matches"].docs["m1:0"]
    assert doc["options_json"] == ""
    assert doc["slots_json"] == ""
    assert doc["raw"]["id"] == "m1"  # the raw document is never dropped
