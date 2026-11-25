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

import asyncio
import logging
from typing import Any

import discord

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
    async def on_voice_state_update(member: Any, before: Any, after: Any) -> None:
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
        # discord.py 2.7 removed add_listener — extra events ride bot.event
        bot.event(on_voice_state_update)
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
        # beta-fixes-v1 (Affaire 11): the matchup is the ONLY moment
        # the defender's identity exists — the vocal's name swaps the
        # adverse kingdom for the real defender (or stays « vs l'IA »).
        from .battle import rename_battle_room_vocal_safe

        await rename_battle_room_vocal_safe(guild, stack, attack, strings)
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
    """Announce the meeting-time forfeits of the expired attacks.

    affaire-27 (Drasah 25/11 tranché) : l'annonce part, PUIS l'habitat
    (vocal + rôle + salon texte) d'une résolution AUTO ferme
    immédiatement — un forfait n'ouvre pas de salle de discussion.
    L'anti-blocking AI defense n'est PAS une résolution : la partie
    continue (garde ``is_over``), rien ne se ferme.
    """
    from .battle import announce_forfeit_safe, cleanup_decided_attack_safe
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
        # affaire-30 (Drasah 25/11): la forfaiture atteint Géopolitique —
        # le salon ci-dessous ferme immédiatement, il n'est PAS une
        # surface durable ; Géo est LA surface de vérité des résolutions.
        await announce_forfeit_safe(bot, stack, attack, side, kingdom, strings)
        if getattr(attack, "is_over", False):
            await cleanup_decided_attack_safe(bot, stack, attack)
    return played


async def _run_noshows_safe(
    bot: Any, stack: Any, guild: Any, strings: dict[str, str]
) -> int:
    """Announce the T+5 no-show resolutions of the meetings.

    affaire-27 (Drasah 25/11 tranché) : l'annonce (et le ping du
    vainqueur) part, PUIS l'habitat du no-show ferme immédiatement —
    un forfait ne laisse jamais un rendez-vous fantôme de 30 minutes.
    """
    from .battle import (
        cleanup_decided_attack_safe,
        stamp_room_ping_winner_safe,
        sweep_reveal_notes_safe,
    )
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
            if getattr(attack, "is_over", False):
                await cleanup_decided_attack_safe(bot, stack, attack)
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
        if getattr(attack, "is_over", False):
            await cleanup_decided_attack_safe(bot, stack, attack)
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
    )
    from .common import attack_salon_send_safe, kingdom_name
    from .pickban import (
        edit_pickban_dms_default_reveal,
        edit_pickban_dms_reveal,
        send_pickban_dm,
        sweep_sabotage_dms_on_open_safe,
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
        # decisions-admin-v1 (Drasah 25/11): the auto road now DMs the
        # bot-admins the SAME arbitration panel as the contradictory
        # road — the admin never learns of a dead match by typing a
        # console command.
        disputes = await stack.attacks.dispute_due()
        for attack in disputes:
            await attack_salon_send_safe(
                guild, attack, strings["auto_dispute"].format(map=attack.map_key)
            )
            await dm_admins_dispute_safe(bot, stack, attack, strings)
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
        # meeting-heal-v1 (Drasah 24/11): a meeting opened WITHOUT its
        # salon (the salon-attaque-v1 incident) gets BOTH back here —
        # the next tick, idempotent, zero cost when all is well.
        await _meeting_salon_heal_safe(bot, stack, guild, strings, locale)
        # The resolved meetings free their battle room (channel +
        # role) AND their per-attack salon.
        try:
            await cleanup_battle_rooms_safe(bot, stack, guild)
        except Exception:
            logger.warning("kingdom: battle rooms cleanup failed", exc_info=True)


async def _meeting_salon_heal_safe(bot: Any, stack: Any, guild: Any, strings: dict[str, str], locale: str) -> None:
    """Rebuild the missing half of an open meeting (salon + scoreboard).

    meeting-heal-v1: an attack whose battle room opened while its
    attack salon was the victim of the salon-attaque-v1 bug reaches
    the 5-minute tick with a voice room and NO scoreboard — the
    players cannot ready nor declare a result, the meeting hangs.
    The pass walks the OPEN meetings missing their meeting message:
    the salon is created late when absent, then the scoreboard + its
    persistent buttons land exactly as at the open.
    """
    from .battle import post_meeting_message
    from .common import attack_salon
    from .panel import _open_attack_salon_safe

    try:
        meetings = [
            attack
            for attack in await stack.attacks.attacks()
            if not bool(getattr(attack, "is_over", True))
            and (dict(getattr(attack, "score", None) or {})).get("room_channel_id")
            and not (dict(getattr(attack, "score", None) or {})).get("meeting_message_id")
        ]
    except Exception:
        logger.warning("kingdom: meeting heal read failed — best-effort", exc_info=True)
        return
    for attack in meetings:
        fresh = attack
        if attack_salon(guild, attack) is None:
            try:
                await _open_attack_salon_safe(guild, stack, strings, attack, locale)
            except Exception:
                logger.warning("kingdom: late attack salon heal failed", exc_info=True)
                continue
            # the creation wrote attack_channel_id service-side — the
            # fresh doc carries the ref the posting needs.
            try:
                fresh = next(
                    (
                        candidate
                        for candidate in await stack.attacks.attacks()
                        if str(candidate.id) == str(attack.id)
                    ),
                    attack,
                )
            except Exception:
                fresh = attack
            logger.info(
                "kingdom: meeting heal opened the late attack salon (attack %s)",
                attack.id,
            )
        salon = await post_meeting_message(guild, stack, fresh, strings)
        if salon is not None:
            logger.info("kingdom: meeting heal landed the scoreboard (attack %s)", attack.id)


async def _event_report_text(strings: dict[str, str], report: dict[str, Any]) -> str:
    """Render one due report as a salon announcement (best effort)."""
    kind = str(report.get("kind", "cycle"))
    if kind == "age":
        return str(strings["event_age"]).format(
            age=str(report.get("display_name", report.get("age", "?"))),
            tech=report.get("tech_points", 0),
            marriages=report.get("extra_marriages", 0),
        )
    if kind == "end":
        if report.get("showmatch"):
            return str(strings["event_end_showmatch"])
        return str(strings["event_end"]).format(winner=str(report.get("winner_name") or "?"))
    return str(strings["event_cycle"]).format(
        cycle=report.get("cycle", "?"),
        maps=len(report.get("gaia_new_maps", []) or []),
    )


async def run_economy_due_safe(bot: Any) -> None:
    """Resolve the due explorations and sailing expeditions (the tick).

    marche-v2 art. 6: a 48h exploration ends with a fresh map (or a
    refund). exploration-refonte-v1: a due boarding WITH a captain
    launches itself; exploration-retour-v1: a due sailing flips to its
    RETURNED face. Every pass is idempotent — a restart mid-sail
    never resolves twice. The announcements land in Géopolitique,
    best effort per guild.
    """
    from .battle import _geopolitics_channel
    from .common import strings_by_locale, wiring

    stack = wiring()
    if stack is None:
        return
    from botforge.mods.kingdom.game_clock import game_now

    now = game_now()
    try:
        await stack.economy.resolve_due_explorations(now=now)
    except Exception:
        logger.warning("kingdom: exploration resolution failed — best-effort", exc_info=True)
    try:
        launches = await stack.economy.auto_launch_due_expeditions(now=now)
    except Exception:
        launches = []
        logger.warning("kingdom: expedition auto-launch failed — best-effort", exc_info=True)
    try:
        returns = await stack.economy.resolve_due_expeditions(now=now)
    except Exception:
        returns = []
        logger.warning("kingdom: expedition resolution failed — best-effort", exc_info=True)
    if not launches and not returns:
        return

    def _notes(strings: dict[str, str]) -> list[str]:
        out: list[str] = []
        for kingdom, kind, _value, _salon in launches:
            name = str(getattr(kingdom, "name", kingdom.id))
            out.append(str(strings["expedition_launch_note"]).format(name))
        for kingdom, kind, value, _salon in returns:
            name = str(getattr(kingdom, "name", kingdom.id))
            key = {"map": "expedition_return_map", "civ": "expedition_return_civ"}.get(kind)
            if key is None:
                out.append(str(strings["expedition_return_tech"]).format(name))
            else:
                out.append(str(strings[key]).format(name, str(value)))
        return out

    for guild in list(getattr(bot, "guilds", []) or []):
        locale = await _guild_locale(bot, str(guild.id))
        strings = strings_by_locale(locale)
        try:
            channel = _geopolitics_channel(guild)
            if channel is None:
                continue
            for note in _notes(strings):
                await channel.send(note)
        except Exception:
            logger.warning("kingdom: one expedition announcement failed", exc_info=True)
    # alliances-evenementiel-v1 (Drasah 23/11) : une expédition qui
    # RAPPORTE UNE CIVILISATION change la main du royaume — LE
    # déclencheur du panneau 🏆. Seuls les retours « civ » comptent
    # (une carte ou des points ne touchent pas la main), et la garde
    # de signature filtre le reste.
    civ_kingdoms = [
        str(getattr(kingdom, "id", "")) for kingdom, kind, _v, _s in returns if kind == "civ"
    ]
    if civ_kingdoms:
        try:
            from .realm_content import refresh_alliance_panels

            await refresh_alliance_panels(bot, civ_kingdoms)
        except Exception:
            logger.warning(
                "kingdom: alliances event refresh (expedition) failed — best-effort",
                exc_info=True,
            )


async def run_event_slots_safe(bot: Any) -> None:
    """Replay the due weekly slots (cycle/age/season end) and announce.

    The core season refresher's pattern (``EventService.run_due`` is
    restart-safe: the season state consumes the slots), with Drasah's
    pause rules — a FROZEN season and a season still in ``setup``
    replay no slot. The reports land in each guild's Géopolitique
    salon, best effort per guild.
    """
    from .battle import _geopolitics_channel
    from .common import strings_by_locale, wiring

    stack = wiring()
    if stack is None:
        return
    from botforge.mods.kingdom.game_clock import game_now, sync_game_offset

    await sync_game_offset(stack.kingdoms)
    try:
        season = await stack.kingdoms.current_season()
    except Exception:
        logger.warning("kingdom: events season read failed — best-effort", exc_info=True)
        return
    if season is None or season.frozen or season.phase == "setup":
        return
    async def _snapshotter(kind: str) -> None:
        """machine-temps-v3: photograph the exact pre-slot state.

        The run_due hook (Drasah's 19/11): every cycle/age/end slot
        replays onto a fresh snapshot, so « Cycle/Âge précédent »
        always finds the exact moment before the switch. Best-effort —
        a failed camera never blocks the replay.
        """
        try:
            await stack.kingdoms.snapshot(label=f"slot-{kind}")
        except Exception:
            logger.warning("kingdom: slot snapshot failed — best-effort", exc_info=True)

    try:
        reports = await stack.events.run_due(game_now(), snapshotter=_snapshotter)
    except Exception:
        logger.warning("kingdom: due-slot replay failed — best-effort", exc_info=True)
        return
    if not reports:
        return
    logger.info("kingdom: %s due slot(s) replayed", len(reports))
    for guild in list(getattr(bot, "guilds", []) or []):
        locale = await _guild_locale(bot, str(guild.id))
        strings = strings_by_locale(locale)
        for report in reports:
            try:
                channel = _geopolitics_channel(guild)
                if channel is not None:
                    await channel.send(await _event_report_text(strings, report))
            except Exception:
                logger.warning("kingdom: one event report announcement failed", exc_info=True)
    # alliances-evenementiel-v1 (Drasah 23/11) : un changement de
    # CYCLE vient de recalculer toutes les mains du moteur — LE
    # déclencheur naturel du panneau 🏆 (la main affichée a bougé).
    # La garde de signature fait le tri : un royaume dont la main
    # n'a pas bougé ne coûte AUCUN appel Discord.
    if any(str(report.get("kind", "")) == "cycle" for report in reports):
        try:
            from .realm_content import refresh_alliance_panels

            await refresh_alliance_panels(bot)
        except Exception:
            logger.warning(
                "kingdom: alliances event refresh (cycle) failed — best-effort",
                exc_info=True,
            )


async def run_mercenary_tick_safe(bot: Any) -> None:
    """Run the Chef Mercenaire tick (chef-mercenaire-v1).

    The Chief's clock is REAL Paris wall time (never the offset game
    clock): inside the 20h-21h window the daily market opens
    (idempotent — a CLOSED market of TODAY stays displayed, a closed
    market of ANOTHER day lets a fresh one open) and every tick closes
    the due market (replay-safe awards/refunds). The opening is
    skipped on a paused (frozen/setup) season, but a live market
    still closes — the escrowed écus must always come home. The open
    and close notes land in Géopolitique, best effort per guild.
    """
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from .battle import _geopolitics_channel
    from .common import strings_by_locale, wiring

    stack = wiring()
    if stack is None:
        return
    mercenary = getattr(stack, "mercenary", None)
    if mercenary is None:
        return
    moment = datetime.now(UTC)
    paris_today = moment.astimezone(ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d")

    opened = False
    try:
        doc = await mercenary.market()
    except Exception:  # noqa: BLE001 — a read failure defers to the next tick
        logger.warning("kingdom: mercenary market read failed — best-effort", exc_info=True)
        return
    opens = False
    if doc is None:
        opens = True
    elif doc.get("closed", False):
        opens = str(doc.get("date")) != paris_today
    if opens and mercenary.inside_window(moment):
        try:
            season = await stack.kingdoms.current_season()
            if season is not None and not season.frozen and season.phase != "setup":
                await mercenary.open_market(now=moment)
                opened = True
                logger.info("kingdom: mercenary market opened (window)")
        except Exception:  # noqa: BLE001 — the window guard raced us, next tick retries
            logger.warning("kingdom: mercenary open failed — best-effort", exc_info=True)
    awards: list[Any] = []
    try:
        awards = await mercenary.close_if_due(now=moment)
    except Exception:  # noqa: BLE001
        logger.warning("kingdom: mercenary close failed — best-effort", exc_info=True)
        return
    if not opened and not awards:
        return
    for guild in list(getattr(bot, "guilds", []) or []):
        locale = await _guild_locale(bot, str(guild.id))
        strings = strings_by_locale(locale)
        try:
            channel = _geopolitics_channel(guild)
            if channel is None:
                continue
            if opened:
                await channel.send(str(strings["mercenary_open_note"]))
            if awards:
                await channel.send(str(strings["mercenary_close_note"]).format(len(awards)))
        except Exception:  # noqa: BLE001
            logger.warning("kingdom: one mercenary announcement failed — best-effort", exc_info=True)


async def run_ffa_tick_safe(bot: Any) -> None:
    """Run the Saturday FFA Exploration tick (ffa-exploration-v1).

    Draw (or read back) this Saturday's random start hour; announce in
    Géopolitique 2h before — the announcement carries the persistent
    « Aller explorer » button and opens the enrollments; at the drawn
    hour the game starts. Every step replays safely through the
    persisted document (announced/started flags).

    #367 conformance: the announcement ALSO opens the FFA's ephemeral
    salon (restructuration-serveur-v1 c) right under « Déclarer une
    attaque » — visible to everyone, @everyone denied send — carrying
    the same persistent join button; the start line lands there too,
    and a finished FFA takes its salon with it (idempotent purge).
    """
    from zoneinfo import ZoneInfo

    from .battle import _geopolitics_channel
    from .common import strings_by_locale, wiring
    from .ffa import FFAJoinButton

    stack = wiring()
    if stack is None:
        return
    ffa_service = getattr(stack, "ffa", None)
    if ffa_service is None:
        return
    if not list(getattr(bot, "guilds", []) or []):
        return
    from botforge.mods.kingdom.game_clock import game_now

    now = game_now()
    try:
        ffa = await ffa_service.draw_or_get(now)
    except Exception:  # noqa: BLE001 — a draw failure defers to the next tick
        logger.warning("kingdom: FFA draw failed — best-effort", exc_info=True)
        return
    if ffa is None:
        return
    if getattr(ffa, "finished", False) and getattr(ffa, "salon_id", None):
        for guild in list(getattr(bot, "guilds", []) or []):
            await _ffa_salon_purge_safe(guild, ffa)
    events_settings = getattr(stack.config, "events", None)
    tz = ZoneInfo(str(getattr(events_settings, "schedule_timezone", "UTC") or "UTC"))
    if ffa_service.due_announce(ffa, now):
        try:
            await ffa_service.mark_announced(ffa)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom: FFA announce flag failed — best-effort", exc_info=True)
        time_label = int(ffa.start_at.timestamp())
        maximum = int(ffa_service.max_participants())
        mode_key = "ffa_mode_one" if ffa.one_lord_per_kingdom else "ffa_mode_free"
        for guild in list(getattr(bot, "guilds", []) or []):
            locale = await _guild_locale(bot, str(guild.id))
            strings = strings_by_locale(locale)
            try:
                channel = _geopolitics_channel(guild)
                if channel is None:
                    continue
                text = str(strings["ffa_announce"]).format(
                    time_label,
                    int(getattr(events_settings, "ffa_game_minutes", 75)),
                    maximum,
                    str(strings[mode_key]),
                )
                from .common import surface as _surface

                view = _surface(
                    "panel:mod:kingdom:ffa:salon",
                    discord.ui.ActionRow(FFAJoinButton(strings["ffa_join_button"])),
                )
                await channel.send(text, view=view)
            except Exception:  # noqa: BLE001
                logger.warning("kingdom: FFA announcement failed — best-effort", exc_info=True)
                continue
            try:
                await _open_ffa_salon_safe(bot, ffa_service, ffa, guild, strings, text, view)
            except Exception:  # noqa: BLE001
                logger.warning("kingdom: FFA salon open failed — best-effort", exc_info=True)
        return
    if ffa_service.due_start(ffa, now):
        started = None
        try:
            started = await ffa_service.start_due(now)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom: FFA start failed — best-effort", exc_info=True)
        if started is None:
            return
        for guild in list(getattr(bot, "guilds", []) or []):
            locale = await _guild_locale(bot, str(guild.id))
            strings = strings_by_locale(locale)
            start_text = str(strings["ffa_start"]).format(
                len(started.participants),
                int(getattr(events_settings, "ffa_game_minutes", 75)),
            )
            try:
                channel = _geopolitics_channel(guild)
                if channel is None:
                    continue
                await channel.send(start_text)
            except Exception:  # noqa: BLE001
                logger.warning("kingdom: FFA start announcement failed", exc_info=True)
            salon = _ffa_salon(guild, started)
            if salon is not None:
                try:
                    await salon.send(start_text)
                except Exception:  # noqa: BLE001
                    logger.warning("kingdom: FFA salon start message failed", exc_info=True)


def _ffa_salon(guild: Any, ffa: Any) -> Any:
    """Return the FFA's ephemeral salon by its STORED ref (never a name)."""
    if guild is None:
        return None
    channel_id = int(getattr(ffa, "salon_id", 0) or 0)
    if not channel_id:
        return None
    return getattr(guild, "get_channel", lambda _id: None)(channel_id)


async def _ffa_salon_purge_safe(guild: Any, ffa: Any) -> None:
    """Delete the FFA's ephemeral salon once the FFA is over (idempotent)."""
    channel = _ffa_salon(guild, ffa)
    if channel is None:
        return
    try:
        await channel.delete()
        logger.info("kingdom: FFA salon deleted (FFA over)")
    except Exception:  # noqa: BLE001
        logger.warning("kingdom: FFA salon deletion failed — best-effort", exc_info=True)


async def _open_ffa_salon_safe(
    bot: Any,
    ffa_service: Any,
    ffa: Any,
    guild: Any,
    strings: dict[str, str],
    text: str,
    view: Any,
) -> None:
    """Open the FFA's ephemeral salon and pin its base message.

    restructuration-serveur-v1 c, #367: a dedicated salon — same logic
    as the per-attack salons — opens right under « Déclarer une attaque »
    so the sidebar shows what is being played. Visible to everyone,
    @everyone denied send (the overwrite set carries an explicit
    guild.me entry — lesson Check 75). The base message repeats the
    announcement with the persistent join button; the salon dies with
    the FFA.
    """
    from .common import FFA_SALON_OVERWRITES, delete_dynamic_channel_safe, open_dynamic_channel_safe, slug
    from .panel import _declare_channel

    declare = await _declare_channel(guild)
    if declare is None:
        return
    title = str(strings["ffa_salon_title"])
    wanted = slug(title)
    # A leftover salon from a previous Saturday (or a wipe mid-week) is
    # purged first — the name is fixed, so at most one lives at a time.
    for channel in list(getattr(guild, "text_channels", []) or []):
        if slug(getattr(channel, "name", "")) == wanted:
            await delete_dynamic_channel_safe(bot, channel.id)
    position = int(getattr(declare, "position", 0) or 0) + 1
    channel = await open_dynamic_channel_safe(
        guild,
        title,
        category=getattr(declare, "category", None),
        kind="text",
        overwrites=FFA_SALON_OVERWRITES,
        position=position,
    )
    if channel is None:
        logger.warning("kingdom: FFA salon creation failed")
        return
    try:
        await ffa_service.record_salon(ffa, int(channel.id))
    except Exception:  # noqa: BLE001
        logger.warning("kingdom: FFA salon ref not stored", exc_info=True)
    try:
        await channel.send(text, view=view)
    except Exception:  # noqa: BLE001
        logger.warning("kingdom: FFA salon base message failed", exc_info=True)


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
        try:
            await run_event_slots_safe(bot)
        except Exception:
            logger.warning("kingdom: event slots pass failed — best-effort", exc_info=True)
        try:
            await run_economy_due_safe(bot)
        except Exception:
            logger.warning("kingdom: economy due pass failed — best-effort", exc_info=True)
        try:
            await run_mercenary_tick_safe(bot)
        except Exception:
            logger.warning("kingdom: mercenary tick failed — best-effort", exc_info=True)
        try:
            await run_ffa_tick_safe(bot)
        except Exception:
            logger.warning("kingdom: FFA tick failed — best-effort", exc_info=True)
        # boucle bêta (levier-bêta-v1, Check 140, Drasah 22/11) : une
        # saison bêta qui se termine TOUTE SEULE (slot end → verdict,
        # phase « ended ») se RELANCHE toute seule ici — la boucle de
        # test continue jusqu'au « 🏁 Terminer » de l'admin (LE stop).
        try:
            from .beta_loop import run_beta_loop_safe

            await run_beta_loop_safe(bot)
        except Exception:
            logger.warning("kingdom: beta loop pass failed — best-effort", exc_info=True)
        # territory-reveal-v1-fix (Drasah 23/11) : l'alimentation vit DANS
        # la passe de 5 min, PAS dans la seule relance de fin de bêta (le
        # retour None d'une saison non finie court-circuitait le
        # nourrissage — les salons restaient vides à jamais). Le tirage
        # et les fiches sont idempotents : une saison saine ne coûte
        # QUE l'edit en place des fiches déjà justes (la règle de la
        # référence : aucune vue ne périme, le scheduler re-rend).
        try:
            from .realm_content import feed_season_surfaces

            # alliances-evenementiel-v1 (Drasah 23/11) : le panneau
            # 🏆 ne vit PLUS dans la passe périodique — il s'actualise
            # UNIQUEMENT quand une main change (cycle, expédition,
            # mariage, départ), via le seam refresh_alliance_panels.
            await feed_season_surfaces(bot, include_alliances=False)
        except Exception:
            logger.warning("kingdom: surface feeding pass failed — best-effort", exc_info=True)
        # gate-bêta-v1 (Check 141, Drasah 23/11) : la ceinture de
        # sécurité des salons d'admission — la gate ne vivait qu'aux
        # départs/boot, un levier basculé (ou un raté ponctuel) laissait
        # les permissions en retard jusqu'au prochain départ. Une passe
        # par 5 min les plie sur le parcours EFFECTIF, les deux sens
        # se réparent tout seuls (idempotente : _converged skips les
        # salons déjà conformes, zéro ratelimit Discord inutile).
        try:
            from .conscription_gate import run_conscription_gate_pass

            await run_conscription_gate_pass(bot)
        except Exception:
            logger.warning("kingdom: conscription gate pass failed — best-effort", exc_info=True)

    _loop.start()
    _start_attack_fast_lane(bot)
    logger.info("kingdom: attack phases loop started (every 5 minutes)")


# -- the fast lane (temporalites-beta-v1, Drasah 25/11) ----------------------
#
# The 5-minute tick let every attack phase land up to 5 minutes late
# (the reveal cutoff T-15, the T flip, the draft deadline): under the
# 10-minute beta itinerary the whole draft window died before the
# tick arrived. The lane REUSES the engine's next_phase_deadline probe
# (attack-phases-tick-v1/v2) — no second computation, it only sleeps
# at the next deadline and runs the SAME pass. Best effort: any probe
# failure keeps the stock cadence, and the gate env above cuts it too.

_ATTACK_TICK_EPSILON_SECONDS = 2.0
_ATTACK_TICK_FLOOR_SECONDS = 5.0
_ATTACK_BETA_TICK_SECONDS = 60
_ATTACK_FASTLANE_TASK: Any = None


async def attack_fastlane_sleep_seconds(bot: Any, default_seconds: int) -> int:
    """Sleep until the NEXT attack deadline — never 5 minutes late.

    The lane asks the engine's ``next_phase_deadline`` probe (ported
    intact: the reveal cutoff, T, the AI think times, the no-show
    line, the urgent state flips, the live plans) and sleeps exactly
    that long — bounded by the stock (60 s under an armed beta)
    cadence: an idle board sleeps as long as before, a deadline at
    the door wakes the lane within seconds. Best effort: any probe
    failure keeps the stock cadence.
    """
    from botforge.mods.kingdom.game_clock import game_now

    from .common import wiring

    base = default_seconds
    stack = None
    try:
        stack = wiring()
    except Exception:
        logger.warning("kingdom: the fast lane wiring probe failed", exc_info=True)
    if stack is not None:
        try:
            from botforge.mods.kingdom.beta_weekend import beta_started

            season = await stack.kingdoms.current_season()
            if season is not None and beta_started(season, game_now()):
                base = min(base, _ATTACK_BETA_TICK_SECONDS)
        except Exception:
            logger.warning("kingdom: the fast lane beta probe failed", exc_info=True)
        try:
            now = game_now()
            deadline = await stack.attacks.next_phase_deadline(now=now)
            if deadline is not None:
                delta = (deadline - now).total_seconds()
                if delta <= 0:
                    # A deadline already due (or an urgent state flip
                    # that can advance RIGHT NOW): run the lane's work.
                    return 1
                seconds = max(_ATTACK_TICK_FLOOR_SECONDS, delta + _ATTACK_TICK_EPSILON_SECONDS)
                return min(base, int(seconds))
        except Exception:
            logger.warning("kingdom: the fast lane deadline probe failed", exc_info=True)
    return base


async def _attack_fast_lane(bot: Any) -> None:
    """Run the deadline-driven pass — same work as the tick, at the second."""
    while True:
        await asyncio.sleep(await attack_fastlane_sleep_seconds(bot, 300))
        try:
            await run_attack_phases_safe(bot)
        except Exception:
            logger.warning("kingdom: fast lane pass failed — best-effort", exc_info=True)


def _start_attack_fast_lane(bot: Any) -> None:
    """Arm the fast lane once per process (never a second loop)."""
    global _ATTACK_FASTLANE_TASK

    if _ATTACK_FASTLANE_TASK is not None and not _ATTACK_FASTLANE_TASK.done():
        return
    try:
        loop = asyncio.get_running_loop()
        _ATTACK_FASTLANE_TASK = loop.create_task(_attack_fast_lane(bot))
        logger.info("kingdom: attack fast lane armed (deadline-driven)")
    except RuntimeError:  # no running loop in the test journeys
        logger.warning("kingdom: attack fast lane disarmed (no running loop)")
