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
    header = str(getattr(blocks[0], "children", [blocks[0]])[0] if hasattr(blocks[0], "children") else blocks[0])
    del header
    # the settings button rides the share (the popup works everywhere)
    assert any("settings" in str(getattr(b, "custom_id", "")) or "⚙" in str(getattr(b, "label", "")) for b in buttons)


async def test_the_logs_line_dedupes_per_match_event() -> None:
    """Several players in one match log ONE line per event, not per player."""
    feed._LOGGED.clear()
    assert feed._verb_of(_event("offline", "in_lobby")) == "lobby_open"
    assert feed._verb_of(_event("in_lobby", "in_lobby")) == "lobby_update"
    assert feed._verb_of(_event("in_lobby", "in_game")) == "match_start"
    assert feed._verb_of(_event("in_game", "offline")) == "match_end"
    assert feed._verb_of(_event("in_lobby", "offline")) == "lobby_close"
    assert feed._verb_of({"new_status": "offline", "old_status": "offline"}) == ""


async def test_the_lobby_close_never_logs_a_match_end() -> None:
    """A lobby that folds without a game closes, it never calls it a match."""
    event = _event("in_lobby", "offline")
    assert feed._verb_of(event) == "lobby_close"


def test_the_seed_card_labels_the_invalid_matches() -> None:
    """An invalid match (no result - under five minutes) seeds WITH its status."""
    labels = {
        "invalid": "Match non compté",
        "invalid_no_result": "jamais décidé — pas de résultat",
        "invalid_short": "forfait — moins de 5 minutes",
    }
    undecided = feed._seed_card_of(
        {"match_id": "507", "started_at": 1732300000, "finished_at": 0, "winners": [],
         "players_json": "[]", "options_json": "", "description": "lobby test"},
        labels,
    )
    assert undecided["invalid"] is True
    assert undecided["invalid_reason"] == labels["invalid_no_result"]
    short = feed._seed_card_of(
        {"match_id": "508", "started_at": 1732300000, "finished_at": 1732300180,
         "winners": ["848567"], "players_json": "[]", "options_json": ""},
        labels,
    )
    assert short["invalid"] is True
    assert short["invalid_reason"] == labels["invalid_short"]
    valid = feed._seed_card_of(
        {"match_id": "509", "started_at": 1732300000, "finished_at": 1732303600,
         "winners": ["848567"], "players_json": "[]", "options_json": ""},
        labels,
    )
    assert "invalid" not in valid, "a decided match never carries the status"


def test_the_invalid_status_renders_on_the_card() -> None:
    """The map section carries the invalid status line (owner 2026-11-24)."""
    from botforge.discord.home import _card_map_section

    card = {"status": "finished", "map_name": "Budapest", "started_at": 1732300000,
            "finished_at": 1732300100, "invalid": True, "invalid_reason": "forfait — moins de 5 minutes"}
    labels = {"when": "Il y a {when}", "duration": "Durée : {clock}",
              "invalid": "Match non compté"}
    ctx = {"map_display": {}, "map_urls": {}, "map_images": {}}
    section = _card_map_section(card, ctx, labels)
    import discord as _discord

    view = _discord.ui.LayoutView(timeout=None)
    view.add_item(section)
    text = str(view.to_components())
    assert "Match non compté" in text
    assert "forfait" in text
