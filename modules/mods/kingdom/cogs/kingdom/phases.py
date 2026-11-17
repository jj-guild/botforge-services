"""The attack phases loop (P4.1b tranche 2e — the D77 tick).

Every 5 minutes the tick drives EVERY attack forward one beat: the
plan events, the T-15 reveals, the pick & ban DMs, the battle room at
T, the forfeits, the no-shows, the score confirmations and the
disputes — each step replays SAFELY after a restart through the
engine's per-attack flags (``reveal_due``, ``pick_ban_due``, …).

The loop is the core season refresher's pattern (a gate env for the
test journeys + ``tasks.loop``), started from the cog's
``setup_hook``; the voice-presence listener registers once per
process (the presence tracking feeds the forfeit line).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("kingdom.attack")


# ---------------------------------------------------------------------------
# Locale (per guild, the platform's stored choice — FR fallback)
# ---------------------------------------------------------------------------


async def _guild_locale(bot: Any, guild_id: str) -> str:
    """The guild's effective locale through the platform seam."""
    try:
        from botforge.discord.locales import stored_guild_locale

        return str(await stored_guild_locale(bot, guild_id))
    except Exception:
        return "fr"


# ---------------------------------------------------------------------------
# The voice-presence listener (forfeit-line feeding, restart-safe flag)
# ---------------------------------------------------------------------------

_VOICE_LISTENER_REGISTERED = False


def _register_voice_listener(bot: Any) -> None:
    """Register the voice-presence listener once (restart-safe flag)."""
    global _VOICE_LISTENER_REGISTERED
    if _VOICE_LISTENER_REGISTERED:
        return
    add_listener = getattr(bot, "add_listener", None)
    if add_listener is None:
        return

    async def _on_voice_state_update(member: Any, before: Any, after: Any) -> None:
        from .common import wiring

        channel = getattr(after, "channel", None)
        if channel is None or getattr(member, "bot", False):
            return
        stack = wiring()
        if stack is None:
            return
        try:
            await stack.attacks.record_voice_join(
                int(getattr(channel, "id", 0)), str(getattr(member, "id", ""))
            )
        except Exception:
            logger.warning("kingdom: voice join record failed", exc_info=True)

    try:
        add_listener(_on_voice_state_update, "on_voice_state_update")
        _VOICE_LISTENER_REGISTERED = True
    except Exception:
        logger.warning("kingdom: voice listener registration failed", exc_info=True)


# ---------------------------------------------------------------------------
# The plan events (execute / switch / break + the récap DM edits)
# ---------------------------------------------------------------------------


async def run_plan_events_safe(
    bot: Any,
    stack: Any,
    guild: Any,
    strings: dict[str, str],
    locale: str,
) -> int:
    """Play the due plans: execute/switch/break + the DM récap edits.

    The executed declarations open their attack salon exactly like a
    manual one; every plan event reaches the player through his récap
    DM (edited in place, a fresh DM when the refs are lost).
    """
    from .common import dm_user_safe, fmt_paris
    from .panel import _open_attack_salon_safe
    from .plan import map_label, recap_with_declare, update_plan_dm_safe

    dirty = 0
    for plan in await stack.attacks.plan_events():
        dirty += 1
        executed_attack = None
        if plan.last_event == "executed" and plan.executed_attack_id:
            executed_attack = next(
                (
                    attack
                    for attack in await stack.attacks.attacks()
                    if str(attack.id) == str(plan.executed_attack_id)
                ),
                None,
            )
        # Build the event note FIRST (it reads last_event_map), then
        # clear the flag service side.
        note = ""
        if plan.last_event == "executed" and executed_attack is not None:
            note = strings["plan_event_executed"].format(
                map=map_label(stack, str(executed_attack.map_key)),
                time=fmt_paris(executed_attack.expires_at),
            )
        elif plan.last_event == "switched":
            note = strings["plan_event_switched"].format(
                old=map_label(stack, str(plan.last_event_map or "")),
                map=map_label(stack, str(plan.active_choice or "")),
            )
        elif plan.last_event in ("broken_by_declaration", "broken_target"):
            note = strings["plan_event_broken"].format(
                map=map_label(stack, str(plan.last_event_map or plan.active_choice or ""))
            )
        elif plan.last_event == "broken_budget":
            note = strings["plan_event_broken"].format(
                map=map_label(stack, str(plan.active_choice or ""))
            )
        elif plan.last_event == "broken_engaged":
            note = strings["lord_engaged"]
        elif plan.last_event == "broken_tavern":
            note = strings["lord_tavern_locked"]
        elif plan.last_event == "broken_lords_day":
            note = strings["plan_event_broken"].format(
                map=map_label(stack, str(plan.active_choice or ""))
            )
        elif plan.last_event == "cancelled":
            note = strings["plan_event_cancelled"]
        content = (await recap_with_declare(stack, plan, strings)) + "\n\n" + note
        sent = await update_plan_dm_safe(bot, stack, plan, content)
        if not sent:
            dm = await dm_user_safe(bot, str(plan.lord_id), content)
            if dm is not None:
                try:
                    await stack.attacks.record_plan_dm(
                        str(plan.id),
                        int(getattr(dm, "channel_id", 0) or 0),
                        int(getattr(dm, "id", 0) or 0),
                    )
                except Exception:
                    logger.warning("kingdom: plan DM ref not stored", exc_info=True)
        try:
            await stack.attacks.clear_plan_event(str(plan.id))
        except Exception:
            logger.warning("kingdom: plan event clear failed", exc_info=True)
        # The executed declarations open their salon exactly like a
        # manual one (the engine declared through the ordinary path).
        if executed_attack is not None:
            await _open_attack_salon_safe(guild, stack, strings, executed_attack, locale)
    return dirty


# ---------------------------------------------------------------------------
# The T-15 reveals (strict anonymity + the cover drop)
# ---------------------------------------------------------------------------


async def _record_reveal_message_safe(stack: Any, attack: Any, message: Any) -> None:
    """Record one reveal note ref (salon-nettoyage-v1, best effort).

    The T-15 reveal notes stay ABOVE the room's scoreboard and are
    swept when the WINNER is declared — the refs live in the attack's
    ``score["reveal_message_refs"]`` (restart-safe).
    """
    if message is None:
        return
    try:
        channel = getattr(message, "channel", None)
        await stack.attacks.record_attack_reveal_message(
            str(attack.id), int(getattr(channel, "id", 0)), int(message.id)
        )
    except Exception:
        logger.warning("kingdom: reveal message ref not stored", exc_info=True)


async def _run_reveals_safe(bot: Any, stack: Any, guild: Any, strings: dict[str, str]) -> int:
    """Announce the T-15 reveals in the attack's own salon.

    STRICT anonymity — the note is IDENTICAL whether a lord defended,
    the AI takes over or nobody answered; the WHO VS WHO matchup
    lands in the salon only once both drafts resolve. The cover (if
    any) still drops on the same beat, and the salon's name says the
    truth from then on (the REAL attacker vs the defender).
    """
    from .common import (
        attack_salon,
        attack_salon_send_safe,
        kingdom_name,
        lord_kingdom_name,
        lord_name,
        room_channel_name,
    )

    played = 0
    for attack in await stack.attacks.reveal_due():
        played += 1
        if attack.cover_lord_id:
            # bluff-externe-v1: the reveal puts EVERYTHING clear — the
            # real attacker AND his kingdom, under the cover of whom
            # and of which kingdom.
            cover_note = await attack_salon_send_safe(
                guild,
                attack,
                strings["reveal_cover"].format(
                    map=attack.map_key,
                    attacker=await lord_name(stack.kingdoms, attack.attacker_lord_id),
                    attacker_kingdom=await kingdom_name(
                        stack.kingdoms, attack.attacker_kingdom_id
                    ),
                    cover=await lord_name(stack.kingdoms, attack.cover_lord_id),
                    cover_kingdom=await lord_kingdom_name(
                        stack.kingdoms, attack.cover_lord_id
                    )
                    or "—",
                ),
            )
            await _record_reveal_message_safe(stack, attack, cover_note)
            # The salon wore the COVER name since the declaration — at
            # the reveal the name says the truth. Best effort and
            # idempotent: a failed rename never blocks the reveal.
            salon = attack_salon(guild, attack)
            if salon is not None:
                true_name = room_channel_name(
                    guild,
                    "🗡️",
                    await lord_name(stack.kingdoms, attack.attacker_lord_id),
                    await kingdom_name(stack.kingdoms, attack.defender_kingdom_id),
                )
                if str(getattr(salon, "name", "")) != true_name:
                    try:
                        await salon.edit(name=true_name)
                    except Exception:
                        logger.warning("kingdom: reveal rename failed", exc_info=True)
        note = strings["reveal_battle_anon"]
        sent = await attack_salon_send_safe(guild, attack, note)
        await _record_reveal_message_safe(stack, attack, sent)
    return played


# ---------------------------------------------------------------------------
# The WHO VS WHO matchup note (once BOTH drafts resolve)
# ---------------------------------------------------------------------------


async def _announce_matchup_safe(
    bot: Any,
    stack: Any,
    guild: Any,
    attack: Any,
    strings: dict[str, str],
) -> None:
    """beta-retours-v1: the WHO VS WHO salon note.

    The T-15 reveal stays anonymous — the salon learns the matchup
    only once BOTH drafts resolved: lord VS lord, or VS IA with the
    multijoueur / spectateurs reminders.
    """
    from .common import attack_salon_send_safe, kingdom_name, lord_name

    try:
        attacker = await lord_name(stack.kingdoms, attack.attacker_lord_id)
        if attack.ai_defender or not attack.defender_lord_id:
            kingdom = await kingdom_name(stack.kingdoms, attack.defender_kingdom_id)
            try:
                level = int(await stack.attacks.defense_ai_level(attack.defender_kingdom_id))
            except Exception:
                level = int((attack.effects or {}).get("ai_level", 0)) if attack.effects else 0
            content = str(strings["matchup_ai"]).format(
                attacker=attacker, kingdom=kingdom, level=level
            )
        else:
            defender = await lord_name(stack.kingdoms, attack.defender_lord_id)
            content = str(strings["matchup_v1"]).format(attacker=attacker, defender=defender)
        await attack_salon_send_safe(guild, attack, content)
    except Exception:
        logger.warning("kingdom: matchup note failed", exc_info=True)


# ---------------------------------------------------------------------------
# The 3h no-result reminder (DM only, no auto-forfeit)
# ---------------------------------------------------------------------------


async def _send_score_reminder_dm(bot: Any, attack: Any, strings: dict[str, str]) -> None:
    """Send the 3h no-result reminder DM to each human player."""
    from .common import dm_user_safe, score_players

    content = strings["score_reminder_dm"].format(map=attack.map_key)
    for player_id in score_players(attack):
        await dm_user_safe(bot, player_id, content)


# ---------------------------------------------------------------------------
# The meeting-time forfeits (expire_stale) and no-shows (ready_due)
# ---------------------------------------------------------------------------


async def _run_forfeits_safe(
    bot: Any, stack: Any, guild: Any, strings: dict[str, str]
) -> int:
    """Announce the meeting-time forfeits of the expired attacks."""
    from .common import attack_salon_send_safe, kingdom_name

    played = 0
    for attack in await stack.attacks.expire_stale():
        played += 1
        if attack.ai_defender:
            # The [T-15, T] window closed with no defender — the AI
            # takes the defense at the meeting time.
            await attack_salon_send_safe(
                guild,
                attack,
                strings["reveal_ai"].format(
                    map=attack.map_key,
                    kingdom=await kingdom_name(stack.kingdoms, attack.defender_kingdom_id),
                    level=(attack.effects or {}).get("ai_level", 0) if attack.effects else 0,
                ),
            )
        side = (attack.pickban or {}).get("forfeit_side")
        if not side:
            continue
        kingdom = await kingdom_name(stack.kingdoms, attack.winner_kingdom_id)
        if side == "both":
            await attack_salon_send_safe(
                guild, attack, strings["forfeit_both"].format(map=attack.map_key, kingdom=kingdom)
            )
        else:
            await attack_salon_send_safe(
                guild,
                attack,
                strings["forfeit_side"].format(
                    map=attack.map_key, side=strings[f"side_{side}"], kingdom=kingdom
                ),
            )
    return played


async def _run_noshows_safe(
    bot: Any, stack: Any, guild: Any, strings: dict[str, str]
) -> int:
    """Announce the T+5 no-show resolutions of the meetings."""
    from .battle import stamp_room_ping_winner_safe, sweep_reveal_notes_safe
    from .common import attack_salon_send_safe, kingdom_name

    played = 0
    for attack in await stack.attacks.ready_due():
        played += 1
        noshow = (attack.score or {}).get("noshow")
        if not noshow:
            continue
        if noshow == "both":
            await attack_salon_send_safe(
                guild, attack, strings["noshow_both"].format(map=attack.map_key)
            )
            continue
        kingdom = await kingdom_name(stack.kingdoms, attack.winner_kingdom_id)
        await attack_salon_send_safe(
            guild,
            attack,
            strings["noshow_side"].format(
                map=attack.map_key, side=strings[f"side_{noshow}"], kingdom=kingdom
            ),
        )
        # The room ping wears the winner; the reveal note above the
        # scoreboard dies with the meeting.
        await stamp_room_ping_winner_safe(bot, attack, kingdom, strings)
        await sweep_reveal_notes_safe(bot, attack)
    return played


# ---------------------------------------------------------------------------
# The per-guild phase run (never raises)
# ---------------------------------------------------------------------------


async def _run_phases_announce_safe(
    bot: Any,
    stack: Any,
    guild: Any,
    strings: dict[str, str],
    locale: str,
) -> int:
    """Play the per-attack-salon phases of one guild — never raise."""
    from .battle import (
        announce_conquest_safe,
        create_room_event_safe,
        dm_admins_dispute_safe,
        open_battle_room,
        refresh_room_message_safe,
        stamp_room_ping_winner_safe,
        sweep_reveal_notes_safe,
        sweep_sabotage_dms_on_open_safe,
    )
    from .common import attack_salon_send_safe, kingdom_name
    from .pickban import (
        edit_pickban_dms_default_reveal,
        edit_pickban_dms_reveal,
        send_pickban_dm,
    )

    dirty = 0
    try:
        dirty += await run_plan_events_safe(bot, stack, guild, strings, locale)
        dirty += await _run_reveals_safe(bot, stack, guild, strings)

        pickbans = await stack.attacks.pick_ban_due()
        for attack in pickbans:
            await send_pickban_dm(bot, attack, locale)
        dirty += len(pickbans)

        # Against the AI defender the draft resolves on the tick — the
        # AI validates its 3 random picks at ``ai_validate_at`` so the
        # attacker cannot tell instantly that the adversary is a bot.
        ai_drafts = await stack.attacks.ai_draft_due()
        for attack in ai_drafts:
            await edit_pickban_dms_reveal(bot, attack, strings)
        dirty += len(ai_drafts)

        # A defaulted draft (a side never ranked its civs at T) still
        # owed the players their reveal.
        defaults = await stack.attacks.default_reveal_due()
        for attack in defaults:
            await edit_pickban_dms_default_reveal(bot, attack, strings)
        dirty += len(defaults)

        # The AI « clicks Prêt » at ``ai_ready_at`` — the flip opens
        # the same scheduled event + footer refresh as a human pair.
        ai_readies = await stack.attacks.ai_ready_due()
        for attack in ai_readies:
            await create_room_event_safe(bot, stack, attack, strings)
            await refresh_room_message_safe(bot, stack, attack, locale)
        dirty += len(ai_readies)

        # At T the meeting opens the BATTLE ROOM (dedicated role, voice
        # channel, the shuffled civs in its text channel) and DMs the
        # link to both players.
        scores = await stack.attacks.score_due()
        for attack in scores:
            await open_battle_room(bot, stack, guild, attack, locale)
        dirty += len(scores)

        # The sabotage-phase closures (grace over or both Prêt) — the
        # stale sabotage buttons leave the DMs here, never at open.
        closures = await stack.attacks.sabotage_grace_close_due()
        for attack in closures:
            await sweep_sabotage_dms_on_open_safe(bot, attack, strings)
        dirty += len(closures)

        # The WHO VS WHO matchup note, once both drafts resolved (the
        # reveal stays strictly anonymous).
        matchups = await stack.attacks.matchup_due()
        for attack in matchups:
            await _announce_matchup_safe(bot, stack, guild, attack, strings)
            try:
                await stack.attacks.mark_matchup_announced(str(attack.id))
            except Exception:
                logger.warning("kingdom: matchup flag failed", exc_info=True)
        dirty += len(matchups)

        # The stale ID entry locks (a quit modal) — the room message
        # renders the plain 🔗 button again.
        unlocks = await stack.attacks.room_id_unlock_due()
        for attack in unlocks:
            await refresh_room_message_safe(bot, stack, attack, locale)
        dirty += len(unlocks)

        # A lone result declaration holds score_confirm_minutes, then
        # the declared result applies (fait foi) — announced like any
        # resolution.
        confirmed = await stack.attacks.score_confirm_due()
        for attack in confirmed:
            winner = await kingdom_name(stack.kingdoms, attack.winner_kingdom_id)
            await attack_salon_send_safe(
                guild,
                attack,
                strings["score_resolved"].format(
                    winner=winner,
                    map=attack.map_key,
                    game=(attack.score or {}).get("game_id") or "—",
                ),
            )
            # The room ping wears the winner too; the conquest reaches
            # Géopolitique; the reveal note dies with the meeting.
            await stamp_room_ping_winner_safe(bot, attack, winner, strings)
            await announce_conquest_safe(bot, stack, attack, locale)
            await sweep_reveal_notes_safe(bot, attack)
        dirty += len(confirmed)

        # The dispute DM rounds that failed (deadline past, or both
        # players still contrary) reach the admins — the last resort.
        handovers = await stack.attacks.dispute_handover_due()
        for attack in handovers:
            await dm_admins_dispute_safe(bot, stack, attack, strings)
            try:
                await stack.attacks.mark_dispute_admin_sent(str(attack.id))
            except Exception:
                logger.warning("kingdom: dispute admin flag failed", exc_info=True)
        dirty += len(handovers)

        # The 3h no-result reminder (DM only, no forfeit).
        reminders = await stack.attacks.score_reminder_due()
        for attack in reminders:
            await _send_score_reminder_dm(bot, attack, strings)
        dirty += len(reminders)

        # 15h without a declared result — the dispute auto-opens, the
        # admins arbitrate; no meeting hangs forever.
        disputes = await stack.attacks.dispute_due()
        for attack in disputes:
            await attack_salon_send_safe(
                guild, attack, strings["auto_dispute"].format(map=attack.map_key)
            )
        dirty += len(disputes)

        dirty += await _run_forfeits_safe(bot, stack, guild, strings)
        dirty += await _run_noshows_safe(bot, stack, guild, strings)
    except Exception:
        logger.warning("kingdom: phase run failed", exc_info=True)
    return dirty


# ---------------------------------------------------------------------------
# The tick (every guild, one pass)
# ---------------------------------------------------------------------------


async def run_attack_phases_safe(bot: Any) -> None:
    """Drive the D77 phases for every guild: reveal, DMs, rooms, forfeits.

    The resolved meetings free their battle room (channel + role) AND
    their per-attack salon — whatever the resolution (declared,
    forfeit, admin, cancelled).
    """
    from .battle import cleanup_battle_rooms_safe
    from .common import strings_by_locale, wiring

    stack = wiring()
    if stack is None:
        return
    _register_voice_listener(bot)
    for guild in list(getattr(bot, "guilds", []) or []):
        locale = await _guild_locale(bot, str(guild.id))
        strings = strings_by_locale(locale)
        await _run_phases_announce_safe(bot, stack, guild, strings, locale)
        # The resolved meetings free their battle room (channel +
        # role) AND their per-attack salon.
        try:
            await cleanup_battle_rooms_safe(bot, stack, guild)
        except Exception:
            logger.warning("kingdom: battle rooms cleanup failed", exc_info=True)


def start_attack_refresher(bot: Any) -> None:
    """Start the attack phases loop (every 5 minutes).

    Gated off in the test journeys
    (``BOTFORGE_KINGDOM_ATTACK_REFRESHER=off``): a background loop
    never settles, and the journeys' runner waits for the bot's
    outstanding work to drain.
    """
    import os

    if os.environ.get("BOTFORGE_KINGDOM_ATTACK_REFRESHER", "").lower() in {"off", "0", "false"}:
        return

    from discord.ext import tasks

    @tasks.loop(minutes=5)
    async def _loop() -> None:
        try:
            await run_attack_phases_safe(bot)
        except Exception:
            logger.warning("kingdom: attack phases pass failed — best-effort", exc_info=True)

    _loop.start()
    logger.info("kingdom: attack phases loop started (every 5 minutes)")
