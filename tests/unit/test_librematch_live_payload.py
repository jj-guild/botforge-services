"""Unit tests: the deterministic parse of a REAL libre:match payload.

The fixture (``fixtures/librematch/recent_match_history_jeanjack.json``)
is a verbatim upstream ``GetRecentMatchHistory`` reply (captured live
2026-11-20, profile 17190369 — JeanJack): one ranked 1v1 (Arabia), one
custom lobby ("Test bot", played on Arabia), one ranked 4v4
(CoastalForest). The expected outputs below are the agreed post-parse
values: the reconstruction must be deterministic against this exact
payload, so any drift in the decode, the reference tables or the
ingest must surface here — this test is the contract.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from botforge.ext_librematch.history import MatchHistorySyncer

FIXTURE = Path(__file__).parent / "fixtures" / "librematch" / "recent_match_history_jeanjack.json"
#: the REAL shipped tables (config/providers/librematch) — the test is
#: end-to-end: raw payload -> blob decode -> reference naming -> doc
REFERENCE_DIR = Path(__file__).parents[2] / "config" / "providers" / "librematch"
ME = "17190369"  # JeanJack


def _payload() -> list[dict[str, Any]]:
    """The fixture's matches, aliases attached the way the adapter does."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    aliases = {str(p["profile_id"]): str(p.get("alias", "")) for p in data["profiles"]}
    matches = [dict(m, profile_aliases=aliases) for m in data["matchHistoryStats"]]
    assert matches, "the fixture must carry matches"
    return matches


@pytest.fixture(autouse=True)
def _real_reference_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the reference lookup at the REAL shipped tables."""
    monkeypatch.setenv("LIBREMATCH_REFERENCE_DIR", str(REFERENCE_DIR))
    os.environ["LIBREMATCH_REFERENCE_DIR"] = str(REFERENCE_DIR)
    from botforge.ext_librematch import reference

    reference._indexed.cache_clear()
    yield
    reference._indexed.cache_clear()


def _doc(match_id: str) -> dict[str, Any]:
    """The stored document of one fixture match (find by id)."""
    syncer = MatchHistorySyncer.__new__(MatchHistorySyncer)
    for match in _payload():
        if str(match["id"]) == match_id:
            return syncer._match_doc(match)
    raise AssertionError(f"match {match_id} not in the fixture")


def _entry(match_id: str) -> Any:
    """The served projection of one fixture match."""
    syncer = MatchHistorySyncer.__new__(MatchHistorySyncer)
    return syncer._entry_of(_doc(match_id))


def test_the_blob_decode_is_deterministic() -> None:
    """The options/slotinfo blobs of the real payload fully decode."""
    from botforge.aoe2.codecs import decode_blob

    raw = {str(m["id"]): m for m in _payload()}
    # the ranked 1v1: 11 option pairs, 2 human slots, the location id
    options = decode_blob(raw["397662136"]["options"])
    assert options["10"] == "10875"  # the location key — Arabia
    assert options["8"] == "120"  # map size tiny (a 1v1 lobby)
    assert options["37"] == "0"  # standard resources
    slots = decode_blob(raw["397662136"]["slotinfo"])
    assert len(slots) == 2
    assert slots[0] == {
        "profileInfo.id": 17190369,
        "stationID": 2,
        "teamID": 0,
        "factionID": 0,
        "raceID": 27,
        "rankLevel": 0,
        "rankMatchTypeID": -1,
        "timePerFrameMS": 0,
        "isReady": 1,
        "status": 0,
        "metaData": slots[0]["metaData"],  # base64 payload, opaque by design
    }
    assert slots[1]["profileInfo.id"] == 4276665
    assert slots[1]["teamID"] == 1


def test_the_ranked_1v1_reconstructs_exactly() -> None:
    """Arabia, 1v1, the members' civs, JeanJack wins and gains 48 elo."""
    doc = _doc("397662136")
    assert doc["map_name"] == "Arabia"
    assert doc["lobby_title"] == "AUTOMATCH"
    assert doc["players"] == [
        {
            "profile_id": "4276665",
            "alias": "Lastdrop",
            "civ": "Persians",
            "team": 1,
            "rating_before": 1174,
            "rating_after": 1156,
        },
        {
            "profile_id": ME,
            "alias": "JeanJack",
            "civ": "Magyars",
            "team": 0,
            "rating_before": 1137,
            "rating_after": 1185,
        },
    ]
    assert doc["winners"] == [ME]
    assert doc["profile_ids"] == ["4276665", ME]


def test_the_custom_lobby_names_itself_and_the_map() -> None:
    """The "Test bot" lobby played on Arabia — both labels reconstruct."""
    doc = _doc("473574107")
    # the upstream mapname would have said "my map"; the options blob
    # location (10875) names Arabia via the reference table
    assert doc["map_name"] == "Arabia"
    assert doc["lobby_title"] == "Test bot"
    by_id = {p["profile_id"]: p for p in doc["players"]}
    assert by_id["848567"]["alias"] == "Merlin Pinpin"
    assert by_id[ME]["civ"] == "Shu"
    assert doc["winners"] == [ME]
    # a custom lobby still reports elo deltas (a bot-test lobby with
    # ranked-style reporting) — JeanJack +18, Merlin Pinpin -18
    assert by_id[ME]["rating_after"] - by_id[ME]["rating_before"] == 18
    assert by_id["848567"]["rating_after"] - by_id["848567"]["rating_before"] == -18


def test_the_ranked_4v4_lists_every_seat() -> None:
    """Eight members, four winners, every civ named from the tables."""
    doc = _doc("433589647")
    assert doc["map_name"] == "CoastalForest"
    assert len(doc["players"]) == 8
    assert doc["winners"] == ["1244374", "1036384", "4524901", "4982290"]
    mine = next(p for p in doc["players"] if p["profile_id"] == ME)
    assert mine["civ"] == "Vikings"
    assert mine["team"] == 1
    assert mine["rating_before"] == 1445
    assert mine["rating_after"] == 1432


def test_the_served_entry_carries_the_projection() -> None:
    """The wire entry keeps the named map, the civs and the outcome."""
    entry = _entry("397662136")
    assert entry.map_name == "Arabia"
    assert entry.description == "AUTOMATCH"
    assert entry.winners == (ME,)
    players = json.loads(entry.players_json)
    assert players[0]["civ"] == "Persians"
    assert players[1]["alias"] == "JeanJack"
    assert json.loads(entry.options_json)["10"] == "10875"


def test_the_view_blocks_render_from_the_real_payload() -> None:
    """The rendered discord blocks, verbatim \u2014 the end-to-end contract."""
    from botforge.discord.stats_views import finished_match_block

    labels = {"team": "\u00c9quipe", "ongoing": "en cours", "untitled": "Match {id}"}

    # the ranked 1v1 win \u2014 map titled, duration, one bullet per seat
    assert finished_match_block(_entry("397662136"), {ME}, {"848567"}, labels) == [
        "- \u2705 **Arabia** \u2014 <t:1749127503:R> \u00b7 17 min \u00b7 1v1",
        "  - **\u00c9quipe 1**",
        "      - **JeanJack** \u00b7 Magyars \u00b7 **1185 Elo** (+48)",
        "  - **\u00c9quipe 2**",
        "      - Lastdrop \u00b7 Persians \u00b7 **1156 Elo** (-18)",
    ]
    # the custom lobby \u2014 its own name carries the title, the map rides along
    assert finished_match_block(_entry("473574107"), {ME}, {"848567"}, labels) == [
        "- \u2705 **Test bot** \u00b7 *Arabia* \u2014 <t:1777283898:R> \u00b7 1v1",
        "  - **\u00c9quipe 1**",
        "      - *Merlin Pinpin* \u00b7 Saracens \u00b7 **1238 Elo** (-18)",
        "  - **\u00c9quipe 2**",
        "      - **JeanJack** \u00b7 Shu \u00b7 **1237 Elo** (+18)",
    ]
    # the 4v4 loss \u2014 every seat stacked, the viewed profile bold
    assert finished_match_block(_entry("433589647"), {ME}, set(), labels) == [
        "- \u274c **CoastalForest** \u2014 <t:1763320771:R> \u00b7 16 min \u00b7 4v4",
        "  - **\u00c9quipe 1**",
        "      - TheGooseTransporter \u00b7 Vietnamese \u00b7 **1512 Elo** (+16)",
        "      - Saladin45 \u00b7 Bulgarians \u00b7 **1502 Elo** (+16)",
        "      - konstid \u00b7 Gurjaras \u00b7 **1564 Elo** (+13)",
        "      - Richman \u00b7 Dravidians \u00b7 **1495 Elo** (+17)",
        "  - **\u00c9quipe 2**",
        "      - **JeanJack** \u00b7 Vikings \u00b7 **1432 Elo** (-13)",
        "      - DippityDang \u00b7 Malians \u00b7 **1535 Elo** (-18)",
        "      - Cyo Electryx \u00b7 Saracens \u00b7 **1396 Elo** (-12)",
        "      - SSS \u00b7 Mongols \u00b7 **1554 Elo** (-19)",
    ]
