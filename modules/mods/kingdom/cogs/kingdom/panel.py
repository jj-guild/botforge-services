"""The attack declare panel + wizard (P4.1b tranche 1).

The ported functional reference (kingdom_attack_panel.py, P4.1b):

* the pinned panel of the ``attack`` salon — the frozen-menu contract
  (Panels SDK static pin): title/help/pointer + the declare, history
  and info buttons, nothing else (Drasah 17/10: this salon keeps only
  the declare flow, every attack owns its own salon);
* the GUIDED declaration wizard (Drasah's recâblage 2026-10-14):
  (mode?) kingdom → territory → (cover?) → declaration — the attacker
  SEES the defense AI level, the patrol shields and the cadastre of
  every option before choosing;
* the attack salons (restructuration-serveur-v1 b): every declared
  attack opens its own 🗡️ salon under the declare salon, with the
  🛡️ Défendre (never disappears) and ❌ Annuler buttons — the Gaïa
  free-for-all carries 🦅 Rejoindre instead of Défendre.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord

from botforge.mods.kingdom.game_clock import game_now
from botforge.mods.kingdom.models import AttackKind, AttackState

from .common import (
    attack_salon,
    combat_failure_note,
    fmt_delay,
    fmt_paris,
    fmt_rdv_auto,
    kingdom_mention,
    kingdom_name,
    lord_kingdom_name,
    lord_name,
    lord_of,
    locale_of,
    open_unique_ephemeral,
    open_dynamic_channel_safe,
    room_channel_name,
    room_key,
    SALON_OVERWRITES,
    surface_footer,
    silent_ack,
    strings_for,
    wiring,
)
from .plan import PlanButton

logger = logging.getLogger("kingdom.attack.panel")

PANEL_VIEW_KEY = "panel:mod:kingdom:attack"

# The 12 Drasah cadastre tags (cadastre-diplomatie-v1, 15/10).
_MAP_TAG_KEYS: tuple[tuple[str, str], ...] = (
    ("eau", "💧"),
    ("hybride", "🌊"),
    ("objectif", "🎯"),
    ("nomade", "🌾"),
    ("foret", "🌲"),
    ("montagne", "⛰️"),
    ("desert", "🏜️"),
    ("marais", "🪷"),
    ("ouverte", "🌞"),
    ("chaotique", "🌀"),
    ("mur_depart", "🧱"),
    ("ferme", "🔒"),
)


# ---------------------------------------------------------------------------
# The pinned panel (the frozen-menu contract)
# ---------------------------------------------------------------------------


async def build_attack_panel(guild_id: str) -> discord.ui.LayoutView:
    """Build the declare panel's pinned layout (guild-locale strings)."""
    from .strings import strings

    strings_dict = strings(await _guild_locale(guild_id))
    from .common import surface

    container = (
        discord.ui.Container(
            discord.ui.TextDisplay(f"# {strings_dict['panel_title']}"),
            discord.ui.TextDisplay(strings_dict["panel_help"]),
            discord.ui.Separator(),
            discord.ui.TextDisplay(strings_dict["panel_pointer"]),
            discord.ui.ActionRow(
                DeclareButton(strings_dict["declare_button"]),
                HistoryButton(strings_dict["history_button"]),
                PlanButton(strings_dict["plan_button"]),
                InfoButton(strings_dict["attack_info_button"]),
            ),
            accent_colour=discord.Colour(0xA72D2D),
        )
    )
    return surface("panel:mod:kingdom:attack", container)


_PANEL_BOT: Any = None


def remember_bot(bot: Any) -> None:
    """Called by the cog's ``register`` hook — locale + heal seams."""
    global _PANEL_BOT
    _PANEL_BOT = bot


def current_bot() -> Any:
    """The bot remembered at register (None when the cog never loaded)."""
    return _PANEL_BOT


async def _guild_locale(guild_id: str) -> str:
    """The guild's effective locale (stored choice first, fr fallback)."""
    try:
        from botforge.discord.locales import stored_guild_locale

        return str(await stored_guild_locale(_PANEL_BOT, guild_id))
    except Exception:
        return "fr"


# ---------------------------------------------------------------------------
# The persistent declare panel buttons
# ---------------------------------------------------------------------------


class DeclareButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:declare",
):
    """The restart-proof declare button of the pinned attack panel."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:attack:declare",
                style=discord.ButtonStyle.primary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> DeclareButton:
        return cls(strings_for(interaction)["declare_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then open the GUIDED declaration flow."""
        from botforge.mods.kingdom.attacks import LordEngagedError, LordTavernLockedError

        strings = strings_for(interaction)
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, strings["no_service"])
            return
        lord = await lord_of(stack.kingdoms, str(interaction.user.id), interaction)
        if lord is None:
            await open_unique_ephemeral(interaction, strings["not_a_lord"])
            return
        # declare-early-lock-v1 (Drasah 31/10): an ENGAGED or tavern-
        # locked lord discovers it AT THE CLICK — no view opens at all.
        try:
            await stack.attacks._refuse_engaged(str(interaction.user.id), game_now())
            stack.attacks._refuse_tavern(lord, game_now())
        except LordEngagedError:
            await open_unique_ephemeral(interaction, strings["lord_engaged"])
            return
        except LordTavernLockedError:
            await open_unique_ephemeral(interaction, strings["lord_tavern_locked"])
            return
        own_kingdom_id = str(getattr(lord, "kingdom_id", "") or "")
        # embuscade-v1 (Drasah 27/10): with bought Embuscade cards the
        # flow opens on the MODE view first; zero cards and the mode
        # view is not offered at all.
        mode_content, mode_view = await _attack_mode_select_view(
            stack, own_kingdom_id, strings, interaction
        )
        if mode_view is not None:
            await open_unique_ephemeral(interaction, mode_content, view=mode_view)
            return
        content, view = await _kingdom_select_view(stack, own_kingdom_id, strings, interaction)
        if view is None:
            await open_unique_ephemeral(interaction, strings["no_target"])
            return
        await open_unique_ephemeral(interaction, content, view=view)


class HistoryButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:history",
):
    """The restart-proof 📜 Historique button of the declare panel."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:attack:history",
                style=discord.ButtonStyle.secondary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> HistoryButton:
        return cls(strings_for(interaction)["history_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Show the paginated history of the resolved confrontations."""
        strings = strings_for(interaction)
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, strings["no_service"])
            return
        try:
            lines = await _history_lines(stack, strings)
        except Exception:
            logger.warning("kingdom: history build failed", exc_info=True)
            lines = []
        if not lines:
            await open_unique_ephemeral(interaction, strings["history_empty"])
            return
        pages = ["\n".join(lines[start : start + 10]) for start in range(0, len(lines), 10)]
        await open_unique_ephemeral(
            interaction,
            "\n".join(
                (
                    strings["history_title"],
                    "",
                    pages[0],
                    "",
                    strings["history_page"].format(page=1, pages=len(pages)),
                    "",
                    surface_footer("panel:mod:kingdom:attack:history"),
                )
            ),
            view=_history_page_view(strings, pages, 0),
        )


class InfoButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:info",
):
    """The ⚔️ rundown sheet — one ephemeral window (attaque-ergonomie-v1)."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:attack:info",
                style=discord.ButtonStyle.secondary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> InfoButton:
        return cls(strings_for(interaction)["attack_info_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await open_unique_ephemeral(interaction, strings_for(interaction)["thread_body"])


async def _history_lines(stack: Any, strings: dict[str, str]) -> list[str]:
    """The timestamped history lines (resolved confrontations, desc)."""
    try:
        attacks = [a for a in await stack.attacks.attacks() if a.is_over]
    except Exception:
        return []
    attacks.sort(key=lambda a: str(getattr(a, "resolved_at", None) or ""), reverse=True)
    lines: list[str] = []
    for attack in attacks:
        resolved = getattr(attack, "resolved_at", None)
        date = fmt_paris(resolved) if resolved is not None else "—"
        attacker = await kingdom_name(stack.kingdoms, attack.attacker_kingdom_id)
        defender = await kingdom_name(stack.kingdoms, attack.defender_kingdom_id)
        if attack.state is AttackState.CANCELLED:
            outcome = strings["history_outcome_cancelled"]
        elif attack.winner_kingdom_id:
            winner = await kingdom_name(stack.kingdoms, attack.winner_kingdom_id)
            outcome = strings["history_outcome_win"].format(kingdom=winner)
        elif attack.state is AttackState.EXPIRED:
            outcome = strings["history_outcome_double"]
        else:
            outcome = strings["history_outcome_expired"]
        lines.append(
            strings["history_line"].format(
                date=date, map=attack.map_key, attacker=attacker, defender=defender, outcome=outcome
            )
        )
    return lines


def _history_page_view(
    strings: dict[str, str], pages: list[str], page: int
) -> discord.ui.View:
    """The ephemeral history pager view (prev/next)."""

    async def _show(target: discord.Interaction, target_page: int) -> None:
        await target.response.edit_message(
            content="\n".join(
                (
                    strings["history_title"],
                    "",
                    pages[target_page],
                    "",
                    strings["history_page"].format(page=target_page + 1, pages=len(pages)),
                    "",
                    surface_footer("panel:mod:kingdom:attack:history"),
                )
            ),
            view=_history_page_view(strings, pages, target_page),
        )

    async def _on_prev(target: discord.Interaction) -> None:
        await _show(target, max(0, page - 1))

    async def _on_next(target: discord.Interaction) -> None:
        await _show(target, min(len(pages) - 1, page + 1))

    view = discord.ui.View(timeout=600)
    if page > 0:
        prev: discord.ui.Button[discord.ui.View] = discord.ui.Button(
            label="◀", style=discord.ButtonStyle.secondary
        )
        prev.callback = _on_prev  # type: ignore[method-assign,assignment]
        view.add_item(prev)
    if page < len(pages) - 1:
        nxt: discord.ui.Button[discord.ui.View] = discord.ui.Button(
            label="▶", style=discord.ButtonStyle.secondary
        )
        nxt.callback = _on_next  # type: ignore[method-assign,assignment]
        view.add_item(nxt)
    return view


# ---------------------------------------------------------------------------
# The GUIDED declaration wizard (Drasah's recâblage, 2026-10-14)
# ---------------------------------------------------------------------------


async def _embuscade_stock(stack: Any, own_kingdom_id: str) -> int:
    """The kingdom's bought Embuscade cards (0 on any hiccup)."""
    try:
        return int(
            (await stack.attacks.technology_state(own_kingdom_id)).purchases.get("embuscade", 0)
        )
    except Exception:
        return 0


def _map_description(entry: Any) -> str:
    """One select-option description: the map's tags + cadastre bonus."""
    types = getattr(entry, "types", None)
    tags = [icon for key, icon in _MAP_TAG_KEYS if bool(getattr(types, key, False))]
    bonus = str((getattr(entry, "cadastre", None) or {}).get("bonus", "") or "")
    parts = [" ".join(tags)] if tags else []
    if bonus:
        parts.append(bonus)
    return " · ".join(parts)[:100]


def _kingdom_option(kingdom: Any, level: int, count: int, strings: dict[str, str]) -> discord.SelectOption:
    """One step-1 option: the kingdom, its defence AI level and map count."""
    return discord.SelectOption(
        label=str(kingdom.name)[:100],
        value=str(kingdom.id)[:100],
        description=strings["ai_level_desc"].format(level=level, count=count)[:100],
    )


async def _kingdom_step_options(
    stack: Any, own_kingdom_id: str, strings: dict[str, str], now: Any, base: int
) -> tuple[list[discord.SelectOption], list[str]]:
    """Classify every kingdom as attackable or patrol-protected (step 1)."""
    from botforge.mods.kingdom.attacks import (
        DEFENSE_AI_BASE,
        patrouille_active_at,
        patrouille_reinforced,
        patrouille_slots,
    )

    territories = await stack.territories.territories()
    options: list[discord.SelectOption] = []
    protected: list[str] = []
    for kingdom in await stack.kingdoms.kingdoms():
        if str(kingdom.id) == own_kingdom_id:
            continue
        owned = [t for t in territories if t.owner_kingdom_id == kingdom.id]
        if not owned:
            continue
        if getattr(kingdom, "is_gaia", False):
            options.append(_kingdom_option(kingdom, base, len(owned), strings))
            continue
        state = await stack.attacks.technology_state(str(kingdom.id))
        if patrouille_active_at(state, now, base_level=base):
            slots = patrouille_slots(state)
            span = 3 if patrouille_reinforced(state, base) else 2
            end = (slots[-1] + span) % 24 if slots else 0
            protected.append(
                strings["patrol_kingdom"].format(name=str(kingdom.name), end=f"{end:02d}")
            )
            continue
        level = await stack.attacks.defense_ai_level(str(kingdom.id))
        options.append(_kingdom_option(kingdom, level, len(owned), strings))
    return options, protected


async def _kingdom_select_view(
    stack: Any,
    own_kingdom_id: str,
    strings: dict[str, str],
    origin: Any = None,
    mode: str = "classic",
) -> tuple[str, discord.ui.View | None]:
    """Step 1 — the attackable kingdoms (patrol-shielded ones stay visible)."""
    from botforge.mods.kingdom.attacks import DEFENSE_AI_BASE

    now = game_now()
    base = DEFENSE_AI_BASE
    options, protected = await _kingdom_step_options(stack, own_kingdom_id, strings, now, base)
    if not options:
        return "", None
    select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id="kingdom:attack:choose:kingdom",
        placeholder=str(strings["choose_kingdom"])[:100],
        options=options[:25],
    )

    async def on_choose(target: discord.Interaction[Any]) -> None:
        values = getattr(target, "data", None) or {}
        chosen = [str(v) for v in values.get("values", [])]
        if not chosen:
            return
        content, view = await _territory_select_view(
            stack, own_kingdom_id, chosen[0], strings, origin, mode=mode
        )
        if view is None:
            await target.response.edit_message(content=strings["no_target"], view=None)
            return
        await target.response.edit_message(content=content, view=view)

    select.callback = on_choose  # type: ignore[method-assign, assignment]
    view = discord.ui.View(timeout=600)
    view.add_item(select)
    # shirar-v1 (Drasah 06/11): the wizard wears EXPLICIT step markers.
    lines = [str(strings["declare_step_one"]), "", str(strings["choose_kingdom"])]
    if mode == "embuscade":
        lines.append(
            str(strings["embuscade_armed_line"]).format(
                count=await _embuscade_stock(stack, own_kingdom_id),
            )
        )
        lines.append(str(strings["embuscade_warning_line"]))
    if protected:
        lines.append(str(strings["protected_line"]).format(kingdoms=" · ".join(protected)))
    lines.append(str(strings["traquenard_hint"]))
    lines.append(surface_footer("panel:mod:kingdom:attack:declare"))
    return "\n".join(lines), view


async def _territory_select_view(
    stack: Any,
    own_kingdom_id: str,
    kingdom_id: str,
    strings: dict[str, str],
    origin: Any = None,
    mode: str = "classic",
) -> tuple[str, discord.ui.View | None]:
    """Step 2 — the territories of the chosen kingdom (tags + cadastre)."""
    kingdom = next(
        (k for k in await stack.kingdoms.kingdoms() if str(k.id) == kingdom_id), None
    )
    if kingdom is None:
        return "", None
    catalog = {
        str(getattr(entry, "key", "")): entry for entry in getattr(stack.config, "maps", None) or ()
    }
    owned = [t for t in await stack.territories.territories() if t.owner_kingdom_id == kingdom_id]
    if not owned:
        return "", None
    options = [
        discord.SelectOption(
            label=str(
                getattr(catalog.get(str(t.map_key), None), "display_name", None) or t.map_key
            )[:100],
            value=str(t.map_key)[:100],
            description=_map_description(catalog.get(str(t.map_key), None)),
        )
        for t in owned
    ][:25]
    embuscade_mode = mode == "embuscade"
    select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id=(
            "kingdom:attack:embuscade:territory"
            if embuscade_mode
            else "kingdom:attack:choose:territory"
        ),
        placeholder=str(strings["embuscade_choose" if embuscade_mode else "choose_territory"])[:100],
        options=options,
    )

    async def on_choose(target: discord.Interaction[Any]) -> None:
        values = getattr(target, "data", None) or {}
        chosen = [str(v) for v in values.get("values", [])]
        if not chosen:
            return
        # battle-ai-rdv-v1: the map is chosen — the selector ephemeral
        # dies INSTANTLY (no stale wizard left behind).
        if origin is not None:
            try:
                await origin.delete_original_response()
            except Exception:
                logger.debug("kingdom: selector ephemeral delete failed", exc_info=True)
        if embuscade_mode:
            await _declare_embuscade_attack(stack, target, strings, chosen[0])
            return
        await _open_cover_step(
            stack,
            target,
            strings,
            chosen[0],
            own_kingdom_id,
            kingdom_id,
            is_gaia=bool(getattr(kingdom, "is_gaia", False)),
        )

    select.callback = on_choose  # type: ignore[method-assign, assignment]
    view = discord.ui.View(timeout=600)
    view.add_item(select)
    delay_minutes = _declare_delay_minutes(stack, kingdom)
    if embuscade_mode:
        delay_minutes = int(stack.attacks.embuscade_delay_minutes)
    lines = [
        str(strings["declare_step_two"]),
        "",
        str(strings["declare_step_chosen"]).format(kingdom=f"**{kingdom.name}**"),
        str(strings["embuscade_choose"])
        if embuscade_mode
        else str(strings["choose_territory"]).format(kingdom=f"**{kingdom.name}**"),
    ]
    if delay_minutes:
        lines.append(str(strings["itinerary_line"]).format(minutes=delay_minutes))
    lines.append(str(strings["traquenard_hint"]))
    lines.append(surface_footer("panel:mod:kingdom:attack:declare"))
    return "\n".join(lines), view


def _declare_delay_minutes(stack: Any, kingdom: Any) -> int:
    """The LIVE declaration delay of this target (battle-ai-rdv-v1)."""
    try:
        if bool(getattr(kingdom, "is_gaia", False)):
            return int(stack.attacks.gaia_attack_delay_minutes)
        return int(stack.attacks.player_attack_delay_minutes)
    except Exception:
        return 0


async def _attack_mode_select_view(
    stack: Any,
    own_kingdom_id: str,
    strings: dict[str, str],
    origin: Any = None,
) -> tuple[str, discord.ui.View | None]:
    """Step 0 — the itinerary choice (embuscade-v1, Drasah 27/10)."""
    if await _embuscade_stock(stack, own_kingdom_id) <= 0:
        return "", None
    classic: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["mode_classic_button"]).format(
            delay=_fmt(stack.attacks.player_attack_delay_minutes)
        )[:80],
        style=discord.ButtonStyle.primary,
        custom_id="kingdom:attack:mode:classic",
    )

    async def on_classic(target: discord.Interaction[Any]) -> None:
        content, view = await _kingdom_select_view(
            stack, own_kingdom_id, strings, origin, mode="classic"
        )
        if view is None:
            await target.response.edit_message(content=strings["no_target"], view=None)
            return
        await target.response.edit_message(content=content, view=view)

    classic.callback = on_classic  # type: ignore[method-assign, assignment]
    embuscade: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["mode_embuscade_button"]).format(
            delay=_fmt(stack.attacks.embuscade_delay_minutes)
        )[:80],
        style=discord.ButtonStyle.danger,
        custom_id="kingdom:attack:mode:embuscade",
    )

    async def on_embuscade(target: discord.Interaction[Any]) -> None:
        content, view = await _kingdom_select_view(
            stack, own_kingdom_id, strings, origin, mode="embuscade"
        )
        if view is None:
            await target.response.edit_message(content=strings["no_target"], view=None)
            return
        await target.response.edit_message(content=content, view=view)

    embuscade.callback = on_embuscade  # type: ignore[method-assign, assignment]
    view = discord.ui.View(timeout=600)
    view.add_item(classic)
    view.add_item(embuscade)
    lines = [str(strings["mode_choose"]), str(strings["traquenard_hint"])]
    lines.append(surface_footer("panel:mod:kingdom:attack:declare"))
    return "\n".join(lines), view


def _fmt(minutes: int) -> str:
    return fmt_delay(minutes)


async def _declare_player_attack(
    stack: Any,
    target: discord.Interaction[Any],
    strings: dict[str, str],
    map_key: str,
    cover_lord_id: str | None,
) -> None:
    """Declare a player attack — no modal anymore (live beta 18/10)."""
    # hygiene-ephemere-v1 (Drasah 30/10): the wizard that led here
    # DIES with the declaration — the window is never reusable.
    await target.response.defer()
    try:
        await target.delete_original_response()
    except Exception:
        logger.debug("kingdom: declare wizard delete skipped", exc_info=True)
    try:
        attack = await stack.attacks.declare_attack(
            str(target.user.id), map_key, "", cover_lord_id=cover_lord_id
        )
    except Exception as exc:
        await target.followup.send(combat_failure_note(exc, strings), ephemeral=True)
        return
    try:
        delay_minutes = int((attack.expires_at - attack.declared_at).total_seconds() // 60)
    except Exception:
        delay_minutes = 0
    await target.followup.send(
        strings["itinerary_note"].format(
            map=attack.map_key,
            delay=delay_minutes,
            time=fmt_rdv_auto(attack.expires_at, locale_of(target)),
        ),
        ephemeral=True,
    )
    await _open_attack_salon_safe(target.guild, stack, strings, attack, locale_of(target))


async def _declare_embuscade_attack(
    stack: Any,
    target: discord.Interaction[Any],
    strings: dict[str, str],
    map_key: str,
) -> None:
    """Declare the exceptional Embuscade at the mode flow's step 2."""
    await target.response.defer()
    try:
        await target.delete_original_response()
    except Exception:
        logger.debug("kingdom: declare wizard delete skipped", exc_info=True)
    try:
        attack = await stack.attacks.declare_embuscade(str(target.user.id), map_key, "")
    except Exception as exc:
        await target.followup.send(combat_failure_note(exc, strings), ephemeral=True)
        return
    try:
        delay_minutes = int((attack.expires_at - attack.declared_at).total_seconds() // 60)
    except Exception:
        delay_minutes = 0
    await target.followup.send(
        strings["embuscade_note"].format(
            map=attack.map_key,
            delay=delay_minutes,
            time=fmt_rdv_auto(attack.expires_at, locale_of(target)),
        ),
        ephemeral=True,
    )
    await _open_attack_salon_safe(target.guild, stack, strings, attack, locale_of(target))


async def _cover_candidates(stack: Any, defender_kingdom_id: str, except_user_id: str) -> list[Any]:
    """The bluff candidates (bluff-externe-v1, Drasah 29/10).

    EVERY active lord of the season is eligible — the attacker's own
    kingdom (D77) AND the foreign kingdoms — EXCEPT the lords of the
    ATTACKED kingdom and the attacker himself.
    """
    try:
        lords = await stack.kingdoms.lords()
    except Exception:
        logger.warning("kingdom: cover lord scan failed", exc_info=True)
        return []
    return [
        lord
        for lord in lords
        if getattr(lord, "kingdom_id", None)
        and not getattr(lord, "left", False)
        and str(lord.kingdom_id) != str(defender_kingdom_id)
        and str(lord.id) != str(except_user_id)
    ]


async def _open_cover_step(
    stack: Any,
    interaction: discord.Interaction,
    strings: dict[str, str],
    map_key: str,
    own_kingdom_id: str,
    defender_kingdom_id: str,
    *,
    is_gaia: bool = False,
) -> None:
    """Step 3 — the counter-espionage question (skipped without a charge)."""
    if is_gaia:
        await _declare_player_attack(stack, interaction, strings, map_key, None)
        return
    state = await stack.attacks.technology_state(own_kingdom_id)
    has_stock = state.purchases.get("contre_espionnage", 0) > 0
    candidates = await _cover_candidates(stack, defender_kingdom_id, str(interaction.user.id))
    if not has_stock or not candidates:
        await _declare_player_attack(stack, interaction, strings, map_key, None)
        return
    view = discord.ui.View(timeout=600)

    async def open_lobby(cover_lord_id: str | None, target: discord.Interaction[Any]) -> None:
        await _declare_player_attack(stack, target, strings, map_key, cover_lord_id)

    async def _cover_options(target: discord.Interaction[Any]) -> list[discord.SelectOption[Any]]:
        lords = await _cover_candidates(stack, defender_kingdom_id, str(target.user.id))
        kingdom_names: dict[str, str] = {}
        try:
            kingdom_names = {
                str(k.id): str(k.name) for k in await stack.kingdoms.kingdoms()
            }
        except Exception:
            kingdom_names = {}
        entries = [
            (
                kingdom_names.get(str(getattr(lord, "kingdom_id", "")), ""),
                str(getattr(lord, "display_name", lord.id)),
                lord,
            )
            for lord in lords
        ]
        entries.sort(key=lambda entry: (entry[0].lower(), entry[1].lower()))
        return [
            discord.SelectOption(
                label=entry[1][:100],
                value=str(entry[2].id)[:100],
                description=entry[0][:100],
            )
            for entry in entries
        ][:25]

    async def on_yes(target: discord.Interaction[Any]) -> None:
        options = await _cover_options(target)
        if not options:
            await open_lobby(None, target)
            return
        select: discord.ui.Select[Any] = discord.ui.Select(
            custom_id="kingdom:attack:choose:cover",
            placeholder=str(strings["choose_cover"])[:100],
            options=options,
        )

        async def on_cover(chosen: discord.Interaction[Any]) -> None:
            values = getattr(chosen, "data", None) or {}
            picked = [str(v) for v in values.get("values", [])]
            await open_lobby(picked[0] if picked else None, chosen)

        select.callback = on_cover  # type: ignore[method-assign, assignment]
        cover_view = discord.ui.View(timeout=600)
        cover_view.add_item(select)
        cover_content = "\n".join(
            (str(strings["choose_cover"]), surface_footer("panel:mod:kingdom:attack:declare"))
        )
        await target.response.edit_message(content=cover_content, view=cover_view)

    async def on_no(target: discord.Interaction[Any]) -> None:
        await open_lobby(None, target)

    yes: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["cover_yes_button"])[:80],
        style=discord.ButtonStyle.primary,
        custom_id="kingdom:attack:cover:yes",
    )
    no: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["cover_no_button"])[:80],
        style=discord.ButtonStyle.secondary,
        custom_id="kingdom:attack:cover:no",
    )
    yes.callback = on_yes  # type: ignore[method-assign, assignment]
    no.callback = on_no  # type: ignore[method-assign, assignment]
    view.add_item(yes)
    view.add_item(no)
    await interaction.response.send_message(
        content="\n".join(
            (str(strings["cover_question"]), surface_footer("panel:mod:kingdom:attack:declare"))
        ),
        view=view,
        ephemeral=True,
    )


# ---------------------------------------------------------------------------
# The attack salons (restructuration-serveur-v1 b)
# ---------------------------------------------------------------------------


def _attack_salon_view(strings: dict[str, str], attack: Any) -> discord.ui.View:
    """The base-message view of an attack's own salon.

    Player attack: 🛡️ Défendre (NEVER disappears) + ❌ Annuler (declarant
    only). Gaïa free-for-all: 🦅 Rejoindre + ❌ Annuler.
    """
    view = discord.ui.View(timeout=None)
    if getattr(attack, "kind", None) is AttackKind.GAIA:
        view.add_item(JoinButton(str(attack.id), strings["gaia_join_button"]))
    else:
        view.add_item(DefendButton(str(attack.id), strings["defend_button"]))
    view.add_item(CancelButton(str(attack.id), strings["cancel_attack_button"]))
    return view


async def _open_attack_salon_safe(
    guild: Any, stack: Any, strings: dict[str, str], attack: Any, locale: str = "fr"
) -> None:
    """Open the attack's OWN salon and pin its base message."""
    declare = await _declare_channel(guild)
    if declare is None:
        return
    shown_id = attack.cover_lord_id or attack.attacker_lord_id
    shown_name = await lord_name(stack.kingdoms, shown_id)
    defender_name = await kingdom_name(stack.kingdoms, attack.defender_kingdom_id)
    # bluff-externe-v1: the illusion wears the COVER lord's KINGDOM too.
    if attack.cover_lord_id:
        attacker_kingdom_name = await lord_kingdom_name(stack.kingdoms, attack.cover_lord_id) or "—"
    else:
        attacker_kingdom_name = await kingdom_name(stack.kingdoms, attack.attacker_kingdom_id)
    name = room_channel_name(guild, "🗡️", shown_name, defender_name)
    position = int(getattr(declare, "position", 0) or 0) + 1
    channel = await open_dynamic_channel_safe(
        guild,
        name,
        category=getattr(declare, "category", None),
        position=position,
        overwrites=SALON_OVERWRITES,
    )
    if channel is None:
        return
    await _record_safe(stack, "record_attack_channel", attack, int(channel.id))
    content = str(strings["announce_v1"]).format(
        attacker=f"<@{shown_id}>",
        kingdom=kingdom_mention(guild, attacker_kingdom_name),
        defender=kingdom_mention(guild, defender_name),
        time=fmt_rdv_auto(attack.expires_at, locale),
    )
    if getattr(attack, "traquenard", False):
        content += str(strings["announce_v1_traquenard"])
    if getattr(attack, "kind", None) is AttackKind.GAIA:
        gaia_max = int(getattr(stack.attacks, "gaia_max_participants", 7) or 7)
        content += str(strings["announce_v1_gaia"]).format(max=gaia_max)
    content += "\n" + surface_footer("panel:mod:kingdom:attack:salon")
    try:
        message = await channel.send(content, view=_attack_salon_view(strings, attack))
        await _record_safe(stack, "record_attack_base_message", attack, int(message.id))
    except Exception:
        logger.warning("kingdom: attack salon base message failed", exc_info=True)


async def _record_safe(stack: Any, method: str, attack: Any, value: int) -> None:
    """Store a salon/message ref through the attacks service (best effort)."""
    try:
        await getattr(stack.attacks, method)(str(attack.id), int(value))
    except Exception:
        logger.warning("kingdom: attack ref not stored (%s)", method, exc_info=True)


async def _declare_channel(guild: Any) -> Any:
    """The guild's « Déclarer une attaque » salon via the stored resolution."""
    if guild is None:
        return None
    channel_id = await _stored_channel_id(guild)
    if channel_id:
        channel = getattr(guild, "get_channel", lambda _id: None)(int(channel_id))
        if channel is not None:
            return channel
    # fallback: the salon's declared name (the provisioning owns the ids)
    from .common import slug

    wanted = slug("déclarer une attaque")
    return next(
        (c for c in getattr(guild, "text_channels", []) if slug(getattr(c, "name", "")) == wanted),
        None,
    )


async def _stored_channel_id(guild: Any) -> str:
    """The provisioning's stored resolution of the attack channel."""
    from botforge.discord.ui.panels_provisioning import stored_channel_id

    try:
        return str(await stored_channel_id(str(guild.id), "mod/kingdom", "attack") or "")
    except Exception:
        return ""


async def resolve_attack_id_by_key(key: str) -> str:
    """Resolve a salon-button digest back to an attack id (Check 73)."""
    stack = wiring()
    if stack is None:
        return ""
    try:
        for attack in await stack.attacks.attacks():
            if room_key(str(attack.id)) == key:
                return str(attack.id)
    except Exception:
        logger.warning("kingdom: salon key resolution failed", exc_info=True)
    return ""


# ---------------------------------------------------------------------------
# The salon buttons: defend / join / cancel
# ---------------------------------------------------------------------------


class DefendButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:defend:(?P<key>[0-9a-f]{16})",
):
    """The restart-proof defend button of one waiting attack."""

    def __init__(self, attack_id: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"kingdom:attack:defend:{room_key(attack_id)}",
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
    ) -> DefendButton:
        return cls(
            await resolve_attack_id_by_key(match["key"]),
            strings_for(interaction)["defend_button"],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Take the defense — the button NEVER disappears (effet de surprise)."""
        from botforge.mods.kingdom.attacks import LordEngagedError, LordTavernLockedError

        strings = strings_for(interaction)
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, strings["no_service"])
            return
        try:
            attack = next(
                item
                for item in await stack.attacks.attacks()
                if str(item.id) == self.attack_id
            )
        except Exception:
            await open_unique_ephemeral(interaction, strings["gaia_gone"])
            return
        if attack.is_over:
            await open_unique_ephemeral(interaction, strings["gaia_gone"])
            return
        lord = await lord_of(stack.kingdoms, str(interaction.user.id), interaction)
        # shirar-v1: the ATTACKER's camp clicks NOTHING.
        if lord is not None and str(getattr(lord, "kingdom_id", "") or "") == str(
            attack.attacker_kingdom_id
        ):
            await silent_ack(interaction)
            return
        # defend-probe-leak: ANY lord outside the defending kingdom gets
        # the SAME generic refusal — probing must never reveal a defense.
        if lord is None or str(getattr(lord, "kingdom_id", "") or "") != str(
            attack.defender_kingdom_id
        ):
            await open_unique_ephemeral(interaction, strings["defend_wrong_kingdom"])
            return
        if getattr(attack, "state", None) is not AttackState.DECLARED and not getattr(
            attack, "ai_defender", False
        ):
            await open_unique_ephemeral(interaction, strings["defend_already"])
            return
        if getattr(attack, "state", None) is not AttackState.DECLARED:
            await open_unique_ephemeral(interaction, strings["gaia_gone"])
            return
        # declare-early-lock-v1: the early-guard fires AT THE CLICK.
        try:
            await stack.attacks._refuse_engaged(str(interaction.user.id), game_now())
            stack.attacks._refuse_tavern(lord, game_now())
        except LordEngagedError:
            await open_unique_ephemeral(interaction, strings["lord_engaged"])
            return
        except LordTavernLockedError:
            await open_unique_ephemeral(interaction, strings["lord_tavern_locked"])
            return
        await interaction.response.defer(ephemeral=True)
        try:
            attack = await stack.attacks.respond_defense(self.attack_id, str(interaction.user.id))
        except Exception as exc:
            await interaction.followup.send(combat_failure_note(exc, strings), ephemeral=True)
            return
        await interaction.followup.send(
            strings["defense_done"].format(
                map=attack.map_key, time=fmt_paris(attack.expires_at)
            ),
            ephemeral=True,
        )
        # effet de surprise: no public sign — the base message stays.


class JoinButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:join:(?P<key>[0-9a-f]{16})",
):
    """The restart-proof join button of one open Gaïa battle."""

    def __init__(self, attack_id: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"kingdom:attack:join:{room_key(attack_id)}",
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
    ) -> JoinButton:
        return cls(
            await resolve_attack_id_by_key(match["key"]),
            strings_for(interaction)["gaia_join_button"],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Join the open Gaïa battle of this button's attack."""
        from .common import attack_salon_send_safe

        strings = strings_for(interaction)
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, strings["no_service"])
            return
        battle = next(
            (
                a
                for a in await stack.attacks.attacks()
                if str(a.id) == self.attack_id and not a.is_over
            ),
            None,
        )
        if (
            battle is None
            or getattr(battle, "kind", None) is not AttackKind.GAIA
            or battle.state.value != "declared"
        ):
            await open_unique_ephemeral(interaction, strings["gaia_gone"])
            return
        await interaction.response.defer(ephemeral=True)
        try:
            attack = await stack.attacks.declare_gaia_attack(
                str(interaction.user.id),
                battle.map_key,
                str(battle.lobby_url or ""),
            )
        except Exception as exc:
            message = getattr(exc, "message", None) or str(exc)
            await interaction.followup.send(
                strings["failed"].format(message=message), ephemeral=True
            )
            return
        await interaction.followup.send(
            strings["gaia_join_note"].format(
                map=attack.map_key,
                count=len(attack.participants),
                time=fmt_paris(attack.expires_at),
            ),
            ephemeral=True,
        )
        await attack_salon_send_safe(
            interaction.guild,
            attack,
            strings["gaia_join_announce"].format(
                lord=interaction.user.display_name,
                map=attack.map_key,
                count=len(attack.participants),
            ),
        )


class CancelButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:cancel:(?P<key>[0-9a-f]{16})",
):
    """The restart-proof ❌ Annuler button of an attack salon.

    The DECLARANT alone, inside the cancellation window — budgets
    refunded, and the salon is purged right away.
    """

    def __init__(self, attack_id: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"kingdom:attack:cancel:{room_key(attack_id)}",
                style=discord.ButtonStyle.danger,
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
    ) -> CancelButton:
        return cls(
            await resolve_attack_id_by_key(match["key"]),
            strings_for(interaction)["cancel_attack_button"],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Cancel the attack, purge its salon, confirm (ephemeral)."""
        from .common import close_previous_ephemeral

        strings = strings_for(interaction)
        stack = wiring()
        if stack is None or not self.attack_id:
            await open_unique_ephemeral(interaction, strings["no_service"])
            return
        # shirar-v1: the DECLARANT alone can cancel — every other
        # player clicks NOTHING (silent ack).
        try:
            attack = next(
                item
                for item in await stack.attacks.attacks()
                if str(item.id) == self.attack_id
            )
            if str(interaction.user.id) != str(attack.attacker_lord_id):
                await silent_ack(interaction)
                return
        except Exception:
            pass  # unknown attack — fall through to the service refusal
        await interaction.response.defer(ephemeral=True)
        try:
            attack = await stack.attacks.cancel_attack(self.attack_id, str(interaction.user.id))
        except Exception as exc:
            message = getattr(exc, "message", None) or str(exc)
            await interaction.followup.send(
                strings["failed"].format(message=message), ephemeral=True
            )
            return
        salon = attack_salon(interaction.guild, attack)
        if salon is not None:
            try:
                await salon.delete()
            except Exception:
                logger.warning("kingdom: attack salon purge failed", exc_info=True)
        try:
            await stack.attacks.mark_attack_salon_cleaned(str(attack.id))
        except Exception:
            logger.warning("kingdom: attack salon flag failed", exc_info=True)
        # beta-retours-v1 point 8: the cancelled attack leaves NO stale
        # window behind — the declarant's ephemeral view dies with it.
        await close_previous_ephemeral(str(interaction.user.id))
        note = (
            strings["cancel_attack_embuscade_done"]
            if getattr(attack, "embuscade", False)
            else strings["cancel_attack_done"]
        )
        if getattr(attack, "cover_lord_id", None):
            note = f"{note}\n{strings['cancel_attack_cover_refunded']}"
        await interaction.followup.send(note, ephemeral=True)


__all__ = [
    "CancelButton",
    "DeclareButton",
    "DefendButton",
    "HistoryButton",
    "InfoButton",
    "JoinButton",
    "PANEL_VIEW_KEY",
    "build_attack_panel",
]
