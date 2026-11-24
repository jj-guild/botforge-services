"""The AoE2 activity surfaces: the matches salon + the logs channel.

Every match involving a linked player lives in TWO surfaces, each with
its own contract (owner 2026-11-24):

- the MATCHES salon (``games/aoe2/matches``): ONE rich message per
  (guild, match) \u2014 the very same card class as the profile panels
  (owner 2026-11-23: "tu n'utilises pas la m\u00eame classe" \u2014 the
  dashboard and the feed both render through ``_match_card_parts``):
  the contextual AoE2 header, the seats, the links, the settings
  button. The card LIVES with the match (lobby \u2192 in game \u2192
  finished \u2192 the real result) and the salon reads as the guild's
  AoE2 history. When the salon does not exist, NOTHING is sent (the
  tree owns the channel: no adoption, no fallback).

  On the salon's very first use the LAST WEEK of stored history seeds
  the channel, OLDEST first: the valid matches AND the invalid ones
  (no result, under five minutes) \u2014 an invalid match still shows,
  with its status (owner 2026-11-24).

- the LOGS channel (``bot/logs``): very short, DENSE, append-only
  event lines \u2014 one log per (match, event), never per player (a
  match with several linked players logs once). Components V2, one
  accent-coloured container, emphasis and links, no image; the
  messages are NEVER edited \u2014 the logs are a journal, the cards
  (the matches salon) carry the living state.

The source is the game service's ``WatchPlayerEvents`` stream (the
enrollments already subscribe the provider to the guilds' linked
profile ids); the loop is resilient (a stream break reconnects, a
send failure never kills the feed).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

import discord

logger = logging.getLogger("botforge.live_activity")

__all__ = ["start_live_activity_feed"]

# the seed sweep: a salon created (or repaired) after the boot seeds
# within this window - the seed never waits on the next match event
_SEED_SWEEP_S = 300.0

# the seed's BUILD: a seed producing broken cards gets versioned up -
# every salon re-seeds once with the fixed build (the old cards stay,
# the guild owns its channel)
_SEED_VERSION = 3

_MATCHES_SCOPE = "games/aoe2"
_MATCHES_KEY = "matches"
# the seed window: the salon's first use replays the last WEEK
_SEED_WINDOW_S = 7 * 86400
# an invalid match (owner 2026-11-24): under 5 minutes or no result
_INVALID_DURATION_S = 5 * 60

# (guild, match_ref) -> the sent message (the LIVING card)
_CARDS: dict[tuple[str, str], Any] = {}
# (guild, match_ref) -> the card's current model (re-rendered in place)
_CARD_STATE: dict[tuple[str, str], dict[str, Any]] = {}
# (guild, match_ref) -> the first-seen epoch s (the live card's "since")
_FIRST_SEEN: dict[tuple[str, str], int] = {}
# the last known summary per match - the end card keeps the context
_LAST_SUMMARY: dict[str, dict[str, Any]] = {}
# the last in-game name seen per profile (labels survive the offline event)
_LAST_NAME: dict[str, str] = {}
# the match's profiles + started-at epoch s - the result correlation keys
_MATCH_PLAYERS: dict[str, tuple[list[str], int]] = {}
# the (guild, match_ref, verb) events already logged this boot (one log per event)
_LOGGED: set[tuple[str, str, str]] = set()
# the guilds whose matches salon already saw their week of history
_SEEDED: set[str] = set()
# the fire-and-forget tasks (kept alive until they finish)
_BG_TASKS: set[asyncio.Task[Any]] = set()

# per-guild render memos (labels, then the civ/map enrichment): the
# feed re-renders cards on every event delta - the label pack and the
# civ/map posts resolve once per window, never per event
_LABELS_MEMO: dict[str, tuple[float, dict[str, Any]]] = {}
_CTX_MEMO: dict[tuple[str, str, str], tuple[float, dict[str, Any]]] = {}
_MEMO_TTL_S = 600.0

# the accent of the logs line per verb (verdict at a glance, dense)
_LOG_ACCENTS = {
    "lobby_open": 0xF1C40F,  # yellow: a lobby stands
    "lobby_update": 0x99AAB5,  # grey: a tweak, nothing more
    "lobby_close": 0x71368A,  # purple: the lobby left, nothing ran
    "match_start": 0x2ECC71,  # green: the game runs
    "match_end": 0x9B59B6,  # the finished verdict
}


async def _label_pack(bot: discord.Client, guild_id: str) -> dict[str, Any]:
    """Resolve the guild's match-panel label pack - memoized per window."""
    from botforge.discord.home import _match_panel_labels_guild

    cached = _LABELS_MEMO.get(guild_id)
    if cached and time.monotonic() - cached[0] < _MEMO_TTL_S:
        return cached[1]
    labels = await _match_panel_labels_guild(guild_id, bot)
    _LABELS_MEMO[guild_id] = (time.monotonic(), labels)
    return labels


async def _card_ctx(bot: discord.Client, guild_id: str, card: dict[str, Any]) -> dict[str, Any]:
    """Resolve the guild's enrichment ctx for one card - memoized per window."""
    from botforge.discord.home import _match_panels_ctx_for

    civs = ",".join(
        sorted({str((p or {}).get("civ") or "") for p in card.get("players") or [] if (p or {}).get("civ")})
    )
    map_name = str(card.get("map_name") or "")
    key = (guild_id, civs, map_name)
    cached = _CTX_MEMO.get(key)
    if cached and time.monotonic() - cached[0] < _MEMO_TTL_S:
        return cached[1]
    ctx = await _match_panels_ctx_for(bot, [card], guild_id)
    _CTX_MEMO[key] = (time.monotonic(), ctx)
    return ctx


def start_live_activity_feed(bot: discord.Client) -> asyncio.Task[None] | None:
    """Run the AoE2 activity feed: matches cards + short event logs.

    One stream consumer, forever; None when the game service is not
    wired (the feed degrades to nothing, silently).
    """
    game_key = "aoe2"
    uri = os.environ.get(f"GAME_{game_key.upper()}_URI", "")
    if not uri:
        logger.info("live activity feed: no game service wired - off")
        return None

    async def _run() -> None:
        while True:
            try:
                from botforge.game_aoe2.client import GameDataClient

                client = GameDataClient(uri)
                async for event in client.stream_player_events(game_key):
                    await _deliver_event(bot, event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # UNIMPLEMENTED: the game service does not serve the
                # stream yet - retrying every 5 s forever spams both
                # logs; log once and stay idle (a restart picks it up).
                code = getattr(exc, "code", None)
                if code is not None and getattr(code(), "name", "") == "UNIMPLEMENTED":
                    logger.info("live activity feed: the stream is not served yet - staying idle")
                    return
                logger.warning("live activity feed: stream broke - reconnecting", exc_info=True)
                await asyncio.sleep(5)

    task = asyncio.create_task(_run())
    # the seed sweep watches for a freshly created (or repaired) matches
    # salon: a channel provisioned AFTER the boot seeds within the
    # sweep window - never waiting on the next match to fire an event
    seed_task = asyncio.create_task(_seed_loop(bot))

    def _log_death(task: asyncio.Task[None]) -> None:
        if not task.cancelled() and task.exception() is not None:
            logger.error("live activity feed DIED: %r", task.exception())

    task.add_done_callback(_log_death)
    seed_task.add_done_callback(_log_death)
    return task


async def _seed_loop(bot: discord.Client) -> None:
    """Sweep the guilds' matches salons for a seeding to run."""
    while True:
        for guild in list(bot.guilds):
            try:
                channel_id = await _matches_channel_id(bot, str(guild.id))
                if channel_id is None:
                    continue
                await _maybe_seed_matches_salon(bot, str(guild.id), channel_id)
            except Exception:
                logger.debug(
                    "the seed sweep skipped a guild (%s) - best-effort", guild.id, exc_info=True
                )
        await asyncio.sleep(_SEED_SWEEP_S)


async def _deliver_event(bot: discord.Client, event: dict[str, Any]) -> None:
    """Route one transition to the matches salon card + the logs line."""
    profile_id = str(event.get("profile_id", ""))
    user_id = str(event.get("user_id", ""))
    if not profile_id or not user_id:
        return
    match = event.get("match") or {}
    _remember_name(profile_id, match)
    ref = str(match.get("match_ref") or "")
    if ref and match.get("players"):
        _LAST_SUMMARY[ref] = match
    logger.info(
        "live activity EVENT: profile=%s user=%s %s->%s match=%s",
        profile_id,
        user_id,
        event.get("old_status", "?"),
        event.get("new_status", "?"),
        ref,
    )
    for guild in list(bot.guilds):
        if not await _is_guild_member(bot, guild, user_id):
            continue
        guild_id = str(guild.id)
        await _upsert_matches_card(bot, guild_id, event, profile_id)
        await _log_event_line(bot, guild_id, event, profile_id)


def _remember_name(profile_id: str, match: dict[str, Any]) -> None:
    for p in _players(match):
        if isinstance(p, dict) and str(p.get("profile_id")) == profile_id:
            name = str(p.get("name") or "")
            if name:
                _LAST_NAME[profile_id] = name


# ---------------------------------------------------------------------
# the MATCHES salon: one living card per (guild, match)


async def _matches_channel_id(bot: discord.Client, guild_id: str) -> str | None:
    """Resolve the guild's matches salon by its stored tree id.

    The tree owns the channel (owner 2026-11-24): the boot never
    creates, no name adoption - a guild without the salon sees the
    feed's logs only.
    """
    from botforge.discord.ui.panels_provisioning import stored_channel_id

    try:
        return await stored_channel_id(guild_id, _MATCHES_SCOPE, _MATCHES_KEY)
    except Exception:
        return None


async def _upsert_matches_card(
    bot: discord.Client, guild_id: str, event: dict[str, Any], profile_id: str
) -> None:
    """Create or update the guild's living card for the event's match."""
    channel_id = await _matches_channel_id(bot, guild_id)
    if channel_id is None:
        return
    match = event.get("match") or {}
    status = str(event.get("new_status", ""))
    old_status = str(event.get("old_status", ""))
    match_ref = str(match.get("match_ref") or "")
    if not match_ref:
        # an offline event carries no match: the card to touch is the
        # player's live one
        match_ref = _player_live_ref(profile_id)
    if not match_ref:
        return
    key = (guild_id, match_ref)
    if key not in _FIRST_SEEN:
        _FIRST_SEEN[key] = int(time.time())
        await _maybe_seed_matches_salon(bot, guild_id, channel_id)

    if status == "offline":
        card = _CARD_STATE.get(key)
        if card is None:
            return
        # the match ended or the lobby folded: one LAST render, then
        # the result correlation (the upstream records the true
        # outcome a few seconds later) refreshes the card in place
        ended = old_status == "in_game"
        if not ended:
            # the lobby folded without a game: the card closes,
            # no result ever comes
            await _drop_card(bot, guild_id, channel_id, match_ref, status_suffix="lobby fin")
            return
        _CARD_STATE[key] = {**card, "status": "finished", "finished_at": int(time.time())}
        await _send_card(bot, guild_id, channel_id, match_ref)
        profiles, started_at = _MATCH_PLAYERS.get(match_ref, ([], 0))
        _spawn(_fetch_result_then_update(bot, guild_id, channel_id, match_ref, profiles, started_at))
        return

    _remember_player_ref(profile_id, match_ref)
    _remember_match_profiles(match, match_ref)
    card = _CARD_STATE.get(key)
    summary = _LAST_SUMMARY.get(match_ref) or {}
    state = "lobby" if status == "in_lobby" else "ongoing"
    _CARD_STATE[key] = {
        **(card or {}),
        **_live_card_of(match_ref, summary, state, _FIRST_SEEN[key]),
    }
    await _send_card(bot, guild_id, channel_id, match_ref)


def _live_card_of(
    match_ref: str, summary: dict[str, Any], state: str, started_at: int
) -> dict[str, Any]:
    """Build the live card's model from the event's match summary.

    The SAME shape as the /live dashboard's cards - the shared
    renderer (``_match_card_parts``) reads it untouched.
    """
    from botforge.discord.home import _live_summary_players

    return {
        "status": state,
        "match_ref": match_ref,
        "match_id": match_ref,
        "started_at": started_at,
        "finished_at": 0,
        "winners": [],
        "map_name": str(summary.get("map") or ""),
        "lobby_title": str(summary.get("match_type") or "") if state == "lobby" else "",
        "description": str(summary.get("match_type") or ""),
        "players": _live_summary_players(summary),
        "lobby_url": str(summary.get("lobby_url") or ""),
        "spectate_url": str(summary.get("spectate_url") or ""),
        "live_settings_json": str(summary.get("settings_json") or ""),
    }


async def _send_card(
    bot: discord.Client,
    guild_id: str,
    channel_id: str,
    match_ref: str,
) -> None:
    """Send (create) or edit (update) the guild's card for one match."""
    from botforge.discord.home import _match_card_view

    key = (guild_id, match_ref)
    card = _CARD_STATE.get(key)
    if card is None:
        return
    try:
        labels = await _label_pack(bot, guild_id)
        ctx = await _card_ctx(bot, guild_id, card)
        view = _match_card_view(card, ctx, set(), labels)
    except Exception:
        # the render NEVER kills the feed - the card stays as it was
        logger.debug("live activity card render failed (match %s)", match_ref, exc_info=True)
        return
    live = _CARDS.get(key)
    if live is not None:
        try:
            await live.edit(view=view)
            return
        except Exception:
            logger.info(
                "live activity card edit failed (guild %s, match %s) - recreating",
                guild_id,
                match_ref,
            )
            _CARDS.pop(key, None)
    guild = bot.get_guild(int(guild_id))
    channel = guild.get_channel(int(channel_id)) if guild else None
    if channel is None or not isinstance(channel, discord.TextChannel):
        return
    try:
        message = await channel.send(view=view, silent=True)
        _CARDS[key] = message
    except Exception:
        logger.debug("live activity card send skipped (guild %s) - best-effort", guild_id, exc_info=True)


async def _drop_card(
    bot: discord.Client,
    guild_id: str,
    channel_id: str,
    match_ref: str,
    status_suffix: str = "",
) -> None:
    """Fold the card (a lobby that never ran) and forget the match."""
    del status_suffix
    key = (guild_id, match_ref)
    _CARD_STATE.pop(key, None)
    _CARDS.pop(key, None)
    _FIRST_SEEN.pop(key, None)
    _MATCH_PLAYERS.pop(match_ref, None)
    _LAST_SUMMARY.pop(match_ref, None)


async def _apply_result_to_card(
    bot: discord.Client,
    guild_id: str,
    channel_id: str,
    match_ref: str,
    result: Any,
) -> None:
    """Edit the finished card with the real outcome (winner, duration, elo)."""
    key = (guild_id, match_ref)
    card = _CARD_STATE.get(key)
    if card is None:
        return
    winners = [w for w in str(result.winner_profile_id or "").split(",") if w]
    duration_ms = int(result.duration_ms or 0)
    started = int(card.get("started_at") or 0)
    finished = int(card.get("finished_at") or started + duration_ms // 1000 or 0)
    players = []
    for player in card.get("players") or []:
        pid = str((player or {}).get("profile_id", ""))
        old_new = (result.ratings or {}).get(pid)
        seat = dict(player)
        if old_new is not None:
            seat["rating_before"] = int(old_new[0])
            seat["rating_after"] = int(old_new[1])
        players.append(seat)
    _CARD_STATE[key] = {
        **card,
        "status": "finished",
        "started_at": started,
        "finished_at": finished,
        "winners": winners,
        "map_name": str(result.map_name or card.get("map_name") or ""),
        "players": players,
    }
    await _send_card(bot, guild_id, channel_id, match_ref)
    _CARD_STATE.pop(key, None)
    _CARDS.pop(key, None)
    _FIRST_SEEN.pop(key, None)
    _MATCH_PLAYERS.pop(match_ref, None)


# ---------------------------------------------------------------------
# the salon's SEED: the last week of stored history, oldest first


async def _maybe_seed_matches_salon(
    bot: discord.Client, guild_id: str, channel_id: str
) -> None:
    """Seed a FRESH matches salon with the guild's last week.

    Once per guild (a stored marker): the finished matches AND the
    invalid ones (no result, under five minutes) - an invalid match
    still shows, with its status (owner 2026-11-24). The cards go in
    CHRONOLOGICAL order, the guild's history reads itself.
    """
    marker = await _seed_marker(guild_id)
    if guild_id in _SEEDED or (
        isinstance(marker, dict) and marker.get("v") == _SEED_VERSION
    ):
        _SEEDED.add(guild_id)
        return
    _SEEDED.add(guild_id)
    try:
        cards = await _week_cards(bot, guild_id)
        await _write_seed_marker(guild_id)
        if not cards:
            return
        logger.info(
            "matches salon seed: %d card(s) for guild %s (the last week)",
            len(cards),
            guild_id,
        )
        from botforge.discord.home import _match_card_view

        labels = await _label_pack(bot, guild_id)
        for card in cards:
            try:
                ctx = await _card_ctx(bot, guild_id, card)
                guild = bot.get_guild(int(guild_id))
                channel = guild.get_channel(int(channel_id)) if guild else None
                if channel is None or not isinstance(channel, discord.TextChannel):
                    return
                await channel.send(view=_match_card_view(card, ctx, set(), labels), silent=True)
            except Exception:
                logger.debug("matches salon seed card skipped - best-effort", exc_info=True)
    except Exception:
        logger.warning("matches salon seed failed (guild %s) - best-effort", guild_id, exc_info=True)


async def _week_cards(bot: discord.Client, guild_id: str) -> list[dict[str, Any]]:
    """Return the guild's stored matches of the last week, OLDEST first.

    Seeded cards read the RAW store (the served history skips the
    invalidated matches - the seed shows them with their status).
    """
    profiles = await _guild_profiles(bot, guild_id)
    if not profiles:
        return []
    try:
        from botforge.core.models.db import get_async_database

        cursor = get_async_database()["librematch:matches"].find(
            {"profile_ids": {"$in": profiles}}
        )
        docs = [dict(doc) async for doc in cursor]
    except Exception:
        logger.debug("the seed's raw store read failed", exc_info=True)
        return []
    deadline = int(time.time()) - _SEED_WINDOW_S
    by_ref: dict[str, dict[str, Any]] = {}
    for doc in docs:
        ref = str(doc.get("match_id") or "")
        stamp = _int_of(doc.get("finished_at") or doc.get("started_at"))
        if not ref or stamp < deadline:
            continue
        # an INVALIDATED match still seeds - with its status (owner
        # 2026-11-24); a (match, leaderboard) pair may store twice,
        # the richer capture (decided, options decoded) wins
        previous = by_ref.get(ref)
        if previous is None or _doc_weight(doc) > _doc_weight(previous):
            by_ref[ref] = doc
    labels = await _label_pack(bot, guild_id)
    cards = [_seed_card_of(doc, labels) for doc in by_ref.values()]
    cards.sort(key=lambda c: int(c.get("started_at") or 0))
    return cards


def _int_of(value: Any) -> int:
    """Coerce a raw document field to int (0 on garbage)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _doc_weight(doc: dict[str, Any]) -> int:
    """Weigh a duplicate capture: decided > described > raw."""
    weight = 0
    if doc.get("finished_at"):
        weight += 4
    if doc.get("winners"):
        weight += 2
    if doc.get("options_json"):
        weight += 1
    return weight


def _seed_card_of(doc: dict[str, Any], labels: dict[str, Any]) -> dict[str, Any]:
    """Build one stored document's seed card - valid OR invalid.

    The stored document IS the served projection (the decode folded
    the seats back onto it): ``players_json`` parses like the entry's.
    """
    started = int(doc.get("started_at") or 0)
    finished = int(doc.get("finished_at") or 0)
    winners = [str(w) for w in doc.get("winners") or []]
    duration = max(0, finished - started) if finished >= started > 0 else 0
    invalid_reason = ""
    if not finished or not winners:
        invalid_reason = str(labels.get("invalid_no_result", ""))
    elif duration < _INVALID_DURATION_S:
        invalid_reason = str(labels.get("invalid_short", ""))
    card: dict[str, Any] = {
        "status": "finished",
        "match_id": str(doc.get("match_id") or ""),
        "match_ref": str(doc.get("match_id") or ""),
        "leaderboard_id": str(doc.get("leaderboard_id") or ""),
        "map_name": str(doc.get("map_name") or ""),
        "lobby_title": str(doc.get("description") or ""),
        "description": str(doc.get("description") or ""),
        "started_at": started,
        "finished_at": finished,
        "winners": winners,
        "players": _players_json(doc),
        "settings": [],
        "options_json": str(doc.get("options_json") or ""),
    }
    if invalid_reason:
        card["invalid"] = True
        card["invalid_reason"] = invalid_reason
    return card


async def _guild_profiles(bot: discord.Client, guild_id: str) -> list[str]:
    """Return the guild members' bound AoE2 profiles."""
    registration = getattr(bot, "registration_service", None)
    if registration is None:
        return []
    guild = bot.get_guild(int(guild_id))
    if guild is None:
        return []
    try:
        from botforge.discord.member_cache import guild_members

        members = await guild_members(guild)
    except Exception:
        return []
    if not members:
        return []
    out: list[str] = []
    for binding in await registration.list_bindings_for_game("aoe2"):
        user_id = str(binding.get("user_id", ""))
        if user_id and user_id.isdigit() and int(user_id) in members:
            profile = str(binding.get("profile_id", ""))
            if profile:
                out.append(profile)
    return sorted(set(out))


def _players_json(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse a stored document's seats (``players_json``, the fold output)."""
    try:
        seats = json.loads(str(doc.get("players_json") or "[]"))
    except (ValueError, TypeError):
        return []
    return [dict(seat) for seat in seats if isinstance(seat, dict)]


async def _seed_marker(guild_id: str) -> Any | None:
    """Read the guild's seed marker (None when the salon never seeded)."""
    try:
        from botforge.core.models.db import get_async_database

        return await get_async_database()["channels"].find_one(
            {"_id": f"{guild_id}:livefeed:matches:seeded"}
        )
    except Exception:
        return "unreachable"  # a broken read never re-seeds


async def _write_seed_marker(guild_id: str) -> None:
    """Write the guild's seed marker (once, forever)."""
    try:
        from botforge.core.models.db import get_async_database

        await get_async_database()["channels"].update_one(
            {"_id": f"{guild_id}:livefeed:matches:seeded"},
            {"$set": {"seeded_at": int(time.time()), "v": _SEED_VERSION}},
            upsert=True,
        )
    except Exception:
        logger.debug("the seed marker write failed", exc_info=True)


# ---------------------------------------------------------------------
# the LOGS channel: short, dense, append-only event lines


async def _log_event_line(
    bot: discord.Client, guild_id: str, event: dict[str, Any], profile_id: str
) -> None:
    """Append ONE short line per (match, event) to the guild's logs."""
    logs = getattr(bot, "logs_service", None)
    if logs is None:
        return
    try:
        resolved = await logs.resolve_channel(guild_id)
    except Exception:
        return
    channel_id = str(resolved) if resolved else ""
    if not channel_id:
        return
    guild = bot.get_guild(int(guild_id))
    channel = guild.get_channel(int(channel_id)) if guild else None
    if channel is None or not isinstance(channel, discord.TextChannel):
        return
    match = event.get("match") or {}
    match_ref = str(match.get("match_ref") or "")
    verb = _verb_of(event)
    if verb == "":
        return
    if match_ref and (guild_id, match_ref, verb) in _LOGGED:
        return  # one log per (match, event) - never per player
    if match_ref:
        _LOGGED.add((guild_id, match_ref, verb))
    text = await _log_line(bot, guild_id, event, profile_id, match_ref, verb)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(text),
            accent_colour=discord.Colour(_LOG_ACCENTS.get(verb, 0x5865F2)),
        )
    )
    try:
        await channel.send(view=view, silent=True)
    except Exception:
        logger.debug("live activity log send skipped (guild %s) - best-effort", guild_id, exc_info=True)


def _verb_of(event: dict[str, Any]) -> str:
    """Map the event to its log verb - the owner's lifecycle lexicon."""
    new = str(event.get("new_status", ""))
    old = str(event.get("old_status", ""))
    if new == "in_lobby":
        return "lobby_open" if old != "in_lobby" else "lobby_update"
    if new == "in_game":
        return "match_start"
    if new == "offline":
        return "match_end" if old == "in_game" else ("lobby_close" if old == "in_lobby" else "")
    return ""


async def _log_line(
    bot: discord.Client,
    guild_id: str,
    event: dict[str, Any],
    profile_id: str,
    match_ref: str,
    verb: str,
) -> str:
    """Render one dense log line: the player, the verb, the links."""
    from botforge.discord.commands_i18n import reply_guild

    match = event.get("match") or {}
    name = _LAST_NAME.get(profile_id) or profile_id
    player = f"**[{name}](https://www.aoe2insights.com/user/relic/{profile_id}/)**"
    id_part = f"n\u00b0`{match_ref}`" if match_ref else ""
    duration_bit = ""
    if verb == "match_end":
        started = _first_seen_of(guild_id, match_ref)
        if started:
            span = max(0, int(time.time()) - started)
            duration_bit = f"{span // 60}m{span % 60:02d}"
    line = await reply_guild(
        guild_id,
        bot,
        f"profile.live_log_{verb}",
        player=player,
        id=id_part,
        duration=duration_bit,
    )
    links: list[str] = []
    summary = _LAST_SUMMARY.get(match_ref) or match
    lobby_url = str(summary.get("lobby_url") or match.get("lobby_url") or "")
    spectate_url = str(summary.get("spectate_url") or match.get("spectate_url") or "")
    if verb in ("lobby_open", "lobby_update") and lobby_url:
        links.append(f"[\U0001f3ae aoe2lobby]({lobby_url})")
    if verb == "match_start" and spectate_url:
        links.append(f"[\U0001f441\ufe0f spectate]({spectate_url})")
    if match_ref:
        links.append(
            f"[\U0001f50d insights](https://www.aoe2insights.com/match/{match_ref}/)"
        )
    tail = " \u2014 " + " \u00b7 ".join(bit for bit in links if bit) if links else ""
    return line + tail


def _first_seen_of(guild_id: str, match_ref: str) -> int:
    return _FIRST_SEEN.get((guild_id, match_ref), 0)


# ---------------------------------------------------------------------
# the event plumbing (statuses, players, the result correlation)


def _players(match: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the match's players payload (decoded from JSON when needed)."""
    raw = match.get("players")
    if isinstance(raw, list):
        return [p for p in raw if isinstance(p, dict)]
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
            return [p for p in decoded if isinstance(p, dict)]
        except (ValueError, TypeError):
            return []
    return []


# the profile -> live match index (an offline event carries no match)
_PLAYER_REF: dict[str, str] = {}


def _remember_player_ref(profile_id: str, match_ref: str) -> None:
    _PLAYER_REF[profile_id] = match_ref


def _forget_player_ref(profile_id: str) -> None:
    _PLAYER_REF.pop(profile_id, None)


def _player_live_ref(profile_id: str) -> str:
    return _PLAYER_REF.get(profile_id, "")


def _remember_match_profiles(match: dict[str, Any], match_ref: str) -> None:
    """Keep the match's profile ids + the started-at epoch (the result keys)."""
    profiles = [str(p.get("profile_id")) for p in _players(match) if p.get("profile_id")]
    if profiles:
        started = int(time.time())
        previous = _MATCH_PLAYERS.get(match_ref)
        if previous:
            profiles = sorted(set(previous[0]) | set(profiles))
            started = min(previous[1], started) if previous[1] else started
        _MATCH_PLAYERS[match_ref] = (profiles, started)


_RESULT_BACKOFF_S = (2.0, 5.0, 10.0, 20.0)


def _spawn(coro: Any) -> None:
    """Run a fire-and-forget coroutine, kept alive until it finishes."""
    task = asyncio.create_task(coro)
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)


async def _fetch_result_then_update(
    bot: discord.Client,
    guild_id: str,
    channel_id: str,
    match_ref: str,
    profile_ids: list[str],
    started_after: int,
) -> None:
    """Fetch the real match outcome with a backoff, then update the card.

    The upstream records the result a few seconds after the end
    notification; the card's message is known, the final edit lands on
    it directly.
    """
    if not profile_ids:
        await _drop_card(bot, guild_id, channel_id, match_ref)
        return
    import os

    uri = os.environ.get("GAME_AOE2_URI", "")
    if not uri:
        return
    from botforge.game_aoe2.client import GameDataClient

    client = GameDataClient(uri)
    result = None
    for delay in _RESULT_BACKOFF_S:
        await asyncio.sleep(delay)
        try:
            result = await client.get_match_result(profile_ids, started_after)
        except Exception:
            logger.debug("match result fetch failed (match %s) - retrying", match_ref, exc_info=True)
            continue
        if result is not None:
            break
    if result is None:
        logger.info("match result never appeared (match %s) - the card stays as-is", match_ref)
        _forget_player_ref(profile_ids[0])
        return
    await _apply_result_to_card(bot, guild_id, channel_id, match_ref, result)
    for pid in profile_ids:
        _forget_player_ref(pid)


async def _is_guild_member(bot: discord.Client, guild: discord.Guild, user_id: str) -> bool:
    """Answer guild membership through the cache; an unresolvable roster fails open."""
    from botforge.discord.member_cache import guild_members

    del bot
    try:
        members = await guild_members(guild)
    except Exception:
        return True
    if not members:
        return True
    return user_id.isdigit() and int(user_id) in members
