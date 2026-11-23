"""The ⏱️ machine à temps — the game-clock cockpit pinned panel (19/11).

The mod's admin test surface for the SEASON'S CLOCK (Drasah's recette
capture, machine-temps-v3): one pinned panel in the declared
``time_machine`` salon carrying the clock's state (game now, phase,
next cycle/age slots, verdict, snapshots) and the operator's buttons:

- the clock: +1/+3/+7 days, a free jump (modal), a reset to 0;
- the switches: next cycle / next age / season end, and the rewinds
  (previous cycle = the last snapshot's restore, previous age =
  ``rollback_age``);
- the season: pause/resume (``frozen``), back to setup, the Lord's
  Day force-open/close;
- the camera: a manual snapshot + a restore picker (every due slot
  replays onto a fresh pre-slot snapshot — the phases loop wires
  ``run_due``'s snapshotter hook).

Announce-ready (#396): the whole surface is ONE declared template
(``panel:mod:kingdom:time-machine``) + its data; the buttons are
restart-proof DynamicItems under the ``kingdom:machine:`` namespace,
guarded at click time by the settings panel's platform admin check.
"""

from __future__ import annotations

import logging
from typing import Any

import discord

from .common import mod_catalog, open_unique_ephemeral, surface, wiring

logger = logging.getLogger("kingdom.machine")

MACHINE_VIEW_KEY = "panel:mod:kingdom:time-machine"
RESTORE_VIEW_KEY = "panel:mod:kingdom:time-machine:restore"
_NS = "kingdom:machine"


async def _guild_locale(guild_id: str) -> str:
    from .panel import _guild_locale as _panel_locale

    return await _panel_locale(guild_id)


def machine_strings(locale: str) -> dict[str, str]:
    """The machine panel's strings (``kingdom.machine`` catalog section)."""
    return dict(mod_catalog().section("kingdom.machine", str(locale)[:2]))


async def build_time_machine_panel(guild_id: str) -> discord.ui.LayoutView:
    """Build the pinned time-machine layout (guild-locale strings)."""
    from botforge.mods.kingdom.events import next_cron_slot, verdict_slot
    from botforge.mods.kingdom.game_clock import game_now, game_offset_seconds

    locale = await _guild_locale(guild_id)
    strings = machine_strings(locale)
    stack = wiring()
    now = game_now()
    season = None
    snapshots: list[dict[str, Any]] = []
    next_cycle = None
    next_age = None
    verdict = None
    if stack is not None:
        try:
            season = await stack.kingdoms.current_season()
        except Exception:
            logger.warning("kingdom: machine season read failed", exc_info=True)
        try:
            snapshots = await stack.kingdoms.snapshots()
        except Exception:
            logger.warning("kingdom: machine snapshots read failed", exc_info=True)
        if season is not None:
            config = getattr(stack, "config", None)
            try:
                next_cycle = next_cron_slot(config, config.events.cycle_cron, now)
                next_age = next_cron_slot(config, config.events.age_cron, now)
                verdict = verdict_slot(config, season, now)
            except Exception:
                logger.warning("kingdom: machine slots read failed", exc_info=True)

    from .common import fmt_paris

    lines = [f"# {strings['title']}", str(strings["help"]), ""]
    lines.append(str(strings["clock_line"]).format(fmt_paris(now)))
    phase = str(getattr(season, "phase", "setup")) if season is not None else "setup"
    phase_label = str(strings.get(f"phase_{phase}", phase))
    lines.append(str(strings["phase_line"]).format(phase_label))
    if getattr(season, "frozen", False):
        lines.append(str(strings["paused_line"]))
    else:
        lines.append(str(strings["running_line"]))

    from botforge.mods.kingdom.game_clock import format_offset

    lines.append(str(strings["offset_line"]).format(format_offset(game_offset_seconds())))
    if season is not None:
        lines.append(
            str(strings["next_cycle_line"]).format(fmt_paris(next_cycle) if next_cycle else "—")
        )
        lines.append(
            str(strings["next_age_line"]).format(fmt_paris(next_age) if next_age else "—")
        )
        lines.append(
            str(strings["verdict_line"]).format(fmt_paris(verdict) if verdict else "—")
        )
    if snapshots:
        latest = [str(doc.get("_id", "")) for doc in snapshots[:3]]
        lines.append(str(strings["snapshots_line"]).format(len(snapshots), " · ".join(latest)))
    else:
        lines.append(str(strings["snapshots_empty"]))

    rows: list[discord.ui.ActionRow[discord.ui.LayoutView]] = []
    row_buttons: tuple[tuple[discord.ui.DynamicItem[Any], discord.ButtonStyle], ...] = (
        (
            MachineRefreshButton(strings["refresh_button"]),
            discord.ButtonStyle.secondary,
        ),
        (
            MachinePauseButton(
                strings["resume_button"] if getattr(season, "frozen", False) else strings["pause_button"]
            ),
            discord.ButtonStyle.secondary,
        ),
        (MachineSnapshotButton(strings["snapshot_button"]), discord.ButtonStyle.success),
        (MachineRestoreButton(strings["restore_button"]), discord.ButtonStyle.secondary),
        (MachineSetupButton(strings["setup_button"]), discord.ButtonStyle.danger),
        (MachineJumpButton(1, strings["d1_button"]), discord.ButtonStyle.primary),
        (MachineJumpButton(3, strings["d3_button"]), discord.ButtonStyle.primary),
        (MachineJumpButton(7, strings["d7_button"]), discord.ButtonStyle.primary),
        (MachineFreeJumpButton(strings["freejump_button"]), discord.ButtonStyle.success),
        (MachineClockZeroButton(strings["clockzero_button"]), discord.ButtonStyle.danger),
        (MachineSwitchButton("cycle", strings["next_cycle_button"]), discord.ButtonStyle.primary),
        (MachineSwitchButton("age", strings["next_age_button"]), discord.ButtonStyle.primary),
        (MachineSwitchButton("end", strings["end_button"]), discord.ButtonStyle.danger),
        (MachineRollbackButton("snapshot", strings["prev_cycle_button"]), discord.ButtonStyle.secondary),
        (MachineRollbackButton("age", strings["prev_age_button"]), discord.ButtonStyle.secondary),
        (MachineLordsButton("open", strings["lords_open_button"]), discord.ButtonStyle.primary),
        (MachineLordsButton("close", strings["lords_close_button"]), discord.ButtonStyle.secondary),
    )
    for button, style in row_buttons:
        if not rows or len(rows[-1].children) >= 5:
            rows.append(discord.ui.ActionRow())
        rows[-1].add_item(button.item)
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [discord.ui.TextDisplay("\n".join(lines))]
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        *blocks,
        discord.ui.Separator(),
        *rows,
        accent_colour=discord.Colour(0x5865F2),
    )
    return surface(MACHINE_VIEW_KEY, container)


# ---------------------------------------------------------------------------
# The action plumbing (one guard, one stack, one report)
# ---------------------------------------------------------------------------


async def _guard(interaction: discord.Interaction) -> bool:
    """Ride the settings panel's platform admin guard."""
    from .settings_panel import _panel_guard

    return await _panel_guard(interaction)


def _strings(interaction: discord.Interaction) -> dict[str, str]:
    from .common import locale_of

    return machine_strings(locale_of(interaction))


async def _run(interaction: discord.Interaction, action: str) -> None:
    """Run one machine action (deferred, reported, never raised)."""
    from .common import service_failure_note

    strings = _strings(interaction)
    await interaction.response.defer(ephemeral=True)
    stack = wiring()
    if stack is None:
        await interaction.followup.send(strings["no_service"], ephemeral=True)
        return
    note = strings["error"]
    try:
        if action == "refresh":
            from botforge.discord.scope_pins import ensure_mod_pins

            pins = await ensure_mod_pins(interaction.client, str(interaction.guild_id or ""), "kingdom")
            note = str(strings["refresh_done"]).format(pins)
        else:
            kingdoms = stack.kingdoms
            if action == "pause":
                season = await kingdoms.current_season()
                frozen = not bool(getattr(season, "frozen", False)) if season else True
                await kingdoms.set_frozen(frozen)
                note = str(strings["resumed_line"] if not frozen else strings["paused_set_line"])
            elif action == "snapshot":
                snapshot_id = await kingdoms.snapshot(label="manual")
                note = str(strings["snapshot_done"]).format(snapshot_id)
            elif action == "clockzero":
                await kingdoms.set_clock_offset(0)
                note = str(strings["clockzero_done"])
            elif action.startswith("jump:"):
                days = int(action.split(":", 1)[1])
                season = await kingdoms.current_season()
                offset = int(getattr(season, "clock_offset", 0) or 0)
                await kingdoms.set_clock_offset(offset + days * 86400)
                note = str(strings["jump_done"]).format(days)
            elif action == "freejump":
                # the modal answers its own window — no note here
                return
            elif action.startswith("switch:"):
                what = action.split(":", 1)[1]
                if what == "cycle":
                    await stack.events.run_cycle_switch()
                    note = str(strings["switch_cycle_done"])
                elif what == "age":
                    await stack.events.run_age_switch()
                    note = str(strings["switch_age_done"])
                else:
                    await stack.events.end_season()
                    note = str(strings["end_done"])
            elif action.startswith("rollback:"):
                what = action.split(":", 1)[1]
                if what == "age":
                    await stack.events.rollback_age()
                    note = str(strings["prev_age_done"])
                else:
                    snapshots = await kingdoms.snapshots()
                    if not snapshots:
                        note = str(strings["prev_snapshot_none"])
                    else:
                        target = str(snapshots[0].get("_id", ""))
                        await kingdoms.restore_snapshot(target)
                        note = str(strings["restore_done"]).format(target)
            elif action == "setup":
                await kingdoms.set_phase("setup")
                note = str(strings["setup_done"])
            elif action.startswith("lords:"):
                state = action.split(":", 1)[1]
                if state == "open":
                    await stack.events.enter_lords_day_phase()
                    note = str(strings["lords_open_done"])
                else:
                    await stack.events.exit_lords_day_phase()
                    note = str(strings["lords_closed"])
    except ValueError as exc:
        note = str(strings["bad_input"]).format(str(exc)[:150])
    except Exception as exc:  # noqa: BLE001 — the machine reports, never raises
        logger.warning("kingdom: machine action %s failed", action, exc_info=True)
        note = service_failure_note(strings, "error", exc)
    from .settings_panel import _safe_followup

    await _safe_followup(interaction, note)


# ---------------------------------------------------------------------------
# The buttons (restart-proof DynamicItems, one template per class)
# ---------------------------------------------------------------------------


class MachineRefreshButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:refresh$"
):
    """« 🔄 Rafraîchir » — re-render the mod's pinned panels."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id=f"{_NS}:refresh", style=discord.ButtonStyle.secondary
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        return cls(machine_strings(str(interaction.locale)[:2] if interaction.locale else "fr")["refresh_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        await _run(interaction, "refresh")


class MachinePauseButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:pause$"
):
    """« ⏸️ Pause / ▶️ Reprendre » — flip the season's ``frozen`` flag."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id=f"{_NS}:pause", style=discord.ButtonStyle.secondary
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        strings = machine_strings(str(interaction.locale)[:2] if interaction.locale else "fr")
        return cls(strings["pause_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        await _run(interaction, "pause")


class MachineSnapshotButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:snapshot$"
):
    """« 📸 Snapshot » — photograph the current data set."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id=f"{_NS}:snapshot", style=discord.ButtonStyle.success
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        return cls(machine_strings(str(interaction.locale)[:2] if interaction.locale else "fr")["snapshot_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        await _run(interaction, "snapshot")


class MachineRestoreButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:restore$"
):
    """« ♻️ Restaurer… » — open the snapshot picker window."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id=f"{_NS}:restore", style=discord.ButtonStyle.secondary
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        return cls(machine_strings(str(interaction.locale)[:2] if interaction.locale else "fr")["restore_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        strings = _strings(interaction)
        stack = wiring()
        snapshots = await stack.kingdoms.snapshots() if stack is not None else []
        blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
            discord.ui.TextDisplay(f"# {strings['restore_title']}"),
            discord.ui.TextDisplay(str(strings["restore_help"])),
            discord.ui.Separator(),
        ]
        if not snapshots:
            blocks.append(discord.ui.TextDisplay(str(strings["prev_snapshot_none"])))
        for doc in snapshots[:10]:
            from .common import fmt_paris

            taken = doc.get("archived_at")
            label = str(doc.get("_id", ""))
            blocks.append(
                discord.ui.TextDisplay(
                    str(strings["restore_row"]).format(
                        label, fmt_paris(taken) if taken else "—"
                    )
                )
            )
            row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
            row.add_item(MachineRestorePickButton(str(strings["restore_do_button"]), label).item)
            blocks.append(row)
        container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
            *blocks, accent_colour=discord.Colour(0xED4245)
        )
        await open_unique_ephemeral(interaction, view=surface(RESTORE_VIEW_KEY, container))


class MachineRestorePickButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:restore:(?P<aid>[a-z0-9-]+)$",
):
    """One restore picker row — rewind the whole data set to its snapshot."""

    def __init__(self, label: str, archive_id: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:restore:{archive_id}"[:100],
                style=discord.ButtonStyle.danger,
            )
        )
        self.aid = archive_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        strings = machine_strings(str(interaction.locale)[:2] if interaction.locale else "fr")
        return cls(strings["restore_do_button"], match["aid"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        strings = _strings(interaction)
        stack = wiring()
        if stack is None:
            await interaction.followup.send(strings["no_service"], ephemeral=True)
            return
        target = str(getattr(self, "aid", "")) or str(self.item.custom_id).rsplit(":", 1)[-1]
        try:
            await stack.kingdoms.restore_snapshot(target)
            note = str(strings["restore_done"]).format(target)
        except Exception as exc:  # noqa: BLE001 — the machine reports, never raises
            logger.warning("kingdom: snapshot restore failed", exc_info=True)
            from .common import service_failure_note

            note = service_failure_note(strings, "error", exc)
        from .settings_panel import _safe_followup

        await _safe_followup(interaction, note)


class MachineSetupButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:setup$"
):
    """« ⏮️ Retour setup » — move the phase back (confirm card)."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id=f"{_NS}:setup", style=discord.ButtonStyle.danger
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        return cls(machine_strings(str(interaction.locale)[:2] if interaction.locale else "fr")["setup_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        strings = _strings(interaction)
        confirm = discord.ui.Button(
            label=str(strings["setup_confirm_button"])[:80],
            custom_id=f"{_NS}:setup:yes",
            style=discord.ButtonStyle.danger,
        )
        cancel = discord.ui.Button(
            label=str(strings["setup_cancel_button"])[:80],
            custom_id=f"{_NS}:setup:no",
            style=discord.ButtonStyle.secondary,
        )

        async def on_yes(target: discord.Interaction) -> None:
            await _run(target, "setup")

        async def on_no(target: discord.Interaction) -> None:
            from .settings_panel import _safe_send

            await _safe_send(target, strings["cancelled"])

        confirm.callback = on_yes
        cancel.callback = on_no
        row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        row.add_item(confirm)
        row.add_item(cancel)
        container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
            discord.ui.TextDisplay(
                f"**{strings['setup_confirm_title']}**\n{strings['setup_confirm_hint']}"
            ),
            row,
            accent_colour=discord.Colour(0xED4245),
        )
        await open_unique_ephemeral(interaction, view=surface(RESTORE_VIEW_KEY, container))


class MachineJumpButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:jump:(?P<days>[1-9])$",
):
    """« +1 / +3 / +7 jours » — fast-forward the game clock."""

    def __init__(self, days: int, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:jump:{days}",
                style=discord.ButtonStyle.primary,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        strings = machine_strings(str(interaction.locale)[:2] if interaction.locale else "fr")
        days = int(match["days"])
        key = {1: "d1_button", 3: "d3_button", 7: "d7_button"}.get(days, "d1_button")
        return cls(days, strings[key])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        days = int(str(self.item.custom_id).rsplit(":", 1)[-1])
        await _run(interaction, f"jump:{days}")


class _MachineJumpModal(discord.ui.Modal):
    """« ⏩ Saut libre » — a free duration (additive, « 90m », « 1d2h »)."""

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(title=str(strings["freejump_modal_title"])[:45])
        self._strings = strings
        self.duration = discord.ui.TextInput(
            placeholder="90m",
            min_length=1,
            max_length=20,
            required=True,
            custom_id=f"{_NS}:freejump:duration",
        )
        self.add_item(
            discord.ui.Label(
                text=str(strings["freejump_label"])[:45], component=self.duration
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Read the free duration and advance the clock (deferred note)."""

        from botforge.mods.kingdom.game_clock import parse_duration

        await interaction.response.defer(ephemeral=True)
        strings = self._strings
        try:
            seconds = parse_duration(str(self.duration.value))
        except ValueError as exc:
            await interaction.followup.send(
                str(strings["bad_input"]).format(str(exc)[:150]), ephemeral=True
            )
            return
        stack = wiring()
        if stack is None:
            await interaction.followup.send(strings["no_service"], ephemeral=True)
            return
        try:
            season = await stack.kingdoms.current_season()
            offset = int(getattr(season, "clock_offset", 0) or 0)
            await stack.kingdoms.set_clock_offset(offset + seconds)
            note = str(strings["freejump_done"]).format(seconds // 86400)
        except Exception as exc:  # noqa: BLE001 — the machine reports, never raises
            logger.warning("kingdom: free jump failed", exc_info=True)
            from .common import service_failure_note

            note = service_failure_note(strings, "error", exc)
        from .settings_panel import _safe_followup

        await _safe_followup(interaction, note)


class MachineFreeJumpButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:freejump$"
):
    """« ⏩ Saut libre… » — open the free-jump modal."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id=f"{_NS}:freejump", style=discord.ButtonStyle.success
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        return cls(machine_strings(str(interaction.locale)[:2] if interaction.locale else "fr")["freejump_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        await interaction.response.send_modal(_MachineJumpModal(_strings(interaction)))


class MachineClockZeroButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:clockzero$"
):
    """« 🧹 Réinitialiser l'horloge » — back to offset 0."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id=f"{_NS}:clockzero", style=discord.ButtonStyle.danger
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        return cls(machine_strings(str(interaction.locale)[:2] if interaction.locale else "fr")["clockzero_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        await _run(interaction, "clockzero")


class MachineSwitchButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:switch:(?P<what>cycle|age|end)$",
):
    """« Prochain cycle / prochain âge / fin de saison »."""

    def __init__(self, what: str, label: str) -> None:
        style = {"cycle": discord.ButtonStyle.primary, "age": discord.ButtonStyle.primary}.get(
            what, discord.ButtonStyle.danger
        )
        super().__init__(
            discord.ui.Button(label=label[:80], custom_id=f"{_NS}:switch:{what}", style=style)
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        strings = machine_strings(str(interaction.locale)[:2] if interaction.locale else "fr")
        key = {"cycle": "next_cycle_button", "age": "next_age_button", "end": "end_button"}[
            match["what"]
        ]
        return cls(match["what"], strings[key])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        await _run(interaction, f"switch:{str(self.item.custom_id).rsplit(':', 1)[-1]}")


class MachineRollbackButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:rollback:(?P<what>age|snapshot)$",
):
    """« Cycle précédent » (last snapshot) / « Âge précédent » (rollback)."""

    def __init__(self, what: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id=f"{_NS}:rollback:{what}", style=discord.ButtonStyle.secondary
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        strings = machine_strings(str(interaction.locale)[:2] if interaction.locale else "fr")
        key = {"age": "prev_age_button", "snapshot": "prev_cycle_button"}[match["what"]]
        return cls(match["what"], strings[key])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        await _run(interaction, f"rollback:{str(self.item.custom_id).rsplit(':', 1)[-1]}")


class MachineLordsButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:lords:(?P<state>open|close)$",
):
    """« Ouvrir / Fermer le jour du seigneur » (the forced test window)."""

    def __init__(self, state: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:lords:{state}",
                style=(
                    discord.ButtonStyle.primary
                    if state == "open"
                    else discord.ButtonStyle.secondary
                ),
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        strings = machine_strings(str(interaction.locale)[:2] if interaction.locale else "fr")
        key = {"open": "lords_open_button", "close": "lords_close_button"}[match["state"]]
        return cls(match["state"], strings[key])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        await _run(interaction, f"lords:{str(self.item.custom_id).rsplit(':', 1)[-1]}")


def machine_dynamic_items() -> tuple:
    """Every restart-proof DynamicItem of the machine panel (boot pass)."""
    return (
        MachineRefreshButton,
        MachinePauseButton,
        MachineSnapshotButton,
        MachineRestoreButton,
        MachineRestorePickButton,
        MachineSetupButton,
        MachineJumpButton,
        MachineFreeJumpButton,
        MachineClockZeroButton,
        MachineSwitchButton,
        MachineRollbackButton,
        MachineLordsButton,
    )


__all__ = [
    "MACHINE_VIEW_KEY",
    "RESTORE_VIEW_KEY",
    "build_time_machine_panel",
    "machine_dynamic_items",
    "machine_strings",
]
