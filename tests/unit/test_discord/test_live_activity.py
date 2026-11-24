"""The live activity surfaces' guards (botforge-services#405).

The feed owns TWO surfaces (owner 2026-11-24): the matches salon
carries the SAME card class as the profile panels (rendered through
``_match_card_parts``), and the logs channel carries short, DENSE,
append-only event lines - one log per (match, event), never per
player. A guild WITHOUT the matches salon sees the logs only.
"""

from __future__ import annotations

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


def test_the_seed_card_labels_the_invalid_matches() -> None:
    """An invalid match (no result - under five minutes) seeds WITH its status."""
    undecided = feed._seed_card_of(
        {"match_id": "507", "started_at": 1732300000, "finished_at": 0, "winners": [],
         "players": [], "options_json": "", "description": "lobby test"},
    )
    assert undecided["invalid"] is True
    assert undecided["invalid_reason"] == "no_result"
    short = feed._seed_card_of(
        {"match_id": "508", "started_at": 1732300000, "finished_at": 1732300180,
         "winners": ["848567"], "players": [{"profile_id": "848567", "alias": "Merlin"}],
         "options_json": ""},
    )
    assert short["invalid"] is True
    assert short["invalid_reason"] == "short"
    # the raw doc's seats ride "players" (a list), the panel reads them
    assert short["players"] == [{"profile_id": "848567", "alias": "Merlin"}]
    valid = feed._seed_card_of(
        {"match_id": "509", "started_at": 1732300000, "finished_at": 1732303600,
         "winners": ["848567"], "players_json": "[]", "options_json": ""},
    )
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


async def test_the_listing_shows_the_sealed_matches() -> None:
    """An invalidated entry renders in the five - with its status key."""
    from botforge.discord.home import _invalid_reason_type_of

    # never decided: no completion, no winner
    assert _invalid_reason_type_of(None, 0, ()) == "no_result"
    # decided but under five minutes
    assert _invalid_reason_type_of(None, 1732300180, ("848567",)) == "short"
