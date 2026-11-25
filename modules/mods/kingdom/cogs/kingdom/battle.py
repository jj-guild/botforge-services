"""The battle room + the score flow of a meeting (P4.1b tranche 2b).

The ported functional reference (kingdom_attack_panel.py, D77):

* the room opening — a dedicated « Bataille {map} » role, a voice
  channel under the provisioned « Champs de Bataille » category
  (user_limit 2, never created here), and ONE meeting message in the
  ATTACK SALON carrying the symmetric scoreboard + the persistent
  buttons (restructuration-serveur-v1 b);
* the scoreboard — neutral infos (map, game ID) centered, attacker
  left / defender right, each half with its OWN Prêt state; a Prêt
  click edits the message in place (battle-room-id-v1/v2);
* the 🔗 ID button — a PERSISTED 5-minute lock (the same player
  re-enters, the other is refused), the modal stores the lobby ID and
  unlocks; the ✅ Prêt buttons ride each side (grey → green, disabled
  once marked), 🏆 Déclarer appears once BOTH are Prêt — and the
  second Prêt creates the Discord scheduled event;
* the score flow — a winner select, an EXPLICIT confirmation
  (anti-missclick), the other player's declaration review
  (confirm/contest), one's own declaration (modify), the shared
  ``declare_score`` path (resolved / pending / disputed / already);
* the dispute round — a contrary declaration opens a private DM round
  for BOTH players (modify or confirm) before any admin wakes up, the
  admins arbitrate through the DM's arbitration buttons;
* the resolution — the room ping wears the 🏆 winner, the conquest
  is announced in Géopolitique with its detail thread, the room
  re-renders in place and the reveal notes sweep;
* the cleanup — the room (channel + role) AND the attack salon die
  ``room_cleanup_delay_minutes`` after the winner is known, the
  leftovers sweep re-runs the deletion a refused flag never retried.

Every component is a persistent DynamicItem — a restart between the
send and the click never kills the flow. All Discord writes are
best-effort: a failing edit never breaks the engine state.

Degradation (assumed, reported): the reference's blasons/crests
mosaic banner is NOT ported — the meeting message wears the text
scoreboard alone (the seam returns the day the visual generator
exists).
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import discord

from botforge.discord.ui.views import ComposedView
from botforge.mods.kingdom.game_clock import game_now
from botforge.mods.kingdom.models import AttackState

from .common import (
    attack_by_id,
    attack_salon,
    dm_user_safe,
    dm_view,
    fmt_paris,
    final_civ,
    kingdom_name,
    surface_footer,
    lord_name,
    lord_of,
    locale_of,
    open_unique_ephemeral,
    open_dynamic_channel_safe,
    room_channel_name,
    room_key,
    room_side_of,
    score_players,
    shuffled_civs,
    strings_by_locale,
    wiring,
)

logger = logging.getLogger("kingdom.attack")

# Custom ids (the mod's namespace — never the raw attack id, Check 73).
_ROOM_DRAFT = "kingdom:attack:room:draft:{key}"
_ROOM_URL = "kingdom:attack:room:url:{key}"
_ROOM_RESULT = "kingdom:attack:room:result:{key}"
_ROOM_READY = "kingdom:attack:room:ready:{key}"
# affaire-27: the ready-click phase wake — held so it is never GC'd mid-run.
_PHASE_WAKE_TASKS: set[asyncio.Task[None]] = set()
_ROOM_READY_SIDE = "kingdom:attack:room:ready:{key}:{side}"
_DISPUTE_PICK = "kingdom:attack:dispute:pick:{key}"
_DISPUTE_CONFIRM = "kingdom:attack:dispute:confirm:{key}"
_DISPUTE_ARBITRATE = "kingdom:attack:dispute:arbitrate:{choice}:{key}"

_BATTLE_ROLE_NAME_PREFIXES: tuple[str, ...] = ("Bataille ", "Battle ")
_ROOM_SCORE_WIDTH = 46

# litige-mp-v1: the living dispute DM round of each meeting — one
# message ref per player, so a convergence or an admin handover
# re-edits BOTH DMs in place. Best effort: a restart loses the refs.
_DISPUTE_DMS: dict[str, dict[str, Any]] = {}


def strings_of(interaction: discord.Interaction) -> dict[str, str]:
    return strings_by_locale(locale_of(interaction))


async def resolve_room_key(stack: Any, key: str) -> str:
    """Resolve a room key back to an attack id (the async service scan)."""
    if stack is None or not key:
        return ""
    try:
        for attack in await stack.attacks.attacks():
            if room_key(str(attack.id)) == key:
                return str(attack.id)
    except Exception:
        logger.warning("kingdom: room key resolution failed", exc_info=True)
    return ""


# ---------------------------------------------------------------------------
# The scoreboard (battle-room-id-v1/v2)
# ---------------------------------------------------------------------------


def _score_center(text: str) -> str:
    """Center a neutral line of the scoreboard (monospace block)."""
    text = text[:_ROOM_SCORE_WIDTH]
    pad = _ROOM_SCORE_WIDTH - len(text)
    return " " * (pad // 2) + text + " " * (pad - pad // 2)


def _score_row(left: str, right: str) -> str:
    """One symmetric scoreboard row — left field, right field."""
    half = _ROOM_SCORE_WIDTH // 2
    left = left[: half - 2]
    right = right[: half - 2]
    return left.ljust(half - 2) + " " * 4 + right.rjust(half - 2)


async def room_body_text(stack: Any, attack: Any, strings: dict[str, str]) -> str:
    """Build the meeting scoreboard — the symmetric view of the room.

    The neutral infos (map, game ID) sit centered on top, the attacker
    on the LEFT and the defender on the RIGHT, each with their OWN
    Prêt state. A monospace block keeps the alignment stable whatever
    the name lengths — a Prêt click edits the player's half in place.
    """
    score = dict(attack.score or {})
    ready = {str(player) for player in (score.get("ready") or [])}
    url = str(attack.lobby_url or "").strip()
    attacker = await lord_name(stack.kingdoms, attack.attacker_lord_id)
    defender = await lord_name(stack.kingdoms, attack.defender_lord_id)

    def _status(player_id: Any) -> str:
        if not url:
            # With no game ID yet the sides stay EMPTY — the single
            # centered « 🔗 en attente de l'ID » line says it all.
            return ""
        if player_id and str(player_id) in ready:
            return strings["room_side_ready"]
        return strings["room_side_wait"]

    attacker_status = _status(attack.attacker_lord_id)
    if attack.ai_defender:
        level = int((attack.effects or {}).get("ai_level") or 0)
        defender_status = strings["room_side_ai"].format(level=level)
    else:
        defender_status = _status(attack.defender_lord_id)
    id_line = strings["room_scoreboard_id"].format(id=url) if url else strings["room_side_none"]
    rows = [
        _score_center(strings["room_scoreboard_map"].format(map=attack.map_key)),
        _score_center(id_line),
        "",
        _score_row(attacker, defender),
        _score_row(attacker_status, defender_status),
    ]
    body = "```\n" + "\n".join(rows) + "\n```"
    if attack.ai_defender:
        level = int((attack.effects or {}).get("ai_level") or 0)
        body += "\n" + strings["room_ai_disclaimer"].format(level=level)
    if score.get("all_ready"):
        body += "\n" + strings["room_scoreboard_footer"]
    body += "\n" + surface_footer("panel:mod:kingdom:battle:room")
    return body


def _room_id_locked_by(attack: Any) -> str:
    """The LIVE ID-entry locker's id ("" when free).

    The lock is a PERSISTED stamp in the score doc — an expired
    stamp (or a landed URL) never blocks anyone, restart or not.
    """
    score = dict(attack.score or {})
    lock = dict(score.get("id_lock") or {})
    if not lock.get("by"):
        return ""
    if str(attack.lobby_url or "").strip():
        return ""
    try:
        until = float(lock.get("until") or 0)
    except Exception:
        return ""
    if game_now().timestamp() >= until:
        return ""
    return str(lock["by"])


async def room_view(stack: Any, attack: Any, strings: dict[str, str], *, id_pending: bool = False) -> discord.ui.View:
    """Build the meeting button set — 📜 draft first, then the split row."""
    score = dict(attack.score or {})
    view = discord.ui.View(timeout=None)
    # draft-visible-tous-v1: NO side guard — every member may read it.
    view.add_item(DraftViewButton(str(attack.id), strings["draft_button"]))
    # resultat-nettoyage-v1: once the winner is declared the meeting
    # controls are DEAD WEIGHT — only the 📜 draft sheet survives.
    if getattr(attack, "is_over", False):
        return view
    ready_ids = {str(player) for player in (score.get("ready") or [])}
    url_set = bool(str(attack.lobby_url or "").strip())
    if url_set:
        attacker = await lord_name(stack.kingdoms, attack.attacker_lord_id)
        attacker_done = str(attack.attacker_lord_id) in ready_ids
        label = (
            strings["room_ready_done_attacker_button"]
            if attacker_done
            else strings["room_ready_attacker_button"]
        ).format(player=attacker)
        view.add_item(RoomReadyButton(str(attack.id), label, side="attacker", done=attacker_done))
    locked_by = _room_id_locked_by(attack)
    if id_pending or locked_by:
        # The locked button stays ENABLED — the SAME player may
        # re-click (the modal reopens, the stamp refreshes); the OTHER
        # player is refused at the click while the stamp lives.
        view.add_item(RoomUrlButton(str(attack.id), strings["room_id_pending_button"]))
    else:
        label = strings["room_id_modify_button"] if url_set else strings["room_id_button"]
        style = discord.ButtonStyle.danger if url_set else discord.ButtonStyle.secondary
        view.add_item(RoomUrlButton(str(attack.id), label, style=style))
    if score.get("all_ready"):
        view.add_item(RoomResultButton(str(attack.id), strings["result_button"]))
    if url_set and attack.defender_lord_id and not attack.ai_defender:
        defender = await lord_name(stack.kingdoms, attack.defender_lord_id)
        defender_done = str(attack.defender_lord_id) in ready_ids
        label = (
            strings["room_ready_done_defender_button"]
            if defender_done
            else strings["room_ready_defender_button"]
        ).format(player=defender)
        view.add_item(RoomReadyButton(str(attack.id), label, side="defender", done=defender_done))
    return view


async def refresh_room_message_safe(bot: Any, stack: Any, attack: Any, locale: str, *, id_pending: bool = False) -> None:
    """Best-effort refresh of the room's single message (ID → Prêt → 🏆)."""
    if attack is None:
        return
    score = dict(attack.score or {})
    channel_id = int(score.get("meeting_channel_id") or 0)
    message_id = int(score.get("meeting_message_id") or 0)
    if not channel_id or not message_id or stack is None:
        return
    strings = strings_by_locale(locale)
    for guild in list(getattr(bot, "guilds", []) or []):
        channel = getattr(guild, "get_channel", lambda _id: None)(channel_id)
        if channel is None or not hasattr(channel, "get_partial_message"):
            continue
        try:
            message = channel.get_partial_message(message_id)
            await message.edit(
                content=await room_body_text(stack, attack, strings),
                view=await room_view(stack, attack, strings, id_pending=id_pending),
            )
        except Exception:
            logger.warning("kingdom: battle room refresh failed", exc_info=True)


# ---------------------------------------------------------------------------
# The room opening (Drasah 18/10 v2)
# ---------------------------------------------------------------------------


def _battle_room_overwrites(role_name: str) -> dict[str, dict[str, bool]]:
    """Build the battle-room channel overwrites (players' role only) — DATA form (#408).

    Check 75 live: the @everyone deny locked the BOT itself out of
    the channel it had just created — the bot carries its own
    overwrites (@me).
    """
    return {
        role_name: {"connect": True, "view_channel": True},
        "@me": {
            "view_channel": True,
            "connect": True,
            "send_messages": True,
            "read_message_history": True,
        },
        "@everyone": {"connect": False, "view_channel": False},
    }


async def _grant_battle_room_role_safe(guild: Any, role: Any, player_id: str) -> None:
    """Give the battle-room role to one player (best effort)."""
    member = None
    try:
        member = guild.get_member(int(player_id))
    except (TypeError, ValueError):
        member = None
    if member is None:
        try:
            member = await guild.fetch_member(int(player_id))
        except Exception:
            member = None
    if member is not None:
        try:
            await member.add_roles(role)
        except Exception:
            logger.warning("kingdom: battle room role grant failed", exc_info=True)


async def _record_safe(stack: Any, method: str, attack_id: str, *values: int) -> None:
    """Store a room/message ref through the attacks service (best effort)."""
    if stack is None:
        return
    try:
        await getattr(stack.attacks, method)(str(attack_id), *(int(value) for value in values))
    except Exception:
        logger.warning("kingdom: room ref not stored (%s)", method, exc_info=True)


async def post_meeting_message(guild: Any, stack: Any, attack: Any, strings: dict[str, str]) -> Any:
    """Post the ONE meeting message in the attack salon.

    Extract of open_battle_room (meeting-heal-v1 — Drasah 24/11).
    The scoreboard + the persistent URL/result buttons live here; the
    salon PINGS the players when the message lands. Returns the salon
    (None when the salon is missing — the meeting heal replaces the
    old bare warning by CREATING the salon then retrying).
    """
    salon = attack_salon(guild, attack)
    if salon is None:
        logger.warning("kingdom: no attack salon for the meeting message")
        return None
    try:
        message = await salon.send(
            await room_body_text(stack, attack, strings),
            view=await room_view(stack, attack, strings),
        )
        await _record_safe(stack, "record_meeting_message", attack.id, int(salon.id), int(message.id))
        # beta-fixes-v1: the scoreboard landing IS the phase's real
        # opening — the reminder/dispute clocks re-anchor on it (a
        # healed room inherits a fresh window, a healthy one land at
        # the same second and notices nothing).
        await _restamp_score_clock_safe(stack, attack)
        # The salon PINGS the players the moment the room
        # opens — never the AI (no ping-able user).
        if attack.defender_lord_id and not attack.ai_defender:
            ping = await salon.send(
                strings["room_ping_message"].format(
                    attacker=f"<@{attack.attacker_lord_id}>",
                    defender=f"<@{attack.defender_lord_id}>",
                )
            )
        else:
            ping = await salon.send(
                strings["room_ping_attacker_only"].format(
                    attacker=f"<@{attack.attacker_lord_id}>"
                )
            )
        # The ping is the message the players watch — record
        # its ref so every resolution can stamp the 🏆 winner.
        await _record_safe(stack, "record_ping_message", attack.id, int(salon.id), int(ping.id))
    except Exception:
        logger.warning("kingdom: meeting message post failed", exc_info=True)
        return None
    # salon-nettoyage-v1: the scoreboard just replaced the
    # pre-room messages — the declaration announce is swept
    # so the salon reads in ONE glance (the reveal notes stay
    # until the resolution).
    await sweep_pre_room_announces_safe(guild, stack, attack)
    return salon


async def battle_room_defender_label(stack: Any, attack: Any, strings: dict[str, str]) -> str:
    """Label the vocal's second side per the Affaire 11 rule (beta-fixes-v1).

    « {joueur attaquant} vs {royaume adverse} » until the matchup
    reveal — the ONLY moment the defender's identity exists — then
    the REAL defender's name, or « l'IA » when the bot plays the
    defense (the room stays open against the AI). The attack
    announcement keeps the kingdom's name, even against the AI.
    """
    if getattr(attack, "ai_defender", False) or not getattr(attack, "defender_lord_id", None):
        return str(strings["room_vocal_ai"])
    if (attack.pickban or {}).get("matchup_announced"):
        return await lord_name(stack.kingdoms, attack.defender_lord_id)
    return await kingdom_name(stack.kingdoms, attack.defender_kingdom_id)


async def rename_battle_room_vocal_safe(
    guild: Any, stack: Any, attack: Any, strings: dict[str, str]
) -> None:
    """Swap the vocal's kingdom name for the defender at the reveal.

    Rides the matchup announcement (the moment the defender's
    identity becomes public). Idempotent and best effort — a failed
    rename never blocks the reveal flow.
    """
    if guild is None:
        return
    channel_id = int((attack.score or {}).get("room_channel_id") or 0)
    channel = guild.get_channel(channel_id) if channel_id else None
    if channel is None:
        return
    attacker = await lord_name(stack.kingdoms, attack.attacker_lord_id)
    label = await battle_room_defender_label(stack, attack, strings)
    # The room itself is out of the uniqueness pass — renaming must not
    # collide with the channel's own previous name.
    others = SimpleNamespace(
        channels=[item for item in getattr(guild, "channels", []) or [] if item is not channel]
    )
    desired = room_channel_name(others, "⚔️", attacker, label)
    if str(getattr(channel, "name", "")) == desired:
        return
    try:
        await channel.edit(name=desired)
        logger.info("kingdom: battle room renamed at the reveal (%s)", attack.map_key)
    except Exception:
        logger.warning("kingdom: battle room rename failed", exc_info=True)


async def _restamp_score_clock_safe(stack: Any, attack: Any) -> None:
    """Re-anchor the score clock when the scoreboard REALLY lands.

    beta-fixes-v1 (Affaires 14/17): ``opened_at`` is the moment the
    phase effectively opens for the players — a room rescued by the
    meeting heal gets a fresh reminder (T+3h) and auto-dispute
    (T+12h) window instead of inheriting the clock of its pre-fix
    life. Best effort, never raises.
    """
    if stack is None:
        return
    try:
        await stack.attacks.restamp_score_opening(str(attack.id))
    except Exception:
        logger.warning("kingdom: score clock restamp failed", exc_info=True)


async def open_battle_room(bot: Any, stack: Any, guild: Any, attack: Any, locale: str) -> None:
    """Open the battle room of a meeting (idempotent, best effort).

    A dedicated role (both players), a voice channel under the
    provisioned « Champs de Bataille » category (user_limit 2) and ONE
    meeting message in the ATTACK SALON carrying the scoreboard + the
    persistent URL/result buttons. Both players get a DM pointing at
    the room.
    """
    from .panel import _declare_channel

    if stack is None:
        return
    strings = strings_by_locale(locale)
    score = attack.score or {}
    if score.get("room_channel_id"):
        return  # already opened (tick replay after a restart)
    try:
        attacker = await lord_name(stack.kingdoms, attack.attacker_lord_id)
        # beta-fixes-v1 (Affaire 11): the vocal opens on « {joueur
        # attaquant} vs {royaume adverse} » — the defender's identity
        # stays hidden until the matchup reveal (« Blanc vs Bataille »
        # was the AI fallback leaking through lord_name).
        defender = await battle_room_defender_label(stack, attack, strings)
        role = await guild.create_role(name=strings["room_role"].format(map=attack.map_key)[:100])
        declare = await _declare_channel(guild)
        category = getattr(declare, "category", None) if declare is not None else None
        if category is None:
            from .common import slug

            wanted = {"champs-de-bataille", "battlefields"}
            category = next(
                (
                    item
                    for item in getattr(guild, "categories", [])
                    if slug(str(getattr(item, "name", ""))) in wanted
                ),
                None,
            )
        if category is None:
            logger.warning(
                "kingdom: battlefield category not found — battle room created at the guild root"
            )
        channel = await open_dynamic_channel_safe(
            guild,
            room_channel_name(guild, "⚔️", attacker, defender),
            category=category,
            kind="voice",
            overwrites=_battle_room_overwrites(role.name),
            options={"user_limit": 2},
        )
        if channel is None:
            return
        await _record_safe(stack, "record_battle_room", attack.id, channel.id, role.id)
        # The meeting lives on ONE message in the ATTACK SALON — the
        # voice channel keeps only the voice (restructuration-serveur-v1 b).
        await post_meeting_message(guild, stack, attack, strings)
        for player_id in score_players(attack):
            await _grant_battle_room_role_safe(guild, role, player_id)
        # room-dm-v2: « Tiens-toi prêt » — the voice channel, the text
        # salon, the presence window (ready_deadline, Paris) and the
        # encouragements. A missing salon or deadline degrades the DM
        # by omitting the line — never in error.
        salon_mention = f"<#{salon.id}>" if (salon := attack_salon(guild, attack)) is not None else ""
        deadline = int((attack.score or {}).get("ready_deadline") or 0)
        dm = strings["room_dm"].format(map=attack.map_key, room=f"<#{channel.id}>", salon=salon_mention)
        if deadline > 0:
            dm += strings["room_dm_deadline"].format(
                deadline=fmt_paris(datetime.fromtimestamp(deadline, tz=UTC))
            )
        dm += strings["room_dm_luck"]
        for player_id in score_players(attack):
            await dm_user_safe(bot, player_id, dm)
    except Exception:
        logger.warning("kingdom: battle room opening failed", exc_info=True)


async def open_meeting_and_room_safe(bot: Any, stack: Any, attack: Any, locale: str) -> None:
    """Open the meeting + the battle room once both camps settled (v4).

    battle-rooms-early-v1 (Drasah 18/10 v4, tranche 2c): the LAST
    Sabotage Pass opens the meeting at once, BEFORE T — the scoreboard
    (and its 📜 draft sheet) lives from the phase's end, the sabotage
    buttons stay live inside the grace exactly as at T. Idempotent by
    construction: the engine refuses an already-open meeting, the
    tick's score_due skips a meeting in the MEETING state, and
    open_battle_room guards on the stored room_channel_id.
    """
    if stack is None:
        return
    try:
        fresh = await stack.attacks.open_meeting_now(str(attack.id))
    except Exception:  # a refused open retries at T (score_due)
        logger.warning("kingdom: early meeting open failed", exc_info=True)
        return
    if fresh is None:
        return
    for guild in list(getattr(bot, "guilds", []) or []):
        await open_battle_room(bot, stack, guild, fresh, locale)


async def sweep_pre_room_announces_safe(guild: Any, stack: Any, attack: Any) -> None:
    """Delete the declaration announce of the attack salon (best effort)."""
    salon = attack_salon(guild, attack)
    if salon is None:
        return
    score = dict(getattr(attack, "score", None) or {})
    base_id = int(score.get("attack_base_message_id") or 0)
    if not base_id:
        return
    try:
        message = await salon.fetch_message(base_id)
        await message.delete()
    except Exception:
        logger.debug("kingdom: pre-room announce sweep skipped", exc_info=True)


async def sweep_reveal_notes_safe(bot: Any, attack: Any) -> None:
    """Delete the reveal notes of the attack salon at the resolution."""
    score = dict(getattr(attack, "score", None) or {})
    message_ids: list[int] = []
    for ref in score.get("reveal_message_refs") or []:
        try:
            message_ids.append(int(ref["message_id"]))
        except (KeyError, TypeError, ValueError):
            continue
    if not message_ids:
        return
    for guild in list(getattr(bot, "guilds", []) or []):
        salon = attack_salon(guild, attack)
        if salon is None:
            continue
        for message_id in message_ids:
            try:
                message = await salon.fetch_message(message_id)
                await message.delete()
            except Exception:
                logger.debug("kingdom: reveal note sweep skipped", exc_info=True)


async def stamp_room_ping_winner_safe(bot: Any, attack: Any, winner_name: str, strings: dict[str, str]) -> None:
    """Stamp the 🏆 winner on the room's ping message (sabotage-ux-v1)."""
    score = dict(attack.score or {})
    channel_id = int(score.get("room_ping_channel_id") or 0)
    message_id = int(score.get("room_ping_message_id") or 0)
    if not channel_id or not message_id:
        return
    stamp = strings["room_ping_winner"].format(winner=winner_name)
    for guild in list(getattr(bot, "guilds", []) or []):
        channel = getattr(guild, "get_channel", lambda _id: None)(channel_id)
        if channel is None or not hasattr(channel, "get_partial_message"):
            continue
        try:
            message = channel.get_partial_message(message_id)
            existing = str(getattr(message, "content", "") or "")
            if stamp in existing:
                return
            await message.edit(content=f"{existing}\n{stamp}")
            return
        except Exception:
            logger.warning("kingdom: room ping winner stamp failed", exc_info=True)


# ---------------------------------------------------------------------------
# The conquest announce (Drasah 18/10 v5)
# ---------------------------------------------------------------------------


def _geopolitics_channel(guild: Any) -> Any:
    """The guild's « Géopolitique » recap salon (None when absent)."""
    from .common import slug

    if guild is None:
        return None
    return next(
        (c for c in getattr(guild, "text_channels", []) if "geopolitique" in slug(getattr(c, "name", ""))),
        None,
    )


async def conquest_detail(stack: Any, attack: Any, strings: dict[str, str], attacker_won: bool) -> str:
    """Build the conquest recap's detail body (the thread content)."""
    pickban: dict[str, Any] = dict(attack.pickban or {})
    attacker = await lord_name(stack.kingdoms, attack.attacker_lord_id)
    attacker_kingdom = await kingdom_name(stack.kingdoms, attack.attacker_kingdom_id)
    defender_kingdom = await kingdom_name(stack.kingdoms, attack.defender_kingdom_id)
    lines = [strings["conquest_attacker_line"].format(player=attacker, kingdom=attacker_kingdom)]
    if getattr(attack, "ai_defender", False):
        level = int((attack.effects or {}).get("ai_level") or 0)
        defender = defender_kingdom
        lines.append(strings["conquest_ai_defense"].format(kingdom=defender_kingdom, level=level))
    else:
        defender = await lord_name(stack.kingdoms, attack.defender_lord_id)
        lines.append(strings["conquest_defense_line"].format(player=defender, kingdom=defender_kingdom))
    lines.append(strings["conquest_civ_line"].format(player=attacker, civ=final_civ(pickban, "attacker")))
    defender_civ = final_civ(pickban, "defender")
    if defender_civ:
        lines.append(strings["conquest_civ_line"].format(player=defender, civ=defender_civ))
    if getattr(attack, "embuscade", False):
        lines.append(strings["conquest_embuscade_line"])
    for side in ("attacker", "defender"):
        sabotages = [str(civ) for civ in (pickban.get(f"{side}_sabotages") or [])]
        if sabotages:
            lines.append(
                strings["conquest_sabotages_line"].format(
                    side=strings[f"conquest_side_{side}"], civs=", ".join(sabotages)
                )
            )
    game = str((attack.score or {}).get("game_id") or attack.lobby_url or "")
    lines.append(strings["conquest_id_line"].format(game=game or strings["conquest_none"]))
    # The defeated player's sacred bond breaks when they were married.
    loser_id = str(attack.defender_lord_id) if attacker_won else str(attack.attacker_lord_id)
    if loser_id and not (attacker_won and getattr(attack, "ai_defender", False)):
        lord = await lord_of(stack.kingdoms, loser_id)
        married = str(getattr(lord, "married_civilization", "") or "") if lord else ""
        if married:
            lines.append(
                strings["conquest_married_lost"].format(
                    player=await lord_name(stack.kingdoms, loser_id), civ=married
                )
            )
    return "\n".join(lines)


async def announce_conquest_safe(bot: Any, stack: Any, attack: Any, locale: str) -> None:
    """Post the conquest recap in Géopolitique + its detail thread."""
    strings = strings_by_locale(locale)
    winner_id = str(getattr(attack, "winner_kingdom_id", "") or "")
    if not winner_id or stack is None:
        return
    attacker_won = winner_id == str(attack.attacker_kingdom_id)
    winner = await kingdom_name(stack.kingdoms, winner_id)
    title_key = "conquest_title" if attacker_won else "conquest_defense_title"
    thread_key = "conquest_thread" if attacker_won else "conquest_thread_defense"
    title = strings[title_key].format(winner=winner, map=attack.map_key)
    detail = await conquest_detail(stack, attack, strings, attacker_won)
    for guild in list(getattr(bot, "guilds", []) or []):
        channel = _geopolitics_channel(guild)
        if channel is None:
            continue
        try:
            message = await channel.send(title)
        except Exception:
            logger.warning("kingdom: conquest recap post failed", exc_info=True)
            continue
        try:
            thread = await channel.create_thread(name=strings[thread_key][:100], message=message)
            await thread.send(detail)
        except Exception:
            logger.warning("kingdom: conquest thread failed — flat fallback", exc_info=True)
            try:
                await channel.send(detail)
            except Exception:
                logger.warning("kingdom: conquest detail post failed", exc_info=True)


async def announce_forfeit_safe(
    bot: Any, stack: Any, attack: Any, side: str, winner: str, strings: dict[str, str]
) -> None:
    """affaire-30 (Drasah 25/11): every draft forfeit reaches Géopolitique.

    A played game ends with its conquest recap; a forfeit's note used
    to die inside the attack salon the immediate closure deletes a
    second later. Géopolitique is the durable surface: one flat line,
    the camp that forfeited, the winner by forfeit — the general
    forfeit carries its winner too (the present attacker wins).
    """
    for guild in list(getattr(bot, "guilds", []) or []):
        channel = _geopolitics_channel(guild)
        if channel is None:
            continue
        if side == "both":
            line = strings["forfeit_geo_both"].format(map=attack.map_key, winner=winner)
        else:
            line = strings["forfeit_geo_side"].format(
                map=attack.map_key, side=strings[f"side_{side}"], winner=winner
            )
        try:
            await channel.send(line)
        except Exception:
            logger.warning("kingdom: forfeit recap post failed", exc_info=True)


# ---------------------------------------------------------------------------
# The resolution's shared post-treatment (litige-mp-v1 factoring)
# ---------------------------------------------------------------------------


async def on_score_resolved_safe(
    bot: Any, stack: Any, attack: Any, strings: dict[str, str], winner: str, locale: str = "fr"
) -> None:
    """The shared post-resolution treatment.

    The room ping wears the winner. The conquest is announced. The
    room re-renders in place — the Prêts and the ID button sweep
    themselves (only the 📜 draft sheet survives on a resolved room).
    The reveal notes go too (reveal-survie-v1).
    """
    await stamp_room_ping_winner_safe(bot, attack, winner, strings)
    await announce_conquest_safe(bot, stack, attack, locale)
    await refresh_room_message_safe(bot, stack, attack, locale)
    await sweep_reveal_notes_safe(bot, attack)
    # affaire-27 (Drasah 25/11 tranché) : une PARTIE JOUÉE ferme son
    # habitat immédiatement en bêta (le délai officiel de 30 min garde
    # sa salle de discussion) — l'annonce part TOUJOURS avant la porte.
    if await _played_result_closes_now_safe(stack):
        await cleanup_decided_attack_safe(bot, stack, attack)


async def _played_result_closes_now_safe(stack: Any) -> bool:
    """Whether a PLAYED result closes its habitat at once (beta only).

    affaire-27 : en version officielle une partie jouée laisse la
    salle ouverte ``room_cleanup_delay`` (30 min) — les joueurs
    commentent la game ; en bêta armée tout repart vite, la fermeture
    est immédiate. Best effort : une sonde en échec garde le
    comportement officiel.
    """
    try:
        from botforge.mods.kingdom.beta_weekend import beta_started
        from botforge.mods.kingdom.game_clock import game_now

        season = await stack.kingdoms.current_season()
        return season is not None and beta_started(season, game_now())
    except Exception:
        logger.debug("kingdom: played-result beta probe failed", exc_info=True)
    return False


# ---------------------------------------------------------------------------
# The score flow (battle-room-id-v2)
# ---------------------------------------------------------------------------


async def _room_select_view(stack: Any, strings: dict[str, str], attack: Any, on_choice: Any) -> discord.ui.View:
    """Build the ephemeral winner select (stage 1 of the v2 flow)."""
    view = discord.ui.View(timeout=None)

    async def _on_winner(target: discord.Interaction) -> None:
        await on_choice(target, str(select.values[0]))

    attacker_name = await kingdom_name(stack.kingdoms, attack.attacker_kingdom_id)
    defender_name = await kingdom_name(stack.kingdoms, attack.defender_kingdom_id)
    select: discord.ui.Select[Any] = discord.ui.Select(
        placeholder=strings["result_select_placeholder"][:100],
        options=[
            discord.SelectOption(label=str(attacker_name)[:100], value=str(attack.attacker_kingdom_id)),
            discord.SelectOption(label=str(defender_name)[:100], value=str(attack.defender_kingdom_id)),
        ],
        min_values=1,
        max_values=1,
    )
    select.callback = _on_winner  # type: ignore[method-assign,assignment]
    view.add_item(select)
    return view


async def _edit_room_confirm(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    attack: Any,
    winner_kingdom_id: str,
    winner_name: str,
) -> None:
    """Edit the ephemeral into the explicit confirmation stage (v2)."""
    view = discord.ui.View(timeout=None)
    confirm: discord.ui.Button[Any] = discord.ui.Button(
        label=strings["result_confirm_button"], style=discord.ButtonStyle.success
    )
    change: discord.ui.Button[Any] = discord.ui.Button(
        label=strings["result_edit_button"], style=discord.ButtonStyle.secondary
    )

    async def _on_confirm(target: discord.Interaction) -> None:
        if str(getattr(target.user, "id", "")) != str(interaction.user.id):
            await target.response.defer()
            return
        await declare_room_score(
            target,
            stack,
            strings,
            str(attack.id),
            str(target.user.id),
            winner_kingdom_id,
            game_id=str(attack.lobby_url or ""),
            edit_response=True,
        )

    async def _on_change(target: discord.Interaction) -> None:
        if str(getattr(target.user, "id", "")) != str(interaction.user.id):
            await target.response.defer()
            return
        # Anti-missclick loop: back to the winner select, never a
        # silent declaration.
        await _send_room_select(target, stack, strings, attack, via_edit=True)

    confirm.callback = _on_confirm  # type: ignore[method-assign,assignment]
    change.callback = _on_change  # type: ignore[method-assign,assignment]
    view.add_item(confirm)
    view.add_item(change)
    await interaction.response.edit_message(
        content=strings["result_confirm_title"].format(winner=winner_name), view=view
    )


async def _send_room_select(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    attack: Any,
    *,
    via_edit: bool = False,
) -> None:
    """Post (or edit back to) the winner select stage (v2)."""
    attacker_name = await kingdom_name(stack.kingdoms, attack.attacker_kingdom_id)
    defender_name = await kingdom_name(stack.kingdoms, attack.defender_kingdom_id)

    async def _on_choice(target: discord.Interaction, winner_kingdom_id: str) -> None:
        if str(getattr(target.user, "id", "")) != str(interaction.user.id):
            await target.response.defer()
            return
        winner_name = (
            attacker_name if winner_kingdom_id == str(attack.attacker_kingdom_id) else defender_name
        )
        await _edit_room_confirm(target, stack, strings, attack, winner_kingdom_id, winner_name)

    view = await _room_select_view(stack, strings, attack, _on_choice)
    title = strings["result_select_title"]
    if via_edit:
        await interaction.response.edit_message(content=title, view=view)
    else:
        await open_unique_ephemeral(interaction, title, view=view)


async def _send_room_review(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    attack: Any,
    declarer_id: str,
    winner_kingdom_id: str,
) -> None:
    """Show the OTHER player's declaration — confirm or contest, never re-declare."""
    declarer_name = await lord_name(stack.kingdoms, declarer_id)
    winner_name = await kingdom_name(stack.kingdoms, winner_kingdom_id)
    contrary = (
        str(attack.defender_kingdom_id)
        if winner_kingdom_id == str(attack.attacker_kingdom_id)
        else str(attack.attacker_kingdom_id)
    )
    view = discord.ui.View(timeout=None)
    confirm: discord.ui.Button[Any] = discord.ui.Button(
        label=strings["result_review_confirm_button"], style=discord.ButtonStyle.success
    )
    contest: discord.ui.Button[Any] = discord.ui.Button(
        label=strings["result_review_contest_button"], style=discord.ButtonStyle.danger
    )

    async def _on_confirm(target: discord.Interaction) -> None:
        if str(getattr(target.user, "id", "")) != str(interaction.user.id):
            await target.response.defer()
            return
        await declare_room_score(
            target, stack, strings, str(attack.id), str(target.user.id), winner_kingdom_id,
            game_id=str(attack.lobby_url or ""), edit_response=True,
        )

    async def _on_contest(target: discord.Interaction) -> None:
        if str(getattr(target.user, "id", "")) != str(interaction.user.id):
            await target.response.defer()
            return
        # Contrary declaration → dispute, the admins arbitrate.
        await declare_room_score(
            target, stack, strings, str(attack.id), str(target.user.id), contrary,
            game_id=str(attack.lobby_url or ""), edit_response=True,
        )

    confirm.callback = _on_confirm  # type: ignore[method-assign,assignment]
    contest.callback = _on_contest  # type: ignore[method-assign,assignment]
    view.add_item(confirm)
    view.add_item(contest)
    await interaction.response.send_message(
        strings["result_review_title"].format(player=declarer_name, winner=winner_name),
        view=view,
        ephemeral=True,
    )


async def _send_room_my_declaration(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    attack: Any,
    winner_kingdom_id: str,
    winner_name: str,
) -> None:
    """Show the player HIS OWN declaration + the select to modify it."""
    async def _on_choice(target: discord.Interaction, chosen_id: str) -> None:
        if str(getattr(target.user, "id", "")) != str(interaction.user.id):
            await target.response.defer()
            return
        chosen_name = await kingdom_name(stack.kingdoms, chosen_id)
        await _edit_room_confirm(target, stack, strings, attack, chosen_id, chosen_name)

    view = await _room_select_view(stack, strings, attack, _on_choice)
    title = strings["result_mine_title"].format(winner=winner_name)
    await interaction.response.send_message(title, view=view, ephemeral=True)


async def declare_room_score(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    attack_id: str,
    player_id: str,
    winner_kingdom_id: str,
    game_id: str = "",
    *,
    edit_response: bool = False,
) -> None:
    """Declare the result from the battle room (resolved or pending).

    The ID of the party entered earlier rides the declaration,
    ``resolved`` stays ephemeral in the room and tells the story in
    Géopolitique. A disputed declaration opens the DM round (before
    the resolution) or the direct admin handover (after it).
    """

    async def _respond(content: str) -> None:
        if edit_response:
            await interaction.response.edit_message(content=content, view=None)
        else:
            await interaction.response.send_message(content, ephemeral=True)

    if stack is None or not attack_id:
        await _respond(strings["no_service"])
        return
    try:
        attack, outcome = await stack.attacks.declare_score(attack_id, player_id, winner_kingdom_id, game_id)
    except Exception as exc:
        message = getattr(exc, "message", None) or str(exc)
        await _respond(strings["failed"].format(message=message))
        return
    if outcome == "disputed":
        # The dispute reminder STAYS in the player's ephemeral lane
        # until the admins arbitrate (no auto-delete).
        await _respond(strings["score_disputed"].format(game=game_id or "—"))
        if getattr(attack, "is_over", False):
            await dm_admins_dispute_safe(interaction.client, stack, attack, strings)
        else:
            await send_dispute_dm_round_safe(interaction.client, stack, attack, locale_of(interaction))
        return
    if outcome == "already":
        await _respond(strings["score_already"])
        return
    if outcome == "resolved":
        winner = await kingdom_name(stack.kingdoms, winner_kingdom_id)
        await _respond(
            strings["score_resolved"].format(winner=winner, map=attack.map_key, game=game_id or "—")
        )
        await on_score_resolved_safe(
            interaction.client, stack, attack, strings, winner, locale_of(interaction)
        )
        return
    minutes = 10
    try:
        minutes = int(
            getattr(
                getattr(getattr(stack.attacks, "_config", None), "attacks", None),
                "score_confirm_minutes",
                10,
            )
            or 10
        )
    except Exception:
        minutes = 10
    await _respond(strings["score_pending"].format(game=game_id or "—", minutes=minutes))


# ---------------------------------------------------------------------------
# The dispute round (litige-mp-v1, Drasah 30/10)
# ---------------------------------------------------------------------------


async def _dispute_select_options(stack: Any, attack: Any) -> list[discord.SelectOption]:
    """The two-kingdom winner options of the dispute DM select."""
    attacker_name = await kingdom_name(stack.kingdoms, attack.attacker_kingdom_id)
    defender_name = await kingdom_name(stack.kingdoms, attack.defender_kingdom_id)
    return [
        discord.SelectOption(label=str(attacker_name)[:100], value=str(attack.attacker_kingdom_id)),
        discord.SelectOption(label=str(defender_name)[:100], value=str(attack.defender_kingdom_id)),
    ]


async def _edit_dispute_dm_safe(attack_id: str, player_id: str, content: str) -> None:
    """Edit one player's dispute DM in place (best effort)."""
    message = (_DISPUTE_DMS.get(str(attack_id)) or {}).get(str(player_id))
    if message is None:
        return
    try:
        await message.edit(content=content)
    except Exception:
        logger.warning("kingdom: dispute DM edit failed (%s)", player_id, exc_info=True)


async def send_dispute_dm_round_safe(bot: Any, stack: Any, attack: Any, locale: str) -> None:
    """Open the DM round of a disputed meeting — BOTH players.

    Each player receives HIS own declaration back with the
    two-kingdom select (modify) and the ✅ confirm button. The round
    is bounded by the service deadline (30 min); the tick hands the
    litige over to the admins on failure. Manche UNIQUE: the
    ``dispute_dm_sent`` flag makes the send idempotent.
    """
    strings = strings_by_locale(locale)
    if stack is None:
        return
    if (attack.score or {}).get("dispute_dm_sent"):
        return
    try:
        attack = await stack.attacks.open_dispute_dm_round(str(attack.id))
    except Exception:
        logger.warning("kingdom: dispute DM round open failed", exc_info=True)
        return
    declarations = dict((attack.score or {}).get("declarations") or {})
    options = await _dispute_select_options(stack, attack)
    refs: dict[str, Any] = {}
    for player_id in score_players(attack):
        declaration = declarations.get(str(player_id)) or {}
        winner_name = await kingdom_name(stack.kingdoms, str(declaration.get("winner") or ""))
        content = strings["dispute_dm_open"].format(winner=winner_name or "—")
        view = dm_view(timeout=None)
        view.add_item(DisputeChoiceSelect(str(attack.id), options, strings["result_select_placeholder"]))
        view.add_item(DisputeConfirmButton(str(attack.id), strings["dispute_confirm_button"]))
        message = await dm_user_safe(bot, str(player_id), content, view)
        if message is not None:
            refs[str(player_id)] = message
    _DISPUTE_DMS[str(attack.id)] = refs


async def dm_admins_dispute_safe(bot: Any, stack: Any, attack: Any, strings: dict[str, str]) -> None:
    """DM the bot-admins a disputed meeting with the arbitration buttons."""
    declarations = (attack.score or {}).get("declarations") or {}
    lines = [
        f"• <@{player}> → {decl.get('winner')} (game {decl.get('game_id')})"
        for player, decl in declarations.items()
    ]
    content = strings["dispute_admin_dm"].format(
        map=attack.map_key,
        declarations="\n".join(lines) or "—",
        game=(attack.score or {}).get("game_id") or "—",
    )
    view = DisputeView(str(attack.id), "fr")
    from .common import _bot_admins

    for admin_id in _bot_admins() or ():
        await dm_user_safe(bot, str(admin_id), content, view)


async def handle_dispute_reply_safe(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    attack_id: str,
    winner_kingdom_id: str,
) -> None:
    """The shared DM-round reply path (select pick or confirm button)."""
    bot = interaction.client
    if stack is None or not attack_id:
        await interaction.response.edit_message(content=strings["no_service"], view=None)
        return
    try:
        attack = await attack_by_id(stack, attack_id)
    except Exception:
        attack = None
    if attack is None:
        await interaction.response.edit_message(content=strings["no_service"], view=None)
        return
    player_id = str(interaction.user.id)
    if room_side_of(attack, player_id) == "":
        await interaction.response.edit_message(content=strings["room_not_player"], view=None)
        return
    game_id = str((attack.score or {}).get("game_id") or attack.lobby_url or "")
    if getattr(attack, "is_over", False) or attack.state is not AttackState.MEETING:
        # An admin arbitrated (or the round closed) meanwhile — the DM
        # dies gracefully, the room carries the outcome.
        winner = await kingdom_name(stack.kingdoms, str(getattr(attack, "winner_kingdom_id", "") or ""))
        await interaction.response.edit_message(
            content=strings["dispute_dm_resolved"].format(winner=winner), view=None
        )
        return
    try:
        attack, outcome = await stack.attacks.declare_score(attack_id, player_id, winner_kingdom_id, game_id)
    except Exception as exc:
        message = getattr(exc, "message", None) or str(exc)
        await interaction.response.edit_message(content=strings["failed"].format(message=message), view=None)
        return
    if outcome == "resolved":
        winner = await kingdom_name(stack.kingdoms, winner_kingdom_id)
        closed = strings["dispute_dm_resolved"].format(winner=winner)
        await interaction.response.edit_message(content=closed, view=None)
        for other in score_players(attack):
            if str(other) != player_id:
                await _edit_dispute_dm_safe(attack_id, str(other), closed)
        _DISPUTE_DMS.pop(str(attack_id), None)
        await on_score_resolved_safe(bot, stack, attack, strings, winner, locale_of(interaction))
        return
    if outcome == "already":
        winner = await kingdom_name(stack.kingdoms, winner_kingdom_id)
        await interaction.response.edit_message(
            content=strings["dispute_dm_resolved"].format(winner=winner), view=None
        )
        return
    # Still disputed — record the round reply.
    winner = await kingdom_name(stack.kingdoms, winner_kingdom_id)
    both_replied = False
    try:
        attack, both_replied = await stack.attacks.record_dispute_reply(
            attack_id, player_id, winner_kingdom_id
        )
    except Exception:
        both_replied = False
    if both_replied:
        # Both replied without converging — the admins take over NOW.
        await dm_admins_dispute_safe(bot, stack, attack, strings)
        try:
            await stack.attacks.mark_dispute_admin_sent(attack_id)
        except Exception:
            logger.warning("kingdom: dispute admin flag failed", exc_info=True)
        handover = strings["dispute_dm_handover"]
        await interaction.response.edit_message(content=handover, view=None)
        for other in score_players(attack):
            if str(other) != player_id:
                await _edit_dispute_dm_safe(attack_id, str(other), handover)
        _DISPUTE_DMS.pop(str(attack_id), None)
        return
    confirmed = strings["dispute_dm_confirmed"].format(winner=winner)
    await interaction.response.edit_message(content=confirmed, view=None)


# ---------------------------------------------------------------------------
# The room match event (beta-retours-v1: Prêt = engagement)
# ---------------------------------------------------------------------------


async def create_room_event_safe(client: Any, stack: Any, attack: Any, strings: dict[str, str], channel: Any = None) -> None:
    """Create the room's scheduled event from an interaction OR a tick.

    Against the AI defender the ready flip happens in the phase tick
    (no interaction); the channel is then resolved from
    ``score["room_channel_id"]`` across the client's guilds. Best
    effort — never raises.
    """
    if stack is None:
        return
    guild = None
    if channel is None:
        channel_id = int((attack.score or {}).get("room_channel_id") or 0)
        for candidate in list(getattr(client, "guilds", []) or []):
            resolved = getattr(candidate, "get_channel", lambda _id: None)(channel_id)
            if resolved is not None:
                channel = resolved
                guild = candidate
                break
    else:
        guild = getattr(channel, "guild", None) or getattr(
            client, "get_guild", lambda _id: None
        )(getattr(channel, "guild_id", 0))
    if guild is None:
        logger.warning("kingdom: room match announce without a guild")
        return
    if not isinstance(
        channel, (discord.VoiceChannel, discord.StageChannel, discord.TextChannel, discord.Thread)
    ):
        logger.warning("kingdom: room match announce outside a room channel")
        return
    attacker_name = await kingdom_name(stack.kingdoms, attack.attacker_kingdom_id)
    defender_name = await kingdom_name(stack.kingdoms, attack.defender_kingdom_id)
    # beta-fixes-v1 (Affaires 14/17): a retarded salon (meeting heal,
    # room opened long after its RDV window) must not spam a WARNING
    # traceback from Discord — the match's presence window is already
    # over, the event is skipped quietly with an INFO line.
    rdv = int((attack.score or {}).get("ready_deadline") or 0)
    if rdv and datetime.now(UTC).timestamp() > rdv:
        logger.info(
            "kingdom: room event skipped — meeting time already passed (%s)", attack.map_key
        )
        return
    event_id = 0
    try:
        event = await guild.create_scheduled_event(
            name=strings["room_event_name"].format(
                map=attack.map_key, attacker=attacker_name, defender=defender_name
            )[:100],
            description=strings["room_event_description"].format(
                attacker=attacker_name, defender=defender_name
            ),
            start_time=datetime.now(UTC),
            entity_type=discord.EntityType.voice,
            privacy_level=discord.PrivacyLevel.guild_only,
            channel=channel,
        )
        event_id = int(event.id)
    except Exception:
        logger.warning("kingdom: room match event creation failed", exc_info=True)
    if event_id > 0:
        await _record_safe(stack, "record_room_event", str(attack.id), event_id)


# ---------------------------------------------------------------------------
# The cleanup (resultat-nettoyage-v1 / restructuration-serveur-v1 b)
# ---------------------------------------------------------------------------


async def _delete_battle_room_safe(bot: Any, channel_id: int, role_id: Any) -> bool:
    """Delete the battle room channel + role on every guild (best effort).

    affaire-29: the answer tells whether Discord ACCEPTED the delete —
    a refused 403 no longer masquerades as a done cleanup.
    """
    try:
        for guild in list(getattr(bot, "guilds", []) or []):
            channel = getattr(guild, "get_channel", lambda _id: None)(channel_id)
            if channel is not None:
                await channel.delete()
            if role_id is not None:
                role = getattr(guild, "get_role", lambda _id: None)(int(role_id))
                if role is not None and hasattr(role, "delete"):
                    await role.delete()
    except Exception:
        logger.warning("kingdom: battle room cleanup failed", exc_info=True)
        return False
    return True


def _battle_room_sweep_due(attacks: list[Any], delay_minutes: int, now: datetime) -> tuple[list[Any], set[int]]:
    """The overdue-resolved attacks and the live rooms' role ids."""
    keep_role_ids: set[int] = set()
    due: list[Any] = []
    for attack in attacks:
        score = attack.score or {}
        try:
            role_id = int(score.get("room_role_id") or 0)
        except (TypeError, ValueError):
            role_id = 0
        if role_id:
            keep_role_ids.add(role_id)
        if not attack.is_over:
            continue
        resolved_at = getattr(attack, "resolved_at", None)
        deadline = resolved_at + timedelta(minutes=delay_minutes) if resolved_at is not None else None
        if deadline is None or now >= deadline:
            keep_role_ids.discard(role_id)
            due.append(attack)
    return due, keep_role_ids


def _ref_as_int(score: dict[str, Any], key: str) -> int:
    """Read one recorded room ref as an int (0 when absent/invalid)."""
    try:
        return int(score.get(key) or 0)
    except (TypeError, ValueError):
        return 0


async def _sweep_recorded_leftovers_safe(bot: Any, due: list[Any]) -> int:
    """Re-delete the recorded room refs of every overdue-resolved meeting."""
    swept = 0
    for attack in due:
        score = attack.score or {}
        refs = (
            _ref_as_int(score, "room_channel_id"),
            _ref_as_int(score, "attack_channel_id"),
            _ref_as_int(score, "room_role_id"),
        )
        if not any(refs):
            continue
        try:
            for guild in list(getattr(bot, "guilds", []) or []):
                swept += await _delete_recorded_refs_safe(guild, refs)
        except Exception:
            logger.warning("kingdom: battle room leftover sweep failed", exc_info=True)
    return swept


async def _delete_recorded_refs_safe(guild: Any, refs: tuple[int, int, int]) -> int:
    """Delete one meeting's recorded channel/role refs on one guild.

    affaire-27 (Drasah 25/11 live report): the sweep hammered Discord
    with 403 « Missing Access » every pass on leftover channels the
    bot may NOT manage (old-app ghosts a permission check can't
    heal) — deleting them is the guild's roles' business, not ours.
    The guards skip the undeletable SILENTLY: no call, no 403, no
    rate-limit admission storm.
    """
    room_channel_id, salon_channel_id, role_id = refs
    swept = 0
    me = getattr(guild, "me", None)
    for channel_id in (room_channel_id, salon_channel_id):
        if not channel_id:
            continue
        channel = getattr(guild, "get_channel", lambda _id: None)(channel_id)
        if channel is None or not hasattr(channel, "delete"):
            continue
        if not _bot_may_delete_channel(me, channel):
            logger.info(
                "kingdom: leftover channel %s skipped (no Manage Channels)",
                channel_id,
            )
            continue
        await channel.delete()
        swept += 1
    if role_id:
        role = getattr(guild, "get_role", lambda _id: None)(role_id)
        if role is not None and hasattr(role, "delete"):
            if not _bot_may_delete_role(me, role):
                logger.info("kingdom: leftover role %s skipped (above the bot)", role_id)
                return swept
            await role.delete()
            swept += 1
    return swept


def _bot_may_delete_channel(me: Any, channel: Any) -> bool:
    """Whether the bot holds Manage Channels on a leftover channel.

    Best effort: an unreadable permission surface reads ALLOWED (the
    delete stays best-effort, exactly as before).
    """
    perms = getattr(channel, "permissions_for", None)
    if me is None or perms is None:
        return True
    try:
        return bool(perms(me).manage_channels)
    except Exception:
        logger.debug("kingdom: leftover channel permission probe failed", exc_info=True)
    return True


def _bot_may_delete_role(me: Any, role: Any) -> bool:
    """Whether the bot's top role sits ABOVE a leftover battle role."""
    me_top = getattr(getattr(me, "top_role", None), "position", None)
    top = None if isinstance(me_top, bool) else me_top
    role_top = getattr(role, "position", None)
    if me is None or top is None or role_top is None:
        return True
    try:
        return bool(top > role_top)
    except Exception:
        logger.debug("kingdom: leftover role hierarchy probe failed", exc_info=True)
    return True


async def _sweep_orphan_battle_roles_safe(bot: Any, keep_role_ids: set[int]) -> int:
    """Delete the name-matched battle roles claimed by no live meeting."""
    swept = 0
    try:
        for guild in list(getattr(bot, "guilds", []) or []):
            for role in list(getattr(guild, "roles", []) or []):
                name = str(getattr(role, "name", ""))
                if not name.startswith(_BATTLE_ROLE_NAME_PREFIXES):
                    continue
                try:
                    role_id = int(getattr(role, "id", 0) or 0)
                except (TypeError, ValueError):
                    continue
                if role_id in keep_role_ids:
                    continue  # claimed by a live (or not-yet-due) meeting
                if hasattr(role, "delete"):
                    await role.delete()
                    swept += 1
    except Exception:
        logger.warning("kingdom: battle role orphan sweep failed", exc_info=True)
    return swept


async def _sweep_battle_room_leftovers_safe(bot: Any, attacks_service: Any, attacks: list[Any]) -> int:
    """Delete the battle-room leftovers a flagged cleanup never deleted.

    The cleanup marks a resolved meeting ``room_cleaned`` even when
    Discord REFUSED the actual delete — this sweep re-runs the
    deletion on every RESOLVED meeting past its cleanup delay, flag
    or not. Idempotent: a clean guild touches nothing, a live meeting
    keeps its room whatever its flag says.
    """
    try:
        delay_minutes = int(await attacks_service.room_cleanup_delay())
    except Exception:
        # temporalites-beta-v1 : le seam async peut manquer (vieille
        # instance) — la propriété de config reste la valeur officielle.
        delay_minutes = int(getattr(attacks_service, "room_cleanup_delay_minutes", 30) or 30)
    due, keep_role_ids = _battle_room_sweep_due(attacks, delay_minutes, datetime.now(UTC))
    swept = await _sweep_recorded_leftovers_safe(bot, due)
    swept += await _sweep_orphan_battle_roles_safe(bot, keep_role_ids)
    if swept:
        logger.info("kingdom: swept %d battle room leftover(s)", swept)
    return swept


async def _cleanup_one_battle_room(bot: Any, stack: Any, attack: Any, score: dict[str, Any]) -> int:
    """Delete one resolved meeting's voice room (channel + role) and flag it.

    affaire-29 (Drasah 25/11, live 403): the « room_cleaned » flag is
    ONLY set on an ACCEPTED delete — a refused channel stays uncleaned
    so the sweep keeps retrying it instead of abandoning the ghost.
    """
    accepted = await _delete_battle_room_safe(
        bot, int(score["room_channel_id"]), score.get("room_role_id")
    )
    if not accepted:
        logger.warning("kingdom: battle room delete refused — the room stays uncleaned (retry at the sweep)")
        return 0
    try:
        await stack.attacks.mark_room_cleaned(str(attack.id))
    except Exception:
        logger.warning("kingdom: battle room cleanup flag failed", exc_info=True)
    return 1


async def _cleanup_one_attack_salon(guild: Any, stack: Any, attack: Any) -> int:
    """Delete one resolved attack's salon and flag it cleaned."""
    salon = attack_salon(guild, attack)
    if salon is not None:
        try:
            await salon.delete()
        except Exception:
            logger.warning("kingdom: attack salon cleanup failed", exc_info=True)
    try:
        await stack.attacks.mark_attack_salon_cleaned(str(attack.id))
    except Exception:
        logger.warning("kingdom: attack salon cleanup flag failed", exc_info=True)
    return 1


async def cleanup_battle_rooms_safe(bot: Any, stack: Any, guild: Any) -> int:
    """Delete the room (channel + role) AND the salon of every resolved meeting.

    The per-attack salon follows the same pattern as the voice room —
    it disappears ``room_cleanup_delay_minutes`` after the winner is
    known. A salon already purged at a CANCELLATION rides its own
    flag.
    """
    if stack is None:
        return 0
    played = 0
    try:
        attacks = await stack.attacks.attacks()
    except Exception:
        logger.warning("kingdom: battle room scan failed", exc_info=True)
        return 0
    try:
        delay_minutes = int(await stack.attacks.room_cleanup_delay())
    except Exception:
        # temporalites-beta-v1 : fallback sur la propriété de config.
        delay_minutes = int(getattr(stack.attacks, "room_cleanup_delay_minutes", 30) or 30)
    now = datetime.now(UTC)
    for attack in attacks:
        score = attack.score or {}
        if not attack.is_over:
            continue
        resolved_at = getattr(attack, "resolved_at", None)
        if resolved_at is not None:
            deadline = resolved_at + timedelta(minutes=delay_minutes)
            if now < deadline:
                continue
        # The room only disappears 30 minutes after a winner is known —
        # never mid-game.
        if score.get("room_channel_id") and not score.get("room_cleaned"):
            played += await _cleanup_one_battle_room(bot, stack, attack, score)
        if score.get("attack_channel_id") and not score.get("attack_salon_cleaned"):
            played += await _cleanup_one_attack_salon(guild, stack, attack)
    await _sweep_battle_room_leftovers_safe(bot, stack.attacks, attacks)
    return played


async def cleanup_decided_attack_safe(bot: Any, stack: Any, attack: Any) -> int:
    """Close a DECIDED meeting's habitat AT ONCE (annulation-joueur-v2).

    Drasah's live finding (25/11): a decided meeting kept its voice
    room, its role and its text salon for the whole 30-minute cleanup
    delay — the closed decision left a ghost rendezvous behind. The
    admin decision modal calls this right after the resolution: the
    room, the role and the salon disappear IMMEDIATELY. Idempotent —
    the flags (``room_cleaned`` / ``attack_salon_cleaned``) make the
    30-minute tick replay nothing, and a second call touches nothing.
    """
    if stack is None or attack is None:
        return 0
    played = 0
    score = dict(getattr(attack, "score", None) or {})
    if score.get("room_channel_id") and not score.get("room_cleaned"):
        played += await _cleanup_one_battle_room(bot, stack, attack, score)
    if score.get("attack_channel_id") and not score.get("attack_salon_cleaned"):
        for guild in list(getattr(bot, "guilds", []) or []):
            played += await _cleanup_one_attack_salon(guild, stack, attack)
            break
    if played:
        logger.info("kingdom: closed the decided meeting's habitat at once (%d)", played)
    return played


# ---------------------------------------------------------------------------
# The persistent buttons
# ---------------------------------------------------------------------------


class DraftViewButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:room:draft:(?P<key>[0-9a-f]{16})",
):
    """The 📜 « Voir la draft » button — each side's 3 civs, secrets kept."""

    def __init__(self, attack_id: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=_ROOM_DRAFT.format(key=room_key(attack_id)),
                style=discord.ButtonStyle.secondary,
            )
        )
        self.attack_id = attack_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> DraftViewButton:
        stack = wiring()
        attack_id = await resolve_room_key(stack, match["key"])
        return cls(attack_id, strings_of(interaction)["draft_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Answer the draft sheet in the single ephemeral window."""
        strings = strings_of(interaction)
        stack = wiring()
        if stack is None or not self.attack_id:
            await open_unique_ephemeral(interaction, strings["no_service"])
            return
        try:
            attack = await attack_by_id(stack, self.attack_id)
        except Exception:
            attack = None
        if attack is None:
            await open_unique_ephemeral(interaction, strings["gaia_gone"])
            return
        embed = await draft_sheet_embed(stack, attack, strings)
        await open_unique_ephemeral(
            interaction, surface_footer("panel:mod:kingdom:battle:draft"), embed=embed
        )


async def draft_sheet_embed(stack: Any, attack: Any, strings: dict[str, str]) -> discord.Embed:
    """The 📜 draft sheet — each side's 3 picks, the sabotaged struck through."""
    pickban = dict(attack.pickban or {})
    attacker = await lord_name(stack.kingdoms, attack.attacker_lord_id)
    if attack.ai_defender:
        defender = str(strings["defender_ai"])
    else:
        defender = await lord_name(stack.kingdoms, attack.defender_lord_id or "")

    # Once the sabotage phase is resolved the sheet shows the REAL
    # stored order; DURING the phase the order stays a SEEDED random
    # (no sabotage-influencing leak) with plain • bullets.
    phase_over = bool(pickban.get("sabotage_resolved"))

    async def _side_picks(side: str) -> str:
        picks = [str(civ) for civ in (pickban.get(f"{side}_picks") or [])]
        enemy = "defender" if side == "attacker" else "attacker"
        struck = {str(civ) for civ in (pickban.get(f"{enemy}_sabotages") or [])}
        shown = picks if phase_over else shuffled_civs(f"{attack.id}:{side}", picks)
        marks = ("1️⃣", "2️⃣", "3️⃣") if phase_over else ("•", "•", "•")
        defaulted = side in [str(x) for x in (pickban.get("default_picks") or [])]
        mode = str(strings["draft_mode_random"] if defaulted else strings["draft_mode_player"])
        body = (
            "\n".join(
                f"{marks[i]} {f'~~{civ}~~ ❌' if civ in struck else civ}"
                for i, civ in enumerate(shown[: len(marks)])
            )
            or "—"
        )
        return f"*{mode}*\n{body}"

    embed = discord.Embed(
        title=str(strings["draft_sheet"]).format(map=attack.map_key),
        description=str(strings["draft_sheet_help"]),
    )
    embed.add_field(name=f"⚔️ {attacker}", value=await _side_picks("attacker"), inline=True)
    embed.add_field(name=f"🛡️ {defender}", value=await _side_picks("defender"), inline=True)
    return embed


class RoomUrlButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:room:url:(?P<key>[0-9a-f]{16})",
):
    """The persistent 🔗 button of the battle room (game ID share)."""

    def __init__(self, attack_id: str, label: str, *, style: Any = None, disabled: bool = False) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=_ROOM_URL.format(key=room_key(attack_id)),
                style=style or discord.ButtonStyle.secondary,
                disabled=disabled,
            )
        )
        self.attack_id = attack_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> RoomUrlButton:
        strings = strings_of(interaction)
        stack = wiring()
        attack_id = await resolve_room_key(stack, match["key"])
        label = strings["room_id_button"]
        style: Any = discord.ButtonStyle.secondary
        if stack is not None and attack_id:
            try:
                current = await attack_by_id(stack, attack_id)
            except Exception:
                current = None
            if current is not None and str(current.lobby_url or "").strip():
                label = strings["room_id_modify_button"]
                style = discord.ButtonStyle.danger
        return cls(attack_id, label, style=style)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the game ID modal — and LOCK the entry for the other player."""
        strings = strings_of(interaction)
        stack = wiring()
        if stack is None or not self.attack_id:
            await interaction.response.send_message(strings["no_service"], ephemeral=True)
            return
        # The meeting message is public — its buttons are reserved to
        # the two players (clean refusal).
        try:
            current = await attack_by_id(stack, self.attack_id)
        except Exception:
            current = None
        if current is None or room_side_of(current, str(interaction.user.id)) == "":
            await interaction.response.send_message(strings["room_not_player"], ephemeral=True)
            return
        # The persisted lock — the other player is refused, the same
        # player refreshes his own stamp and reopens the modal.
        try:
            locked = await stack.attacks.lock_room_id(self.attack_id, str(interaction.user.id))
        except Exception as exc:
            message = getattr(exc, "message", None) or str(exc)
            await interaction.response.send_message(
                strings["room_id_locked_other"] if "saisit" in message else strings["failed"].format(message=message),
                ephemeral=True,
            )
            return
        # Instant visual lock: the room message shows the ⏳ face.
        await refresh_room_message_safe(interaction.client, stack, locked, locale_of(interaction), id_pending=True)
        await interaction.response.send_modal(RoomUrlModal(self.attack_id, str(interaction.user.id)))


class RoomUrlModal(discord.ui.Modal):
    """The battle-room game ID modal."""

    def __init__(self, attack_id: str, player_id: str) -> None:
        strings = strings_by_locale("fr")
        super().__init__(title=strings["score_url_modal_title"][:45], timeout=300)
        self.attack_id = attack_id
        self.player_id = player_id
        self.strings = strings
        self.url_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label=strings["score_url_modal_label"][:45],
            placeholder=strings["score_url_modal_placeholder"][:100],
            required=True,
            max_length=200,
        )
        self.add_item(self.url_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Store the ID and refresh the scoreboard in place."""
        strings = self.strings
        stack = wiring()
        if stack is None:
            await interaction.response.send_message(strings["no_service"], ephemeral=True)
            return
        url = str(self.url_input.value or "").strip()
        try:
            attack = await stack.attacks.set_lobby_url(self.attack_id, self.player_id, url)
        except Exception as exc:
            message = getattr(exc, "message", None) or str(exc)
            await interaction.response.send_message(strings["failed"].format(message=message), ephemeral=True)
            return
        # The submission clears the PERSISTED ID lock.
        try:
            await stack.attacks.unlock_room_id(self.attack_id, self.player_id)
        except Exception:
            logger.debug("kingdom: room ID lock clear skipped", exc_info=True)
        await refresh_room_message_safe(interaction.client, stack, attack, locale_of(interaction))
        # NO ephemeral bubble — the scoreboard IS the feedback.
        await interaction.response.defer(ephemeral=True)


class RoomReadyButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:room:ready:(?P<key>[0-9a-f]{16})(?::(?P<side>attacker|defender))?",
):
    """The persistent ✅ Prêt button of the battle room — one per side.

    The Prêt unlocks only once the lobby ID is shared; the click
    records the readiness and edits the player's half of the
    scoreboard in place (NO ephemeral bubble); when BOTH players are
    ready the match event is created and a still-live sabotage phase
    closes at once.
    """

    def __init__(self, attack_id: str, label: str, *, side: str | None = None, done: bool = False) -> None:
        key = room_key(attack_id)
        custom_id = _ROOM_READY.format(key=key) if side is None else _ROOM_READY_SIDE.format(key=key, side=side)
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=custom_id,
                style=discord.ButtonStyle.success if done else discord.ButtonStyle.secondary,
                disabled=done,
            )
        )
        self.attack_id = attack_id
        self.side = side

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> RoomReadyButton:
        strings = strings_of(interaction)
        side = match["side"] if "side" in match.groupdict() else None
        if side:
            label = strings[f"room_ready_{side}_button"].format(
                player=strings[f"room_side_{side}"]
            )
        else:
            label = strings["room_ready_button"]
        return cls(await resolve_room_key(wiring(), match["key"]), label, side=side)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Record the readiness — both ready starts the match."""
        from .pickban import sweep_sabotage_dms_on_open_safe

        strings = strings_of(interaction)
        stack = wiring()
        if stack is None or not self.attack_id:
            await interaction.response.send_message(strings["no_service"], ephemeral=True)
            return
        try:
            current = await attack_by_id(stack, self.attack_id)
        except Exception:
            current = None
        if current is None:
            await interaction.response.send_message(strings["no_service"], ephemeral=True)
            return
        side_of = room_side_of(current, str(interaction.user.id))
        if side_of == "":
            await interaction.response.send_message(strings["room_not_player"], ephemeral=True)
            return
        if self.side is not None and side_of != self.side:
            # Each Prêt button belongs to ONE side.
            await interaction.response.send_message(strings["room_not_your_side"], ephemeral=True)
            return
        if not str(current.lobby_url or "").strip():
            await interaction.response.send_message(strings["room_ready_needs_url"], ephemeral=True)
            return
        try:
            attack = await stack.attacks.mark_ready(self.attack_id, str(interaction.user.id))
        except Exception as exc:
            message = getattr(exc, "message", None) or str(exc)
            await interaction.response.send_message(strings["failed"].format(message=message), ephemeral=True)
            return
        # The scoreboard refreshes in place — the click answers with a
        # silent defer (no ephemeral bubble, the view IS the feedback).
        await refresh_room_message_safe(interaction.client, stack, attack, locale_of(interaction))
        await interaction.response.defer()
        score = attack.score or {}
        if not score.get("all_ready"):
            return
        # « Prêt = engagement » — the second Prêt STARTS the game: a
        # still-live sabotage phase closes at once and its DM buttons
        # die with it.
        if not (attack.pickban or {}).get("sabotage_resolved"):
            try:
                closed = await stack.attacks.close_sabotage_now(self.attack_id)
                await sweep_sabotage_dms_on_open_safe(interaction.client, closed, strings)
            except Exception:
                logger.warning("kingdom: sabotage close on both-Prêt failed", exc_info=True)
        if score.get("room_event_id"):
            return
        await create_room_event_safe(interaction.client, stack, attack, strings, interaction.channel)
        # affaire-27 : « Prêt = la partie part » ne doit jamais
        # dépendre de la cadence du tick — le clic réveille la passe
        # de phases (idempotente, best effort), le vocal et l'événement
        # atterrissent dans la seconde du clic.
        try:
            from .phases import run_attack_phases_safe

            task = asyncio.create_task(run_attack_phases_safe(interaction.client))
            _PHASE_WAKE_TASKS.add(task)
            task.add_done_callback(_PHASE_WAKE_TASKS.discard)
        except Exception:
            logger.debug("kingdom: ready-click phase wake skipped", exc_info=True)


class RoomResultButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:room:result:(?P<key>[0-9a-f]{16})",
):
    """The persistent 🏆 button of the battle room (result declaration)."""

    def __init__(self, attack_id: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=_ROOM_RESULT.format(key=room_key(attack_id)),
                style=discord.ButtonStyle.primary,
            )
        )
        self.attack_id = attack_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> RoomResultButton:
        label = strings_of(interaction)["result_button"]
        return cls(await resolve_room_key(wiring(), match["key"]), label)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Ephemeral winner flow (battle-room-id-v2).

        No pending declaration: a winner select → an EXPLICIT
        confirmation (anti-missclick). Another player's pending
        declaration: only ✅ Confirmer or ⚖️ Contester. One's own
        declaration: the select to modify it.
        """
        strings = strings_of(interaction)
        stack = wiring()
        if stack is None or not self.attack_id:
            await interaction.response.send_message(strings["no_service"], ephemeral=True)
            return
        try:
            attack = await attack_by_id(stack, self.attack_id)
        except Exception:
            attack = None
        if attack is None or attack.is_over or attack.state is not AttackState.MEETING:
            await interaction.response.send_message(strings["no_service"], ephemeral=True)
            return
        if room_side_of(attack, str(interaction.user.id)) == "":
            await interaction.response.send_message(strings["room_not_player"], ephemeral=True)
            return
        if not (attack.score or {}).get("all_ready"):
            # No 🏆 before both players are Prêt — a stale click (an
            # old view) is politely refused.
            await interaction.response.send_message(strings["result_not_ready"], ephemeral=True)
            return
        score = dict(attack.score or {})
        if score.get("disputed"):
            # Once the dispute is open the flow is frozen — the ephemeral
            # reminder STAYS until the admins arbitrate. beta-fixes-v1
            # (Affaires 14/17): a dispute AUTO-OPENED by the deadline is
            # not a contradictory pair of declarations — the bubble
            # says what really happened instead of the misleading
            # generic label.
            dispute_key = (
                "score_auto_dispute_open" if score.get("auto_dispute") else "score_disputed"
            )
            await interaction.response.send_message(
                strings[dispute_key].format(game=str(attack.lobby_url or "") or "—"),
                ephemeral=True,
            )
            return
        player_id = str(interaction.user.id)
        declarations = dict(score.get("declarations") or {})
        others = {
            declarer: declaration
            for declarer, declaration in declarations.items()
            if str(declarer) != player_id
        }
        if others:
            declarer, declaration = next(iter(others.items()))
            await _send_room_review(interaction, stack, strings, attack, str(declarer), str(declaration["winner"]))
            return
        mine = declarations.get(player_id)
        if mine:
            winner_name = await kingdom_name(stack.kingdoms, str(mine.get("winner") or ""))
            await _send_room_my_declaration(
                interaction, stack, strings, attack, str(mine.get("winner") or ""), winner_name
            )
            return
        await _send_room_select(interaction, stack, strings, attack)


class DisputeChoiceSelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]],
    template=r"kingdom:attack:dispute:pick:(?P<key>[0-9a-f]{16})",
):
    """The dispute DM's two-kingdom select — modify one's declaration."""

    def __init__(self, attack_id: str, options: list[discord.SelectOption], placeholder: str) -> None:
        super().__init__(
            discord.ui.Select(
                custom_id=_DISPUTE_PICK.format(key=room_key(attack_id)),
                options=options[:25],
                placeholder=placeholder[:100],
                min_values=1,
                max_values=1,
            )
        )
        self.attack_id = attack_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> DisputeChoiceSelect:
        strings = strings_of(interaction)
        stack = wiring()
        attack_id = await resolve_room_key(stack, match["key"])
        options: list[discord.SelectOption] = []
        if stack is not None and attack_id:
            try:
                attack = await attack_by_id(stack, attack_id)
                options = await _dispute_select_options(stack, attack)
            except Exception:
                options = []
        if not options:
            options = [discord.SelectOption(label="—", value="none")]
        return cls(attack_id, options, strings["result_select_placeholder"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Modify the declaration — the canonical declare_score path."""
        strings = strings_of(interaction)
        data = dict(getattr(interaction, "data", None) or {})
        values = [str(value) for value in (data.get("values") or [])]
        if not values:
            values = [str(value) for value in (getattr(self.item, "values", None) or [])]
        if not values:
            await interaction.response.defer()
            return
        await handle_dispute_reply_safe(interaction, wiring(), strings, self.attack_id, values[0])


class DisputeConfirmButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:dispute:confirm:(?P<key>[0-9a-f]{16})",
):
    """The dispute DM's ✅ button — re-confirm one's CURRENT declaration."""

    def __init__(self, attack_id: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=_DISPUTE_CONFIRM.format(key=room_key(attack_id)),
                style=discord.ButtonStyle.success,
            )
        )
        self.attack_id = attack_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> DisputeConfirmButton:
        strings = strings_of(interaction)
        return cls(await resolve_room_key(wiring(), match["key"]), strings["dispute_confirm_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Re-confirm the CURRENT declaration through declare_score."""
        strings = strings_of(interaction)
        stack = wiring()
        if stack is None or not self.attack_id:
            await interaction.response.edit_message(content=strings["no_service"], view=None)
            return
        try:
            attack = await attack_by_id(stack, self.attack_id)
        except Exception:
            attack = None
        if attack is None:
            await interaction.response.edit_message(content=strings["no_service"], view=None)
            return
        player_id = str(interaction.user.id)
        mine = (dict((attack.score or {}).get("declarations") or {})).get(player_id) or {}
        await handle_dispute_reply_safe(
            interaction, stack, strings, self.attack_id, str(mine.get("winner") or "")
        )


class DisputeView(ComposedView):
    """The admin arbitration view of a disputed meeting (bot-admin only).

    decisions-admin-v1 (Drasah 25/11): the view serves EVERY admin
    surface (the bot-admins DM and the console's ⚖️ inbox alike) and
    every click demands the MANDATORY reason modal — the public trace
    is the anti-abus. «cancel» (annulation) joins the choices: no
    winner, no points, the locks release — versus «both», the double
    forfait. The resolve/record/announce path lives ONCE in the
    decisions layer (apply_admin_decision + DecisionReasonModal).
    """

    def __init__(self, attack_id: str, locale: str) -> None:
        super().__init__(mod="kingdom", timeout=None)
        self.attack_id = attack_id
        self.locale = locale
        strings = strings_by_locale(locale)
        self.strings = strings
        for choice, key in (
            ("attacker", "dispute_win_attacker"),
            ("defender", "dispute_win_defender"),
            ("both", "dispute_double"),
            ("cancel", "dispute_cancel_button"),
        ):
            button: discord.ui.Button[discord.ui.View] = discord.ui.Button(
                label=strings[key][:80],
                custom_id=_DISPUTE_ARBITRATE.format(choice=choice, key=room_key(attack_id)),
                style=discord.ButtonStyle.danger,
            )
            button.callback = self._make_on_arbitrate(choice)  # type: ignore[method-assign]
            self.add_item(button)

    def _make_on_arbitrate(self, choice: str) -> Any:
        async def _on_arbitrate(interaction: discord.Interaction) -> None:
            strings = self.strings
            from .common import _bot_admins

            if str(getattr(interaction.user, "id", "")) not in (_bot_admins(interaction) or ()):
                await interaction.response.send_message(strings["dispute_not_admin"], ephemeral=True)
                return
            from .decisions import DecisionReasonModal

            await interaction.response.send_modal(
                DecisionReasonModal(self.attack_id, choice, self.locale)
            )

        return _on_arbitrate


__all__ = [
    "DisputeChoiceSelect",
    "DisputeConfirmButton",
    "DisputeView",
    "DraftViewButton",
    "RoomReadyButton",
    "RoomResultButton",
    "RoomUrlButton",
    "RoomUrlModal",
    "announce_conquest_safe",
    "announce_forfeit_safe",
    "cleanup_battle_rooms_safe",
    "cleanup_decided_attack_safe",
    "create_room_event_safe",
    "declare_room_score",
    "dm_admins_dispute_safe",
    "draft_sheet_embed",
    "handle_dispute_reply_safe",
    "on_score_resolved_safe",
    "open_battle_room",
    "open_meeting_and_room_safe",
    "refresh_room_message_safe",
    "resolve_room_key",
    "room_body_text",
    "room_view",
    "send_dispute_dm_round_safe",
    "stamp_room_ping_winner_safe",
    "sweep_pre_room_announces_safe",
    "sweep_reveal_notes_safe",
]
