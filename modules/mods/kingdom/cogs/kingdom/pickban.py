"""The pick & ban draft DMs + the sabotage phase (P4.1b tranche 2a).

The ported functional reference (kingdom_attack_panel.py, D77):

* the draft DM — THREE dropdowns (« Choix 1/2/3 »), each offering the
  civs the other slots do not hold, ✏️ Modifier GLOBAL, ✅ Valider the
  ONLY consumer (restart-proof through the engine's ``{side}_draft``
  staged wizard state, shirar-v1);
* the reveal — once BOTH sides validated, each DM becomes the
  adversary's SHUFFLED civs (seeded, the ranking stays secret) + the
  sabotage prompt (pickban-ordre-v2, reveal-mp-ping-v1);
* the sabotage phase — 🗡️ Saboter (the bought Sabotage techno, the
  🦅 Faucon rides the volière seam the day it exists) and ⚔️ Passer;
  the picks edit the SAME ephemeral panel (sabotage-ux-v1) and the
  DM reveal stays the ONE living surface (sabotage-dm-fresh-v1).

Every component is a persistent DynamicItem — a restart between the
DM send and the click never kills the flow. All Discord writes are
best-effort: a failing DM/edition never breaks the engine state.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import discord

from botforge.mods.kingdom.game_clock import game_now
from botforge.mods.kingdom.models import AttackState

from .common import (
    PICKBAN_RANKS,
    attack_by_id,
    attack_salon_send_safe,
    close_previous_ephemeral,
    delete_dm_message_safe,
    dm_user_safe,
    dm_view,
    edit_dm_message_safe,
    fmt_paris,
    kingdom_by_id,
    own_picks_line,
    pickban_staged,
    surface_footer,
    ready_key,
    reveal_civs,
    room_side_of,
    score_players,
    side_of,
    strings_by_locale,
    wiring,
)

logger = logging.getLogger("kingdom.attack")

# sabotage-ux-v1: ONE live sabotage panel per (attack, player) —
# self-destructs at the webhook token limit (15 min) so the
# ephemeral never outlives its phase.
_SABOTAGE_PANELS: dict[tuple[str, str], dict[str, Any]] = {}
_SABOTAGE_PANEL_SECONDS = 15 * 60
_SABOTAGE_SWEEP_SECONDS = 30


def _error_note_followup(interaction: discord.Interaction, content: str) -> None:
    """Answer a deferred DM click with a one-shot refusal note."""
    async def _delete_later(message: Any) -> None:
        await asyncio.sleep(60)
        try:
            await message.delete()
        except Exception:  # noqa: S110 - a lost note never blocks
            pass

    async def _send() -> None:
        try:
            message = await interaction.followup.send(content)
            asyncio.create_task(_delete_later(message))
        except Exception:
            logger.warning("kingdom: pickban refusal note failed", exc_info=True)

    asyncio.create_task(_send())


def _arm_sabotage_panel_timer(key: tuple[str, str], seconds: float | None = None) -> None:
    """(Re)arm the auto-destruction of one sabotage panel.

    affaire-26 (Drasah 25/11 live report): the panel flashed for a
    millisecond then vanished — this arm used to DELETE the panel
    before arming, so every open or click erased its own surface. The
    arm now NEVER deletes: it cancels the prior timer and schedules a
    fresh one; a short ``seconds`` (no action left) sweeps the closed
    panel quickly.
    """
    panel = _SABOTAGE_PANELS.get(key)
    if panel is None:
        return
    existing = panel.get("task")
    if existing is not None:
        existing.cancel()
    interaction = panel["interaction"]

    async def _delete_later() -> None:
        try:
            await asyncio.sleep(seconds if seconds is not None else _SABOTAGE_PANEL_SECONDS)
            await interaction.delete_original_response()
        except Exception:
            logger.debug("kingdom: sabotage panel auto-delete skipped", exc_info=True)
        finally:
            if panel.get("task") is asyncio.current_task():
                panel.pop("task", None)
            if _SABOTAGE_PANELS.get(key) is panel and "task" not in panel:
                _SABOTAGE_PANELS.pop(key, None)

    panel["task"] = asyncio.create_task(_delete_later())


async def _delete_sabotage_panel(key: tuple[str, str]) -> None:
    """Delete one player's sabotage panel NOW and unarm it."""
    panel = _SABOTAGE_PANELS.pop(key, None)
    if panel is None:
        return
    task = panel.get("task")
    if task is not None:
        task.cancel()
    try:
        await panel["interaction"].delete_original_response()
    except Exception:
        logger.debug("kingdom: sabotage panel delete skipped", exc_info=True)


# ---------------------------------------------------------------------------
# The key resolvers (a dead click answers once, never raises)
# ---------------------------------------------------------------------------


async def resolve_pickban_key(stack: Any, key: str) -> tuple[str, str]:
    """Resolve a draft-view key back to (attack_id, player_id).

    Only OPEN drafts (sent, unresolved) match — a resolved draft's
    buttons die with a graceful refusal.
    """
    if stack is None:
        return ("", "")
    try:
        for attack in await stack.attacks.attacks():
            if attack.state is not AttackState.DEFENDED:
                continue
            pickban = dict(attack.pickban or {})
            if not pickban.get("sent") or pickban.get("resolved_pickban"):
                continue
            for player_id in score_players(attack):
                if ready_key(str(attack.id), player_id) == key:
                    return (str(attack.id), player_id)
    except Exception:
        logger.warning("kingdom: pickban key resolution failed", exc_info=True)
    return ("", "")


async def resolve_sabotage_key(stack: Any, key: str) -> tuple[str, str]:
    """Resolve a sabotage key back to (attack_id, player_id)."""
    if stack is None:
        return ("", "")
    try:
        for attack in await stack.attacks.attacks():
            if attack.state not in (AttackState.DEFENDED, AttackState.MEETING):
                continue
            pickban = dict(attack.pickban or {})
            if not pickban.get("resolved_pickban") or pickban.get("sabotage_resolved"):
                continue
            for player_id in score_players(attack):
                if ready_key(str(attack.id), player_id) == key:
                    return (str(attack.id), player_id)
    except Exception:
        logger.warning("kingdom: sabotage key resolution failed", exc_info=True)
    return ("", "")


# ---------------------------------------------------------------------------
# The draft DM view (shirar-v1: staged, restart-proof)
# ---------------------------------------------------------------------------


async def pickban_hand_safe(stack: Any, kingdom_id: str | None, player_id: str) -> list[str]:
    """One player's draft hand — his mercenary civ included (T2c)."""
    if stack is not None:
        try:
            return [str(civ) for civ in await stack.attacks.pickban_hand(kingdom_id or "", player_id)]
        except Exception:
            logger.warning("kingdom: pickban hand read failed", exc_info=True)
    kingdom = await kingdom_by_id(stack.kingdoms if stack else None, kingdom_id)
    return list(getattr(kingdom, "civilizations", None) or []) if kingdom else []


async def pickban_dm_view(
    stack: Any, attack: Any, side: str, player_id: str, locale: str
) -> discord.ui.View:
    """The draft DM view — three dropdowns + Modifier + Valider."""
    strings = strings_by_locale(locale)
    kingdom_id = str(
        attack.attacker_kingdom_id if side == "attacker" else attack.defender_kingdom_id
    )
    hand = await pickban_hand_safe(stack, kingdom_id, str(player_id))
    picks = pickban_staged(dict(attack.pickban or {}), side)
    count = min(3, len(hand) or 1)
    view = dm_view(timeout=None)
    for index in range(count):
        own = picks[index]
        offered = [civ for civ in hand if civ not in picks or civ == own]
        if not offered:
            continue
        view.add_item(PickBanSelect(str(attack.id), str(player_id), index, offered, own, locale))
    chosen = any(picks[:count])
    view.add_item(PickBanModifyButton(str(attack.id), str(player_id), chosen, locale))
    view.add_item(
        PickBanValidateButton(
            str(attack.id),
            str(player_id),
            len([p for p in picks[:count] if p]) == count,
            locale,
        )
    )
    return view


class PickBanSelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]],
    template=r"kingdom:attack:pickban:pick:(?P<key>[0-9a-f]{16}):(?P<slot>[0-2])",
):
    """The restart-proof dropdown of ONE draft slot."""

    def __init__(
        self,
        attack_id: str,
        player_id: str,
        index: int,
        options: list[str],
        selected: str,
        locale: str,
    ) -> None:
        strings = strings_by_locale(locale)
        key = ready_key(attack_id, player_id)
        select: discord.ui.Select[Any] = discord.ui.Select(
            custom_id=f"kingdom:attack:pickban:pick:{key}:{index}",
            placeholder=strings["pickban_pick"].format(n=PICKBAN_RANKS[index])[:100],
            options=[
                discord.SelectOption(label=civ[:100], value=civ, default=(civ == selected))
                for civ in options
            ][:25],
            min_values=1,
            max_values=1,
        )
        super().__init__(select)
        self.attack_id = attack_id
        self.player_id = player_id
        self.index = index
        self.locale = locale

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> PickBanSelect:
        # beta-retours-v1: ACK FIRST — the key scan must not eat the
        # 3-second window (a deferred UPDATE acknowledges at once).
        try:
            await interaction.response.defer()
        except Exception:  # noqa: S110
            pass
        stack = wiring()
        attack_id, player_id = await resolve_pickban_key(stack, match["key"])
        return cls(attack_id, player_id, int(match["slot"]), [], "", str(interaction.locale or "fr"))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Stage the pick, re-render the DM view in place."""
        strings = strings_by_locale(self.locale)
        stack = wiring()
        if stack is None or not self.attack_id:
            _error_note_followup(interaction, strings["no_service"])
            return
        values = list((getattr(interaction, "data", None) or {}).get("values") or [])
        if not values:
            return
        try:
            attack = await stack.attacks.stage_draft_pick(
                self.attack_id, self.player_id, self.index, str(values[0])
            )
        except Exception as exc:
            message = getattr(exc, "message", None) or str(exc)
            _error_note_followup(interaction, strings["failed"].format(message=message))
            return
        view = await pickban_dm_view(
            stack, attack, side_of(attack, self.player_id), self.player_id, self.locale
        )
        try:
            await interaction.edit_original_response(view=view)
        except Exception:
            logger.warning("kingdom: pick & ban DM edit failed", exc_info=True)


class PickBanModifyButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:pickban:modify:(?P<key>[0-9a-f]{16})",
):
    """The restart-proof global ✏️ Modifier — resets the three slots."""

    def __init__(self, attack_id: str, player_id: str, chosen: bool, locale: str) -> None:
        strings = strings_by_locale(locale)
        key = ready_key(attack_id, player_id)
        super().__init__(
            discord.ui.Button(
                label=strings["pickban_modify_button"][:80],
                custom_id=f"kingdom:attack:pickban:modify:{key}",
                style=discord.ButtonStyle.success if chosen else discord.ButtonStyle.secondary,
                disabled=not chosen,
            )
        )
        self.attack_id = attack_id
        self.player_id = player_id
        self.locale = locale

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> PickBanModifyButton:
        try:
            await interaction.response.defer()
        except Exception:  # noqa: S110
            pass
        stack = wiring()
        attack_id, player_id = await resolve_pickban_key(stack, match["key"])
        return cls(attack_id, player_id, False, str(interaction.locale or "fr"))

    async def callback(self, interaction: discord.Interaction) -> None:
        strings = strings_by_locale(self.locale)
        stack = wiring()
        if stack is None or not self.attack_id:
            _error_note_followup(interaction, strings["no_service"])
            return
        try:
            attack = await stack.attacks.clear_draft_picks(self.attack_id, self.player_id)
        except Exception as exc:
            message = getattr(exc, "message", None) or str(exc)
            _error_note_followup(interaction, strings["failed"].format(message=message))
            return
        view = await pickban_dm_view(
            stack, attack, side_of(attack, self.player_id), self.player_id, self.locale
        )
        try:
            await interaction.edit_original_response(view=view)
        except Exception:
            logger.warning("kingdom: pick & ban DM edit failed", exc_info=True)


class PickBanValidateButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:pickban:validate:(?P<key>[0-9a-f]{16})",
):
    """The restart-proof ✅ Valider — the ONLY consumer of the wizard."""

    def __init__(self, attack_id: str, player_id: str, complete: bool, locale: str) -> None:
        strings = strings_by_locale(locale)
        key = ready_key(attack_id, player_id)
        super().__init__(
            discord.ui.Button(
                label=strings["pickban_validate"][:80],
                custom_id=f"kingdom:attack:pickban:validate:{key}",
                style=discord.ButtonStyle.success,
                disabled=not complete,
            )
        )
        self.attack_id = attack_id
        self.player_id = player_id
        self.locale = locale

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> PickBanValidateButton:
        try:
            await interaction.response.defer()
        except Exception:  # noqa: S110
            pass
        stack = wiring()
        attack_id, player_id = await resolve_pickban_key(stack, match["key"])
        return cls(attack_id, player_id, False, str(interaction.locale or "fr"))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Submit the ranked picks, then validate (D77, blind)."""
        strings = strings_by_locale(self.locale)
        stack = wiring()
        if stack is None or not self.attack_id:
            _error_note_followup(interaction, strings["no_service"])
            return
        attack = await attack_by_id(stack, self.attack_id)
        if attack is None or (attack.pickban or {}).get("resolved_pickban"):
            _error_note_followup(
                interaction, strings["failed"].format(message="le pick & ban est fermé")
            )
            return
        side = side_of(attack, self.player_id)
        pickban: dict[str, Any] = dict(attack.pickban or {})
        picks = [str(civ) for civ in pickban_staged(pickban, side) if civ]
        hand_count = min(3, len(pickban.get(f"{side}_hand") or []) or 3)
        if len(set(picks)) != len(picks):
            _error_note_followup(interaction, strings["pickban_duplicate"])
            return
        if not picks or len(picks) != hand_count:
            _error_note_followup(interaction, strings["pickban_missing"].format(count=hand_count))
            return
        try:
            await stack.attacks.set_picks(self.attack_id, self.player_id, picks)
            attack = await stack.attacks.validate_pickban(self.attack_id, self.player_id)
        except Exception as exc:
            message = getattr(exc, "message", None) or str(exc)
            _error_note_followup(interaction, strings["failed"].format(message=message))
            return
        # Symmetry: the SAME answer for the first and the second
        # validator — nobody sees the adversary civs.
        content = strings["pickban_waiting"]
        try:
            await interaction.edit_original_response(content=content, view=None)
        except Exception:
            logger.warning("kingdom: pick & ban DM edit failed", exc_info=True)
        pickban = dict(attack.pickban or {})
        if not pickban.get("resolved_pickban"):
            return
        # The draft resolved — edit BOTH DMs into the reveal + the
        # sabotage prompt (no new surface, anti-spam).
        await edit_pickban_dms_reveal(interaction.client, attack, strings)
        await announce_matchup_now_safe(interaction.client, stack, attack, strings)


async def announce_matchup_now_safe(bot: Any, stack: Any, attack: Any, strings: dict[str, str]) -> None:
    """Announce the WHO VS WHO note in the attack's salon at once.

    beta-retours-v1: the second validation ends the draft — the salon
    learns the matchup AT THIS BEAT (the tick sleeps to the next
    deadline otherwise). Strict anonymity: names only, no civs.
    """
    guild = None
    for candidate in list(getattr(bot, "guilds", []) or []):
        salon = getattr(candidate, "get_channel", lambda _id: None)(
            int((attack.score or {}).get("attack_channel_id") or 0)
        )
        if salon is not None:
            guild = candidate
            break
    if guild is None:
        return
    attacker = await kingdom_name_safe(stack, attack.attacker_kingdom_id)
    defender = await kingdom_name_safe(stack, attack.defender_kingdom_id)
    await attack_salon_send_safe(guild, attack, strings["matchup_note"].format(attacker=attacker, defender=defender))
    try:
        await stack.attacks.mark_matchup_announced(str(attack.id))
    except Exception:
        logger.warning("kingdom: matchup flag failed", exc_info=True)


async def kingdom_name_safe(stack: Any, kingdom_id: str | None) -> str:
    from .common import kingdom_name

    return await kingdom_name(stack.kingdoms if stack else None, kingdom_id)


# ---------------------------------------------------------------------------
# The DM sends + the reveal edits (reveal-mp-ping-v1)
# ---------------------------------------------------------------------------


async def _salon_dm_failure_note_safe(bot: Any, attack: Any, player_id: str, strings: Any) -> None:
    """Leave a LOUD note in the attack salon when a draft DM is refused.

    Drasah's live finding (25/11): the defender's draft DM died on
    Discord's 403 « no mutual guilds » (the account refuses the app's
    DMs) and the draft silently defaulted 5 minutes later — nobody
    knew WHY. The failed send now leaves a WARNING in the attack's
    own salon: the player is told to fix his privacy settings before
    the draft window closes. Never a crash, never a block.
    """
    guilds = list(getattr(bot, "guilds", []) or [])
    if not guilds:
        return
    note = str(strings.get("pickban_dm_failed_sal", "")).format(player=str(player_id))
    if not note:
        return
    try:
        await attack_salon_send_safe(guilds[0], attack, note)
    except Exception:
        logger.warning("kingdom: the draft DM failure note failed", exc_info=True)


async def send_pickban_dm(bot: Any, attack: Any, locale: str) -> None:
    """Send the pick & ban DM to each human player."""
    strings = strings_by_locale(locale)
    stack = wiring()
    hand = await pickban_hand_safe(stack, attack.attacker_kingdom_id, str(attack.attacker_lord_id))
    theirs = await pickban_hand_safe(stack, attack.defender_kingdom_id, str(attack.defender_lord_id))
    view = await pickban_dm_view(stack, attack, "attacker", str(attack.attacker_lord_id), locale)
    stock_attacker = await sabotage_stock_line(stack, attack, "attacker", strings)
    message = await dm_user_safe(
        bot,
        str(attack.attacker_lord_id),
        strings["pickban_dm"].format(
            map=attack.map_key,
            count=min(3, len(hand)) or 1,
            deadline=fmt_paris(attack.expires_at),
            hand=", ".join(hand) or "—",
            theirs=", ".join(theirs) or "—",
        )
        + (f"\n\n{stock_attacker}" if stock_attacker else ""),
        view,
    )
    if message is not None:
        await record_pickban_dm_safe(str(attack.id), str(attack.attacker_lord_id), message)
    else:
        await _salon_dm_failure_note_safe(bot, attack, str(attack.attacker_lord_id), strings)
    if not attack.ai_defender and attack.defender_lord_id:
        view = await pickban_dm_view(stack, attack, "defender", str(attack.defender_lord_id), locale)
        stock_defender = await sabotage_stock_line(stack, attack, "defender", strings)
        message = await dm_user_safe(
            bot,
            str(attack.defender_lord_id),
            strings["pickban_dm"].format(
                map=attack.map_key,
                count=min(3, len(theirs)) or 1,
                deadline=fmt_paris(attack.expires_at),
                hand=", ".join(theirs) or "—",
                theirs=", ".join(hand) or "—",
            )
            + (f"\n\n{stock_defender}" if stock_defender else ""),
            view,
        )
        if message is not None:
            await record_pickban_dm_safe(str(attack.id), str(attack.defender_lord_id), message)
        else:
            await _salon_dm_failure_note_safe(bot, attack, str(attack.defender_lord_id), strings)


async def record_pickban_dm_safe(attack_id: str, player_id: str, message: Any) -> None:
    """Store the DM refs so the resolution edits the SAME message."""
    stack = wiring()
    if stack is None:
        return
    try:
        channel = getattr(message, "channel", None)
        await stack.attacks.record_pickban_dm(
            attack_id, player_id, int(getattr(channel, "id", 0)), int(getattr(message, "id", 0))
        )
    except Exception:
        logger.warning("kingdom: pick & ban DM refs not stored", exc_info=True)


async def reveal_mosaic_files(
    attack: Any, side: str, pickban: dict[str, Any], shuffled: list[str]
) -> list[discord.File] | None:
    """Build one side's reveal mosaic (best effort, None keeps text)."""
    try:
        from .civ_crests import civ_crest_mosaic_file

        used = {str(civ) for civ in (pickban.get(f"{side}_sabotages") or [])}
        mosaic = await civ_crest_mosaic_file(
            [(civ, "", civ) for civ in shuffled],
            filename="reveal.png",
            with_origin_badges=False,
            crossed=used,
        )
        return [mosaic] if mosaic is not None else None
    except Exception:
        logger.warning("kingdom: reveal mosaic composition failed", exc_info=True)
        return None


async def sabotage_reveal_payload(
    stack: Any, attack: Any, side: str, strings: dict[str, str]
) -> tuple[str, str, discord.ui.View, list[discord.File] | None]:
    """Build one side's REVEAL DM content + view + crossed mosaic.

    sabotage-visuel-v1 (Affaire 26): the revealed civs wear ONE
    composite mosaic — each civ name painted above its crest (the
    alliances-lisibilite-v1 style), in the SEEDED shuffled order (a
    fresh shuffle would reorder the mosaic at each snipe), and every
    civ this side already sabotaged wears the ❌ cross. Shared by the
    initial reveal AND every post-pick refresh — the DM stays the ONE
    living surface. Best effort: a failed composition keeps the text.
    """
    pickban = dict(attack.pickban or {})
    player_id = str(attack.attacker_lord_id if side == "attacker" else attack.defender_lord_id)
    enemy = "defender" if side == "attacker" else "attacker"
    shuffled = reveal_civs(f"{attack.id}:{enemy}", pickban.get(f"{enemy}_picks"))
    own = [str(civ) for civ in (pickban.get(f"{side}_picks") or [])]
    own_line = strings["pickban_own_picks_line"].format(picks=own_picks_line(own) or "—")
    content = (
        f"<@{player_id}>\n"
        f"{strings['pickban_reveal_adversary']}\n**{', '.join(shuffled) or '—'}**\n\n"
        f"{own_line}\n\n"
        f"{strings['pickban_reveal_dm'].format(map=attack.map_key, deadline=fmt_paris(attack.expires_at))}"
    )
    if stack is not None:
        stock = await sabotage_stock_line(stack, attack, side, strings)
        if stock:
            content = f"{content}\n\n{stock}"
    view = await sabotage_dm_view(stack, attack, side, strings)
    files = await reveal_mosaic_files(attack, side, pickban, shuffled)
    return player_id, content, view, files



async def edit_pickban_dms_reveal(bot: Any, attack: Any, strings: dict[str, str]) -> None:
    """Send both players the REVEAL as a FRESH DM (a real ping), the
    old draft DM deleted, the refs re-pointed (reveal-mp-ping-v1)."""
    pickban: dict[str, Any] = dict(attack.pickban or {})
    stack = wiring()
    for side, player_id in (
        ("attacker", str(attack.attacker_lord_id)),
        ("defender", str(attack.defender_lord_id or "")),
    ):
        if not player_id or (side == "defender" and attack.ai_defender):
            continue
        _pid, content, view, files = await sabotage_reveal_payload(stack, attack, side, strings)
        ref = pickban.get(f"{side}_dm") or {}
        sent = await dm_user_safe(bot, player_id, content, view, files)
        if sent is not None:
            await delete_dm_message_safe(bot, ref)
            await record_pickban_dm_safe(str(attack.id), player_id, sent)
        elif ref.get("channel_id") and ref.get("message_id"):
            edited = await edit_dm_message_safe(bot, ref, content, view, files)
            if not edited:
                await dm_user_safe(bot, player_id, content, view, files)


async def edit_pickban_dms_default_reveal(bot: Any, attack: Any, strings: dict[str, str]) -> None:
    """The DEFAULTED draft's reveal (timeline-timers-v1) — same
    persistent sabotage view (shirar-v1: the phase survives)."""
    pickban: dict[str, Any] = dict(attack.pickban or {})
    stack = wiring()
    for side, player_id in (
        ("attacker", str(attack.attacker_lord_id)),
        ("defender", str(attack.defender_lord_id or "")),
    ):
        if not player_id or (side == "defender" and attack.ai_defender):
            continue
        enemy = "defender" if side == "attacker" else "attacker"
        shuffled = reveal_civs(f"{attack.id}:{enemy}", pickban.get(f"{enemy}_picks"))
        civs = ", ".join(shuffled) or "—"
        own = [str(civ) for civ in (pickban.get(f"{side}_picks") or [])]
        content = (
            f"<@{player_id}>\n"
            f"{strings['pickban_reveal_adversary']}\n**{civs}**\n\n"
            f"{strings['pickban_own_picks_line'].format(picks=own_picks_line(own) or '—')}\n\n"
            f"{strings['pickban_default_reveal_dm'].format(map=attack.map_key)}"
        )
        view = await sabotage_dm_view(stack, attack, side, strings)
        files = await reveal_mosaic_files(attack, side, pickban, shuffled)
        ref = pickban.get(f"{side}_dm") or {}
        sent = await dm_user_safe(bot, player_id, content, view, files)
        if sent is not None:
            await delete_dm_message_safe(bot, ref)
            await record_pickban_dm_safe(str(attack.id), player_id, sent)
        elif ref.get("channel_id") and ref.get("message_id"):
            edited = await edit_dm_message_safe(bot, ref, content, view, files)
            if not edited:
                await dm_user_safe(bot, player_id, content, view, files)


async def edit_pickban_dms_cancelled_safe(bot: Any, attack: Any, strings: dict[str, str]) -> None:
    """A cancelled attack closes BOTH draft DMs (beta-retours-v1.8)."""
    pickban: dict[str, Any] = dict(attack.pickban or {})
    content = str(strings["attack_cancelled_dm"]).format(map=attack.map_key)
    for side, player_id in (
        ("attacker", str(attack.attacker_lord_id)),
        ("defender", str(attack.defender_lord_id or "")),
    ):
        if not player_id or (side == "defender" and attack.ai_defender):
            continue
        ref = pickban.get(f"{side}_dm") or {}
        if ref.get("channel_id") and ref.get("message_id"):
            await edit_dm_message_safe(bot, ref, content, None)


async def edit_pickban_dms_phase_done(bot: Any, attack: Any, strings: dict[str, str]) -> None:
    """Edit both DMs into the « sabotage phase over » notice."""
    pickban: dict[str, Any] = dict(attack.pickban or {})
    content = strings["sab_phase_done"].format(map=attack.map_key)
    for side, player_id in (
        ("attacker", str(attack.attacker_lord_id)),
        ("defender", str(attack.defender_lord_id or "")),
    ):
        if not player_id or (side == "defender" and attack.ai_defender):
            continue
        ref = pickban.get(f"{side}_dm") or {}
        edited = False
        if ref.get("channel_id") and ref.get("message_id"):
            edited = await edit_dm_message_safe(bot, ref, content, None)
        if not edited:
            await dm_user_safe(bot, player_id, content, None)


async def sweep_sabotage_dms_on_open_safe(bot: Any, attack: Any, strings: dict[str, str]) -> None:
    """Clear the sabotage DMs' buttons when the meeting opens."""
    await edit_pickban_dms_phase_done(bot, attack, strings)


async def refresh_sabotage_dm_safe(bot: Any, attack: Any, side: str, strings: dict[str, str]) -> None:
    """Edit one side's reveal DM after a sabotage pick (dm-fresh-v1)."""
    _pid, content, view, files = await sabotage_reveal_payload(wiring(), attack, side, strings)
    player_id = str(
        attack.attacker_lord_id if side == "attacker" else attack.defender_lord_id
    )
    if not player_id:
        return
    ref = (attack.pickban or {}).get(f"{side}_dm") or {}
    edited = False
    if ref.get("channel_id") and ref.get("message_id"):
        edited = await edit_dm_message_safe(bot, ref, content, view, files)
    if not edited:
        await dm_user_safe(bot, player_id, content, view, files)


async def refresh_sabotage_dms_after_purchase_safe(bot: Any, player_id: str) -> None:
    """A Sabotage bought DURING the grace re-renders the buyer's live
    attack DMs at once (beta-retours-v1.4)."""
    stack = wiring()
    if stack is None or not player_id:
        return
    strings = strings_by_locale("fr")
    try:
        for attack in await stack.attacks.attacks():
            if getattr(attack, "is_over", False):
                continue
            pickban = dict(attack.pickban or {})
            if not pickban.get("resolved_pickban") or pickban.get("sabotage_resolved"):
                continue
            if attack.state not in (AttackState.DEFENDED, AttackState.MEETING):
                continue
            side = room_side_of(attack, player_id)
            if not side:
                continue
            await refresh_sabotage_dm_safe(bot, attack, side, strings)
    except Exception:
        logger.warning("kingdom: post-purchase sabotage DM refresh failed", exc_info=True)


# ---------------------------------------------------------------------------
# The sabotage phase (sabotage-ux-v1: ONE panel, edited in place)
# ---------------------------------------------------------------------------


async def sabotage_stock_line(stack: Any, attack: Any, side: str, strings: dict[str, str]) -> str:
    """The « 🗡️ Sabotage : n · 🦅 Faucon : … » line — best effort."""
    kingdom_id = str(
        attack.attacker_kingdom_id if side == "attacker" else attack.defender_kingdom_id
    )
    if not kingdom_id or stack is None:
        return ""
    sabotage = 0
    faucon = strings["sab_faucon_absent"]
    try:
        state = await stack.attacks.technology_state(kingdom_id)
        sabotage = int(state.purchases.get("sabotage", 0))
    except Exception:
        sabotage = 0
    # the Faucon rides the volière seam — degraded to « absent » until
    # the volière service exists (the stock stays honest either way).
    return strings["sab_stock_line"].format(sabotage=sabotage, faucon=faucon)


async def sabotage_open_available(stack: Any, attack: Any, side: str, strings: dict[str, str]) -> bool:
    """Whether this side can still sabotage (blue button vs grey)."""
    if stack is None:
        return True
    pickban = dict(attack.pickban or {})
    used = len([str(civ) for civ in (pickban.get(f"{side}_sabotages") or [])])
    if used >= 2:
        return False
    view = await sabotage_menu_view(stack, attack, side, strings)
    return view is not None and bool(list(view.children))


async def sabotage_dm_view(stack: Any, attack: Any, side: str, strings: dict[str, str]) -> discord.ui.View:
    """The persistent sabotage-phase view of one player's DM."""
    player_id = str(attack.attacker_lord_id if side == "attacker" else attack.defender_lord_id)
    available = await sabotage_open_available(stack, attack, side, strings)
    view = dm_view(timeout=None)
    view.add_item(
        SabotageOpenButton(str(attack.id), player_id, strings["sab_open_button"], available=available)
    )
    view.add_item(SabotagePassButton(str(attack.id), player_id, strings["sab_pass_button"]))
    return view


async def sabotage_menu_view(
    stack: Any, attack: Any, side: str, strings: dict[str, str]
) -> discord.ui.View | None:
    """The ephemeral sabotage menu of one side (None when empty).

    The 🦅 Faucon action rides the volière seam — it shows the day a
    ``stack.voliere`` service exists (faucon_sabotage consumption);
    until then only the bought 🧪 Sabotage techno acts.
    """
    kingdom_id = str(attack.attacker_kingdom_id if side == "attacker" else attack.defender_kingdom_id)
    view = discord.ui.View(timeout=300)
    bought = False
    try:
        state = await stack.attacks.technology_state(kingdom_id)
        bought = state.purchases.get("sabotage", 0) > 0
    except Exception:
        bought = False
    if bought:
        view.add_item(await sabotage_action_button(stack, attack, side, "techno", strings))
    if not list(view.children):
        return None
    return view


async def sabotage_action_button(
    stack: Any, attack: Any, side: str, action: str, strings: dict[str, str]
) -> discord.ui.Button[discord.ui.View] | None:
    """One sabotage action button (the ✅-only consumable flow)."""
    user_id = str(attack.attacker_lord_id if side == "attacker" else attack.defender_lord_id)
    button: discord.ui.Button[discord.ui.View] = discord.ui.Button(
        label=strings[f"sab_{action}"][:80], style=discord.ButtonStyle.secondary
    )

    async def _on_action(target: discord.Interaction) -> None:
        key = (str(attack.id), user_id)
        if str(getattr(target.user, "id", "")) != user_id:
            await target.response.defer()
            return
        try:
            fresh = await attack_by_id(stack, str(attack.id))
        except Exception:
            fresh = attack
        if fresh is None:
            fresh = attack
        content, menu = await sabotage_panel_content(stack, fresh, side, strings)
        civ_view = await sabotage_civ_select_view(stack, str(attack.id), side, action, strings)
        if civ_view is None:
            await target.response.edit_message(content=f"{content}\n\n{strings['sab_empty']}", view=menu)
            _arm_sabotage_panel_timer(key)
            return
        await target.response.edit_message(
            content=f"{content}\n\n{strings['sab_choose']}", view=civ_view
        )
        _arm_sabotage_panel_timer(key)

    button.callback = _on_action  # type: ignore[method-assign,assignment]
    return button


async def sabotage_panel_content(
    stack: Any, attack: Any, side: str, strings: dict[str, str]
) -> tuple[str, discord.ui.View | None]:
    """The sabotage PANEL content (X/2 récap + stock line) + menu."""
    pickban = dict(attack.pickban or {})
    used = [str(civ) for civ in (pickban.get(f"{side}_sabotages") or [])]
    lines = [strings["sab_panel_title"].format(used=len(used))]
    if used:
        lines.append(strings["sab_panel_used"].format(list=", ".join(used)))
    else:
        lines.append(strings["sab_panel_none"])
    lines.append("")
    stock = await sabotage_stock_line(stack, attack, side, strings)
    if stock:
        lines.append(stock)
    lines.append(surface_footer("panel:mod:kingdom:sabotage"))
    view = await sabotage_menu_view(stack, attack, side, strings)
    return "\n".join(lines), view


async def sabotage_civ_select_view(
    stack: Any, attack_id: str, side: str, action: str, strings: dict[str, str], *, note: str = ""
) -> discord.ui.View | None:
    """The enemy-civ select (the pick REPLACES it with the confirm row)."""
    attack = await attack_by_id(stack, attack_id)
    if attack is None:
        return None
    user_id = str(attack.attacker_lord_id if side == "attacker" else attack.defender_lord_id)
    pickban = dict(attack.pickban or {})
    enemy = "defender" if side == "attacker" else "attacker"
    already = [str(civ) for civ in (pickban.get(f"{side}_sabotages") or [])]
    options = [
        civ
        for civ in reveal_civs(f"{attack.id}:{enemy}", pickban.get(f"{enemy}_picks"))
        if civ not in already
    ][:25]
    if not options:
        return None
    view = discord.ui.View(timeout=300)
    select: discord.ui.Select[Any] = discord.ui.Select(
        placeholder=strings["sab_choose"][:100],
        options=[discord.SelectOption(label=civ[:100], value=civ) for civ in options],
        min_values=1,
        max_values=1,
    )

    async def _on_pick(target: discord.Interaction) -> None:
        if str(getattr(target.user, "id", "")) != user_id:
            await target.response.defer()
            return
        civ = str(select.values[0])
        content, _menu = await sabotage_panel_content(stack, attack, side, strings)
        body = "\n".join([content, strings["sab_pick_line"].format(action=strings[f"sab_{action}"], civ=civ)])
        if note:
            body = f"{body}\n\n{note}"
        confirm = sabotage_confirm_view(stack, attack_id, side, action, civ, strings)
        await target.response.edit_message(content=body, view=confirm)
        _arm_sabotage_panel_timer((attack_id, user_id))

    select.callback = _on_pick  # type: ignore[method-assign,assignment]
    view.add_item(select)
    return view


def sabotage_confirm_view(
    stack: Any, attack_id: str, side: str, action: str, civ: str, strings: dict[str, str]
) -> discord.ui.View:
    """The ✏️ Modifier / ✅ Valider / ❌ Annuler row of a CHOSEN civ."""
    view = discord.ui.View(timeout=300)

    async def _user_of(target: discord.Interaction) -> str:
        attack = await attack_by_id(stack, attack_id)
        user_id = (
            str(attack.attacker_lord_id if side == "attacker" else attack.defender_lord_id)
            if attack is not None
            else ""
        )
        if not user_id or str(getattr(target.user, "id", "")) != user_id:
            return ""
        return user_id

    async def _on_modify(target: discord.Interaction) -> None:
        user_id = await _user_of(target)
        if not user_id:
            await target.response.defer()
            return
        attack = await attack_by_id(stack, attack_id)
        retry = (
            await sabotage_civ_select_view(stack, attack_id, side, action, strings)
            if attack is not None
            else None
        )
        content, menu = (
            await sabotage_panel_content(stack, attack, side, strings) if attack is not None else ("", None)
        )
        if retry is None or attack is None:
            await target.response.edit_message(content=f"{content}\n\n{strings['sab_empty']}", view=menu)
            _arm_sabotage_panel_timer((attack_id, user_id), seconds=_SABOTAGE_SWEEP_SECONDS)
            return
        await target.response.edit_message(content=f"{content}\n\n{strings['sab_choose']}", view=retry)
        _arm_sabotage_panel_timer((attack_id, user_id))

    async def _on_validate(target: discord.Interaction) -> None:
        user_id = await _user_of(target)
        if not user_id:
            await target.response.defer()
            return
        await sabotage_apply_pick(target, stack, attack_id, side, action, civ, strings)

    async def _on_cancel(target: discord.Interaction) -> None:
        user_id = await _user_of(target)
        if not user_id:
            await target.response.defer()
            return
        attack = await attack_by_id(stack, attack_id)
        menu = await sabotage_menu_view(stack, attack, side, strings) if attack is not None else None
        content, _menu = (
            await sabotage_panel_content(stack, attack, side, strings) if attack is not None else ("", None)
        )
        if menu is None or not list(menu.children):
            await target.response.edit_message(
                content=f"{content}\n\n{strings['sab_no_resources']}", view=None
            )
            _arm_sabotage_panel_timer((attack_id, user_id), seconds=_SABOTAGE_SWEEP_SECONDS)
            return
        await target.response.edit_message(content=content, view=menu)
        _arm_sabotage_panel_timer((attack_id, user_id))

    modify = discord.ui.Button(label=strings["sab_modify_button"][:80], style=discord.ButtonStyle.secondary)
    validate = discord.ui.Button(label=strings["sab_validate_button"][:80], style=discord.ButtonStyle.success)
    cancel = discord.ui.Button(label=strings["sab_cancel_button"][:80], style=discord.ButtonStyle.danger)
    modify.callback = _on_modify  # type: ignore[method-assign,assignment]
    validate.callback = _on_validate  # type: ignore[method-assign,assignment]
    cancel.callback = _on_cancel  # type: ignore[method-assign,assignment]
    view.add_item(modify)
    view.add_item(validate)
    view.add_item(cancel)
    return view


async def sabotage_apply_pick(
    target: discord.Interaction,
    stack: Any,
    attack_id: str,
    side: str,
    action: str,
    civ: str,
    strings: dict[str, str],
) -> None:
    """Consume ONE sabotage charge (the ✅ Valider path)."""
    attack = await attack_by_id(stack, attack_id)
    user_id = (
        str(attack.attacker_lord_id if side == "attacker" else attack.defender_lord_id)
        if attack is not None
        else ""
    )
    key = (attack_id, user_id)
    try:
        if action == "faucon":
            # the volière seam: consumed the day the service exists.
            raise RuntimeError("le Faucon n'est pas encore branché")
        await stack.attacks.sabotage_techno(attack_id, user_id, civ)
    except Exception as exc:
        message = getattr(exc, "message", None) or str(exc)
        failed = strings["failed"].format(message=message)
        retry = (
            await sabotage_civ_select_view(stack, attack_id, side, action, strings, note=failed)
            if attack is not None
            else None
        )
        if retry is None or attack is None:
            content, menu = await sabotage_panel_content(stack, attack, side, strings)
            await target.response.edit_message(content=f"{content}\n\n{failed}", view=menu)
        else:
            content, _menu = await sabotage_panel_content(stack, attack, side, strings)
            await target.response.edit_message(
                content=f"{content}\n\n{strings['sab_choose']}\n\n{failed}", view=retry
            )
        if key[1]:
            _arm_sabotage_panel_timer(key)
        return
    try:
        fresh = await attack_by_id(stack, attack_id)
    except Exception:
        fresh = attack
    if fresh is None:
        fresh = attack
    content, menu = await sabotage_panel_content(stack, fresh, side, strings)
    used = len([str(c) for c in ((fresh.pickban or {}).get(f"{side}_sabotages") or [])])
    note = strings["sab_panel_done"].format(civ=civ, used=used)
    await refresh_sabotage_dm_safe(getattr(target, "client", None), fresh, side, strings)
    more = used < 2 and menu is not None and bool(list(menu.children))
    if more:
        body = f"{content}\n\n{note}\n\n{strings['sab_again_ask']}"
        view: discord.ui.View | None = sabotage_again_view(stack, attack_id, side, strings)
    else:
        body = f"{content}\n\n{note}"
        view = None
    try:
        await target.response.edit_message(content=body, view=view)
    except Exception:
        logger.warning("kingdom: sabotage panel edit failed", exc_info=True)
        await close_previous_ephemeral(user_id)
        await target.followup.send(body, view=view, ephemeral=True)
    if key[1]:
        _arm_sabotage_panel_timer(key, seconds=None if more else _SABOTAGE_SWEEP_SECONDS)


def sabotage_again_view(stack: Any, attack_id: str, side: str, strings: dict[str, str]) -> discord.ui.View:
    """The « one more sabotage ? » in-place confirmation."""
    view = discord.ui.View(timeout=300)

    async def _on_yes(target: discord.Interaction) -> None:
        attack = await attack_by_id(stack, attack_id)
        user_id = (
            str(attack.attacker_lord_id if side == "attacker" else attack.defender_lord_id)
            if attack is not None
            else ""
        )
        if not user_id or str(getattr(target.user, "id", "")) != user_id:
            await target.response.defer()
            return
        key = (attack_id, user_id)
        content, menu = await sabotage_panel_content(stack, attack, side, strings)
        if menu is None or not list(menu.children):
            await target.response.edit_message(
                content=f"{content}\n\n{strings['sab_empty']}", view=None
            )
            _arm_sabotage_panel_timer(key, seconds=_SABOTAGE_SWEEP_SECONDS)
            return
        await target.response.edit_message(content=f"{content}\n\n{strings['sab_choose']}", view=menu)
        _arm_sabotage_panel_timer(key)

    async def _on_no(target: discord.Interaction) -> None:
        await target.response.defer()
        attack = await attack_by_id(stack, attack_id)
        user_id = (
            str(attack.attacker_lord_id if side == "attacker" else attack.defender_lord_id)
            if attack is not None
            else str(getattr(target.user, "id", ""))
        )
        await _delete_sabotage_panel((attack_id, user_id))

    yes = discord.ui.Button(label=strings["sab_again_yes"][:80], style=discord.ButtonStyle.success)
    no = discord.ui.Button(label=strings["sab_again_no"][:80], style=discord.ButtonStyle.danger)
    yes.callback = _on_yes  # type: ignore[method-assign,assignment]
    no.callback = _on_no  # type: ignore[method-assign,assignment]
    view.add_item(yes)
    view.add_item(no)
    return view


class SabotageOpenButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:sab:open:(?P<key>[0-9a-f]{16})",
):
    """The restart-proof 🗡️ Sabotage / Faucon button of the reveal DM."""

    def __init__(self, attack_id: str, player_id: str, label: str, *, available: bool = True) -> None:
        key = ready_key(attack_id, player_id)
        # convention couleurs: BLUE while the side can still sabotage,
        # GREY + disabled once the stock is dry or the 2-cap is hit.
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"kingdom:attack:sab:open:{key}",
                style=discord.ButtonStyle.primary if available else discord.ButtonStyle.secondary,
                disabled=not available,
            )
        )
        self.attack_id = attack_id
        self.player_id = player_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> SabotageOpenButton:
        strings = strings_by_locale(str(interaction.locale or "fr"))
        stack = wiring()
        attack_id, player_id = await resolve_sabotage_key(stack, match["key"])
        available = True
        if stack is not None and attack_id and player_id:
            attack = await attack_by_id(stack, attack_id)
            side = room_side_of(attack, player_id) if attack is not None else ""
            if attack is not None and side:
                available = await sabotage_open_available(stack, attack, side, strings)
        return cls(attack_id, player_id, strings["sab_open_button"], available=available)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the ephemeral sabotage menu (or the notice)."""
        strings = strings_for(interaction)
        stack = wiring()
        if stack is None or not self.attack_id:
            await open_unique_ephemeral(interaction, strings["no_service"])
            return
        attack = await attack_by_id(stack, self.attack_id)
        if attack is None:
            await open_unique_ephemeral(interaction, strings["no_service"])
            return
        if attack.is_over or (attack.pickban or {}).get("sabotage_resolved"):
            await open_unique_ephemeral(interaction, strings["sab_over"])
            return
        pickban = dict(attack.pickban or {})
        grace_until = int(
            pickban.get("sabotage_grace_until")
            or pickban.get("default_sabotage_grace_until")
            or 0
        )
        state_ok = attack.state in (AttackState.DEFENDED, AttackState.MEETING)
        if not state_ok or (grace_until and game_now().timestamp() >= grace_until):
            await open_unique_ephemeral(interaction, strings["sab_over"])
            return
        user_id = str(interaction.user.id)
        side = room_side_of(attack, user_id)
        if side == "":
            await open_unique_ephemeral(interaction, strings["sab_not_player"])
            return
        view = await sabotage_menu_view(stack, attack, side, strings)
        if view is None or not list(view.children):
            await open_unique_ephemeral(interaction, strings["sab_no_resources"])
            return
        # sabotage-visuel-v1: a NEW click closes the player's PREVIOUS
        # panel FIRST — the panels never stack.
        key = (str(attack.id), user_id)
        await _delete_sabotage_panel(key)
        await close_previous_ephemeral(user_id)
        content, _menu = await sabotage_panel_content(stack, attack, side, strings)
        await interaction.response.send_message(content, ephemeral=True, view=view)
        _SABOTAGE_PANELS[key] = {"interaction": interaction}
        _arm_sabotage_panel_timer(key)


class SabotagePassButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:sab:pass:(?P<key>[0-9a-f]{16})",
):
    """The restart-proof ⚔️ Passer button — settles the clicking side."""

    def __init__(self, attack_id: str, player_id: str, label: str) -> None:
        key = ready_key(attack_id, player_id)
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"kingdom:attack:sab:pass:{key}",
                style=discord.ButtonStyle.success,
            )
        )
        self.attack_id = attack_id
        self.player_id = player_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> SabotagePassButton:
        strings = strings_by_locale(str(interaction.locale or "fr"))
        stack = wiring()
        attack_id, player_id = await resolve_sabotage_key(stack, match["key"])
        return cls(attack_id, player_id, strings["sab_pass_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Settle the side; the last one closes the phase."""
        strings = strings_for(interaction)
        stack = wiring()
        if stack is None or not self.attack_id:
            await open_unique_ephemeral(interaction, strings["no_service"])
            return
        try:
            fresh = await stack.attacks.sabotage_settle(self.attack_id, self.player_id)
        except Exception as exc:
            message = getattr(exc, "message", None) or str(exc)
            await open_unique_ephemeral(interaction, strings["failed"].format(message=message))
            return
        await _delete_sabotage_panel((self.attack_id, self.player_id))
        if (fresh.pickban or {}).get("sabotage_resolved"):
            await edit_pickban_dms_phase_done(interaction.client, fresh, strings)
            await open_unique_ephemeral(
                interaction, strings["sab_phase_done"].format(map=fresh.map_key)
            )
            # The early room-open rides the battle module (tranche 2c):
            # until it lands, the tick opens the meeting at T — the
            # players' DMs already say the phase is over.
            return
        await open_unique_ephemeral(interaction, strings["sab_settled"])


def strings_for(interaction: discord.Interaction) -> dict[str, str]:
    from .common import strings_for as _strings_for

    return _strings_for(interaction)


def open_unique_ephemeral(interaction: discord.Interaction, content: str, **kwargs: Any) -> Any:
    from .common import open_unique_ephemeral as _open

    return _open(interaction, content, **kwargs)


__all__ = [
    "PickBanModifyButton",
    "PickBanSelect",
    "PickBanValidateButton",
    "SabotageOpenButton",
    "SabotagePassButton",
    "announce_matchup_now_safe",
    "edit_pickban_dms_cancelled_safe",
    "edit_pickban_dms_default_reveal",
    "edit_pickban_dms_phase_done",
    "edit_pickban_dms_reveal",
    "pickban_dm_view",
    "refresh_sabotage_dm_safe",
    "refresh_sabotage_dms_after_purchase_safe",
    "resolve_pickban_key",
    "resolve_sabotage_key",
    "send_pickban_dm",
    "sweep_sabotage_dms_on_open_safe",
]
