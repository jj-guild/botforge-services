"""Unit tests for the game-aoe2 aggregator (enriched player states)."""

from __future__ import annotations

import logging
from typing import Any

from botforge.game_aoe2.aggregator import (
    STATE_IN_GAME,
    STATE_IN_LOBBY,
    STATE_OFFLINE,
    GameAoe2Aggregator,
)

AGGREGATOR_LOGGER = "botforge.game_aoe2.aggregator"

SUMMARY = {
    "map": "Arabia",
    "format": "1v1",
    "players": "Alice(Britons),Bob(Franks)",
    "lobby_url": "https://www.aoe2lobby.com/j/111",
    "deep_link": "aoe2de://1/-111",
}


class FakeEvent:
    """Minimal MatchEvent stand-in carrying a match summary."""

    def __init__(
        self,
        type: str,
        profile_ids: tuple[str, ...],
        occurred_at: int,
        match_ref: str = "111",
        metadata: tuple = (),
    ) -> None:
        self.type = type
        self.profile_ids = profile_ids
        self.occurred_at = occurred_at
        self.match_ref = match_ref
        self.metadata = metadata


def _summary_event(type: str, occurred_at: int = 1_000) -> FakeEvent:
    return FakeEvent(type, ("123",), occurred_at, "111", tuple(SUMMARY.items()))


async def test_event_folds_enriched_state() -> None:
    agg = GameAoe2Aggregator()
    agg.set_roster(["123"])
    await agg.apply_event(_summary_event("lobby_opened"))
    snapshot = agg.snapshot()
    player = snapshot["players"][0]
    assert player["state"] == STATE_IN_LOBBY
    assert player["match"]["map"] == "Arabia"
    assert player["match"]["deep_link"] == "aoe2de://1/-111"
    assert snapshot["degraded"] is False


async def test_transitions_queued_with_summary() -> None:
    agg = GameAoe2Aggregator()
    agg.set_roster(["123"])
    await agg.apply_event(_summary_event("lobby_opened"))
    await agg.apply_event(_summary_event("game_started", 2_000))
    first = await agg.next_transition()
    assert first["old_status"] == STATE_OFFLINE
    assert first["new_status"] == STATE_IN_LOBBY
    assert first["match"]["format"] == "1v1"
    second = await agg.next_transition()
    assert second["new_status"] == STATE_IN_GAME


async def test_lobby_closed_grace_keeps_game_state() -> None:
    agg = GameAoe2Aggregator()
    agg.set_roster(["123"])
    await agg.apply_event(_summary_event("game_started", 100_000))
    await agg.apply_event(_summary_event("lobby_closed", 105_000))
    player = agg.snapshot()["players"][0]
    assert player["state"] == STATE_IN_GAME


async def test_offline_clears_the_match() -> None:
    agg = GameAoe2Aggregator()
    agg.set_roster(["123"])
    await agg.apply_event(_summary_event("game_started", 1_000))
    await agg.apply_event(_summary_event("game_ended", 50_000))
    player = agg.snapshot()["players"][0]
    assert player["state"] == STATE_OFFLINE
    assert player["match_ref"] == ""
    assert player["match"] == {}


async def test_unknown_event_type_ignored() -> None:
    agg = GameAoe2Aggregator()
    agg.set_roster(["123"])
    await agg.apply_event(FakeEvent("chat_message", ("123",), 1_000))
    assert agg._players == {}
    assert agg.pending_transitions() == 0


async def test_roster_baseline_shows_enrolled_offline_players() -> None:
    """Every enrolled player renders, offline when never seen in a match."""
    agg = GameAoe2Aggregator()
    agg.set_roster(
        [
            {"profile_id": "123", "user_id": "10"},
            {"profile_id": "456", "user_id": "20"},
        ]
    )
    await agg.apply_event(_summary_event("game_started"))
    snap = agg.snapshot()
    players = {p["profile_id"]: p for p in snap["players"]}
    assert set(players) == {"123", "456"}
    assert players["123"]["state"] == STATE_IN_GAME
    assert players["456"]["state"] == STATE_OFFLINE
    assert players["456"]["user_id"] == "20"


async def _persist_spy(agg: GameAoe2Aggregator, monkeypatch: Any) -> list[str]:
    """Replace the Mongo persist with a recording spy; returns the calls."""
    persisted: list[str] = []

    async def fake_persist(profile_id: str, state: dict[str, Any]) -> None:
        persisted.append(profile_id)

    monkeypatch.setattr(agg, "_persist_player_state", fake_persist)
    return persisted


async def test_stranger_event_dropped_before_any_side_effect(caplog: Any, monkeypatch: Any) -> None:
    """#423: unknown ids + untracked match → no state, no transition, no persist, no INFO."""
    agg = GameAoe2Aggregator()
    agg.set_roster([{"profile_id": "999", "user_id": "1", "name": "Zoe"}])
    queue = agg.subscribe()
    persisted = await _persist_spy(agg, monkeypatch)
    with caplog.at_level(logging.INFO, logger=AGGREGATOR_LOGGER):
        await agg.apply_event(FakeEvent("lobby_opened", ("111", "222"), 1_000, "777", tuple(SUMMARY.items())))
    assert agg._players == {}
    assert agg.pending_transitions() == 0
    assert queue.empty()
    assert persisted == []
    assert [r for r in caplog.records if r.levelno >= logging.INFO and r.name == AGGREGATOR_LOGGER] == []
    # receiving the event still proves provider liveness
    assert agg.snapshot()["degraded"] is False
    snap = agg.snapshot()
    assert {p["profile_id"]: p["state"] for p in snap["players"]} == {"999": STATE_OFFLINE}


async def test_mixed_event_folds_only_the_known_profile() -> None:
    """#423: one known + one unknown profile id → only the known one changes."""
    agg = GameAoe2Aggregator()
    agg.set_roster([{"profile_id": "123", "user_id": "10", "name": "Alice"}])
    await agg.apply_event(FakeEvent("lobby_opened", ("123", "999"), 1_000, "111", tuple(SUMMARY.items())))
    assert set(agg._players) == {"123"}
    assert agg._players["123"]["state"] == STATE_IN_LOBBY
    assert agg.pending_transitions() == 1
    transition = await agg.next_transition()
    assert transition["profile_id"] == "123"
    assert transition["new_status"] == STATE_IN_LOBBY


async def test_known_profile_on_fresh_match_is_accepted() -> None:
    """#423: a known player joining a brand-new match_ref is interesting."""
    agg = GameAoe2Aggregator()
    agg.set_roster([{"profile_id": "123", "user_id": "10"}])
    await agg.apply_event(FakeEvent("game_started", ("123",), 1_000, "555", tuple(SUMMARY.items())))
    player = agg.snapshot()["players"][0]
    assert player["state"] == STATE_IN_GAME
    assert player["match_ref"] == "555"
    assert player["match"]["map"] == "Arabia"
    assert agg.pending_transitions() == 1


async def test_match_updated_unknown_profile_noop_known_profile_refreshes(monkeypatch: Any) -> None:
    """#423: match_updated only refreshes known profiles on that match."""
    agg = GameAoe2Aggregator()
    agg.set_roster([{"profile_id": "123", "user_id": "10"}])
    persisted = await _persist_spy(agg, monkeypatch)
    await agg.apply_event(FakeEvent("lobby_opened", ("123",), 1_000, "111", tuple(SUMMARY.items())))
    assert persisted == ["123"]
    # an unknown profile on the tracked match: no-op, never persisted
    await agg.apply_event(FakeEvent("match_updated", ("999",), 2_000, "111", (("map", "Hideout"),)))
    assert "999" not in agg._players
    assert agg._players["123"]["match"]["map"] == "Arabia"
    assert persisted == ["123"]
    # the known profile on its current match: payload refreshed
    await agg.apply_event(FakeEvent("match_updated", ("123",), 3_000, "111", (("map", "Hideout"),)))
    assert agg._players["123"]["match"]["map"] == "Hideout"
    assert persisted == ["123", "123"]
    # match_updated never queues a transition
    assert agg.pending_transitions() == 1


async def test_empty_profiles_on_tracked_match_updates_its_players() -> None:
    """#423 edge case: empty profile_ids + tracked match_ref → match-level update."""
    agg = GameAoe2Aggregator()
    agg.set_roster([{"profile_id": "123", "user_id": "10"}])
    await agg.apply_event(FakeEvent("lobby_opened", ("123",), 1_000, "111", tuple(SUMMARY.items())))
    await agg.apply_event(FakeEvent("match_updated", (), 2_000, "111", (("map", "Hideout"),)))
    assert agg._players["123"]["match"]["map"] == "Hideout"


async def test_empty_profiles_on_untracked_match_dropped() -> None:
    """#423 edge case: empty profile_ids + untracked match_ref → dropped."""
    agg = GameAoe2Aggregator()
    agg.set_roster([{"profile_id": "123", "user_id": "10"}])
    await agg.apply_event(FakeEvent("match_updated", (), 1_000, "777"))
    await agg.apply_event(FakeEvent("lobby_opened", (), 2_000, "777"))
    assert agg._players == {}
    assert agg.pending_transitions() == 0


async def test_newly_enrolled_profile_becomes_known_mid_stream() -> None:
    """#423: set_roster mid-stream → newly enrolled profiles are known from then on."""
    agg = GameAoe2Aggregator()
    await agg.apply_event(FakeEvent("lobby_opened", ("123",), 1_000, "111"))
    assert agg._players == {}
    agg.set_roster([{"profile_id": "123", "user_id": "10"}])
    await agg.apply_event(FakeEvent("lobby_opened", ("123",), 2_000, "111"))
    assert agg._players["123"]["state"] == STATE_IN_LOBBY


async def test_known_event_logs_info_naming_the_player(caplog: Any) -> None:
    """#423 taxonomy: a known profile's event is INFO and carries the pseudo."""
    agg = GameAoe2Aggregator()
    agg.set_roster([{"profile_id": "123", "user_id": "10", "name": "Alice"}])
    with caplog.at_level(logging.INFO, logger=AGGREGATOR_LOGGER):
        await agg.apply_event(FakeEvent("lobby_opened", ("123",), 1_000, "111", tuple(SUMMARY.items())))
    info_lines = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO and r.name == AGGREGATOR_LOGGER]
    assert any("Alice" in line and "lobby_opened" in line and "111" in line for line in info_lines)


async def test_nameless_known_profile_falls_back_to_id_in_info(caplog: Any) -> None:
    """#423 taxonomy: a nameless-but-known profile is not demoted — its id names it."""
    agg = GameAoe2Aggregator()
    agg.set_roster([{"profile_id": "123", "user_id": "10"}])
    with caplog.at_level(logging.INFO, logger=AGGREGATOR_LOGGER):
        await agg.apply_event(FakeEvent("game_started", ("123",), 1_000, "111"))
    info_lines = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO and r.name == AGGREGATOR_LOGGER]
    assert any("123" in line and "game_started" in line for line in info_lines)
