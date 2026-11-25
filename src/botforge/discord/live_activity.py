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
_SEED_VERSION = 7  # 7: the salon becomes a FORUM, one post per known player (owner 2026-11-25)

_MATCHES_SCOPE = "games/aoe2"
_MATCHES_KEY = "matches"
# the seed window: the salon's first use replays the last WEEK
# the salon's window (owner 2026-11-25: the week was starving it - his
# November history deserves its cards; 90 days)
_SEED_WINDOW_S = 90 * 86400
# an invalid match (owner 2026-11-24): under 5 minutes or no result
_INVALID_DURATION_S = 5 * 60

# (guild, profile_id, match_ref) -> the sent message - one LIVING
# card per known participant's post (owner 2026-11-25: the forum is
# per player), updated in place while the match lives, dropped at the
# end
_CARDS: dict[tuple[str, str, str], Any] = {}
# (guild, match_ref) -> the card's current model (re-rendered in place)
_CARD_STATE: dict[tuple[str, str], dict[str, Any]] = {}
# (guild, match_ref) -> the first-seen epoch s (the live card's "since")
_FIRST_SEEN: dict[tuple[str, str], int] = {}
# the last known summary per match - the end card keeps the context
_LAST_SUMMARY: dict[str, dict[str, Any]] = {}
# the FINISHED card model per match - the rich end line reads it after
# the correlation (the state lives on past the card's own death)
_FINISHED_CARDS: dict[str, dict[str, Any]] = {}
# the last in-game name seen per profile (labels survive the offline event)
_LAST_NAME: dict[str, str] = {}
# the match's profiles + started-at epoch s - the result correlation keys
_MATCH_PLAYERS: dict[str, tuple[list[str], int]] = {}
# the (guild, match_ref, verb) events already logged this boot (one log per event)
_LOGGED: set[tuple[str, str, str]] = set()
# the guilds whose matches salon already saw their week of history
_SEEDED: set[str] = set()
# the (guild, match_ref) the salon already carries a message for - the
# ONE-message-per-match bookkeeping (owner 2026-11-25): the live cards,
# the seeds and the store gap-fills all share it
_POSTED: dict[str, set[str]] = {}
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


async def instant_sweep(bot: discord.Client, guild_id: str) -> None:
    """Run the salon reconcile NOW for one guild (the pokes' entry).

    The member join/leave and the bind/unbind hooks ride this - the
    posts' lifecycle answers the EVENT, the 5-minute sweep stays the
    safety net.
    """
    try:
        channel_id = await _matches_channel_id(bot, guild_id)
        if channel_id is None:
            return
        _SEEDED.discard(guild_id)
        await _maybe_seed_matches_salon(bot, guild_id, channel_id)
        await _gap_fill_matches_salon(bot, guild_id, channel_id)
    except Exception:
        logger.debug("the instant salon sweep failed (guild %s)", guild_id, exc_info=True)


def _bind_instant_repair(bot: discord.Client) -> None:
    """Bind the channel delete/create events to an INSTANT salon sweep.

    The owner's rule (2026-11-25): a repaired salon repopulates
    INSTANTLY, nobody waits for the 5-minute sweep - the sweep stays
    the safety net, the event is the fast path. The marker decides
    cheaply: an unchanged salon returns in one read.
    """

    async def _on_channel_event(channel: Any) -> None:
        guild = getattr(channel, "guild", None)
        if guild is None:
            return
        await instant_sweep(bot, str(guild.id))

    async def _on_member_event(member: Any) -> None:
        # a known player ENTERS or LEAVES the guild (owner 2026-11-25):
        # his post is created/deleted NOW, not at the next sweep
        guild = getattr(member, "guild", None)
        if guild is None:
            return
        await instant_sweep(bot, str(guild.id))

    if getattr(bot, "_matches_instant_bound", False):
        return
    try:
        bot._matches_instant_bound = True  # type: ignore[attr-defined]
        add_listener: Any = getattr(bot, "add_listener", None)
        if add_listener is None:
            return
        add_listener(_on_channel_event, "on_guild_channel_delete")
        add_listener(_on_channel_event, "on_guild_channel_create")
        add_listener(_on_member_event, "on_member_join")
        add_listener(_on_member_event, "on_member_remove")
    except Exception:
        logger.debug("the instant salon binding failed - the sweep stays", exc_info=True)


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
    # the INSTANT repair (owner 2026-11-25: "au delete, tout repopulate
    # instant"): a channel deleted or created sweeps NOW
    _bind_instant_repair(bot)

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
                guild_id = str(guild.id)
                channel_id = await _matches_channel_id(bot, guild_id)
                if channel_id is None:
                    continue
                await _maybe_seed_matches_salon(bot, guild_id, channel_id)
                await _gap_fill_matches_salon(bot, guild_id, channel_id)
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
        _spawn(
            _fetch_result_then_update(
                bot, guild_id, channel_id, match_ref, profiles, started_at, profile_id
            )
        )
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
    """Send (create) or edit (update) the match's LIVING cards.

    The salon is a FORUM, one post per KNOWN player (owner
    2026-11-25): every known participant of the match carries a live
    card in HIS post, updated in place. A match with several known
    players duplicates (assumed).
    """
    from botforge.discord.home import _match_card_view

    key = (guild_id, match_ref)
    card = _CARD_STATE.get(key)
    if card is None:
        return
    participants = _known_participants(card, await _guild_profiles(bot, guild_id))
    if not participants:
        return
    forum = await _sweep_channel(bot, guild_id, channel_id)
    if forum is None or not isinstance(forum, discord.ForumChannel):
        return
    posts = await _ensure_player_posts(bot, guild_id, forum, sorted(participants))
    try:
        labels = await _label_pack(bot, guild_id)
        ctx = await _card_ctx(bot, guild_id, card)
        known = set(participants)
        view = _match_card_view(card, ctx, set(), labels, known)
    except Exception:
        # the render NEVER kills the feed - the card stays as it was
        logger.debug("live activity card render failed (match %s)", match_ref, exc_info=True)
        return
    for profile_id in sorted(participants):
        await _upsert_participant_card(bot, guild_id, profile_id, match_ref, posts, forum, view)


async def _upsert_participant_card(
    bot: discord.Client,
    guild_id: str,
    profile_id: str,
    match_ref: str,
    posts: dict[str, dict[str, Any]],
    forum: Any,
    view: Any,
) -> None:
    """Edit one participant's live card in HIS post, send it when new."""
    del bot
    entry = posts.get(profile_id)
    if entry is None:
        return
    thread = _thread_of(forum, entry)
    if thread is None:
        return
    live_key = (guild_id, profile_id, match_ref)
    live = _CARDS.get(live_key)
    if live is not None:
        try:
            await live.edit(view=view)
            return
        except Exception:
            logger.info(
                "live activity card edit failed (guild %s, post %s, match %s) - recreating",
                guild_id,
                profile_id,
                match_ref,
            )
            _CARDS.pop(live_key, None)
    try:
        message = await thread.send(view=view, silent=True)
        _CARDS[live_key] = message
        # the live card rides the post's registry: the gap-fill never
        # duplicates a match the live feed already carries
        if match_ref not in _post_refs(entry):
            entry.setdefault("refs", [])
            entry["refs"] = sorted({*entry["refs"], match_ref})
            entry.setdefault("messages", {})[match_ref] = str(message.id)
            await _save_post(guild_id, profile_id, entry)
    except Exception:
        logger.debug(
            "live activity card send skipped (guild %s, post %s) - best-effort",
            guild_id,
            profile_id,
            exc_info=True,
        )


def _known_participants(card: dict[str, Any], profiles: list[str]) -> set[str]:
    """Return the match's seats that belong to the guild's KNOWN players."""
    known = {str(p) for p in profiles}
    return {
        str((player or {}).get("profile_id") or "")
        for player in card.get("players") or []
    } & known


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
    for live_key in [k for k in _CARDS if k[0] == guild_id and k[2] == match_ref]:
        _CARDS.pop(live_key, None)
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
    # the FINISHED model stays for the rich end line (owner
    # 2026-11-25): the verdict reads partners, map and format from it
    _FINISHED_CARDS[match_ref] = dict(_CARD_STATE.get(key) or {})
    _CARD_STATE.pop(key, None)
    for live_key in [k for k in _CARDS if k[0] == guild_id and k[2] == match_ref]:
        _CARDS.pop(live_key, None)
    _FIRST_SEEN.pop(key, None)
    _MATCH_PLAYERS.pop(match_ref, None)


# ---------------------------------------------------------------------
# the salon's SEED: the last week of stored history, oldest first


async def _maybe_seed_matches_salon(  # noqa: C901 - one orchestration, no branch soup
    bot: discord.Client, guild_id: str, channel_id: str
) -> None:
    """Seed the guild's matches FORUM: one post per KNOWN player.

    Once per guild (a stored marker): the window's finished matches
    AND the invalid ones (no result, under five minutes) - an invalid
    match still shows, with its status (owner 2026-11-24). A match
    with several known players lands in EACH one's post (owner
    2026-11-25: the duplicates are assumed), chronologically.
    """
    marker = await _seed_marker(guild_id)
    if guild_id in _SEEDED or (
        isinstance(marker, dict)
        and marker.get("v") == _SEED_VERSION
        # a REPAIRED salon (deleted, recreated) changed its id - the
        # window re-seeds into the new channel (owner 2026-11-24)
        and str(marker.get("channel_id") or "") == str(channel_id)
    ):
        _SEEDED.add(guild_id)
        return
    _SEEDED.add(guild_id)
    marker_channel = str((marker or {}).get("channel_id") or "") if isinstance(marker, dict) else ""
    if marker_channel and marker_channel != str(channel_id):
        logger.info(
            "matches forum repaired (guild %s): channel %s -> %s",
            guild_id,
            marker_channel,
            channel_id,
        )
    try:
        forum = await _sweep_channel(bot, guild_id, channel_id)
        if forum is None:
            return
        profiles = await _guild_profiles(bot, guild_id)
        if not profiles:
            await _write_seed_marker(guild_id, channel_id)
            return
        posts = await _ensure_player_posts(bot, guild_id, forum, profiles)
        cards = await _week_cards(bot, guild_id)
        await _write_seed_marker(guild_id, channel_id)
        if not cards:
            return
        labels = await _label_pack(bot, guild_id)
        known = set(profiles)
        posted_total = 0
        for profile_id, entry in posts.items():
            group = _cards_of_player(cards, profile_id)
            if not group:
                continue
            refs = _post_refs(entry)
            pending_cards = [c for c in group if str(c.get("match_id") or "") not in refs]
            if not pending_cards:
                continue
            thread = _thread_of(forum, entry)
            if thread is None:
                continue
            ctx_by_ref: dict[str, dict[str, Any]] = {}
            for card in pending_cards:
                ctx_by_ref[str(card.get("match_id"))] = await _card_ctx(bot, guild_id, card)
            marked = await _send_cards_grouped(thread, pending_cards, ctx_by_ref, labels, known)
            if marked:
                entry.setdefault("refs", [])
                entry["refs"].extend(ref for ref, _mid in marked)
                entry["refs"] = sorted(set(entry["refs"]))
                entry.setdefault("messages", {}).update(dict(marked))
                await _save_post(guild_id, profile_id, entry)
                posted_total += len(marked)
        if posted_total:
            logger.info(
                "matches forum seed: %d card(s) across %d post(s) for guild %s (the last window)",
                posted_total,
                len(posts),
                guild_id,
            )
    except Exception:
        logger.warning("matches forum seed failed (guild %s) - best-effort", guild_id, exc_info=True)


def _cards_of_player(cards: list[dict[str, Any]], profile_id: str) -> list[dict[str, Any]]:
    """Return the match cards the player took part in (the duplicates are assumed)."""
    pid = str(profile_id)
    out: list[dict[str, Any]] = []
    for card in cards:
        for player in card.get("players") or []:
            if str((player or {}).get("profile_id") or "") == pid:
                out.append(card)
                break
    return out


def _thread_of(forum: Any, entry: dict[str, Any]) -> Any | None:
    """Resolve a post's thread object from the forum's caches."""
    thread_id = int(entry.get("thread_id") or 0)
    if not thread_id:
        return None
    thread = forum.get_thread(thread_id)
    if thread is not None:
        return thread
    try:
        return forum.get_partial_messageable(thread_id)
    except Exception:
        return None


async def _week_cards(bot: discord.Client, guild_id: str) -> list[dict[str, Any]]:
    """Return the guild's stored matches of the last week, OLDEST first.

    The seed rides the SERVED history (rule 4): the entries commute
    through the game service, the AI seats already fold ext-side with
    their real civ names, and the SEAL travels with the entry - the
    seed renders the invalid matches with their status, never as a
    hole (owner 2026-11-24).
    """
    profiles = await _guild_profiles(bot, guild_id)
    if not profiles:
        return []
    from botforge.discord.stats_views import recent_match_entries

    # the fetch window rides the SALON's own window (owner 2026-11-
    # 25): 90 days of history BEFORE the local filter, never a bare 50
    entries = await recent_match_entries(profiles, limit=200)
    deadline = int(time.time()) - _SEED_WINDOW_S
    cards: list[dict[str, Any]] = []
    for entry in entries:
        stamp = _int_of(getattr(entry, "finished_at", 0) or getattr(entry, "started_at", 0))
        if stamp and stamp < deadline:
            continue
        cards.append(_seed_card_of(entry))
    cards.sort(key=lambda c: int(c.get("started_at") or 0))
    return cards


def _int_of(value: Any) -> int:
    """Coerce a raw field to int (0 on garbage)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _seed_card_of(entry: Any) -> dict[str, Any]:
    """Build one served entry's seed card - valid OR invalid.

    The entry IS the served projection: the players json folds the AI
    seats ext-side, with their civ names; the seal rule colours the
    AI-decided matches as the DEFEAT they are (owner 2026-11-24).
    """
    from botforge.discord.home import _entry_settings_of, _invalid_reason_type_of

    started = _int_of(getattr(entry, "started_at", 0))
    finished = _int_of(getattr(entry, "finished_at", 0))
    winners = [str(w) for w in getattr(entry, "winners", ()) or ()]
    import json as _json

    try:
        seats = [dict(s) for s in _json.loads(str(getattr(entry, "players_json", "") or "[]")) if isinstance(s, dict)]
    except (ValueError, TypeError):
        seats = []
    card: dict[str, Any] = {
        "status": "finished",
        "match_id": str(getattr(entry, "match_id", "") or ""),
        "match_ref": str(getattr(entry, "match_id", "") or ""),
        "leaderboard_id": str(getattr(entry, "leaderboard_id", "") or ""),
        "map_name": str(getattr(entry, "map_name", "") or ""),
        "lobby_title": str(getattr(entry, "description", "") or "").strip(),
        "description": str(getattr(entry, "description", "") or ""),
        "started_at": started,
        "finished_at": finished,
        "winners": winners,
        "players": seats,
        "settings": _entry_settings_of(entry),
        "options_json": str(getattr(entry, "options_json", "") or ""),
    }
    reason = _invalid_reason_type_of(started, finished, winners, seats)
    if reason:
        card["invalid"] = True
        card["invalid_reason"] = reason
    return card


def _posts_doc_id(guild_id: str) -> str:
    """Return the per-player posts registry's mongo id."""
    return f"{guild_id}:livefeed:matches:posts"


async def _posts_of(guild_id: str) -> dict[str, dict[str, Any]]:
    """Read the salon's PER-PLAYER posts registry (owner 2026-11-25).

    The salon is a FORUM, one post per KNOWN player:
    ``{profile_id: {"thread_id": ..., "name": ..., "refs": [...],
    "messages": {match_ref: message_id}}}`` - a match with several
    known participants lands in EACH one's post (the duplicate is
    assumed), each post owns its own refs and message ids.
    """
    try:
        from botforge.core.models.db import get_async_database

        document = await get_async_database()["channels"].find_one({"_id": _posts_doc_id(guild_id)})
        raw = (document or {}).get("posts") or {}
        if not isinstance(raw, dict):
            raw = {}
        posts: dict[str, dict[str, Any]] = {}
        for pid, entry in raw.items():
            if isinstance(entry, dict) and str(entry.get("thread_id") or ""):
                posts[str(pid)] = {
                    "thread_id": str(entry.get("thread_id")),
                    "name": str(entry.get("name") or ""),
                    "refs": sorted({str(r) for r in (entry.get("refs") or [None]) if r}),
                    "messages": {
                        str(k): str(v)
                        for k, v in (entry.get("messages") or {}).items()
                        if str(k) and str(v)
                    },
                }
        return posts
    except Exception:
        return {}


async def _save_post(guild_id: str, profile_id: str, entry: dict[str, Any] | None) -> None:
    """Write one player's post entry - None drops it (the post died)."""
    try:
        from botforge.core.models.db import get_async_database

        patch: dict[str, Any] = {"$set": {f"posts.{profile_id}": entry}}
        if entry is None:
            patch = {"$unset": {f"posts.{profile_id}": ""}}
        await get_async_database()["channels"].update_one(
            {"_id": _posts_doc_id(guild_id)}, patch, upsert=True
        )
    except Exception:
        logger.debug("the posts registry write failed (guild %s, post %s)", guild_id, profile_id, exc_info=True)


def _post_refs(entry: dict[str, Any]) -> set[str]:
    """Return the post's posted match refs."""
    return {str(r) for r in (entry.get("refs") or [])}


def _post_messages(entry: dict[str, Any]) -> dict[str, str]:
    """Return the post's match-ref -> message-id map."""
    return {str(k): str(v) for k, v in (entry.get("messages") or {}).items()}


async def _player_names(bot: discord.Client, guild_id: str) -> dict[str, str]:
    """Return the known profiles' display names (the bindings' own aliases)."""
    registration = getattr(bot, "registration_service", None)
    if registration is None:
        return {}
    out: dict[str, str] = {}
    try:
        for binding in await registration.list_bindings_for_game("aoe2"):
            profile = str(binding.get("profile_id", ""))
            if profile:
                name = str((binding.get("profile") or {}).get("alias") or "")
                out[profile] = name
    except Exception:
        out.clear()
    out.update({pid: name for pid, name in _LAST_NAME.items() if pid in out and not out.get(pid)})
    return out


async def _ensure_player_posts(
    bot: discord.Client, guild_id: str, forum: Any, profiles: list[str]
) -> dict[str, dict[str, Any]]:
    """Reconcile the forum's posts with the KNOWN players.

    The owner's lifecycle rule (2026-11-25): a known player entering
    or leaving the guild creates/deletes his post; a member binding
    or unbinding a profile does the same - the reconcile creates the
    missing threads, deletes the orphaned ones, the sweep (and the
    join/leave/bind listeners) trigger it.
    """
    known = [str(p) for p in profiles if str(p)]
    posts = await _posts_of(guild_id)
    names = await _player_names(bot, guild_id)
    for profile_id in list(posts):
        if profile_id not in known:
            # the player left or unbound: the post dies
            try:
                thread = forum.get_thread(int(posts[profile_id]["thread_id"]))
                if thread is None:
                    threads = getattr(forum, "threads", {})
                    thread = threads.get(int(posts[profile_id]["thread_id"]))
                if thread is not None:
                    await thread.delete()
            except Exception:
                logger.debug("the orphan post delete failed (post %s)", profile_id, exc_info=True)
            await _save_post(guild_id, profile_id, None)
            posts.pop(profile_id, None)
            logger.info("matches forum: post deleted for %s (guild %s)", profile_id, guild_id)
    for profile_id in known:
        if profile_id in posts and str(posts[profile_id].get("name") or ""):
            continue
        name = names.get(profile_id) or f"Profil {profile_id}"
        try:
            thread = await forum.create_thread(name=_thread_title(name), auto_archive_duration=10080)
        except Exception:
            logger.debug("the player post creation failed (post %s)", profile_id, exc_info=True)
            continue
        entry = {
            "thread_id": str(thread.id),
            "name": name,
            "refs": [],
            "messages": {},
        }
        posts[profile_id] = entry
        await _save_post(guild_id, profile_id, entry)
        logger.info("matches forum: post created for %s (guild %s, thread %s)", profile_id, guild_id, thread.id)
    return posts


def _thread_title(name: str) -> str:
    """Build the post's title: the player's name, capped at the forum's limit."""
    clean = " ".join(str(name or "?").split())[:90] or "?"
    return clean


async def _posted_messages(guild_id: str) -> dict[str, str]:
    """Return the salon's match-ref -> message-id map (the reconcile's truth).

    A posted ref carries the DISCORD MESSAGE it lives in (owner
    2026-11-25): listing the channel tells live from deleted - the
    reconcile drops the dead ones, the re-seed recreates the missing.
    """
    try:
        from botforge.core.models.db import get_async_database

        document = await get_async_database()["channels"].find_one(
            {"_id": f"{guild_id}:livefeed:matches:posted"}
        )
        raw: Any = (document or {}).get("messages") or {}
        if not isinstance(raw, dict):
            raw = {}
        return {str(k): str(v) for k, v in raw.items() if str(k) and str(v)}
    except Exception:
        return {}


async def _posted_refs(guild_id: str) -> set[str]:
    """Retrieve the salon messages' matches - persisted, process-wide cache."""
    cached = _POSTED.get(guild_id)
    if cached is not None:
        return cached
    refs: set[str] = set()
    try:
        from botforge.core.models.db import get_async_database

        document = await get_async_database()["channels"].find_one(
            {"_id": f"{guild_id}:livefeed:matches:posted"}
        )
        raw_refs: Any = (document or {}).get("refs") or []
        if not isinstance(raw_refs, (list, tuple, set)):
            raw_refs = []
        refs = {str(ref) for ref in raw_refs}
    except Exception:
        refs = set()
    _POSTED[guild_id] = refs
    return refs


async def _mark_posted(
    guild_id: str, match_ref: str, message_id: str | None = None
) -> None:
    """Record one match's salon message - the ONE-message bookkeeping.

    The message id rides the ref when known (owner 2026-11-25): the
    reconcile reads it to tell a LIVING card from a deleted one.
    """
    refs = await _posted_refs(guild_id)
    if match_ref in refs and not message_id:
        return
    refs.add(match_ref)
    patch: dict[str, Any] = {"$addToSet": {"refs": match_ref}}
    if message_id:
        patch["$set"] = {f"messages.{match_ref}": str(message_id)}
    try:
        from botforge.core.models.db import get_async_database

        await get_async_database()["channels"].update_one(
            {"_id": f"{guild_id}:livefeed:matches:posted"},
            patch,
            upsert=True,
        )
    except Exception:
        logger.debug("the posted-refs write failed (match %s)", match_ref, exc_info=True)


async def _sweep_channel(bot: discord.Client, guild_id: str, channel_id: str) -> Any | None:
    """Resolve the salon's text channel - the CACHE may not know it yet.

    A channel created after the boot never rides the client's cache
    (owner 2026-11-25: the repaired salon stayed EMPTY - the seed
    resolved get_channel, read None, returned in silence). The
    matches salon is a FORUM (owner 2026-11-25) - both text and
    forum channels resolve here.
    """
    guild = bot.get_guild(int(guild_id))
    if guild is None:
        return None
    channel: Any = guild.get_channel(int(channel_id))
    if channel is not None:
        return channel
    try:
        fetched: Any = await guild.fetch_channel(int(channel_id))
    except Exception:
        return None
    return fetched if isinstance(fetched, (discord.TextChannel, discord.ForumChannel)) else None


async def _send_cards_grouped(
    thread: Any, cards: list[dict[str, Any]], ctx_by_ref: dict[str, dict[str, Any]],
    labels: dict[str, Any], known: set[str], max_group: int = 10,
) -> list[tuple[str, str]]:
    """Send cards into one forum post, GROUPED messages (owner 2026-11-25).

    "Cree les messages par groupe de 10 si tu peux": the cards fold
    into ONE LayoutView per message (the same multi-
    card fold the live dashboard rides); a batch Discord refuses
    (the component cap bites) halves until it fits - one card per
    message as the floor. Returns [(match_ref, message_id), ...].
    """
    from botforge.discord.home import _match_card_parts
    from botforge.discord.ui.view_footer import add_view_footer

    marked: list[tuple[str, str]] = []
    for start in range(0, len(cards), max_group):
        group = cards[start : start + max_group]
        while group:
            try:
                view = discord.ui.LayoutView(timeout=None)
                refs: list[str] = []
                for card in group:
                    blocks, buttons, match_id, accent = _match_card_parts(
                        card, ctx_by_ref.get(str(card.get("match_id")), {}), set(), labels, known
                    )
                    view.add_item(discord.ui.Container(*blocks, accent_colour=discord.Colour(accent)))
                    if buttons:
                        view.add_item(discord.ui.ActionRow(*buttons))
                    refs.append(str(card.get("match_id") or match_id))
                view = add_view_footer(view, f"panel:match:aoe2:{refs[0]}")
                message = await thread.send(view=view, silent=True)
                marked.extend((ref, str(message.id)) for ref in refs)
                break
            except Exception:
                if len(group) == 1:
                    logger.debug("the grouped card send failed (post %s)", thread.id, exc_info=True)
                    break  # even a single card refuses: move on, never a crash
                group = group[: len(group) // 2]  # the 40-component cap bites: halve
    return marked


async def _reconcile_posted_refs(bot: discord.Client, guild_id: str, channel_id: str) -> None:
    """Reconcile the posted refs with the LIVE channel messages.

    The owner's rule (2026-11-25): on repair, LIST the salon's
    messages, DROP the refs whose message was deleted, RECREATE the
    missing cards - ZERO duplicates (a living message keeps its ref, a
    dead one posts again exactly once).
    """
    channel = await _sweep_channel(bot, guild_id, channel_id)
    if channel is None:
        return
    messages = await _posted_messages(guild_id)
    if not messages:
        return  # nothing mapped yet: the refs assume alive, never a dup
    live: set[int] = set()
    try:
        async for message in channel.history(limit=500):
            live.add(message.id)
    except Exception:
        logger.debug("the salon history read failed (guild %s)", guild_id, exc_info=True)
        return
    dead = [ref for ref, mid in messages.items() if int(mid) not in live]
    if not dead:
        return
    try:
        from botforge.core.models.db import get_async_database

        await get_async_database()["channels"].update_one(
            {"_id": f"{guild_id}:livefeed:matches:posted"},
            {
                "$pull": {"refs": {"$in": dead}},
                "$unset": {f"messages.{ref}": "" for ref in dead},
            },
        )
    except Exception:
        logger.debug("the posted-refs reconcile write failed (guild %s)", guild_id, exc_info=True)
        return
    _POSTED.pop(guild_id, None)
    logger.info(
        "matches salon reconcile (guild %s): %d dead message(s) dropped, recreating",
        guild_id,
        len(dead),
    )


async def _gap_fill_matches_salon(  # noqa: C901 - one orchestration, no branch soup
    bot: discord.Client, guild_id: str, channel_id: str
) -> None:
    """Post the store matches the forum's posts never saw (owner 2026-11-25).

    A match played without a live feed only lives in the store: the
    sweep posts its card into EVERY known participant's post (the
    duplicates are assumed), batched, one registry per post - the
    live events, the seeds and the store gap-fills all share it.
    """
    profiles = await _guild_profiles(bot, guild_id)
    if not profiles:
        return
    forum = await _sweep_channel(bot, guild_id, channel_id)
    if forum is None:
        return
    posts = await _ensure_player_posts(bot, guild_id, forum, profiles)
    from botforge.discord.stats_views import recent_match_entries

    known = set(profiles)
    entries = await recent_match_entries(profiles, limit=200)
    deadline = int(time.time()) - _SEED_WINDOW_S
    cards: list[dict[str, Any]] = []
    for entry in entries:
        finished_at = _int_of(getattr(entry, "finished_at", 0))
        if finished_at and finished_at >= deadline:
            cards.append(_seed_card_of(entry))
    if not cards:
        return
    labels = await _label_pack(bot, guild_id)
    for profile_id, entry in posts.items():
        refs = _post_refs(entry)
        group = [
            c for c in _cards_of_player(cards, profile_id)
            if str(c.get("match_id") or "") not in refs
        ]
        if not group:
            continue
        thread = _thread_of(forum, entry)
        if thread is None:
            continue
        ctx_by_ref: dict[str, dict[str, Any]] = {}
        for card in group:
            ctx_by_ref[str(card.get("match_id"))] = await _card_ctx(bot, guild_id, card)
        try:
            marked = await _send_cards_grouped(thread, group, ctx_by_ref, labels, known)
        except Exception:
            logger.debug("the gap-fill group skipped (post %s) - best-effort", profile_id, exc_info=True)
            continue
        if marked:
            entry.setdefault("refs", []).extend(ref for ref, _mid in marked)
            entry["refs"] = sorted(set(entry["refs"]))
            entry.setdefault("messages", {}).update(dict(marked))
            await _save_post(guild_id, profile_id, entry)
            logger.info(
                "matches forum gap-fill: %d card(s) posted in %s's post (guild %s)",
                len(marked),
                profile_id,
                guild_id,
            )


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


async def _seed_marker(guild_id: str) -> Any | None:
    """Read the guild's seed marker (None when the salon never seeded)."""
    try:
        from botforge.core.models.db import get_async_database

        return await get_async_database()["channels"].find_one(
            {"_id": f"{guild_id}:livefeed:matches:seeded"}
        )
    except Exception:
        return "unreachable"  # a broken read never re-seeds


async def _write_seed_marker(guild_id: str, channel_id: str) -> None:
    """Write the guild's seed marker (the salon it last seeded)."""
    try:
        from botforge.core.models.db import get_async_database

        await get_async_database()["channels"].update_one(
            {"_id": f"{guild_id}:livefeed:matches:seeded"},
            {"$set": {"seeded_at": int(time.time()), "v": _SEED_VERSION, "channel_id": str(channel_id)}},
            upsert=True,
        )
    except Exception:
        logger.debug("the seed marker write failed", exc_info=True)


# ---------------------------------------------------------------------
# the LOGS channel: short, dense, append-only event lines


async def _log_event_line(
    bot: discord.Client, guild_id: str, event: dict[str, Any], profile_id: str
) -> None:
    """Append ONE short line per (match, event) to the guild's logs.

    The MATCH END line defers (owner 2026-11-25): its verdict, the
    streak, the forum post link and the known partners all live on
    the result correlation - the offline transition itself says
    nothing, the correlated result says everything.
    """
    logs = getattr(bot, "logs_service", None)
    if logs is None:
        return
    verb = _verb_of(event)
    if verb == "match_end":
        return  # the correlated result renders the rich end line
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
    if verb == "":
        return
    if match_ref and (guild_id, match_ref, verb) in _LOGGED:
        return  # one log per (match, event) - never per player
    if match_ref:
        _LOGGED.add((guild_id, match_ref, verb))
    text = await _log_line(bot, guild_id, event, profile_id, match_ref, verb)
    await _append_logs_line(bot, guild_id, verb, text)


async def _append_logs_line(bot: discord.Client, guild_id: str, verb: str, text: str) -> None:
    """Append one rendered line to the guild's logs (the shared sender)."""
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
        # the link LABELS carry NO emoji (owner 2026-11-25: they
        # never render inside a masked link)
        links.append(f"[aoe2lobby]({lobby_url})")
    if verb == "match_start" and spectate_url:
        links.append(f"[spectate]({spectate_url})")
    if match_ref:
        links.append(
            f"[insights](https://www.aoe2insights.com/match/{match_ref}/)"
        )
    tail = " \u2014 " + " \u00b7 ".join(bit for bit in links if bit) if links else ""
    return line + tail


async def _log_match_end_line(
    bot: discord.Client,
    guild_id: str,
    match_ref: str,
    profile_id: str,
    result: Any,
) -> None:
    """Render the RICH match-end bullet (owner 2026-11-25).

    One dense line, the logs channel is a bullet list:
    ``{player} a perdu une [partie](le post du joueur) - 1v1 Classée -
    avec/contre {les connus} - sur {la carte} {<t:R>} - série : VVDDV``
    The verdict, the partners, the map, the streak all read the
    CORRELATED result - never a stale snapshot.
    """
    from botforge.discord.commands_i18n import reply_guild
    from botforge.discord.home import _card_format, _is_ranked

    key = (guild_id, match_ref)
    card = _CARD_STATE.get(key) or _FINISHED_CARDS.get(match_ref) or {}
    winners = {str(w) for w in (result.winner_profile_id or "").split(",") if w}
    won = str(profile_id) in winners
    players = _players(card) or _players(_LAST_SUMMARY.get(match_ref) or {})
    # the subject's side: same team when the team field reads
    team_of = {str(p.get("profile_id", "")): int(p.get("team", 0) or 0) for p in players}
    known = {str(p) for p in await _guild_profiles(bot, guild_id)}
    subject_team = team_of.get(str(profile_id), 0)
    with_names: list[str] = []
    against_names: list[str] = []
    for player in players:
        pid = str(player.get("profile_id", ""))
        if not pid or pid == str(profile_id) or pid not in known:
            continue
        name = str(player.get("alias") or player.get("name") or pid)
        mate = " **" + name + "**"
        if team_of.get(pid, subject_team) == subject_team:
            with_names.append(mate)
        else:
            against_names.append(mate)
    known_bit = ""
    if with_names:
        known_bit += f"{with_word(guild_id, bot)}{''.join(with_names)}"
    if against_names:
        known_bit += f" {against_word(guild_id, bot)}{''.join(against_names)}"
    # the forum post link: the player's own thread message
    match_link = await _forum_post_link(bot, guild_id, profile_id, match_ref)
    if not match_link:
        match_link = f"https://www.aoe2insights.com/match/{match_ref}/"
    map_name = str(card.get("map_name") or "") or "carte ?"
    finished_at = int(card.get("finished_at") or 0) or int(time.time())
    fmt = _card_format(card)
    labels = await _label_pack(bot, guild_id)
    if fmt == "FFA":
        badge = "FFA"
    elif _is_ranked(card):
        badge = f"{fmt} {labels.get('ranked_word') or 'Classée'!s}".strip()
    else:
        badge = str(labels.get("custom_badge") or "Personnalisée")
    streak = await _player_streak(bot, profile_id, match_ref, won)
    line = await reply_guild(
        guild_id,
        bot,
        "profile.live_log_match_won" if won else "profile.live_log_match_lost",
        player=f"**[{_LAST_NAME.get(profile_id) or profile_id}](https://www.aoe2insights.com/user/relic/{profile_id}/)**",
        match=f"[une partie]({match_link})",
        badge=badge,
    )
    bits = [bit for bit in (known_bit, f"sur {map_name}", f"<t:{finished_at}:R>") if bit]
    line += " — " + " · ".join(bits)
    if streak:
        line += f" — série : `{streak}`"
    await _append_logs_line(bot, guild_id, "match_end", line)


def with_word(guild_id: str, bot: Any) -> str:
    """Return the 'avec' joiner."""
    del guild_id, bot
    return "avec"


def against_word(guild_id: str, bot: Any) -> str:
    """Return the 'contre' joiner."""
    del guild_id, bot
    return "contre"


async def _forum_post_link(
    bot: discord.Client, guild_id: str, profile_id: str, match_ref: str
) -> str:
    """Return the match's card message link in the PLAYER'S forum post."""
    del bot
    try:
        posts = await _posts_of(guild_id)
        entry = posts.get(str(profile_id)) or {}
        message_id = _post_messages(entry).get(str(match_ref), "")
        thread_id = str(entry.get("thread_id") or "")
        if message_id and thread_id:
            return f"https://discord.com/channels/{guild_id}/{thread_id}/{message_id}"
    except Exception:
        return ""
    return ""


async def _player_streak(
    bot: discord.Client, profile_id: str, match_ref: str, won: bool
) -> str:
    """Return the player's last results, oldest first.

    The owner's bullet reads the HISTORY (owner 2026-11-25):
    ``VVDDV`` - V for a win, D for a defeat; the current match's
    letter rides last. Five letters maximum, dense like the game's
    own UI.
    """
    try:
        from botforge.discord.stats_views import recent_match_entries

        entries = await recent_match_entries([str(profile_id)], limit=6)
    except Exception:
        entries = []
    letters: list[str] = []
    order: list[tuple[int, str]] = []
    for entry in entries:
        ref = str(getattr(entry, "match_id", "") or "")
        if not ref:
            continue
        finished = _int_of(getattr(entry, "finished_at", 0))
        inner = {str(w) for w in getattr(entry, "winners", ()) or ()}
        letter = "V" if str(profile_id) in inner else "D"
        if not inner:
            continue  # unplayed loot: no streak letter
        order.append((finished, letter))
    order.sort(key=lambda row: row[0])
    letters = [letter for _at, letter in order if letter] or []
    result = "".join(letters[-4:]) + ("V" if won else "D")
    return result[-5:]


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
    subject_profile_id: str = "",
) -> None:
    """Fetch the real match outcome with a backoff, then update the card.

    The upstream records the result a few seconds after the end
    notification; the card's message is known, the final edit lands on
    it directly. The END LINE rides the verdict (owner 2026-11-25):
    won/lost, the forum post link, the known partners, the map, the
    streak - one dense bullet, after the correlation.
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
    await _log_match_end_line(bot, guild_id, match_ref, subject_profile_id or profile_ids[0], result)
    for pid in profile_ids:
        _forget_player_ref(pid)
    # the store warms the MOMENT the verdict lands (owner 2026-11-25):
    # the listing answers from the store in under a second - its sync
    # rides the background, this hook is what keeps it fresh
    try:
        from botforge.discord.stats_views import stats_client

        stats = stats_client()
        if stats is not None:
            await stats.sync_stats(profile_ids, wait=False)
    except Exception:
        logger.debug("the post-match store sync failed", exc_info=True)


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
