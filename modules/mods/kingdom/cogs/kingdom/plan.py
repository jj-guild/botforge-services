"""The attack planning wizard (P4.1b tranche 2d).

The ported functional reference (kingdom_attack_panel.py, D77):

* the 📅 « Planifier une attaque » button of the declare panel — the
  same early-guards as a manual declaration (engaged, taverne);
* the wizard — step 1 the choice-1 territory (every enemy player
  territory, Gaïa and sacred excluded), then the RDV time through
  THREE dropdowns « Jour / Heure / Minute » (planification-attaque-
  v2: « libre, c'est pas ouf » — the free-text modal is gone), then
  the confirm step with the OPTIONAL choices 2 and 3;
* the récap DM — the full plan (3 choices, the active one tagged, the
  RDV and the auto-declare hours, the budget disclaimer) with the
  persistent ❌ cancel button (free — nothing consumed);
* the tick side (``run_plan_events_safe``) lives in ``phases.py`` —
  the executed/switched/broken/cancelled events edit the récap DM in
  place, and an executed plan opens its attack salon exactly like a
  manual declaration.

The plan wizard views are ephemeral closures (timeout 600 s) exactly
like the reference — only the cancel button is a persistent
DynamicItem, restart-safe through its 16-hex plan key.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import discord

from botforge.mods.kingdom.game_clock import game_now

from .common import (
    dm_user_safe,
    fmt_paris,
    lord_of,
    locale_of,
    open_unique_ephemeral,
    room_key,
    strings_by_locale,
    wiring,
)

logger = logging.getLogger("kingdom.attack")

_PARIS = ZoneInfo("Europe/Paris")
_PLAN_CANCEL = "kingdom:attack:plan:cancel:{key}"


def strings_of(interaction: discord.Interaction) -> dict[str, str]:
    return strings_by_locale(locale_of(interaction))


def map_label(stack: Any, map_key: str) -> str:
    """The display name of a map key (fallback: the raw key)."""
    catalog = {
        str(getattr(entry, "key", "")): entry for entry in getattr(stack.config, "maps", None) or ()
    }
    return str(getattr(catalog.get(str(map_key), None), "display_name", None) or map_key)


async def _enemy_territory_options(stack: Any, own_kingdom_id: str, strings: dict[str, str]) -> list[Any]:
    """The plan choice options: every enemy player territory (cap 25)."""
    from .panel import _map_description

    if stack is None:
        return []
    gaia_ids = {str(k.id) for k in await stack.kingdoms.kingdoms() if getattr(k, "is_gaia", False)}
    catalog = {
        str(getattr(entry, "key", "")): entry for entry in getattr(stack.config, "maps", None) or ()
    }
    options: list[discord.SelectOption] = []
    for territory in await stack.territories.territories():
        owner = str(territory.owner_kingdom_id)
        if owner == str(own_kingdom_id) or owner in gaia_ids or getattr(territory, "sacred", False):
            continue
        options.append(
            discord.SelectOption(
                label=map_label(stack, str(territory.map_key))[:100],
                value=str(territory.map_key)[:100],
                description=_map_description(catalog.get(str(territory.map_key), None)),
            )
        )
        if len(options) >= 25:
            break
    return options


def _meeting_from_selections(day_offset: int, hour: int, minute: int, now: datetime) -> datetime:
    """Compose the RDV datetime from the wizard dropdowns (Europe/Paris).

    The 24h golden rule makes « aujourd'hui » and « demain » the only
    useful days — ``day_offset`` is 0 or 1. Refuses the past and
    anything beyond 24h (the service re-checks — early feedback).
    """
    now_local = now.astimezone(_PARIS)
    day = (now_local + timedelta(days=day_offset)).date()
    meeting_at = datetime(day.year, day.month, day.day, hour, minute, tzinfo=_PARIS)
    if meeting_at <= now_local:
        raise ValueError("the meeting must be in the future")
    if meeting_at - now_local > timedelta(hours=24):
        raise ValueError("the meeting must be within 24h")
    return meeting_at


async def plan_declare_at(stack: Any, plan: Any) -> Any:
    """The plan's auto-declare moment (the engine's seam, best effort)."""
    try:
        return await stack.attacks._plan_declare_at(plan)  # type: ignore[attr-defined]
    except Exception:
        return plan.meeting_at


async def recap_with_declare(stack: Any, plan: Any, strings: dict[str, str]) -> str:
    """The récap with the TRUE auto-declare hour (async seam resolved)."""
    declare_at = await plan_declare_at(stack, plan)
    if not isinstance(declare_at, datetime):
        declare_at = plan.meeting_at
    lines = [strings["plan_dm_header"].format(map=map_label(stack, str(plan.active_choice or "")))]
    for index, choice in enumerate(plan.choices, start=1):
        lines.append(
            strings["plan_choices_line"].format(
                n=index,
                map=map_label(stack, str(choice)),
                active=strings["plan_active_tag"] if index - 1 == int(plan.active_index) else "",
            )
        )
    lines.append(
        strings["plan_dm_time"].format(
            time=fmt_paris(plan.meeting_at), declare_time=fmt_paris(declare_at)
        )
    )
    lines.append(strings["plan_dm_budget"])
    lines.append(strings["plan_disclaimer"])
    return "\n".join(lines)


async def _confirm_step(
    stack: Any,
    interaction: discord.Interaction,
    strings: dict[str, str],
    own_kingdom_id: str,
    choice1: str,
    meeting_at: datetime,
) -> None:
    """The planning confirm step — récap + the optional choices 2 and 3."""
    state: dict[str, Any] = {"choice2": None, "choice3": None}
    options = await _enemy_territory_options(stack, own_kingdom_id, strings)
    view = discord.ui.View(timeout=600)

    def _extras() -> list[str]:
        extras = [choice1]
        if state.get("choice2"):
            extras.append(str(state["choice2"]))
        if state.get("choice3"):
            extras.append(str(state["choice3"]))
        return extras

    def _remaining_options() -> list[discord.SelectOption]:
        taken = set(_extras())
        return [option for option in options if str(option.value) not in taken][:25]

    async def _confirm(target: discord.Interaction) -> None:
        from botforge.mods.kingdom.attacks import LordEngagedError, LordTavernLockedError

        if stack is None:
            await target.followup.send(strings["plan_no_service"], ephemeral=True)
            return
        try:
            plan = await stack.attacks.plan_attack(str(target.user.id), _extras(), meeting_at)
        except Exception as exc:
            message = (
                strings["lord_tavern_locked"]
                if isinstance(exc, LordTavernLockedError)
                else (
                    strings["lord_engaged"]
                    if isinstance(exc, LordEngagedError)
                    else strings["plan_failed"].format(
                        message=getattr(exc, "message", None) or str(exc)
                    )
                )
            )
            await target.followup.send(message, ephemeral=True)
            return
        content = await recap_with_declare(stack, plan, strings)
        cancel_view = discord.ui.View(timeout=None)
        cancel_view.add_item(PlanCancelButton(plan.id, strings["plan_cancel_button"]))
        dm = await dm_user_safe(target.client, str(target.user.id), content, cancel_view)
        if dm is not None:
            try:
                await stack.attacks.record_plan_dm(
                    str(plan.id), int(getattr(dm, "channel_id", 0) or 0), int(getattr(dm, "id", 0) or 0)
                )
            except Exception:
                logger.warning("kingdom: plan DM ref not stored", exc_info=True)
            await target.followup.send(strings["plan_created_note"], ephemeral=True)
        else:
            await target.followup.send(strings["plan_no_dm"], ephemeral=True)
        try:
            await target.response.edit_message(content=strings["plan_created_note"], view=None)
        except Exception:
            logger.debug("kingdom: plan confirm ephemeral edit failed", exc_info=True)

    confirm = discord.ui.Button(
        label=str(strings["plan_confirm_button"])[:80],
        custom_id="kingdom:attack:plan:confirm",
        style=discord.ButtonStyle.success,
    )
    confirm.callback = _confirm  # type: ignore[method-assign,assignment]
    view.add_item(confirm)
    for slot, key in (("choice2", "plan_choice2_placeholder"), ("choice3", "plan_choice3_placeholder")):
        select: discord.ui.Select[Any] = discord.ui.Select(
            custom_id=f"kingdom:attack:plan:{slot}",
            placeholder=str(strings[key])[:100],
            options=_remaining_options(),
            min_values=1,
            max_values=1,
        )

        async def on_pick(target: discord.Interaction, slot: str = slot) -> None:  # noqa: B023
            values = getattr(target, "data", None) or {}
            picked = [str(v) for v in values.get("values", [])]
            if picked:
                state[slot] = picked[0]
            # Redraw both selects without the taken choices.
            for item in view.children:
                if getattr(item, "custom_id", "") == "kingdom:attack:plan:choice2":
                    item.options = _remaining_options()  # type: ignore[union-attr]
                elif getattr(item, "custom_id", "") == "kingdom:attack:plan:choice3":
                    rest = [
                        o for o in _remaining_options() if str(o.value) != str(state.get("choice2"))
                    ][:25]
                    item.options = rest  # type: ignore[union-attr]
            await target.response.edit_message(content=_confirm_content(), view=view)

        select.callback = on_pick  # type: ignore[method-assign,assignment]
        view.add_item(select)

    def _confirm_content() -> str:
        lines = [
            strings["plan_confirm_title"].format(
                map=map_label(stack, choice1), time=fmt_paris(meeting_at)
            ),
            strings["plan_dm_budget"],
            strings["plan_disclaimer"],
        ]
        return "\n".join(lines)

    try:
        await interaction.response.edit_message(content=_confirm_content(), view=view)
    except Exception:
        logger.debug("kingdom: plan confirm step edit failed", exc_info=True)


async def _time_step(
    stack: Any,
    interaction: discord.Interaction,
    strings: dict[str, str],
    own_kingdom_id: str,
    choice1: str,
) -> None:
    """The RDV-hour step of the planning wizard — dropdowns + Valider."""
    state: dict[str, int] = {"day": 0, "hour": 20, "minute": 0}
    now_local = game_now().astimezone(_PARIS)
    today = now_local.date()
    day_select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id="kingdom:attack:plan:time-day",
        placeholder=str(strings["plan_time_day_label"])[:100],
        options=[
            discord.SelectOption(
                label=str(strings["plan_time_day_today"]).format(date=today.strftime("%d/%m"))[:100],
                value="0",
            ),
            discord.SelectOption(
                label=str(strings["plan_time_day_tomorrow"]).format(
                    date=(today + timedelta(days=1)).strftime("%d/%m")
                )[:100],
                value="1",
            ),
        ],
        min_values=1,
        max_values=1,
    )
    hour_select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id="kingdom:attack:plan:time-hour",
        placeholder=str(strings["plan_time_hour_label"])[:100],
        options=[
            discord.SelectOption(label=f"{value:02d}h", value=str(value)) for value in range(24)
        ],
        min_values=1,
        max_values=1,
    )
    minute_select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id="kingdom:attack:plan:time-minute",
        placeholder=str(strings["plan_time_minute_label"])[:100],
        options=[
            discord.SelectOption(label=f"{value:02d}", value=str(value))
            for value in (0, 15, 30, 45)
        ],
        min_values=1,
        max_values=1,
    )

    def _hint() -> str:
        return "\n".join([str(strings["plan_wizard_title"]), strings["plan_time_hint"]])

    view = discord.ui.View(timeout=600)

    async def _pick(target: discord.Interaction, key: str) -> None:
        values = getattr(target, "data", None) or {}
        picked = [str(v) for v in values.get("values", [])]
        if picked:
            state[key] = int(picked[0])
        await target.response.edit_message(content=_hint(), view=view)

    for select, key in ((day_select, "day"), (hour_select, "hour"), (minute_select, "minute")):

        async def on_pick(target: discord.Interaction, key: str = key) -> None:  # noqa: B023
            await _pick(target, key)

        select.callback = on_pick  # type: ignore[method-assign,assignment]
        view.add_item(select)

    validate = discord.ui.Button(
        label=str(strings["plan_time_validate_button"])[:80],
        custom_id="kingdom:attack:plan:time-validate",
        style=discord.ButtonStyle.success,
    )

    async def _validate(target: discord.Interaction) -> None:
        try:
            meeting_at = _meeting_from_selections(
                state["day"], state["hour"], state["minute"], game_now()
            )
        except ValueError:
            await target.response.edit_message(content=strings["plan_time_invalid"], view=view)
            return
        await _confirm_step(stack, target, strings, own_kingdom_id, choice1, meeting_at)

    validate.callback = _validate  # type: ignore[method-assign,assignment]
    view.add_item(validate)
    await interaction.response.edit_message(content=_hint(), view=view)


class PlanButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:plan$",
):
    """The 📅 « Planifier une attaque » button of the declare panel."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:attack:plan",
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
    ) -> PlanButton:
        return cls(strings_of(interaction)["plan_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Step 1 of the planning wizard — the choice-1 territory select."""
        from botforge.mods.kingdom.attacks import LordEngagedError, LordTavernLockedError

        strings = strings_of(interaction)
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, strings["plan_no_service"])
            return
        lord = await lord_of(stack.kingdoms, str(interaction.user.id), interaction)
        if lord is None or getattr(lord, "kingdom_id", None) is None:
            await open_unique_ephemeral(interaction, strings["not_a_lord"])
            return
        try:
            await stack.attacks._refuse_engaged(str(interaction.user.id), game_now())
            stack.attacks._refuse_tavern(lord, game_now())
        except LordEngagedError:
            await open_unique_ephemeral(interaction, strings["lord_engaged"])
            return
        except LordTavernLockedError:
            await open_unique_ephemeral(interaction, strings["lord_tavern_locked"])
            return
        options = await _enemy_territory_options(stack, str(lord.kingdom_id), strings)
        if not options:
            await open_unique_ephemeral(interaction, strings["no_target"])
            return
        select: discord.ui.Select[Any] = discord.ui.Select(
            custom_id="kingdom:attack:plan:choice1",
            placeholder=str(strings["choose_territory"]).split("—")[0].strip()[:100],
            options=options,
            min_values=1,
            max_values=1,
        )

        async def on_pick(target: discord.Interaction) -> None:
            values = getattr(target, "data", None) or {}
            picked = [str(v) for v in values.get("values", [])]
            if not picked:
                return
            await _time_step(stack, target, strings, str(lord.kingdom_id), picked[0])

        select.callback = on_pick  # type: ignore[method-assign,assignment]
        view = discord.ui.View(timeout=600)
        view.add_item(select)
        lines = [str(strings["plan_wizard_title"]), strings["plan_disclaimer"]]
        await open_unique_ephemeral(interaction, "\n".join(lines), view=view)


class PlanCancelButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:attack:plan:cancel:(?P<key>[0-9a-f]{16})",
):
    """The ❌ cancel button of one live plan (free — nothing consumed)."""

    def __init__(self, plan_id: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=_PLAN_CANCEL.format(key=room_key(plan_id)),
                style=discord.ButtonStyle.danger,
            )
        )
        self.plan_id = plan_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> PlanCancelButton:
        return cls(
            await resolve_plan_key(wiring(), match["key"]),
            strings_of(interaction)["plan_cancel_button"],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Cancel the plan and edit the DM in place."""
        strings = strings_of(interaction)
        stack = wiring()
        if stack is None:
            await interaction.response.send_message(strings["plan_no_service"], ephemeral=True)
            return
        try:
            await stack.attacks.cancel_plan(self.plan_id, str(interaction.user.id))
        except Exception:
            await interaction.response.send_message(
                strings["plan_failed"].format(message="plannification introuvable"), ephemeral=True
            )
            return
        try:
            await interaction.response.edit_message(
                content=strings["plan_cancelled_ephemeral"], view=None
            )
        except Exception:
            await interaction.followup.send(strings["plan_cancelled_ephemeral"], ephemeral=True)


async def resolve_plan_key(stack: Any, key: str) -> str:
    """Resolve the hashed plan key back to its id (restart-proof)."""
    if stack is None:
        return ""
    try:
        for plan in await stack.attacks.plans():
            if room_key(str(plan.id)) == str(key):
                return str(plan.id)
    except Exception:
        logger.debug("kingdom: plan key resolution failed", exc_info=True)
    return ""


async def update_plan_dm_safe(bot: Any, stack: Any, plan: Any, content: str) -> bool:
    """Edit the plan's récap DM in place (best effort, False when lost)."""
    from .common import edit_dm_message_safe

    channel_id = int(getattr(plan, "dm_channel_id", 0) or 0)
    message_id = int(getattr(plan, "dm_message_id", 0) or 0)
    if not channel_id or not message_id:
        return False
    channel = getattr(bot, "get_channel", lambda _id: None)(channel_id)
    if channel is None or not hasattr(channel, "get_partial_message"):
        return False
    try:
        message = channel.get_partial_message(message_id)
        await message.edit(content=content, view=None)
        return True
    except Exception:
        logger.debug("kingdom: plan DM edit failed", exc_info=True)
        return False


__all__ = [
    "PlanButton",
    "PlanCancelButton",
    "map_label",
    "plan_declare_at",
    "recap_with_declare",
    "resolve_plan_key",
    "update_plan_dm_safe",
]
