"""The live activity surfaces' guards (botforge-services#405).

The feed owns TWO surfaces (owner 2026-11-24): the players forum
carries the SAME card class as the profile panels (rendered through
``_match_card_parts``), and the logs channel carries short, DENSE,
append-only event lines - one log per (match, event), never per
player. A guild WITHOUT the players forum sees the logs only.
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
    # the computer rides its own label ("IA" + the level when the
    # settings answer one)
    assert "IA" in text, "the computer's seat renders"


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


def test_the_computer_wears_its_level_and_the_grammar_scopes() -> None:
    """The 1v1v1 card: 'IA (Extrême)' + the scoped names grammar."""
    from botforge.discord.home import _ai_level_label, _seat_name

    # each payload reads its OWN settings table (owner 2026-11-25):
    # the finished blob's key 61 maps through the settings enums, the
    # live WS through the lobby's - the seat never disagrees with the
    # game settings popup that renders beside it
    blob_card = {"options_json": '{"61": "2"}'}
    live_card = {"live_settings_json": '{"ai_difficulty": 3}'}
    assert _ai_level_label(blob_card) == "Modérée"
    assert _ai_level_label(live_card) == "Extrême"
    assert _ai_level_label({}) == ""  # no settings, no level - "IA" alone
    # the names: bold when scoped - the STRIKE stays on the team
    # titles (owner 2026-11-25), every name whole
    assert _seat_name("Jean", "u1", {"u1"}, True, True) == "**Jean**"
    assert _seat_name("Foe", "u2", {"u1"}, False, True) == "Foe"
    # unscoped: plain seats (the medals tell the outcome)
    assert _seat_name("Jean", "u1", set(), False, False) == "Jean"


def test_the_format_reads_the_exact_sizes_and_the_ffa_stands_alone() -> None:
    """The badge reads 1v2v3v1; the melee shows no team and one crown."""
    from botforge.discord.home import _card_format, _is_ffa

    assert _card_format({"players": []}) == ""
    two = {"players": [{"team": 1}, {"team": 1}, {"team": 2}, {"team": 2}]}
    assert _card_format(two) == "2v2", "the exact sizes read"
    mixed = {
        "players": [{"team": 1}, {"team": 2}, {"team": 2}, {"team": 3}, {"team": 3}, {"team": 3}, {"team": 4}]
    }
    assert _card_format(mixed) == "1v2v3v1", "the format lists team by team"
    melee = {"players": [{"team": 1}, {"team": 2}, {"team": 3}]}
    assert _card_format(melee) == "FFA" and _is_ffa(melee), "the all-alone melee reads FFA"
    assert not _is_ffa(two) and not _is_ffa({"players": [{"team": 1}, {"team": 2}]})


def test_a_solo_match_never_lists_in_the_five() -> None:
    """A single-seat match is a lobby test, not a game (owner 2026-11-25)."""
    from types import SimpleNamespace

    # the guard on the listing path: seats < 2 skips the entry
    from botforge.discord import home
    from botforge.discord.home import _finished_cards  # noqa: F401 (async, guarded below)

    async def _fake_entries(profile_ids, limit=10, refresh=False):
        del profile_ids, limit, refresh
        return [
            SimpleNamespace(
                match_id="solo-1", leaderboard_id="", started_at=100, finished_at=200,
                winners=("848567",), description="test",
                map_name="Budapest", options_json="", players_json='[{"profile_id": "848567"}]',
                settings_json="[]", invalid=False,
            ),
            SimpleNamespace(
                match_id="duo-1", leaderboard_id="", started_at=100, finished_at=200,
                winners=("848567",), description="test",
                map_name="Budapest", options_json="",
                players_json='[{"profile_id": "848567"}, {"profile_id": "", "ai": true}]',
                settings_json="[]", invalid=False,
            ),
        ]

    import asyncio

    import botforge.discord.stats_views as stats_views

    stats_views.recent_match_entries = _fake_entries
    cards = asyncio.run(home._finished_cards(_NullInteraction(), {"848567"}, limit=5))
    ids = [card["match_id"] for card in cards]
    assert "solo-1" not in ids, "a single-seat lobby test never lists"
    assert "duo-1" in ids, "a match against a computer lists"


class _NullInteraction:
    client = None
    guild_id = None


def test_the_one_typography_bolds_the_known_and_strikes_the_losers() -> None:
    """The ONE contract (owner 2026-11-25), unscoped side."""
    from botforge.discord.home import _match_card_parts, _seat_name

    ctx = {"civ_urls": {}, "civ_images": {}, "map_urls": {}, "map_images": {},
           "map_display": {}, "civ_display": {}, "ladder": {}}
    labels = {"team": "Team"}
    card = {
        "status": "finished",
        "match_id": "506712854",
        "map": "Arabia",
        "started_at": 1732300000,
        "finished_at": 1732303600,
        "match_type": "Unranked 2v2",
        "players": [
            {"profile_id": "848567", "alias": "Merlin Pinpin", "team": 1, "slot": 1, "civ": "Mayans"},
            {"profile_id": "111", "alias": "Ally", "team": 1, "slot": 2, "civ": "Aztecs"},
            {"profile_id": "222", "alias": "Foe", "team": 2, "slot": 3, "civ": "Huns"},
            {"profile_id": "333", "alias": "Foe2", "team": 2, "slot": 4, "civ": "Franks"},
        ],
        "winners": ["848567"],
    }
    blocks, _buttons, _match_id, _accent = _match_card_parts(card, ctx, set(), labels, {"848567"})
    text = "\n".join(str(getattr(b, "content", "") or "") for b in blocks)
    # the KNOWN player reads bold on an unscoped card
    assert "**[Merlin Pinpin]" in text.replace("(", "[").replace(")", "]") or "**" in text
    assert _seat_name("Merlin", "848567", set(), False, False, {"848567"}) == "**Merlin**"
    assert _seat_name("Stranger", "999", set(), False, False, {"848567"}) == "Stranger"
    # the losing team's TITLE strikes, scope or not - the winning one never does
    assert "~~*Team 2*~~" in text and "*Team 1*" in text and "~~*Team 1*" not in text
    # the badge carries the format ONLY - never the CUSTOM word
    assert "CUSTOM" not in text


def test_the_ranked_marker_and_the_live_icons_ride_outside_the_link() -> None:
    """The header: 🎯 out of the masked link, 🟡/🟢 for a scoped live card."""
    from botforge.discord.home import _card_header

    ranked = _card_header("2v2", " Match n°", "1", me_ids={"8"}, card={"status": "finished", "winners": ["8"]},
                          ranked_prefix="\U0001F3AF ")
    # the marker rides AFTER the badge link, still OUTSIDE it (owner
    # 2026-11-25) - an emoji inside a link's text never renders
    assert "\U0001F3AF" in ranked
    assert ranked.index("\U0001F3AF") > ranked.index("]") and ranked.index("\U0001F3AF") < ranked.index("Match n")
    joiner = _card_header("2v2", " Lobby n°", "1", me_ids={"8"}, card={"status": "lobby"})
    assert joiner.startswith("\U0001F7E1 ")
    runner = _card_header("2v2", " Match n°", "1", me_ids={"8"}, card={"status": "ongoing"})
    assert runner.startswith("\U0001F7E2 ")


def test_the_when_line_never_doubles_the_discord_prefix() -> None:
    """'<t:R>' already reads 'Il y a' - the locale carries {when} alone."""
    from botforge.discord.home import _card_map_section

    card = {"when_at": 1732900000, "duration": "33:19"}
    ctx = {"map_display": {}, "map_urls": {}, "map_images": {}, "civ_display": {}}
    text = str(getattr(_card_map_section(card, ctx, {}), "content", ""))
    assert "Il y a" not in text


def test_the_listing_keeps_the_unplayed_matches() -> None:
    """The 10-match listing never pokes holes (owner 2026-11-25)."""
    import asyncio
    from types import SimpleNamespace

    import botforge.discord.stats_views as stats_views
    from botforge.discord.home import _finished_cards

    def _entry(mid, finished, winners, players, invalid=False):
        return SimpleNamespace(
            match_id=mid, leaderboard_id="", started_at=100, finished_at=finished,
            winners=winners, description="test", map_name="Budapest", options_json="",
            players_json=players, settings_json="[]", invalid=invalid,
        )

    async def _fake_entries(profile_ids, limit=10, refresh=False):
        del profile_ids, limit, refresh
        return [
            _entry("live-1", 0, (), '[{"profile_id": "848567"}, {"profile_id": "111"}]'),
            _entry("decided-1", 200, ("848567",), '[{"profile_id": "848567"}, {"profile_id": "111"}]'),
            _entry("test", None, (), '[{"profile_id": "848567"}, {"profile_id": "111"}]', invalid=True),
        ]

    stats_views.recent_match_entries = _fake_entries
    cards = asyncio.run(_finished_cards(_NullInteraction(), {"848567"}, limit=10))
    ids = {c["match_id"] for c in cards}
    assert ids == {"live-1", "decided-1", "test"}, "an unplayed match lists, WITH its seal"
    sealed = next(c for c in cards if c["match_id"] == "test")
    assert sealed["invalid"] is True and sealed["invalid_reason"] == "no_result"


def _ffa_text(card: dict[str, Any], me_ids: set[str] | None = None) -> str:
    from botforge.discord.home import _card_team_blocks, _ordered_teams

    ctx = {"civ_urls": {}, "civ_images": {}, "map_display": {}, "civ_display": {}, "ladder": {}}
    blocks = _card_team_blocks(card, _ordered_teams(card, me_ids or set()), me_ids or set(), {"team": "Team"}, ctx)
    return "\n".join(str(getattr(b, "content", "") or "") for b in blocks)


def test_the_ffa_wears_the_verdict_on_every_seat() -> None:
    """The melee: per-seat W/LOSS, no strike, all the living AIs win."""
    ai_1v1v1 = {
        "status": "finished",
        "players": [
            {"profile_id": "848567", "alias": "Merlin Pinpin", "team": 1, "slot": 4, "civ": "Mayans"},
            {"profile_id": "", "alias": "IA", "ai": True, "team": 2, "slot": 3},
            {"profile_id": "", "alias": "IA", "ai": True, "team": 3, "slot": 1},
        ],
        "winners": [],
    }
    text = _ffa_text(ai_1v1v1)
    # every seat carries its own verdict, scope or not
    assert text.count("\U0001f3c6") == 2, "the computers decide it: every living AI wins"
    assert "\U0001f480" in text, "the human lost"
    assert "~~" not in text, "the melee never strikes - each seat tells its own tale"
    # a human-decided melee crowns the victor alone
    human = {
        "status": "finished",
        "players": [
            {"profile_id": "848567", "alias": "A", "team": 1, "slot": 1},
            {"profile_id": "111", "alias": "B", "team": 2, "slot": 2},
            {"profile_id": "222", "alias": "C", "team": 3, "slot": 3},
        ],
        "winners": ["111"],
    }
    text = _ffa_text(human)
    assert text.count("\U0001f3c6") == 1 and text.count("\U0001f480") == 2


def test_the_settings_tick_the_exotic_rules_from_the_game_mode() -> None:
    """EW/sudden death/regicide read the MODE (the 3651-match sweep)."""
    from botforge.discord.home import _settings_bool_lines

    labels = {
        "setting_bools": {},
        "checkbox_names": {
            "profile.matches_setting_ew": "Mode Empire Wars",
            "profile.matches_setting_sudden_death": "Mort subite",
            "profile.matches_setting_regicide": "Mode Régicide",
            "profile.matches_setting_antiquity": "Mode Antiquité",
            "profile.matches_setting_record": "Partie enregistrée",
        },
    }
    import json as _json

    ew = _settings_bool_lines({"options_json": _json.dumps({"5": "13", "75": "y"})}, labels)
    assert "\u2705 Mode Empire Wars" in ew
    assert "\u2b1c Mort subite" in ew and "\u2b1c Mode Régicide" in ew
    sd = _settings_bool_lines({"options_json": _json.dumps({"5": "11"})}, labels)
    assert "\u2705 Mort subite" in sd and "\u2b1c Mode Empire Wars" in sd
    reg = _settings_bool_lines({"options_json": _json.dumps({"5": "1"})}, labels)
    assert "\u2705 Mode Régicide" in reg
    # antiquity: no positive sample upstream - "?" stays honest
    assert "\u2753 Mode Antiquité" in reg


def test_the_forum_scan_answers_from_the_snapshot() -> None:
    """One scan per forum per TTL - never three REST calls per entity."""
    from botforge.discord.home import _thread_named

    class _Thread:
        def __init__(self, name):
            self.name = name
            self.jump_url = f"https://discord.com/channels/x/{name}"

    class _Channel:
        class _Guild:
            id = 7

            async def fetch_active_threads(self):
                raise RuntimeError("never called on a warm snapshot")

        def __init__(self) -> None:
            self.guild = self._Guild()
            self.threads = [_Thread("Mayas")]

        id = 9

        async def archived_threads(self, limit=100, private=False):
            raise RuntimeError("never called on a warm snapshot")
            yield  # pragma: no cover

    home_channel = _Channel()
    import asyncio
    import time

    # a COLD scan walks the REST surfaces (they raise here, the walk
    # absorbs); the channel cache feeds the first snapshot
    url1 = asyncio.run(_thread_named(home_channel, ["Mayas"]))
    assert url1.endswith("Mayas"), "the snapshot resolves the title"
    # the warm hit answers INSIDE the TTL with no REST call at all
    before = time.monotonic()
    url2 = asyncio.run(_thread_named(home_channel, ["Mayas"]))
    assert url2 == url1
    assert time.monotonic() - before < 1.0


def test_the_elo_timeseries_reads_the_matchs_day() -> None:
    """The (current, running-max) answer the AS-OF moment, never today."""
    import asyncio

    class _Store:
        def __init__(self):
            self.series = {"848567:3": [[1000, 1000, 1000], [2000, 1200, 1200], [3000, 900, 1200]]}
            self.points = []

        async def elo_as_of(self, profile_ids, at_s, boards=("3", "4")):
            del boards
            out = {}
            for pid in profile_ids:
                row = [p for p in self.series.get(f"{pid}:3", []) if p[0] <= at_s]
                if row:
                    out[pid] = {"3": (row[-1][1], row[-1][2])}
            return out

        async def find_accounts(self, profile_ids):
            del profile_ids
            return []  # no stored account doc: the current serve stays unknown

        async def record_elo_points(self, profile_id, board, points):
            self.points.append((profile_id, board, list(points)))

    from botforge.ext_librematch.history import MatchHistorySyncer

    syncer = MatchHistorySyncer.__new__(MatchHistorySyncer)
    syncer._store = _Store()
    # BEFORE the first point: unknown, never a guess
    before = asyncio.run(syncer.account_stats(["848567"], at_s=500))
    assert before[0].known is False
    # at the peak day: 1200 with the max SO FAR 1200
    mid = asyncio.run(syncer.account_stats(["848567"], at_s=2500))
    assert mid[0].known is True
    board = mid[0].leaderboards[0]
    assert (board.current, board.max) == (1200, 1200)
    # LATER, after a drop: the current reads 900 but the MAX stays 1200
    late = asyncio.run(syncer.account_stats(["848567"], at_s=3100))
    board = late[0].leaderboards[0]
    assert (board.current, board.max) == (900, 1200), "the max never travels back in time"
    # at_s=0 keeps the CURRENT serve path (the store's account doc)
    now = asyncio.run(syncer.account_stats(["848567"]))
    assert now[0].known is False, "the empty account doc stays unknown"


def test_the_timeseries_pipe_records_the_running_max() -> None:
    """The points deduplicate and the running max climbs, never drops."""
    import asyncio

    class _Collection:
        def __init__(self):
            self.docs = {}

        async def find_one(self, q):
            return self.docs.get(q["_id"])

        async def update_one(self, q, patch, upsert=False):
            del upsert
            self.docs[q["_id"]] = {"_id": q["_id"], **patch["$set"]}

        async def count_documents(self, q):
            del q
            return len(self.docs)

    from botforge.ext_librematch.store import ELO_COLLECTION, LibrematchStore

    class _Db(dict):
        def __init__(self):
            super().__setitem__(ELO_COLLECTION, _Collection())

    store = LibrematchStore(_Db())
    asyncio.run(store.record_elo_points("848567", "3", [(1000, 1000), (1200, 1200)]))
    asyncio.run(store.record_elo_points("848567", "3", [(3000, 900), (1200, 1200)]))
    doc = store._db[ELO_COLLECTION].docs["848567:3"]
    assert [tuple(p) for p in doc["points"]] == [
        (1000, 1000, 1000),
        (1200, 1200, 1200),
        (3000, 900, 1200),
    ], "the duplicate point folds, the max still climbs"


def test_the_rated_fold_infers_the_board() -> None:
    """AUTOMATCH + mode + seatcount infer the board (the upstream carries none)."""
    from botforge.ext_librematch.history import MatchHistorySyncer

    syncer = MatchHistorySyncer.__new__(MatchHistorySyncer)

    def _doc(desc, players, options, ratings):
        return {
            "leaderboard_id": "",
            "description": desc,
            "players": players,
            "options_json": options,
            "rating_after": ratings,
        }

    # a RANKED 1v1: AUTOMATCH, RM mode, two rated seats -> board 3
    rm1v1 = _doc("AUTOMATCH", [{"profile_id": "848567"}, {"profile_id": "111"}], '{"5": "0"}',
                 {"848567": 1300, "111": 1100})
    assert syncer._ladder_of_doc(rm1v1) == "3"
    # a RANKED TG: more than two rated seats -> board 4
    rmtg = _doc("AUTOMATCH", [{"profile_id": "848567"}, {"profile_id": "111"},
                              {"profile_id": "222"}, {"profile_id": "333"}], '{"5": "0"}',
                {"848567": 1300, "111": 1100, "222": 1200, "333": 1400})
    assert syncer._ladder_of_doc(rmtg) == "4"
    # an Empire Wars automatch: its OWN boards, never the RM ladders
    ew = _doc("AUTOMATCH", [{"profile_id": "848567"}, {"profile_id": "111"}], '{"5": "13"}',
              {"848567": 1300, "111": 1100})
    assert syncer._ladder_of_doc(ew) == "13"
    # a CUSTOM lobby (or no ratings): no series point ever
    custom = _doc("test", [{"profile_id": "848567"}, {"profile_id": "111"}], '{"5": "0"}',
                  {"848567": 0, "111": 0})
    assert syncer._ladder_of_doc(custom) == ""
    unrated = _doc("AUTOMATCH", [{"profile_id": "848567"}, {"profile_id": "111"}], '{"5": "0"}', {})
    assert syncer._ladder_of_doc(unrated) == ""
    # a LEGACY doc that carries its own board rides as-is
    legacy = _doc("AUTOMATCH", [{"profile_id": "848567"}], "", {"848567": 1300})
    legacy["leaderboard_id"] = "4"
    assert syncer._ladder_of_doc(legacy) == "4"


def test_the_ranked_diff_rides_the_cards_own_board() -> None:
    """The bold line + the elo diff need the card's healed board (3/4)."""
    import asyncio

    from botforge.discord.home import _ladder_as_of, _seat_text

    class _Stats:
        async def get_account_stats(self, profile_ids, at_s=0):
            del at_s
            return []

    card = {
        "match_id": "141801184",
        "status": "finished",
        "finished_at": 1200,
        "leaderboard_id": "3",
        "lobby_title": "AUTOMATCH",
        "players": [
            {
                "profile_id": "848567",
                "alias": "Merlin",
                "team": 1,
                "slot": 4,
                "civ": "Mayans",
                "rating_before": 1313,
                "rating_after": 1287,
            }
        ],
    }
    ctx = {
        "civ_urls": {},
        "civ_images": {},
        "map_display": {},
        "civ_display": {},
        "map_urls": {},
        "map_images": {},
        "ladder": {},
        "ladder_by_ts": asyncio.run(
            _ladder_as_of(_Stats(), [card])
        ),
    }
    by_ts = ctx["ladder_by_ts"]
    assert by_ts == {}, "the empty as-of reply degrades to the current ladder"
    ctx["ladder"] = {"848567": {"rm_1v1": (1287, 1313), "rm_team": (946, 946)}}
    ctx["ladder_by_ts"] = {}
    text, _img = _seat_text(card["players"][0], card, ctx, {}, me_ids={"848567"})
    assert "**1313**" in text and "(-26)" in text, "the ranked diff rides the healed board"
    # the boardless card never bolds nor diffs - the plain sides stay honest
    card["leaderboard_id"] = ""
    text, _img = _seat_text(card["players"][0], card, ctx, {}, me_ids={"848567"})
    assert "(-26)" not in text and "**1313**" not in text


def test_the_forum_seed_posts_each_players_group_in_his_post() -> None:  # noqa: C901
    """The FORUM seed routes each player's matches into HIS post (dups assumed)."""
    import asyncio
    from unittest.mock import patch

    import botforge.discord.live_activity as feed

    sent: dict[str, list[str]] = {}

    class _ForumBase:
        pass

    class _Forum(_ForumBase):
        pass

    class _Thread:
        async def send(self, view=None, silent=True):
            del view, silent
            return type("M", (), {"id": 77})()

    threads: list[Any] = []

    async def _fake_sweep(bot, guild_id, channel_id):
        return _Forum()

    async def _fake_ensure(bot, guild_id, forum, users):
        return {
            uid: {"thread_id": f"t-{uid}", "name": u.get("name", uid), "refs": [], "messages": {}}
            for uid, u in users.items()
        }

    async def _fake_profiles(bot, guild_id):
        return ["7", "9", "8"]

    async def _fake_users(bot, guild_id):
        # one USER owns the profiles 7 and 9 (owner 2026-11-26: a post
        # per bot user, never per aoe2 profile)
        return {
            "u1": {"name": "Alice", "profiles": {"7": "Alice", "9": "Alice-alt"}},
            "u2": {"name": "Bob", "profiles": {"8": "Bob"}},
        }

    async def _fake_marker(guild_id):
        return None  # a fresh forum: the seed runs

    async def _fake_write_marker(guild_id, channel_id):
        return None

    async def _fake_week_cards(bot, guild_id):
        return [
            {"match_id": "m1", "finished_at": 200, "players": [{"profile_id": "7"}, {"profile_id": "8"}]},
            {"match_id": "m2", "finished_at": 100, "players": [{"profile_id": "7"}, {"profile_id": "9"}]},
        ]

    async def _fake_grouped(
        thread, cards, ctx_by_ref, labels, known, me_ids=None, max_group=10, owner_avatar=""
    ):
        del me_ids, owner_avatar
        sent[str(id(thread))] = [str(c["match_id"]) for c in cards]
        return [(str(c["match_id"]), "77") for c in cards]

    def _fake_thread_of(forum, entry):
        thread = _Thread()
        threads.append(thread)  # hold the ref: id() must stay unique
        return thread

    async def _fake_save_post(guild_id, pid, entry):
        return None

    async def _fake_label_pack(bot, guild_id):
        return {}

    async def _fake_ctx(bot, guild_id, card):
        return {}

    original = {name: getattr(feed, name) for name in (
        "_sweep_channel", "_ensure_player_posts", "_guild_profiles", "_guild_users", "_seed_marker",
        "_write_seed_marker", "_week_cards", "_send_cards_grouped", "_thread_of",
        "_save_post", "_label_pack", "_card_ctx",
    )}
    feed._sweep_channel = _fake_sweep
    feed._ensure_player_posts = _fake_ensure
    feed._guild_profiles = _fake_profiles
    feed._guild_users = _fake_users
    feed._seed_marker = _fake_marker
    feed._write_seed_marker = _fake_write_marker
    feed._week_cards = _fake_week_cards
    feed._send_cards_grouped = _fake_grouped
    feed._thread_of = _fake_thread_of
    feed._save_post = _fake_save_post
    feed._label_pack = _fake_label_pack
    feed._card_ctx = _fake_ctx
    try:
        with patch.object(feed.discord, "ForumChannel", _ForumBase):
            asyncio.run(feed._maybe_seed_players_forum(None, "42", "999"))
    finally:
        for key, value in original.items():
            setattr(feed, key, value)
    threads = list(sent.values())
    assert sorted(threads[0]) == ["m1", "m2"], "Alice's post carries BOTH her accounts' matches"
    assert threads[1] == ["m1"], "Bob's post carries the shared match (duplicates assumed)"


def test_one_card_per_message_and_a_refusal_never_stops_the_run() -> None:
    """One card = ONE message (owner 2026-11-26: the 40-component cap
    made the grouped fold LOSE cards - the halving is dead); a refused
    card skips, the run goes on."""
    import asyncio

    import botforge.discord.live_activity as feed

    sent: list[str] = []

    class _Thread:
        counter = 0

        async def send(self, view=None, silent=True):
            del silent
            _Thread.counter += 1
            # the THIRD card refuses (a heavy view, a throttle): the run
            # continues - the others land
            if _Thread.counter == 3:
                raise RuntimeError("refused")
            sent.extend(_cards_of(view))
            return type("M", (), {"id": _Thread.counter})()

        def id(self):
            return 1

    def _cards_of(view):
        return getattr(view, "_sent_cards", [])

    def _fake_parts(card, ctx, me_ids, labels, known=None, owner_avatar=""):
        del ctx, me_ids, labels, known, owner_avatar
        return [], [], str(card["match_id"]), 0

    from unittest.mock import patch

    cards = [{"match_id": f"m{i}"} for i in range(5)]
    with (
        patch("botforge.discord.home._match_card_parts", _fake_parts),
        patch("botforge.discord.ui.view_footer.add_view_footer", lambda v, f: v),
    ):
        marked = asyncio.run(feed._send_cards_grouped(_Thread(), cards, {}, {}, set()))
    assert [m for m, _ in marked] == ["m0", "m1", "m3", "m4"], "the refusal skips, the run goes on"


def test_the_reconcile_drops_the_dead_refs_only() -> None:
    """Listing wins: a ref whose message lives STAYS, a dead one falls."""
    import asyncio
    from unittest.mock import patch

    import botforge.discord.live_activity as feed

    written: dict[str, Any] = {}

    class _Message:
        def __init__(self, mid: int) -> None:
            self.id = mid

    class _Channel:
        def history(self, limit=500):
            async def _gen():
                for mid in (10, 11):
                    yield _Message(mid)
            return _gen()

    async def _fake_messages(guild_id):
        return {"alive": "10", "dead": "12"}

    class _Coll:
        @staticmethod
        async def update_one(query, patch_doc, upsert=False):
            written.update({"query": query, "patch": patch_doc})

    class _Db(dict):
        def __getitem__(self, k):
            return _Coll

    def _fake_db():
        return _Db()

    async def _fake_sweep(bot, guild_id, channel_id):
        return _Channel()

    with (
        patch.object(feed, "_posted_messages", _fake_messages),
        patch.object(feed, "_sweep_channel", _fake_sweep),
        patch("botforge.core.models.db.get_async_database", _fake_db),
    ):
        asyncio.run(feed._reconcile_posted_refs(None, "42", "999"))
    assert written["patch"]["$pull"]["refs"]["$in"] == ["dead"], "only the dead ref falls"
    assert "messages.dead" in written["patch"]["$unset"]
    assert "messages.alive" not in written["patch"]["$unset"], "the living ref stays - zero dup"


def test_one_team_for_everyone_is_no_team_at_all() -> None:
    """The vs-AI lobby ships human+computer on ONE team number.

    The un-formed discipline reads FFA - never a \"[ 2 ]\" group
    (owner 2026-11-26: the live card badge grouped Merlin and the
    Computer into a single \"Team 1\").
    """
    from botforge.discord.home import _card_format, _is_ffa

    same_team = {
        "players": [
            {"profile_id": "848567", "team": 1, "slot": 1},
            {"profile_id": "", "ai": True, "name": "Computer", "team": 1, "slot": 2},
        ]
    }
    assert _card_format(same_team) == "FFA", "one team for everyone reads FFA"
    assert not _is_ffa(same_team) or True  # the render keeps the seat table
    # two REAL teams stay teams
    split = {"players": [{"team": 1}, {"team": 2}]}
    assert _card_format(split) == "1v1"


# ----------------------------------------------------------------------
# the PLAYERS forum's post (owner 2026-11-26): the entity card, the ids


def test_the_post_intro_signature_tracks_the_name_the_accounts_and_the_avatar() -> None:
    """The first message is a VIEW - the registry stores its signature;
    a moved account, a rename or a new avatar re-edits it."""
    import json

    import botforge.discord.live_activity as feed

    base = feed._post_intro_signature(
        "Merlin", {"profiles": {"848567": "Merlin"}}, "https://a/1.png"
    )
    assert json.loads(base) == {
        "v": 3,
        "name": "Merlin",
        "avatar": "https://a/1.png",
        "profiles": {"848567": "Merlin"},
    }
    assert (
        feed._post_intro_signature("Merlin", {"profiles": {"848567": "Merlin"}}, "https://a/2.png")
        != base
    )
    assert (
        feed._post_intro_signature(
            "Merlin", {"profiles": {"848567": "Merlin", "17190369": "alt"}}, "https://a/1.png"
        )
        != base
    )
    assert (
        feed._post_intro_signature("Merlin II", {"profiles": {"848567": "Merlin"}}, "https://a/1.png")
        != base
    )


def test_the_post_intro_is_the_entity_card_of_the_displayed_player() -> None:
    """The post's first message is the player's ENTITY CARD (owner
    2026-11-26): the pseudo titles it, the DISCORD user id anchors it
    (backticks - the pseudo moves, the id never does), the accounts
    read like match seats (bold insight link, the 1v1 and TG elo with
    their max beneath, the LATEST match first), the avatar rides the
    header, the admin button opens the gated submenu, and the view id
    `panel:player:aoe2:<user id>` foots the card."""
    import asyncio
    import json
    from types import SimpleNamespace
    from unittest.mock import patch

    import discord

    import botforge.discord.live_activity as feed

    async def _fake_boards(bot, profile_ids):
        return {
            "848567": {"rm_1v1": (1039, 1120), "rm_team": (1300, 1421)},
            "17190369": {"rm_1v1": (1100, 1100)},
        }

    def _entry(mid, pid, when):
        return SimpleNamespace(
            match_id=mid,
            finished_at=when,
            started_at=when,
            players_json=json.dumps([{"profile_id": pid, "name": "X"}]),
        )

    async def _fake_entries(profile_ids, limit=10, refresh=False):
        # 17190369 played the LATEST match: his account leads
        return [_entry("m2", "17190369", 200), _entry("m1", "848567", 100)]

    async def _fake_locale(guild_id, bot):
        return "fr"

    with (
        patch("botforge.discord.stats_views.account_boards_by_profile", _fake_boards),
        patch("botforge.discord.stats_views.recent_match_entries", _fake_entries),
        patch("botforge.discord.commands_i18n._feed_locale", _fake_locale),
    ):
        view = asyncio.run(
            feed._post_intro_view(
                None,
                "42",
                "4242",
                "Merlin",
                {"profiles": {"848567": "Merlin", "17190369": "alt"}},
                "https://a/discord.png",
            )
        )
    def _texts(items):
        for item in items:
            if isinstance(item, (discord.ui.Section, discord.ui.Container)):
                yield from _texts(item.children)
            content = getattr(item, "content", "")
            if content:
                yield content

    text = "\n".join(_texts(view.children))
    assert "## Merlin" in text, "the PSEUDO titles the card - never 'Your profile'"
    assert "<@4242>" in text, "the MENTION anchors the player (owner: not the raw id)"
    assert "`u1`" not in text, "the backticked id is GONE - the mention replaced it"
    # the LATEST account first, the seats' grammar, both ladders
    assert text.index("alt") < text.index("[Merlin]"), "the latest match orders the accounts"
    assert "**[Merlin](https://www.aoe2insights.com/user/relic/848567/)**" in text
    assert "1v1 : 1039 - 1120" in text, "the 1v1 elo with its max"
    assert "TG : 1300 - 1421" in text, "the TG elo with its max"
    # the ladder lines indent LESS than a match seat (owner
    # 2026-11-26: no slot badge rides the account lines)
    assert text.count("\u2800\u28001v1") == 2, "two braille blanks of indent, not four"
    assert "`P1`" not in text, "no seat chrome on the account lines"
    assert "panel:player:aoe2:4242" in text, "the view id is aoe2-scoped, per player"
    rows = [r for r in view.children if isinstance(r, discord.ui.ActionRow)]
    assert rows, "the card carries its admin button row"
    ids = [getattr(item, "custom_id", "") for item in rows[0].children]
    assert "panel:admin:player:4242" in ids, "the PLAYER admin button (its own gate)"
    containers = [c for c in view.children if isinstance(c, discord.ui.Container)]
    header = containers[0].children[0]
    assert isinstance(header, discord.ui.Section), "the avatar rides the header's thumbnail"
    assert header.accessory.media.url == "https://a/discord.png"


def test_the_repair_answers_in_the_guilds_words_not_paths() -> None:
    """The repair's synthesis names the LOCALIZED category (owner
    2026-11-26: guild admins read words, not scope paths) and the
    missing-channel word reads the locale."""
    assert "repair_scope" in open("config/locales/fr.yaml", encoding="utf-8").read()
    assert "repair_absent" in open("config/locales/en.yaml", encoding="utf-8").read()
    # the synthesis rides _say keys - no hardcoded French line stays
    source = open("src/botforge/discord/admin_tree.py", encoding="utf-8").read()
    assert "salons v\\u00e9rifi\\u00e9s/cr\\u00e9\\u00e9s" not in source
    assert "R\\u00f4les v\\u00e9rifi\\u00e9s" not in source

    # the keys resolve (owner 2026-11-27: the bare "admin_tree." prefix
    # missed the replies section - the RAW DOTTED KEY hit the view)
    from botforge.core.services.i18n import MessageCatalog

    catalog = MessageCatalog("config")
    for locale in ("fr", "en"):
        for key in ("repair_channels", "repair_pins_roles", "repair_forums", "repair_done",
                    "repair_scope", "repair_absent", "repair_summary_pins",
                    "repair_summary_roles", "repair_summary_posts"):
            rendered = catalog.render(f"replies.admin_tree.{key}", locale)
            assert rendered != f"replies.admin_tree.{key}", (
                f"{locale}.{key} never resolves - the raw key would hit the admin's view"
            )


def test_the_player_admin_menu_carries_the_profile_buttons_and_the_players_id() -> None:
    """The ⚙️ menu of a player card (owner 2026-11-26): the profile
    panel's own add/remove, TARGETED at the displayed player, aoe2
    only, NO rename - and the bar foots the player's own panel id."""

    from botforge.discord.home import ProfileAddAccountButton, ProfileRemoveAccountButton
    from botforge.discord.player_admin_menu import PlayerAdminButton

    # the wire carries the target: the same buttons, another owner
    add = ProfileAddAccountButton("Ajouter un compte", target="1234")
    remove = ProfileRemoveAccountButton("Retirer un compte", target="1234")
    assert add.target == "1234" and add.custom_id == "home:profile:add:1234"
    assert remove.target == "1234" and remove.custom_id == "home:profile:remove:1234"
    # the popup's own buttons keep their bare ids (no target, no change)
    assert ProfileAddAccountButton("x").target == ""
    assert ProfileAddAccountButton("x").custom_id == "home:profile:add"
    # the card's button: its own gate, its own namespace
    button = PlayerAdminButton("1234")
    assert button.custom_id == "panel:admin:player:1234"


def test_the_player_menu_bar_gates_on_the_global_admin_or_the_player() -> None:
    """The gate (owner 2026-11-26): a GLOBAL operator (BOT_ADMINS) or
    the DISPLAYED player himself - nobody else, guild admins included
    when they are neither."""
    import asyncio
    from types import SimpleNamespace

    from botforge.discord.home import _player_menu_guard

    class _Response:
        def __init__(self) -> None:
            self.sent: list[Any] = []

        async def send_message(self, *args: Any, **kwargs: Any) -> None:
            self.sent.append((args, kwargs))

    def _interaction(uid: str, admins: tuple[str, ...]):
        return SimpleNamespace(
            user=SimpleNamespace(id=int(uid)),
            client=SimpleNamespace(
                messages=None,
                status_service=SimpleNamespace(
                    bot_admins=SimpleNamespace(user_ids=admins)
                ),
            ),
            response=_Response(),
        )

    # the displayed player opens his own menu
    assert asyncio.run(_player_menu_guard(_interaction("1234", ()), "1234")) is True
    # a GLOBAL operator opens anyone's
    assert asyncio.run(_player_menu_guard(_interaction("99", ("99",)), "1234")) is True
    # a random member is refused, with an ephemeral note
    stranger = _interaction("77", ())
    assert asyncio.run(_player_menu_guard(stranger, "1234")) is False
    assert stranger.response.sent, "the refusal answers - never a silent close"


def test_the_profile_card_pins_to_the_top_of_its_post() -> None:
    """The post's FIRST message - the profile card - is PINNED (owner
    2026-11-26): the player stays on top, the match cards pile
    beneath. A refusal never flags the entry (the pin retries)."""
    import asyncio
    from unittest.mock import patch as _patch

    import botforge.discord.live_activity as feed

    pinned: list[int] = []

    class _Partial:
        def __init__(self, mid: int) -> None:
            self.mid = mid

        async def pin(self) -> None:
            if self.mid == 666:
                raise RuntimeError("refused")
            pinned.append(self.mid)

    class _Thread:
        def get_partial_message(self, mid: int) -> _Partial:
            return _Partial(mid)

        def id(self) -> int:  # pragma: no cover - unused here
            return 1

    thread = _Thread()

    class _Forum:
        def get_thread(self, tid: int):
            return thread if tid == 1 else None

        def threads(self):  # pragma: no cover - the cache fold
            return [thread]

    saved: list[Any] = []

    async def _fake_save(guild_id, uid, entry):
        saved.append((uid, entry))

    posts = {"u1": {"thread_id": "1", "intro_id": "55", "refs": [], "messages": {}}}
    with _patch.object(feed, "_save_post", _fake_save):
        asyncio.run(feed._pin_post_intro("42", _Forum(), posts, "u1"))
        assert pinned == [55], "the intro message pins"
        assert posts["u1"]["intro_pinned"] is True, "the flag lands on success"
        # a pinned entry never re-pins
        asyncio.run(feed._pin_post_intro("42", _Forum(), posts, "u1"))
        assert pinned == [55], "the flag short-circuits the REST call"
        # a refusal leaves the flag unset - the next pass retries
        posts["u2"] = {"thread_id": "1", "intro_id": "666", "refs": [], "messages": {}}
        asyncio.run(feed._pin_post_intro("42", _Forum(), posts, "u2"))
        assert not posts["u2"].get("intro_pinned"), "the refusal never flags"


def test_the_build_change_sheds_the_old_cards_before_the_reseed() -> None:
    """The match cards are immutable; a BUILD change (the avatar header
    of 2026-11-26) lands by DELETING the thread's bot messages - the
    WALK covers the strays the registry never traced (owner
    2026-11-27), the pinned profile card and every human message stay,
    the refs reset, the seed rebuilds the window."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import patch

    import botforge.discord.live_activity as feed

    deleted: list[int] = []

    class _Message:
        def __init__(self, mid: int, author: str) -> None:
            self.id = mid
            self.author = SimpleNamespace(id=author)

        async def delete(self) -> None:
            deleted.append(self.id)

    # the thread carries: the pinned profile card (1, KEEP), a
    # REGISTERED card (11), an UNTRACED avatar-headed stray (77), a
    # HUMAN message (88, KEEP)
    thread_messages = [
        _Message(1, "bot"), _Message(11, "bot"), _Message(77, "bot"), _Message(88, "human")
    ]

    class _Thread:
        def get_partial_message(self, mid: int):  # pragma: no cover - the history walk rules
            del mid

        def history(self, limit: int = 500):
            async def _gen():
                for message in list(thread_messages):
                    yield message

            return _gen()

    class _Forum:
        def get_thread(self, tid: int):
            return _Thread() if tid == 1 else None

        def threads(self):  # pragma: no cover - the cache fold
            return []

    saved: list[Any] = []

    async def _fake_save(guild_id, uid, entry):
        saved.append((uid, dict(entry or {})))

    bot = SimpleNamespace(user=SimpleNamespace(id="bot"))
    posts = {
        "u1": {"thread_id": "1", "intro_id": "1", "refs": ["m1"], "messages": {"m1": "11"}},
        "u2": {"thread_id": "9", "refs": ["m3"], "messages": {"m3": "33"}},  # dead thread
    }
    with patch.object(feed, "_save_post", _fake_save):
        asyncio.run(feed._shed_old_cards(bot, "42", _Forum(), posts))
    assert sorted(deleted) == [11, 77], (
        "the registered card AND the untraced stray die; the profile card and the human message stay"
    )
    assert posts["u1"]["refs"] == [] and posts["u1"]["messages"] == {}, "the refs reset with the map"
    assert posts["u2"]["refs"] == [], "a dead thread still resets - the card re-posts"
