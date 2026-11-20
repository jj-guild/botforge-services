"""The mod's ops-console actions (#339, tranche console).

The platform's console is extensible (``register_console_action``):
a mod registers its ops — a stable key, the DynamicItem class
re-registered at every startup, a builder taking the ``disabled``
flag, one description line for the home's intro. The same three
gates (test guild, never prod, bot admin) guard every registered
action's click — the mod's callbacks ride the platform guard and
never re-implement it.

Kingdom's ops (the reference's console surface, ported onto the
registry):

- **relancer** — archive + wipe + a fresh season (``service.launch``);
- **réinitialiser** — archive + wipe only (``service.reset``);
- **horloge** — the game clock jump (machine-temps-v2): a modal reads
  a duration (« 90m », « 2h », « 3d »), the offset persists on the
  season doc and the process cache moves at once.

The destructive ops wear a confirm card — one ephemeral window, the
confirm inline, never a stacked surface.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord

from .common import open_unique_ephemeral, strings_for, wiring

logger = logging.getLogger("kingdom.console")


async def _console_guard(interaction: discord.Interaction) -> bool:
    """Ride the platform's console gate (never re-implemented).

    The platform guard answers the refusal itself; the fallback keeps
    the mod alive if the private helper is ever renamed (a graceful
    degrade, never a bypass: the fallback re-checks the same three
    conditions through the public seams).
    """
    try:
        from botforge.discord.console import _guard

        return await _guard(interaction)
    except Exception:
        from botforge.discord.console_guilds import is_test_guild
        from botforge.discord.guards import require_admin

        if not is_test_guild(interaction.guild_id):
            await interaction.response.send_message(
                "This guild is not on the console allowlist.", ephemeral=True
            )
            return False
        admins = getattr(getattr(interaction.client, "status_service", None), "bot_admins", ())
        roles = getattr(interaction.client, "roles_service", None)
        return await require_admin(
            interaction,
            tuple(admins or ()),
            roles,
            denied_message="The console is reserved for bot admins.",
        )


def _confirm_view(strings: dict[str, str], action_key: str) -> discord.ui.LayoutView:
    """The confirm card of a destructive console op (inline, one window)."""
    from .common import surface

    yes: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["console_confirm_button"])[:80],
        custom_id=f"kingdom:console:{action_key}yes",
        style=discord.ButtonStyle.danger,
    )
    no: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["console_cancel_button"])[:80],
        custom_id=f"kingdom:console:{action_key}no",
        style=discord.ButtonStyle.secondary,
    )

    async def on_yes(target: discord.Interaction) -> None:
        await target.response.defer()
        stack = wiring()
        if stack is None:
            await target.followup.send(strings["plan_no_service"], ephemeral=True)
            return
        try:
            if action_key == "relaunch":
                await stack.kingdoms.launch()
                note = str(strings["console_relaunch_done"])
            else:
                await stack.kingdoms.reset()
                note = str(strings["console_reset_done"])
        except Exception as exc:  # noqa: BLE001 — the console reports, never raises
            logger.warning("kingdom: console %s failed", action_key, exc_info=True)
            from .common import service_failure_note

            note = service_failure_note(strings, "console_error", exc)
        try:
            await target.followup.send(note, ephemeral=True)
        except Exception:  # noqa: S110 — a vanished window is fine
            pass

    async def on_no(target: discord.Interaction) -> None:
        await open_unique_ephemeral(target, strings["console_cancelled"])

    yes.callback = on_yes
    no.callback = on_no
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.TextDisplay(str(strings[f"console_{action_key}_confirm"])),
        accent_colour=discord.Colour(0xED4245),
    )
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row.add_item(yes)
    row.add_item(no)
    container.add_item(row)
    return surface("panel:mod:kingdom:admin:console:confirm", container)


class KingdomRelaunchButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:console:relaunch$",
):
    """The console's « 🔁 Relancer la saison » — archive + wipe + fresh season."""

    def __init__(self, label: str, disabled: bool = False) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:console:relaunch",
                style=discord.ButtonStyle.primary,
                disabled=disabled,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomRelaunchButton:
        return cls(strings_for(interaction)["console_relaunch_label"])

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await _console_guard(interaction):
            return
        strings = strings_for(interaction)
        await open_unique_ephemeral(
            interaction, view=_confirm_view(strings, "relaunch")
        )


class KingdomResetButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:console:reset$",
):
    """The console's « 🧹 Réinitialiser » — archive + wipe only."""

    def __init__(self, label: str, disabled: bool = False) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:console:reset",
                style=discord.ButtonStyle.secondary,
                disabled=disabled,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomResetButton:
        return cls(strings_for(interaction)["console_reset_label"])

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await _console_guard(interaction):
            return
        strings = strings_for(interaction)
        await open_unique_ephemeral(
            interaction, view=_confirm_view(strings, "reset")
        )


class _ClockOffsetModal(discord.ui.Modal):
    """The free-jump modal (« 90m », « 2h », « 1d2h30m »)."""

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(title=str(strings["console_clock_modal_title"])[:45])
        self._strings = strings
        # discord.py 2.7: a TextInput rides a discord.ui.Label (the label
        # property is deprecated)
        self.duration = discord.ui.TextInput(
            placeholder="90m",
            min_length=1,
            max_length=20,
            required=True,
            custom_id="kingdom:console:clock:duration",
        )
        self.add_item(
            discord.ui.Label(
                text=str(strings["console_clock_duration_label"])[:45],
                component=self.duration,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from botforge.mods.kingdom.game_clock import format_offset, parse_duration

        await interaction.response.defer()
        try:
            seconds = parse_duration(str(self.duration.value))
        except ValueError as exc:
            await interaction.followup.send(
                str(self._strings["console_clock_bad"]).format(str(exc)[:120]),
                ephemeral=True,
            )
            return
        stack = wiring()
        if stack is None:
            await interaction.followup.send(
                self._strings["plan_no_service"], ephemeral=True
            )
            return
        try:
            season = await stack.kingdoms.set_clock_offset(seconds)
        except Exception as exc:  # noqa: BLE001 — the console reports, never raises
            logger.warning("kingdom: console clock set failed", exc_info=True)
            await interaction.followup.send(
                str(self._strings["console_error"]).format(str(exc)[:150]),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            str(self._strings["console_clock_done"]).format(
                format_offset(int(getattr(season, "clock_offset", seconds) or 0))
            ),
            ephemeral=True,
        )


class KingdomClockButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:console:clock$",
):
    """The console's « ⏩ Horloge » — the game-clock jump modal."""

    def __init__(self, label: str, disabled: bool = False) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdom:console:clock",
                style=discord.ButtonStyle.success,
                disabled=disabled,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomClockButton:
        return cls(strings_for(interaction)["console_clock_label"])

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await _console_guard(interaction):
            return
        from botforge.mods.kingdom.game_clock import format_offset, game_offset_seconds

        strings = strings_for(interaction)
        await interaction.response.send_modal(
            _ClockOffsetModal(strings)
        )
        logger.info(
            "kingdom: console clock modal opened (current offset %s)",
            format_offset(game_offset_seconds()),
        )


def _debug_service(stack: Any) -> Any:
    """The admin-debug-v1 toolkit (ported from the reference branch)."""
    from botforge.mods.kingdom.admin_debug import build_debug_service

    return build_debug_service(stack)


class _DebugOpMixin:
    """One admin-debug op ported onto the mod console (no slash subgroup).

    A plain mixin: each concrete button subclasses it WITH its own
    DynamicItem template (the base cannot carry one).
    """

    op_key = ""
    label_key = ""

    def __init__(self, label: str, disabled: bool = False) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"kingdom:console:{self.op_key}",
                style=discord.ButtonStyle.secondary,
                disabled=disabled,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "_DebugOpMixin":
        return cls(strings_for(interaction)[cls.label_key])

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await _console_guard(interaction):
            return
        strings = strings_for(interaction)
        await interaction.response.defer(ephemeral=True)
        from .common import service_failure_note, wiring

        stack = wiring()
        if stack is None:
            note = str(strings["console_service_not_ready"])
        else:
            try:
                note = await self._run(stack, strings)
            except Exception as exc:  # the console reports, never raises
                logger.warning("kingdom: debug %s failed", self.op_key, exc_info=True)
                note = service_failure_note(strings, "console_error", exc)
        await interaction.followup.send(note, ephemeral=True)

    async def _run(self, stack: Any, strings: dict[str, str]) -> str:
        raise NotImplementedError


class DebugStatusButton(_DebugOpMixin, discord.ui.DynamicItem[discord.ui.Button[Any]], template=r"kingdom:console:debug-status$"):
    """🐞 Statut debug — the live attacks + cooldowns summary."""

    op_key = "debug-status"
    label_key = "console_debug_status_label"

    async def _run(self, stack: Any, strings: dict[str, str]) -> str:
        debug = _debug_service(stack)
        attacks = await debug.list_attacks()
        cooldowns = await debug.view_cooldowns(None)
        n_cooldowns = len(cooldowns) if isinstance(cooldowns, (list, dict)) else cooldowns
        return str(strings["console_debug_done"]).format(
            f"attacks={len(attacks)} cooldowns={n_cooldowns}"
        )


class BypassOnButton(_DebugOpMixin, discord.ui.DynamicItem[discord.ui.Button[Any]], template=r"kingdom:console:bypass-on$"):
    """🐞 Bypass ON — the admin bypass flag (real buttons run past the gates)."""

    op_key = "bypass-on"
    label_key = "console_bypass_on_label"

    async def _run(self, stack: Any, strings: dict[str, str]) -> str:
        from botforge.mods.kingdom.admin_debug import set_admin_bypass

        set_admin_bypass(True, source="console")
        return str(strings["console_debug_done"]).format("bypass=on")


class BypassOffButton(_DebugOpMixin, discord.ui.DynamicItem[discord.ui.Button[Any]], template=r"kingdom:console:bypass-off$"):
    """🐞 Bypass OFF — restore the gate checks."""

    op_key = "bypass-off"
    label_key = "console_bypass_off_label"

    async def _run(self, stack: Any, strings: dict[str, str]) -> str:
        from botforge.mods.kingdom.admin_debug import set_admin_bypass

        set_admin_bypass(False, source="console")
        return str(strings["console_debug_done"]).format("bypass=off")


class SkipEventButton(_DebugOpMixin, discord.ui.DynamicItem[discord.ui.Button[Any]], template=r"kingdom:console:skip-event$"):
    """⏭️ Événement suivant — fast-forward the event loop to the next event."""

    op_key = "skip-event"
    label_key = "console_skip_event_label"

    async def _run(self, stack: Any, strings: dict[str, str]) -> str:
        result = await _debug_service(stack).skip_to_next_event()
        return str(strings["console_debug_done"]).format(str(result)[:150])


def kingdom_console_actions() -> tuple:
    """The mod's three console ops, scoped to the MOD's console (mod="kingdom").

    Returned as data so tests can pin the scoping without importing the
    platform console (R6: nothing outside cogs/ imports botforge.discord).
    The button labels are the i18n keys' texts (no "(kingdom)" tag — the
    ops already live in the mod's OWN console); the initial render uses
    the English strings, every click re-renders in the invoker's locale
    (from_custom_id).
    """
    from botforge.discord.console import ConsoleAction

    from .strings import strings as _strings

    en = _strings("en")
    return (
        ConsoleAction(
            key="kingdom-relaunch",
            item_cls=KingdomRelaunchButton,
            build=lambda disabled: KingdomRelaunchButton(
                en["console_relaunch_label"], disabled
            ),
            description=en["console_relaunch_label"],
            mod="kingdom",
        ),
        ConsoleAction(
            key="kingdom-reset",
            item_cls=KingdomResetButton,
            build=lambda disabled: KingdomResetButton(
                en["console_reset_label"], disabled
            ),
            description=en["console_reset_label"],
            mod="kingdom",
        ),
        ConsoleAction(
            key="kingdom-clock",
            item_cls=KingdomClockButton,
            build=lambda disabled: KingdomClockButton(
                en["console_clock_label"], disabled
            ),
            description=en["console_clock_label"],
            mod="kingdom",
        ),
        ConsoleAction(
            key="kingdom-debug-status",
            item_cls=DebugStatusButton,
            build=lambda disabled: DebugStatusButton(
                en["console_debug_status_label"], disabled
            ),
            description=en["console_debug_status_label"],
            mod="kingdom",
        ),
        ConsoleAction(
            key="kingdom-bypass-on",
            item_cls=BypassOnButton,
            build=lambda disabled: BypassOnButton(
                en["console_bypass_on_label"], disabled
            ),
            description=en["console_bypass_on_label"],
            mod="kingdom",
        ),
        ConsoleAction(
            key="kingdom-bypass-off",
            item_cls=BypassOffButton,
            build=lambda disabled: BypassOffButton(
                en["console_bypass_off_label"], disabled
            ),
            description=en["console_bypass_off_label"],
            mod="kingdom",
        ),
        ConsoleAction(
            key="kingdom-skip-event",
            item_cls=SkipEventButton,
            build=lambda disabled: SkipEventButton(
                en["console_skip_event_label"], disabled
            ),
            description=en["console_skip_event_label"],
            mod="kingdom",
        ),
    )


def register_console_actions() -> None:
    """Register the mod's ops onto the platform registry (idempotent)."""
    from botforge.discord.console import register_console_action

    for action in kingdom_console_actions():
        try:
            register_console_action(action)
        except ValueError:  # noqa: S110 — already registered (restart re-run)
            pass
