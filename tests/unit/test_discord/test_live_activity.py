"""The live activity surfaces' guards (botforge-services#405).

The feed owns TWO surfaces (owner 2026-11-24): the matches salon
carries the SAME card class as the profile panels (rendered through
``_match_card_parts``), and the logs channel carries short, DENSE,
append-only event lines - one log per (match, event), never per
player. A guild WITHOUT the matches salon sees the logs only.
"""

from __future__ import annotations

import json
from typing import Any

import botforge.discord.live_activity as feed


def _event(old: str, new: str, ref: str = "523338329", user: str = "u1") -> dict[str, Any]:
    match = {
        "match_ref": ref,
        "map": "Budapest",
        "match_type": "Unranked solo",
        "lobby_url": "https://aoe2lobby.com/join",
        "spectate_url": "https://aoe2lobby.com/watch",
        "settings_json": "{}",
        "players": [{"profile_id": "848567", "name": "Merlin Pinpin", "civ": "Mayans", "team": 2, "slot": 4}],
    }
    return {"profile_id": "848567", "user_id": user, "old_status": old, "new_status": new, "match": match}


async def test_the_feed_card_reads_the_same_parts_builder() -> None:
    """The salon card is THE panel card - contextualised, links and all."""
    event = _event("offline", "in_lobby")
    feed._CARD_STATE[("g1", "523338329")] = feed._live_card_of(
        "523338329", feed._LAST_SUMMARY.setdefault("523338329", event["match"]), "lobby", 1732400000
    )
    card = feed._CARD_STATE[("g1", "523338329")]
    from botforge.discord.home import _match_card_parts

    blocks, buttons, match_id, accent = _match_card_parts(
        card, {"civ_urls": {}, "civ_images": {}, "map_urls": {}, "map_images": {},
               "map_display": {}, "civ_display": {}, "ladder": {}},
        set(), {"team": "Team"},
    )
    assert match_id == "523338329" and blocks and accent
    # the settings button rides the share (the popup works everywhere)
    assert any(
        "settings" in str(getattr(b, "custom_id", "") or "") or "⚙" in str(getattr(b, "label", "") or "")
        for b in buttons
    )


def test_the_logs_verbs_and_the_one_line_per_event_dedupe() -> None:
    """Several players in one match log ONE line per event, not per player."""
    feed._LOGGED.clear()
    assert feed._verb_of(_event("offline", "in_lobby")) == "lobby_open"
    assert feed._verb_of(_event("in_lobby", "in_lobby")) == "lobby_update"
    assert feed._verb_of(_event("in_lobby", "in_game")) == "match_start"
    assert feed._verb_of(_event("in_game", "offline")) == "match_end"
    # a lobby that folds without a game closes, it never calls it a match
    assert feed._verb_of(_event("in_lobby", "offline")) == "lobby_close"
    assert feed._verb_of({"new_status": "offline", "old_status": "offline"}) == ""


def _entry(**kw: Any) -> Any:
    """A served MatchHistoryEntry stand-in."""
    from types import SimpleNamespace

    base = {
        "match_id": "507", "leaderboard_id": "", "started_at": 1732300000, "finished_at": 0,
        "winners": (), "players_json": "[]", "settings_json": "[]", "options_json": "",
        "map_name": "Budapest", "description": "lobby test", "invalid": True,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_the_seed_card_labels_the_invalid_matches() -> None:
    """An invalid match (no result - under five minutes) seeds WITH its status."""
    undecided = feed._seed_card_of(_entry(finished_at=0, winners=()))
    assert undecided["invalid"] is True
    assert undecided["invalid_reason"] == "no_result"
    short = feed._seed_card_of(
        _entry(finished_at=1732300180, winners=("848567",),
               players_json='[{"profile_id": "848567", "alias": "Merlin"}]')
    )
    assert short["invalid"] is True
    assert short["invalid_reason"] == "short"
    # the AI rule (owner 2026-11-24): a finished 1v1v1 against two
    # computers records no human victor - the match COUNTS, the
    # computers won, no seal on it
    ffa = feed._seed_card_of(
        _entry(match_id="523338329", finished_at=1732302000, winners=(),
               players_json='[{"profile_id": "848567", "alias": "Merlin Pinpin"},'
                            ' {"profile_id": "", "alias": "IA", "ai": true, "team": 2},'
                            ' {"profile_id": "", "alias": "IA", "ai": true, "team": 6}]')
    )
    assert "invalid" not in ffa, "the computers decided it - the humans lost, the match counts"
    valid = feed._seed_card_of(_entry(match_id="509", finished_at=1732303600, winners=("848567",)))
    assert "invalid" not in valid, "a decided match never carries the status"


def test_the_invalid_status_renders_on_the_card() -> None:
    """The map section carries the invalid status line (owner 2026-11-24)."""
    from botforge.discord.home import _card_map_section

    card = {"status": "finished", "map_name": "Budapest", "started_at": 1732300000,
            "finished_at": 1732300100, "invalid": True, "invalid_reason": "short"}
    labels = {"when": "Il y a {when}", "duration": "Durée : {clock}",
              "invalid": "Match non compté", "invalid_short": "forfait — moins de 5 minutes"}
    ctx = {"map_display": {}, "map_urls": {}, "map_images": {}}
    section = _card_map_section(card, ctx, labels)
    import discord as _discord

    view = _discord.ui.LayoutView(timeout=None)
    view.add_item(section)
    text = str(view.to_components())
    assert "Match non compté" in text
    assert "forfait" in text


def test_the_listing_shows_the_sealed_matches() -> None:
    """An invalidated entry renders in the five - with its status key."""
    from botforge.discord.home import _invalid_reason_type_of

    # never decided: no completion, no winner
    assert _invalid_reason_type_of(0, 0, (), []) == "no_result"
    # decided but under five minutes
    assert _invalid_reason_type_of(1732300000, 1732300180, ("848567",), []) == "short"
    # the AI rule: finished, no human victor, computers on board -
    # the match counts (the AIs won, the scoped human LOST)
    seats = [{"profile_id": "848567", "ai": False}, {"profile_id": "", "ai": True}]
    assert _invalid_reason_type_of(1732300000, 1732302000, (), seats) == ""


def test_the_ai_decrease_the_scoped_emoji_to_a_loss() -> None:
    """The 1v1v1 lost against the computers rides the skull, not a void."""
    from botforge.discord.home import _card_header

    card = {
        "status": "finished",
        "players": [
            {"profile_id": "848567", "ai": False},
            {"profile_id": "", "alias": "IA", "ai": True},
        ],
        "winners": [],
    }
    text = _card_header("CUSTOM FFA", "Match n\u00b0", "523338329", me_ids={"848567"}, card=card)
    assert "\U0001f480" in text, "the human lost to the computers - the skull renders"


def test_the_live_card_serves_the_ai_seats_of_the_other_provider() -> None:
    """An aoe2lobby lobby against computers renders their seats (owner 2026-11-24).

    The LIVE provider (the WS feed) rides a DIFFERENT payload than the
    WE store: the summary's own ``players`` json carries ``ai: true``
    for the computers - the shared builder must keep them, badge and
    all, through ``_live_card_of``.
    """
    summary = {
        "match_ref": "523338329",
        "map": "Budapest",
        "match_type": "Unranked solo",
        "players": json.dumps(
            [
                {"profile_id": "848567", "name": "Merlin Pinpin", "civ": "Mayans", "team": 1, "slot": 4, "ai": False},
                {"profile_id": "", "name": "Computer", "civ": "Franks", "team": 2, "slot": 2, "ai": True},
            ]
        ),
    }
    card = feed._live_card_of("523338329", summary, "lobby", 1732400000)
    from botforge.discord.home import _match_card_parts

    blocks, _buttons, match_id, _accent = _match_card_parts(
        card, {"civ_urls": {}, "civ_images": {}, "map_urls": {}, "map_images": {},
               "map_display": {}, "civ_display": {}, "ladder": {}},
        set(), {"team": "Team"},
    )
    assert match_id == "523338329"
    text = ""
    import discord as _discord

    view = _discord.ui.LayoutView(timeout=None)
    for block in blocks:
        view.add_item(block)
    text = str(view.to_components())
    assert any(bool((p or {}).get("ai")) for p in card["players"]), "the computers ride the card"
    assert "Computer" in text, "the computer's seat renders"


def test_the_we_slotinfo_decodes_the_computer_seats() -> None:
    """A status-2 seat WITHOUT a profile but WITH a civ is a computer.

    The owner's match 518232462 (verified live 2026-11-24): the AI
    rides ``profileInfo.id: -1, status: 2, raceID: 40`` while the
    closed seats answer ``raceID: -1`` - the first decode read the
    computer as a closed slot and the panels never saw an AI.
    """
    slot_ai = {"profileInfo.id": -1, "stationID": -1, "teamID": 6, "factionID": -1, "raceID": 40,
               "isReady": 0, "status": 2}
    slot_closed = {"profileInfo.id": -1, "stationID": -1, "teamID": 0, "factionID": -1,
                   "raceID": -1, "isReady": 0, "status": 1}
    from botforge.ext_librematch.decode import _normalize_slot

    ai = _normalize_slot(slot_ai, 1)
    closed = _normalize_slot(slot_closed, 2)
    assert ai["slot_kind"] == "ai" and not ai["filled"] and ai["profile_id"] == ""
    assert closed["slot_kind"] == "open" and not closed["filled"]
    # a NEGATIVE profile id is NO profile: the AI never reads as filled
    human = _normalize_slot({"profileInfo.id": 848567, "teamID": 5, "raceID": 27,
                             "isReady": 1, "status": 0}, 0)
    assert human["slot_kind"] == "human" and human["filled"] and human["profile_id"] == "848567"


def test_the_ai_verdict_names_the_computer_teams_winners() -> None:
    """An AI-decided match strikes the humans and crowns the computers.

    The salon card (unscoped, owner 2026-11-25): the AI teams ride
    the trophy, the human team the skull - and the scoped view
    strikes the loser.
    """
    from botforge.discord.home import _ai_decided

    card = {
        "status": "finished",
        "winners": [],
        "players": [
            {"profile_id": "848567", "ai": False, "team": 1},
            {"profile_id": "", "ai": True, "team": 6},
        ],
    }
    assert _ai_decided(card) is True
    # a HUMAN verdict keeps reading through the winners
    decided = {**card, "winners": ["848567"]}
    assert _ai_decided(decided) is False
    # an invalid match never crowns the computers
    sealed = {**card, "invalid": True}
    assert _ai_decided(sealed) is False
