"""The admin decisions layer (decisions-admin-v1, Drasah 25/11).

Drasah's live finding (24-25/11): a litige auto-ouvert leaves the
player stuck and the admin with NOTHING but a console command with an
ID to type (« c'est horrible ce fonctionnement »). The decision
tranchée: ONE inbox, ONE view, ONE ledger.

The surface rules (Affaires 15-18):
- the inbox is the drawer ⚖️ of the Mod Kingdom Admin Console — ONE new
  entry, ZERO duplication (the SAS, the régie des royaumes, the
  Machine à temps and the cycle settings stay where they live);
- the inbox queues BOTH dispute roads (auto-opened and contradictory)
  together — the admin never hunts one road in DMs and types the
  other on the console;
- EVERY decision (arbitrage, double forfait, ANNULLATION) demands a
  MANDATORY reason — the public trace is the anti-abus;
- the reason + the admin's name are announced in the discussion salon
  of every CONCERNED kingdom (an empty kingdom list = global decision
  = every kingdom);
- every decision lands in the ledger (``kingdoms_decisions``, never
  season-wiped) — the B2 consultation surface (Kingdom Realm panel)
  will read THIS ledger, nothing else.

#395/#396: the inbox, the action window and the announcement are ONE
template each, instantiated with parameters; #369: the decision types
are DATA, a season-2 kind never rewrites this layer.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import discord

from .common import (
    _bot_admins,
    attack_by_id,
    kingdom_name,
    locale_of,
    open_unique_ephemeral,
    room_key,
    strings_by_locale,
    surface,
    wiring,
)

logger = logging.getLogger("kingdom.decisions")

_DECISION_OPEN_TEMPLATE = r"kingdom:decision:open:(?P<key>[0-9a-z-]+)"
_DECISION_ACT_TEMPLATE = r"kingdom:decision:act:(?P<choice>[a-z]+):(?P<key>[0-9a-z-]+)"
DECISION_ACTION_VIEW_ID = "panel:mod:kingdom:admin:decisions:act"

# The four choices of the action window — attacker/defender/both ride
# the EXISTING resolve_dispute seams; "cancel" is the annulation
# (decisions-admin-v1). One dict = the whole surface, a fifth choice
# is a new row here, never a new code path.
DECISION_CHOICES: tuple[tuple[str, str], ...] = (
    ("attacker", "dispute_win_attacker"),
    ("defender", "dispute_win_defender"),
    ("both", "dispute_double"),
    ("cancel", "dispute_cancel_button"),
)


def dispute_kind(attack: Any) -> str:
    """Which road opened the dispute (the inbox's context line)."""
    return "auto" if (attack.score or {}).get("auto_dispute") else "declarations"


def _decision_summary(
    strings: dict[str, str],
    choice: str,
    map_key: str,
    winner_name: str,
) -> str:
    """One locale-neutral-enough ledger line (data, rendered back)."""
    if choice == "cancel":
        return str(strings["decision_summary_cancel"]).format(map=map_key)
    if choice == "both":
        return str(strings["decision_summary_both"]).format(map=map_key)
    return str(strings["decision_summary_arbitrage"]).format(map=map_key, winner=winner_name)


async def apply_admin_decision(
    stack: Any,
    attack: Any,
    choice: str,
    reason: str,
    admin_id: str,
    locale: str,
) -> tuple[Any, dict[str, Any]]:
    """Terminal path of EVERY admin decision: resolve, record, ready.

    Called by the reason modal's submit (the drawer's windows and the
    DM dispute panel alike) — one path, the reason is MANDATORY.
    """
    strings = strings_by_locale(locale)
    cleaned = str(reason or "").strip()
    if not cleaned:
        raise ValueError(strings["decision_reason_required"])
    if choice == "cancel":
        attack = await stack.attacks.admin_cancel_attack(str(attack.id))
    else:
        attack = await stack.attacks.resolve_dispute(str(attack.id), choice)
    winner_name = ""
    if choice in ("attacker", "defender"):
        winner_name = await kingdom_name(stack.kingdoms, str(attack.winner_kingdom_id or ""))
    decision = await stack.decisions.record_decision(
        type="annulation" if choice in ("cancel", "both") else "arbitrage",
        kingdom_ids=[str(attack.attacker_kingdom_id), str(attack.defender_kingdom_id)],
        summary=_decision_summary(strings, choice, str(attack.map_key), winner_name),
        reason=cleaned,
        admin_id=str(admin_id),
        attack_id=str(attack.id),
        map_key=str(attack.map_key),
        winner_kingdom_id=str(attack.winner_kingdom_id or ""),
    )
    logger.info(
        "kingdom: admin decision recorded on %s (choice %s) — decision %s",
        attack.map_key,
        choice,
        decision.get("_id"),
    )
    return attack, decision


async def announce_decision_safe(bot: Any, stack: Any, decision: dict[str, Any], locale: str) -> None:
    """Post the decision in every CONCERNED kingdom's discussion salon.

    One template + params (#396 annonce-ready): the announcement is
    data-driven, a future surface re-renders it untouched. Idempotent
    through the ledger's ``announced`` flag — the tick replays safely.
    """
    if stack is None or decision.get("announced"):
        return
    strings = strings_by_locale(locale)
    attack = await attack_by_id(stack, str(decision.get("attack_id") or ""))
    map_key = str(decision.get("map_key") or (getattr(attack, "map_key", "") if attack else ""))
    game = ""
    if attack is not None:
        game = str((attack.score or {}).get("game_id") or "")
    kingdom_ids = [str(k) for k in (decision.get("kingdom_ids") or [])]
    winner_name = ""
    if decision.get("winner_kingdom_id"):
        winner_name = await kingdom_name(stack.kingdoms, str(decision["winner_kingdom_id"]))
    if str(decision.get("type")) == "annulation":
        content = str(strings["decision_announce_cancel"]).format(
            map=map_key, game=game or "—", admin=decision.get("admin_id"),
            reason=decision.get("reason"),
        )
    else:
        content = str(strings["decision_announce_arbitrage"]).format(
            map=map_key, game=game or "—", winner=winner_name or "—",
            admin=decision.get("admin_id"), reason=decision.get("reason"),
        )
    guild = _guild_of(bot)
    if guild is None:
        return
    try:
        realms = list(await stack.realms.realms())
    except Exception:  # a read, never a crash
        logger.warning("kingdom: the decision announce realms read failed", exc_info=True)
        return
    posted = await _sweep_decision_salon(guild, realms, kingdom_ids, content)
    try:
        await stack.decisions.mark_announced(str(decision.get("_id") or ""))
    except Exception:  # the announce replays on the tick
        logger.warning("kingdom: the decision announce flag failed", exc_info=True)
    if posted:
        logger.info("kingdom: admin decision announced in %s salon(s)", posted)


async def _sweep_decision_salon(
    guild: Any, realms: list[Any], kingdom_ids: list[str], content: str
) -> int:
    """Post the decision's text in every concerned realm's salon."""
    from .realm_content import _realm_channels

    posted = 0
    for realm in realms:
        engagement = dict(getattr(realm, "engagement", None) or {})
        kingdom_id = str(engagement.get("kingdom_id") or "")
        if not kingdom_id:
            continue  # out of season — no discussion salon to warn
        if kingdom_ids and kingdom_id not in kingdom_ids:
            continue
        channels = await _realm_channels(guild, realm)
        salon = channels.get("discussions")
        if salon is None:
            continue
        try:
            await salon.send(content)
            posted += 1
        except Exception:  # one salon never kills the sweep
            logger.warning("kingdom: the decision announce failed on %s", realm.slug, exc_info=True)
    return posted


def _guild_of(bot: Any) -> Any:
    """Return the single-guild habitat of the mod (best effort, never a crash)."""
    guilds = getattr(bot, "guilds", None) or []
    for guild in guilds:
        return guild
    return None


class DecisionReasonModal(discord.ui.Modal):
    """The MANDATORY reason of an admin decision (anti-abus, public).

    Same modal for EVERY choice and EVERY surface (the drawer's action
    window and the DM dispute panel): one template, parameters only.
    """

    def __init__(self, attack_id: str, choice: str, locale: str) -> None:
        strings = strings_by_locale(locale)
        super().__init__(title=str(strings["decision_reason_modal_title"])[:45], timeout=300)
        self.attack_id = str(attack_id)
        self.choice = str(choice)
        self.strings = strings
        self.reason_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label=str(strings["decision_reason_label"])[:45],
            placeholder=str(strings["decision_reason_placeholder"])[:100],
            required=True,
            max_length=400,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Apply the decision — resolve, record, announce, confirm.

        drawer-build-v1's lesson (Check 136, « n'a pas répondu à
        temps ») : la soumission est acquittée IMMÉDIATEMENT —
        l'arbitrage, le ledger et l'annonce aux salons prennent leur
        temps (et le rate-limit de Discord met parfois 9 s à
        laisser passer un envoi), le chrono de 3 s appartient à
        l'ACK, la note vit dans le followup.
        """
        strings = self.strings
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:  # an already-acked submit
            logger.debug("kingdom: the decision modal defer skipped", exc_info=True)

        async def _note(content: str) -> None:
            await interaction.followup.send(content, ephemeral=True)

        stack = wiring()
        if stack is None:
            await _note(strings["no_service"])
            return
        reason = str(self.reason_input.value or "").strip()
        if not reason:
            await _note(strings["decision_reason_required"])
            return
        attack = await attack_by_id(stack, self.attack_id)
        if attack is None or getattr(attack, "is_over", True):
            await _note(strings["no_service"])
            return
        try:
            attack, decision = await apply_admin_decision(
                stack, attack, self.choice, reason, str(interaction.user.id),
                locale_of(interaction),
            )
        except Exception as exc:  # a live surface never crashes
            message = getattr(exc, "message", None) or str(exc)
            await _note(strings["failed"].format(message=message))
            return
        try:
            await announce_decision_safe(interaction.client, stack, decision, locale_of(interaction))
        except Exception:  # the announce replays on the tick
            logger.warning("kingdom: the decision announce failed", exc_info=True)
        if self.choice == "cancel":
            note = str(strings["decision_applied_cancel"]).format(map=str(attack.map_key))
        elif self.choice == "both":
            note = str(strings["dispute_forfeit"]).format(map=str(attack.map_key))
        else:
            kingdom = await kingdom_name(stack.kingdoms, str(attack.winner_kingdom_id or ""))
            note = str(strings["dispute_applied"]).format(kingdom=kingdom, map=str(attack.map_key))
        await _note(note)


class DecisionActButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=_DECISION_ACT_TEMPLATE,
):
    """One restart-proof choice button of the action window."""

    def __init__(self, choice: str, key: str, label: str, style: discord.ButtonStyle) -> None:
        style = discord.ButtonStyle.danger if choice in ("both", "cancel") else style
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"kingdom:decision:act:{choice}:{key}"[:100],
                style=style,
            )
        )
        self.choice = choice
        self.key = key

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> DecisionActButton:
        """Rebuild from the custom id — the choice walks the label table."""
        strings = strings_by_locale(locale_of(interaction))
        choice = match["choice"]
        label_key = dict(DECISION_CHOICES).get(choice, "")
        label = str(strings.get(label_key, choice))
        return cls(choice, match["key"], label, discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the admin, then demand the reason (the mandatory modal)."""
        from .battle import resolve_room_key

        strings = strings_by_locale(locale_of(interaction))
        if str(getattr(interaction.user, "id", "")) not in (_bot_admins(interaction) or ()):
            await interaction.response.send_message(strings["dispute_not_admin"], ephemeral=True)
            return
        stack = wiring()
        attack_id = await resolve_room_key(stack, self.key) if stack is not None else ""
        if not attack_id:
            await interaction.response.send_message(strings["no_service"], ephemeral=True)
            return
        await interaction.response.send_modal(
            DecisionReasonModal(attack_id, self.choice, locale_of(interaction))
        )


class DecisionOpenButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=_DECISION_OPEN_TEMPLATE,
):
    """One inbox line's « decide » opener — the per-attack action window."""

    def __init__(self, key: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"kingdom:decision:open:{key}"[:100],
                style=discord.ButtonStyle.primary,
            )
        )
        self.key = key

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> DecisionOpenButton:
        """Rebuild from the custom id — the label walks the strings."""
        strings = strings_by_locale(locale_of(interaction))
        return cls(match["key"], str(strings["decision_decide_button"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Re-read the attack fresh, then open the action window.

        Fast-ack d'abord (Check 136) : la relecture de la clé + le
        refetch prennent leur temps sous rate-limit, la fenêtre vit
        dans le followup, les refus deviennent des notes déclarées.
        """
        from .battle import resolve_room_key

        strings = strings_by_locale(locale_of(interaction))
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:  # an already-acked click
            logger.debug("kingdom: the decision open defer skipped", exc_info=True)
        if str(getattr(interaction.user, "id", "")) not in (_bot_admins(interaction) or ()):
            await open_unique_ephemeral(interaction, content=strings["dispute_not_admin"])
            return
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, content=strings["no_service"])
            return
        attack_id = await resolve_room_key(stack, self.key)
        attack = await attack_by_id(stack, attack_id) if attack_id else None
        if attack is None or getattr(attack, "is_over", True):
            await open_unique_ephemeral(interaction, content=strings["no_service"])
            return
        view = decision_action_surface(strings, attack)
        await open_unique_ephemeral(interaction, view=view)


def decision_action_surface(strings: dict[str, str], attack: Any) -> Any:
    """Build the per-attack action window — context + the four choices.

    One template (the declared surface id), parameters only: the same
    window serves the inbox and any future notification surface.
    """
    key = room_key(str(attack.id))
    kind = dispute_kind(attack)
    kind_line = str(strings["decision_kind_auto" if kind == "auto" else "decision_kind_declarations"])
    header = str(strings["decision_action_header"]).format(map=str(attack.map_key))
    items: list[Any] = [
        discord.ui.TextDisplay(f"# {strings['decision_action_title']}"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(header),
        discord.ui.TextDisplay(kind_line),
    ]
    row: Any = discord.ui.ActionRow()
    for choice, label_key in DECISION_CHOICES:
        row.add_item(
            DecisionActButton(choice, key, str(strings[label_key]), discord.ButtonStyle.secondary).item
        )
    items.append(row)
    return surface(DECISION_ACTION_VIEW_ID, discord.ui.Container(*items))
