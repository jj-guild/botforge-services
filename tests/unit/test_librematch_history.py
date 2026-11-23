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


def _doc_value(doc: dict[str, Any], dotted: str) -> Any:
    """Read a dotted path (players.0.civ) from a document."""
    value: Any = doc
    for part in dotted.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value


def _condition_ok(doc: dict[str, Any], key: str, condition: Any) -> bool:
    if key == "$or":
        return any(_condition_ok(doc, k, c) for pair in condition for k, c in pair.items())
    if key == "players.0":
        # the incomplete-capture marker: an empty (or absent)
        # players list means the document's projection is bare
        exists = bool(doc.get("players") or [])
        wants_exists = bool((condition or {}).get("$exists", False))
        return exists if wants_exists else not exists
    value = _doc_value(doc, key)
    if isinstance(condition, dict) and "$in" in condition:
        if isinstance(value, list):
            return any(v in condition["$in"] for v in value)
        return (value in condition["$in"]) or (value is None and None in condition["$in"])
    if isinstance(condition, dict) and "$gte" in condition:
        return value is not None and value >= condition["$gte"]
    if isinstance(condition, dict) and "$lt" in condition:
        return value is not None and value < condition["$lt"]
    if isinstance(condition, dict) and "$exists" in condition:
        return (value is not None) == bool(condition["$exists"])
    if isinstance(condition, dict) and "$ne" in condition:
        return value != condition["$ne"]
    if isinstance(value, list):
        # Mongo equality against an array matches containment
        return condition in value
    return value == condition


def _matches(query: dict[str, Any], docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The Mongo query subset the store uses ($in, $gte, $exists, $or)."""
    out = []
    for doc in docs:
        ok = all(_condition_ok(doc, key, condition) for key, condition in query.items())
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

    async def insert_one(self, doc: dict[str, Any]) -> None:
        self.docs[str(doc["_id"])] = doc
        self.inserted = int(getattr(self, "inserted", 0)) + 1

    async def delete_one(self, query: dict[str, Any]) -> int:
        doc_id = str(query.get("_id", ""))
        if doc_id in self.docs:
            del self.docs[doc_id]
            return 1
        return 0

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> None:
        doc = self.docs.get(str(query.get("_id", "")))
        if doc is None:
            return
        doc.update(update.get("$set", {}))

    async def update_many(self, query: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        touched = 0
        for doc in _matches(query, list(self.docs.values())):
            doc.update(update.get("$set", {}))
            touched += 1
        return {"modified_count": touched}


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
        self.history_counts: list[int] = []

    async def fetch_match_details_raw(self, match_id: str) -> dict[str, Any]:
        self.calls.append(("details", match_id))
        return self.details.get(match_id, {})

    async def fetch_match_history_raw(
        self, profile_id: str, leaderboard_id: str = "", count: int = 1000
    ) -> list[dict[str, Any]]:
        self.calls.append(("history", profile_id))
        self.history_counts.append(int(count))
        return self.history.get(profile_id, [])

    async def fetch_personal_stat_raw(
        self, profile_id: str, leaderboard_id: str
    ) -> dict[str, Any]:
        self.calls.append(("stat", profile_id))
        return self.stats.get(profile_id, {})


def _match(
    match_id: str,
    board: str,
    started: int,
    finished: int,
    members: list[dict[str, Any]],
    options: str = "",
    slotinfo: str = "",
    mapname: str = "arabia.rms",
    description: str = "",
) -> dict[str, Any]:
    payload = {
        "id": match_id,
        "leaderboard": board,
        "startgametime": started,
        "completiontime": finished,
        "mapname": mapname,
        "matchhistorymember": members,
    }
    # The upstream history payload carries the encoded blobs verbatim
    # (the LibreMatch wiki): the ingest decodes THIS, no second call.
    if options:
        payload["options"] = options
    if slotinfo:
        payload["slotinfo"] = slotinfo
    if description:
        payload["description"] = description
    return payload


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


def _stat(
    profile_id: str, rating: int, rank: int, wins: int, losses: int, board: str = "0"
) -> dict[str, Any]:
    """The RAW World's Edge GetPersonalStat reply (the statgroup join)."""
    return {
        "statGroups": [
            {"members": [{"profile_id": profile_id, "alias": "Someone", "personal_statgroup_id": 100}]}
        ],
        "leaderboardStats": [
            {
                "statgroup_id": 100,
                "leaderboard_id": board,
                "rating": rating,
                "rank": rank,
                "wins": wins,
                "losses": losses,
                "highestrating": 0,
            }
        ],
    }


def _syncer(db: FakeDb, adapter: FakeAdapter) -> MatchHistorySyncer:
    return MatchHistorySyncer(adapter, LibrematchStore(db))


async def test_sync_stores_raw_and_status() -> None:
    """The sync stores the RAW match docs and the account status."""
    db, adapter = FakeDb(), FakeAdapter()
    adapter.history["123"] = [
        _match("m1", "0", 100, 200, [_member("123", 1, 1, 1000, 1024)])
    ]
    adapter.stats["123"] = _stat("123", 1024, 55, 10, 2)
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
    adapter.history["123"] = [
        _match("m1", "0", 100, 200, [_member("123", 1, 1, 1200, 1250)])
    ]
    adapter.stats["123"] = _stat("123", 1250, 10, 30, 5)
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")

    # a later sync: the peak match slid out of the history window
    adapter.history["123"] = []
    adapter.stats["123"] = _stat("123", 1100, 12, 31, 6)
    await syncer.sync_account("123")
    account = db["librematch:accounts"].docs["123"]
    assert account["leaderboards"]["0"]["current"] == 1100
    assert account["leaderboards"]["0"]["max"] == 1250


async def test_account_stats_serves_known_and_unknown() -> None:
    """The status answers per account; unknown accounts read known=False."""
    db, adapter = FakeDb(), FakeAdapter()
    adapter.stats["123"] = _stat("123", 1024, 55, 10, 2)
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")

    statuses = await syncer.account_stats(["123", "999"])
    assert [s.profile_id for s in statuses] == ["123", "999"]
    assert statuses[0].known is True
    board = statuses[0].leaderboards[0]
    assert board.name == "unranked"  # LEADERBOARD_KEYS: board 0 IS unranked (3 is rm_1v1)
    assert board.current == 1024
    # the probes work again (signature bug died 2026-11-22): an
    # honestly-absent 1v1 still answers KNOWLEDGE - a none-marked
    # rm_1v1, zeroed - the absence differs from "never fetched"
    assert statuses[1].known is True
    absent1v1 = next((b for b in statuses[1].leaderboards if str(b.name) == "rm_1v1"), None)
    assert absent1v1 is not None and not absent1v1.current


async def test_user_unification_best_elo_and_matches_window() -> None:
    """Multiple accounts aggregate into ONE per-user view."""
    db, adapter = FakeDb(), FakeAdapter()
    store = LibrematchStore(db)
    await store.upsert_bindings(["123", "456"], ["alice", "alice"])
    adapter.stats["123"] = _stat("123", 1000, 100, 10, 2)
    adapter.stats["456"] = _stat("456", 1200, 40, 20, 4)
    now = 2_000_000_000
    adapter.history["123"] = [
        _match("m1", "0", now - 100, now, [_member("123", 1, 1, 990, 1000)]),
        _match("m2", "0", now - 200, now - 150, [_member("123", 1, 1, 980, 990)]),
    ]
    adapter.history["456"] = [
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
    adapter.history["123"] = [
        _match("m1", "0", 100, 200, [_member("123", 1, 1, 1000, 1024)]),
        _match("m2", "0", 300, 400, [_member("123", 1, 1, 1024, 1030)]),
        _match("m3", "3", 500, 600, [_member("123", 1, 1, 900, 910)]),
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
    adapter.stats["123"] = _stat("123", 1000, 1, 1, 0)
    adapter.stats["456"] = _stat("456", 1100, 1, 1, 0)
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
    """T2: the blobs ride the history payload itself, no second endpoint."""
    db, adapter = FakeDb(), FakeAdapter()
    adapter.history["123"] = [
        _match(
            "m1",
            "0",
            100,
            200,
            [_member("123", 1, 1, 1000, 1024)],
            options=_options([("MAP_SIZE", "3"), ("SPEED", "2")]),
            slotinfo=_slotinfo(
                [{"profileInfo": {"id": 123}, "factionID": 1, "teamID": 1, "status": 3}]
            ),
        )
    ]
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
    # no match-details call at all: the blobs ride the history payload
    assert ("details", "m1") not in adapter.calls
    assert ("history", "123") in adapter.calls


async def test_decode_failure_leaves_the_document_untouched() -> None:
    """T2: an undecodable blob degrades — the raw stays, fields stay empty."""
    db, adapter = FakeDb(), FakeAdapter()
    adapter.history["123"] = [
        _match("m1", "0", 100, 200, [_member("123", 1, 1, 1000, 1024)])
    ]
    adapter.details["m1"] = {"id": "m1", "options": "not-a-blob", "slotinfo": "!!!"}
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")

    doc = db["librematch:matches"].docs["m1:0"]
    assert doc["options_json"] == ""
    assert doc["slots_json"] == ""
    assert doc["raw"]["id"] == "m1"  # the raw document is never dropped


async def test_the_second_sync_reads_the_quick_window_and_only_appends() -> None:
    """The smart sync: deep once, then incremental — immutability.

    The FIRST sync of an account pulls the deep window; every later
    one reads the quick window and inserts ONLY the unknown matches —
    a finished match is never rewritten, never re-counted.
    """
    db, adapter = FakeDb(), FakeAdapter()
    adapter.history["123"] = [
        _match("m1", "0", 100, 200, [_member("123", 1, 1, 1000, 1024)]),
        _match("m2", "0", 300, 400, [_member("123", 1, 1, 1024, 1030)]),
    ]
    syncer = _syncer(db, adapter)

    await syncer.sync_account("123")  # the deep first pass
    assert adapter.history_counts[-1] == 1000
    stored_after_first = dict(db["librematch:matches"].docs)

    await syncer.sync_account("123")  # the incremental second pass
    assert adapter.history_counts[-1] == 25
    stored = db["librematch:matches"].docs
    # every match still there, the finished ones byte-identical (never rewritten)
    assert stored_after_first == {k: v for k, v in stored.items() if k in stored_after_first}
    assert 2 <= len(stored)  # both the deep pass's matches
    # and a genuinely NEW match lands appended, without touching the old ones
    n_before = len(stored)
    adapter.history["123"] = [
        *adapter.history["123"],
        _match("m3", "0", 500, 600, [_member("123", 1, 1, 1030, 1041)]),
    ]
    await syncer.sync_account("123")
    assert "m3:0" in db["librematch:matches"].docs
    assert len(db["librematch:matches"].docs) == n_before + 1


async def test_the_elo_refresh_never_fetches_history() -> None:
    """The light loop reads the stats ONLY — no history fetch at all."""
    db, adapter = FakeDb(), FakeAdapter()
    adapter.history["123"] = [_match("m1", "0", 100, 200, [_member("123", 1, 1, 1000, 1024)])]
    adapter.stats["123"] = _stat("123", 1024, 55, 10, 2)
    await LibrematchStore(db).upsert_bindings(["123"], ["alice"])  # the walk reads the bindings
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")
    history_calls = len([c for c in adapter.calls if c[0] == "history"])

    assert await syncer.refresh_status("123") is True
    assert len([c for c in adapter.calls if c[0] == "history"]) == history_calls
    account = db["librematch:accounts"].docs["123"]
    assert account["leaderboards"]["0"]["current"] == 1024

    refreshed = await syncer.refresh_statuses([])
    assert refreshed >= 1  # every BOUND account, never the met players
    assert len([c for c in adapter.calls if c[0] == "history"]) == history_calls


async def test_the_met_players_never_join_the_periodic_sync() -> None:
    """Only the BOUND accounts get walked (the met players stay out).

    The post-purge boot walked THOUSANDS of strangers (every met
    player re-created by the encounter fold): the periodic walks
    read the bindings, not the harvested accounts.
    """
    db, adapter = FakeDb(), FakeAdapter()
    adapter.history["123"] = [
        _match(
            "m14",
            "",
            100,
            200,
            [_member("123", 0, 0, 1292, 1300), _member("456", 1, 1, 1100, 1089)],
            description="AUTOMATCH",
        )
    ]
    adapter.stats["123"] = _stat("123", 1300, 1, 1, 0)
    store = LibrematchStore(db)
    await store.upsert_bindings(["123"], ["alice"])
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")
    # the seen fold knows 456 as a met player (his boards are harvested)...
    assert "456" in db["librematch:accounts"].docs
    synced = await syncer.sync_accounts([])
    probed_histories = [pid for call, pid in adapter.calls if call == "history"]
    # ... but the periodic walk never fetches HIS history
    assert "456" not in probed_histories
    assert synced == 1


async def test_reference_tables_name_the_upstream_ids(tmp_path, monkeypatch) -> None:
    """The provider's config tables reverse the ids, newest epoch first."""
    import json as _json

    table_dir = tmp_path / "reference"
    table_dir.mkdir()
    (table_dir / "maps_aoe2.json").write_text(
        _json.dumps({"Arabia": {"1": 9, "8": 10875}, "Murkwood": {"8": 11016}})
    )
    (table_dir / "civs_aoe2.json").write_text(
        _json.dumps({"Aztec": {"1": 0, "8": 0}, "Malians": {"8": 29}})
    )
    monkeypatch.setenv("LIBREMATCH_REFERENCE_DIR", str(table_dir))

    from botforge.ext_librematch import reference

    reference._indexed.cache_clear()
    try:
        assert reference.map_name_of("11016") == "Murkwood"
        assert reference.map_name_of(10875) == "Arabia"
        assert reference.civ_name_of("29") == "Malians"
        assert reference.map_name_of("999999") == ""
    finally:
        reference._indexed.cache_clear()


async def test_map_label_prefers_the_options_location(tmp_path, monkeypatch) -> None:
    """The options blob's location is THE map source (verified live).

    A custom lobby with a stale ``FrigidLake.rms`` file name answered
    location 10960 = Enclosed — the file name lies, the blob does not.
    """
    import json as _json

    table_dir = tmp_path / "reference"
    table_dir.mkdir()
    (table_dir / "maps_aoe2.json").write_text(
        _json.dumps({"Enclosed": {"8": 10960}, "Arabia": {"1": 9}})
    )
    monkeypatch.setenv("LIBREMATCH_REFERENCE_DIR", str(table_dir))
    from botforge.ext_librematch import reference

    reference._indexed.cache_clear()
    try:
        db, adapter = FakeDb(), FakeAdapter()
        adapter.history["123"] = [
            _match(
                "m1",
                "0",
                100,
                200,
                [_member("123", 1, 1, 1000, 1024)],
                options=_options([("10", "10960")]),
                mapname="FrigidLake.rms",
                description="Test bot",
            )
        ]
        syncer = _syncer(db, adapter)
        await syncer.sync_account("123")

        doc = db["librematch:matches"].docs["m1:0"]
        assert doc["map_name"] == "Enclosed"
        assert doc["lobby_title"] == "Test bot"
        # a useless "my map" without a decodable location gives way to ""
        adapter.history["123"] = [
            _match(
                "m2",
                "0",
                300,
                400,
                [_member("123", 1, 1, 1000, 1000)],
                mapname="my map",
            )
        ]
        await syncer.sync_account("123")
        assert db["librematch:matches"].docs["m2:0"]["map_name"] == ""
    finally:
        reference._indexed.cache_clear()


async def test_decode_stored_heals_an_old_format_document(tmp_path, monkeypatch) -> None:
    """A document stored by an older revision re-derives from its raw.

    No purge, no re-fetch: the immutable raw payload carries the
    blobs and the members, so the labels the tables now name land on
    the already-stored documents.
    """
    import json as _json

    table_dir = tmp_path / "reference"
    table_dir.mkdir()
    (table_dir / "maps_aoe2.json").write_text(_json.dumps({"Murkwood": {"8": 11016}}))
    monkeypatch.setenv("LIBREMATCH_REFERENCE_DIR", str(table_dir))
    from botforge.ext_librematch import reference

    reference._indexed.cache_clear()
    try:
        db, adapter = FakeDb(), FakeAdapter()
        # an OLD-REVISION document: bare, bare labels, empty projections
        raw = _match(
            "m1",
            "0",
            100,
            200,
            [_member("123", 1, 1, 1000, 1024)],
            options=_options([("10", "11016")]),
            mapname="my map",
            description="Test bot",
        )
        old_doc = dict(raw)
        old_doc.update(
            {
                "_id": "m1:0",
                "match_id": "m1",
                "leaderboard_id": "0",
                "started_at": 100,
                "finished_at": 200,
                "map_name": "my map",
                "profile_ids": ["123"],
                "players": [],
                "teams": {},
                "winners": [],
                "options_json": "",
                "slots_json": "",
                "raw": raw,
            }
        )
        db["librematch:matches"].docs["m1:0"] = old_doc

        syncer = _syncer(db, adapter)
        patched = await syncer.decode_stored(["123"])
        assert patched == 1

        doc = db["librematch:matches"].docs["m1:0"]
        assert doc["map_name"] == "Murkwood"
        assert doc["lobby_title"] == "Test bot"
        assert doc["players"][0]["profile_id"] == "123"
        assert doc["winners"] == ["123"]
        assert _json.loads(doc["options_json"])["10"] == "11016"
        assert doc["decoded_at"] > 0
    finally:
        reference._indexed.cache_clear()


async def test_an_incomplete_capture_refetches_deep_and_replaces() -> None:
    """A stored capture without players triggers the deep repair replace.

    The old-revision documents carry a raw payload lacking the
    members/description fields — the decode heal cannot invent them,
    so the sync re-pulls the deep window and REPLACES the incomplete
    captures with the complete upstream payload (same facts).
    """
    db, adapter = FakeDb(), FakeAdapter()
    # an INCOMPLETE capture: raw without members/description, no players
    db["librematch:matches"].docs["m1:0"] = {
        "_id": "m1:0",
        "match_id": "m1",
        "leaderboard_id": "0",
        "profile_ids": ["123"],
        "players": [],
        "teams": {},
        "winners": [],
        "map_name": "",
        "description": "",
        "options_json": "",
        "slots_json": "",
        "raw": {"id": "m1"},  # the poisoned capture: nothing to re-derive
    }
    adapter.history["123"] = [
        _match(
            "m1",
            "0",
            100,
            200,
            [_member("123", 1, 1, 1000, 1024)],
            description="Test bot",
        ),
        _match("m2", "0", 300, 400, [_member("123", 1, 1, 1024, 1030)]),
    ]
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")

    # the repair pulled the DEEP window, not the quick one
    assert adapter.history_counts == [1000]
    # the incomplete capture was REPLACED complete
    doc = db["librematch:matches"].docs["m1:0"]
    assert doc["players"], "the replaced capture carries the members"
    assert doc["description"] == "Test bot"
    assert doc["winners"] == ["123"]
    assert db["librematch:matches"].docs["m2:0"]["players"]


async def test_a_civless_capture_repairs_when_the_raw_carries_the_civ() -> None:
    """A capture with players but no civ repairs when upstream has it.

    The merlin case (2026-11-21): match 517022737 rendered without
    civs while the live upstream carries civilization_id on every
    member — an intermediate revision's capture. The repair replaces
    it; a lobby whose raw genuinely lacks a civ never loops.
    """
    db, adapter = FakeDb(), FakeAdapter()
    members = [
        {"profile_id": "123", "civilization_id": 19, "teamid": 0, "outcome": 1, "oldrating": 1292, "newrating": 1300},
        {"profile_id": "456", "civilization_id": 22, "teamid": 1, "outcome": 0, "oldrating": 1100, "newrating": 1089},
    ]
    raw = {"id": "517022737", "matchhistorymember": members}
    db["librematch:matches"].docs["517022737"] = {
        "_id": "517022737",
        "match_id": "517022737",
        "profile_ids": ["123"],
        "players": [{"profile_id": "123", "alias": "Merlin Pinpin", "civ": ""}],
        "raw": raw,
    }
    adapter.history["123"] = [
        _match("517022737", "0", 100, 200, [
            _member("123", 1, 0, 1292, 1300) | {"civilization_id": 19},
            _member("456", 0, 1, 1100, 1089) | {"civilization_id": 22},
        ]),
    ]
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")

    assert adapter.history_counts == [1000], "the civless capture forces the deep repair"
    doc = db["librematch:matches"].docs["517022737:0"]  # the REPAIRED capture
    seats = {p["profile_id"]: p for p in doc["players"]}
    assert seats["123"].get("civ"), "the replaced capture re-reads the civilization"


async def test_a_civless_lobby_repairs_once_then_stays_quiet() -> None:
    """An old-era capture of a genuinely civless lobby repairs ONCE.

    The era gate beats any content judgment: the lobby's members
    carry no civilization_id at all \u2014 the repair pass cannot give
    the seats a civ \u2014 but it runs once (the deep refetch), stamps
    the current era, and the next pass stays quiet: no loop on data
    the upstream honestly lacks.
    """
    db, adapter = FakeDb(), FakeAdapter()
    raw = {"id": "m9", "matchhistorymember": [{"profile_id": "123", "teamid": 0}]}
    db["librematch:matches"].docs["m9"] = {
        "_id": "m9",
        "match_id": "m9",
        "profile_ids": ["123"],
        "players": [{"profile_id": "123", "alias": "solo", "civ": ""}],
        "raw": raw,
    }
    adapter.history["123"] = [
        _match("m9", "", 100, 200, [_member("123", 1, 0, 1100, 1112)])
    ]
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")
    assert adapter.history_counts == [1000], "the old-era capture repairs once"
    assert db["librematch:matches"].docs["m9"].get("capture_era", 0) >= 2
    adapter.history_counts.clear()
    await syncer.sync_account("123")
    assert adapter.history_counts == [25], "the repaired capture never loops"


async def test_the_repair_deletes_the_poisoned_suffixed_captures() -> None:
    """The repair erases the old board-suffixed captures, not only inserts.

    The merlin loop (2026-11-21): the old era suffixed every document
    id with a board (``517022737:0``); the bare-id inserts never
    overwrote them and the marker looped forever. The repair DELETES
    the poisoned candidates before re-inserting complete captures.
    """
    db, adapter = FakeDb(), FakeAdapter()
    raw = {
        "id": "517022737",
        "matchhistorymember": [
            {"profile_id": "123", "civilization_id": 19, "teamid": 0, "outcome": 1},
        ],
    }
    db["librematch:matches"].docs["517022737:0"] = {
        "_id": "517022737:0",  # the old era's suffixed id
        "match_id": "517022737",
        "profile_ids": ["123"],
        "players": [{"profile_id": "123", "civ": ""}],
        "raw": raw,
    }
    adapter.history["123"] = [
        _match("517022737", "", 100, 200, [
            _member("123", 1, 0, 1292, 1300) | {"civilization_id": 19},
        ]),
    ]
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")
    # the suffixed capture is GONE (no loop: the next pass finds nothing)
    assert "517022737:0" not in db["librematch:matches"].docs
    doc = db["librematch:matches"].docs["517022737"]
    assert doc["players"][0]["civ"] == "Huns"
    # the second pass is QUIET: no repair, quick window
    adapter.history_counts.clear()
    await syncer.sync_account("123")
    assert adapter.history_counts == [25], "the repaired store stops looping"


async def test_a_random_civ_lobby_never_loops_the_repair() -> None:
    """Upstream marks RANDOM seats with civilization_id -1.

    The 2026-11-21 merlin loop: the old verdict read ANY non-null
    civilization_id as "capturable" — the -1 RANDOM marker kept the
    repair firing pass after pass, and (worse) the reference's
    reversed table indexed -1, rendering random seats as
    "Varangians". Both guards are pinned here.
    """
    db, adapter = FakeDb(), FakeAdapter()
    raw = {"id": "m10", "matchhistorymember": [{"profile_id": "123", "civilization_id": -1}]}
    db["librematch:matches"].docs["m10"] = {
        "_id": "m10",
        "match_id": "m10",
        "profile_ids": ["123"],
        "players": [{"profile_id": "123", "alias": "solo", "civ": ""}],
        "raw": raw,
    }
    adapter.history["123"] = [
        _match("m10", "", 100, 200, [_member("123", 1, 0, 1100, 1112)])
    ]
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")
    assert adapter.history_counts == [1000], "the old-era capture repairs once"
    doc = db["librematch:matches"].docs["m10"]
    assert doc["players"][0]["civ"] == "", "the RANDOM seat stays honestly civless"
    adapter.history_counts.clear()
    await syncer.sync_account("123")
    assert adapter.history_counts == [25], "the repaired capture never loops"

    from botforge.ext_librematch.reference import civ_name_of

    assert civ_name_of(-1) == "", "the RANDOM marker never names a civ"


async def test_the_encountered_seats_become_known_players() -> None:
    """The sync folds the payload's seats into the accounts: no extra call.

    The owner's 2026-11-22 direction: every player the bot's users met
    carries his elo through the match itself (old/new rating) - the
    account stats must harvest it so the panels read every seat's
    1v1/TG current+max without another upstream request.
    """
    db, adapter = FakeDb(), FakeAdapter()
    adapter.history["123"] = [
        _match(
            "m11",
            "",
            100,
            200,
            [
                _member("123", 1, 0, 1292, 1300),
                _member("456", 0, 1, 1100, 1089),
                _member("789", 0, 1, 1050, 1051),
                _member("321", 1, 0, 990, 1030),
            ],
            description="AUTOMATCH",
        ),
    ]
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")
    accounts = db["librematch:accounts"].docs
    # the TG board (the WE id 4) carries every seat's current (post-match) and max
    board = accounts["456"]["leaderboards"]["4"]
    assert board["current"] == 1089 and board["max"] == 1100
    board = accounts["321"]["leaderboards"]["4"]
    assert board["current"] == 1030 and board["max"] == 1030
    # the account-stats read answers the ENCOUNTERED player too
    statuses = await syncer.account_stats(["456"])
    assert statuses[0].known
    rm = next(b for b in statuses[0].leaderboards if str(b.name) == "rm_team")
    assert rm.current == 1089 and rm.max == 1100


async def test_a_custom_lobby_never_harvests_boards() -> None:
    """The "test" bot lobbies reported TG elo with one seat per team.

    The team-size heuristic folded them into rm_1v1 and poisoned the
    panels' 1v1 lines (owner 2026-11-22 \u2014 "t'as pris l'elo tg"):
    a custom lobby's ratings stay OUT of the seen harvest; only the
    ranked AUTOMATCH matches fold.
    """
    db, adapter = FakeDb(), FakeAdapter()
    adapter.history["123"] = [
        _match(
            "m13",
            "",
            100,
            200,
            [
                _member("123", 1, 0, 1292, 1300),
                _member("456", 0, 1, 1100, 1089),
            ],
            description="test",
        ),
    ]
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")
    # the custom RATINGS never fold - but the met player's honest 1v1
    # ABSENCE still gets probed once; his TG board stays empty
    boards = db["librematch:accounts"].docs["456"]["leaderboards"]
    # the 1v1 AND the TG absence both probe once (one call answers every
    # board); the custom RATINGS never fold into a board value
    assert boards["3"]["none"] is True and not boards["3"]["current"]
    assert boards["4"]["none"] is True and not boards["4"]["current"]


async def test_the_missing_1v1_gets_probed_once_not_forever() -> None:
    """The met player's 1v1 board is fetched once; a true absence stays."""
    db, adapter = FakeDb(), FakeAdapter()
    adapter.history["123"] = [
        _match(
            "m12",
            "",
            100,
            200,
            [
                _member("123", 1, 0, 1150, 1162),
                _member("789", 1, 0, 1100, 1108),
                _member("456", 0, 1, 980, 988),
                _member("321", 0, 1, 1010, 1018),
            ],
            description="AUTOMATCH",
        ),
    ]
    probed: list[str] = []

    async def _stat(*args: Any) -> dict[str, Any]:
        profile_id = str(args[0])  # the probe calls (profile_id, leaderboard)
        probed.append(profile_id)
        # an honest profile WITHOUT any 1v1 board (rm team only)
        return {}

    adapter.fetch_personal_stat_raw = _stat  # type: ignore[method-assign]
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")
    assert "456" in probed, "the met player without a 1v1 board gets probed"
    await syncer.sync_account("123")  # the second pass stays quiet
    assert probed.count("456") == 1, "the honestly-absent 1v1 never re-probes"
    assert db["librematch:accounts"].docs["456"]["leaderboards"]["3"]["none"] is True


async def test_stale_never_played_match_seals_and_never_serves() -> None:
    """An abandoned lobby (no result for over a day) is invalid (owner 2026-11-23)."""
    import time as _time

    db = FakeDb()
    adapter = FakeAdapter()
    now = int(_time.time())
    # a resultless capture two days old - the abandoned "test" lobby
    adapter.history["123"] = [
        _match("old-lobby", "", now - 200000, 0, [_member("123", 0, 0, 0, 0)], description="test"),
    ]
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")
    assert db["librematch:matches"].docs["old-lobby"]["invalid"] is True
    entries = await syncer.match_history(["123"])
    assert entries == [], "the abandoned lobby never serves"


async def test_recent_ongoing_match_still_serves() -> None:
    """A capture younger than the stale window is NOT sealed (yet)."""
    import time as _time

    db = FakeDb()
    adapter = FakeAdapter()
    now = int(_time.time())
    adapter.history["123"] = [
        _match("fresh-lobby", "", now - 600, 0, [_member("123", 0, 0, 0, 0)], description="test"),
    ]
    syncer = _syncer(db, adapter)
    await syncer.sync_account("123")
    assert "invalid" not in db["librematch:matches"].docs["fresh-lobby"]
    entries = await syncer.match_history(["123"])
    assert [e.match_id for e in entries] == ["fresh-lobby"]
