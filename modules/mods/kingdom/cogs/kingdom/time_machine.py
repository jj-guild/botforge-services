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
  ``run_due``'s snapshotter hook);
- the clock's rhythm (v4, Drasah 20/11): the season length and the
  cycle/age/verdict labels derive from the ACTIVE preset (official
  ``weeks``, beta compressed plan) — never hardcoded — and the pin
  re-renders itself on a light refresher loop.

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


# machine-temps-v4 (Drasah 20/11): the rhythm and length labels are
# DATA-DRIVEN — the season length reads the active preset (official
# ``weeks``, beta compressed plan), never a hardcoded count. The 4-week
# text of v3 was the stale reference value.


_CRON_DAY_LABELS: tuple[str, ...] = (
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
)
_CRON_DAY_LABELS_EN: tuple[str, ...] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _hours_label(locale: str, day: int, hour: int, minute: int) -> str:
    """One weekly slot as Drasah reads it: « dimanche 23h30 » / « Sunday 23:30 »."""
    labels = _CRON_DAY_LABELS if str(locale).startswith("fr") else _CRON_DAY_LABELS_EN
    if str(locale).startswith("fr"):
        return f"{labels[day]} {hour:02d}h{minute:02d}"
    return f"{labels[day]} {hour:02d}:{minute:02d}"


def weekly_slot_label(cron: str, locale: str) -> str:
    """The cron's weekly slot label (« dimanche 23h30 ») — derived, never hardcoded."""
    from botforge.mods.kingdom.events import weekly_cron_parts

    minute, hour, day = weekly_cron_parts(cron)
    return _hours_label(locale, day, hour, minute)


def verdict_slot_label(cycle_cron: str, locale: str) -> str:
    """The verdict slot label — the cycle slot plus 29 minutes (verdict_slot)."""
    from botforge.mods.kingdom.events import weekly_cron_parts

    minute, hour, day = weekly_cron_parts(cycle_cron)
    total = hour * 60 + minute + 29
    return _hours_label(locale, day, total // 60 % 24, total % 60)


def _preset_config(stack: Any) -> Any:
    """The season config from the stack, the declared defaults otherwise."""
    config = getattr(stack, "config", None) if stack is not None else None
    if config is None:
        from botforge.mods.kingdom.config import default_season_config

        config = default_season_config()
    return config


def _beta_armed(season: Any) -> bool:
    """Whether the season rides a compressed beta preset (machine display)."""
    from botforge.mods.kingdom.beta_weekend import BETA_PRESETS

    return bool(BETA_PRESETS.get(str(getattr(season, "beta_name", None) or "")))


def season_length_label(locale: str, config: Any, season: Any) -> str:
    """The ACTIVE preset's season length: « 3 semaines » / « 52h (beta) »."""
    from botforge.mods.kingdom.beta_weekend import BETA_PLAN_OFFSETS

    strings = machine_strings(locale)
    if _beta_armed(season):
        return str(strings["length_beta"]).format(int(BETA_PLAN_OFFSETS["end_hours"]))
    weeks = int(getattr(config, "weeks", 3) or 3)
    if weeks == 1:
        return str(strings["length_one_week"])
    return str(strings["length_weeks"]).format(weeks)


def setup_rhythm_phrase(locale: str, config: Any, season: Any) -> str:
    """The setup phase's rhythm sentence — every piece derived from data."""
    strings = machine_strings(locale)
    if _beta_armed(season):
        from botforge.mods.kingdom.beta_weekend import BETA_PLAN_OFFSETS

        cycles = " et ".join(f"T0+{int(h)}h" for h in BETA_PLAN_OFFSETS["cycle_hours"])
        return str(strings["rhythm_beta"]).format(
            f"T0+{int(BETA_PLAN_OFFSETS['age_hours'])}h",
            cycles,
            f"T0+{int(BETA_PLAN_OFFSETS['end_hours'])}h",
        )
    cycle = weekly_slot_label(config.events.cycle_cron, locale)
    age = weekly_slot_label(config.events.age_cron, locale)
    verdict = verdict_slot_label(config.events.cycle_cron, locale)
    return " · ".join(
        (
            str(strings["rhythm_cycle"]).format(cycle),
            str(strings["rhythm_age"]).format(age),
            str(strings["rhythm_season"]).format(season_length_label(locale, config, season)),
            str(strings["rhythm_verdict"]).format(verdict),
        )
    )


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
            live_config = getattr(stack, "config", None)
            try:
                next_cycle = next_cron_slot(live_config, live_config.events.cycle_cron, now)
                next_age = next_cron_slot(live_config, live_config.events.age_cron, now)
                verdict = verdict_slot(live_config, season, now)
            except Exception:
                logger.warning("kingdom: machine slots read failed", exc_info=True)

    from .common import fmt_paris

    lines = [f"# {strings['title']}", str(strings["help"]), ""]
    lines.append(str(strings["clock_line"]).format(fmt_paris(now)))
    config = _preset_config(stack)
    phase = str(getattr(season, "phase", "setup")) if season is not None else "setup"
    phase_label = str(strings.get(f"phase_{phase}", phase))
    if phase == "setup":
        phase_label = str(phase_label).format(setup_rhythm_phrase(locale, config, season))
    lines.append(str(strings["phase_line"]).format(phase_label))
    # machine-temps-v4: the ACTIVE preset's length, always visible
    lines.append(str(strings["length_line"]).format(season_length_label(locale, config, season)))
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
    failed = False
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
        failed = True
    except Exception as exc:  # noqa: BLE001 — the machine reports, never raises
        logger.warning("kingdom: machine action %s failed", action, exc_info=True)
        note = service_failure_note(strings, "error", exc)
        failed = True
    # logs-admin-v1 (T4a): every machine action SANS refresh (pure
    # navigation) lands in 📜 logs — the mutation trail, failures excluded.
    if action != "refresh" and not failed:
        from .admin_logs import log_admin_action_on_interaction

        await log_admin_action_on_interaction(interaction, "time", note)
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
            from .admin_logs import log_admin_action_on_interaction

            await log_admin_action_on_interaction(interaction, "time", note)
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


# ---------------------------------------------------------------------------
# The auto-refresher (machine-temps-v4, Drasah 20/11): the pinned cockpit
# re-renders ITSELF — « Panneau épinglé auto-mis à jour ». The clock line
# is a live reading: a pin that only refreshes on boot goes stale within
# minutes. The loop rides the platform's own ensure cycle (fingerprint
# guard: an unchanged pin costs NO API call, so the cadence is free in
# steady state and the clock line re-edits only when it actually moved).
# ---------------------------------------------------------------------------

REFRESH_MINUTES = 5
# pins-heal-v1 (Drasah 20/11): the loop re-ensures EVERY kingdom pin,
# not only the machine — « le salon existe mais rien à l'intérieur » : a
# boot pin can be lost to the provisioning's API storm (a 429, a slow
# cache) and the console panel had NO retry. The ensure cycle is
# idempotent (fingerprint guard: an unchanged pin costs one cheap
# fetch), so the cadence is free and every lost pin heals ≤ 5 min.
MOD_PIN_SCOPE = "mod/kingdom"


async def _season_roles_pass(bot: Any, guild: Any, guild_id: str) -> None:
    """liaison-roless-saison-v1 (Drasah 24/11) : la convergence des rôles.

    Un royaume éjecté perd ses rôles, un porteur orphelin les rend, un
    rattrapage guérit tout seul — best-effort, jamais bloquant.
    """
    from .season_roles import sync_season_roles

    try:
        synced = await sync_season_roles(bot, guild)
        if synced:
            logger.info(
                "kingdom: season roles re-synced (%d transition(s), guild %s)",
                synced,
                guild_id,
            )
    except Exception:  # the pass never raises
        logger.warning("kingdom: the season roles pass failed (guild %s)", guild_id, exc_info=True)


async def run_mod_pin_refresh_pass(bot: Any) -> int:
    """One pass: re-ensure EVERY kingdom pin on every served guild.

    Every static pin registered under the mod's scope rides the pass —
    the machine cockpit, the ⚙️ paramètres console panel, the
    distributeur, the validation dashboard… A pin lost at boot (the
    provisioning storm) or deleted by hand heals within one cycle.
    """
    from botforge.discord.static_pins import ensure_static_pin, registered_static_pins

    specs = [
        s
        for s in registered_static_pins()
        if s.scope and (s.scope == MOD_PIN_SCOPE or s.scope.startswith(MOD_PIN_SCOPE + "/"))
    ]
    touched = 0
    for guild in list(getattr(bot, "guilds", []) or []):
        guild_id = str(getattr(guild, "id", ""))
        for spec in specs:
            try:
                # the pin quietly skips when its salon is not resolvable
                await ensure_static_pin(bot, spec, guild_id)
                touched += 1
            except Exception:  # noqa: BLE001 — the refresher never raises
                logger.warning(
                    "kingdom: pin pass failed (%s, guild %s)", spec.key, guild_id, exc_info=True
                )
        # hors-saison-v1 (Drasah 20/11): the conscription rides the LIVE
        # season's TYPE — beta masks #enregistrement entirely and opens
        # #postuler to everyone; classical restores the declared parcours.
        # Idempotent (converge-skip), so the cadence is free.
        from .conscription_gate import run_conscription_gate_pass

        try:
            await run_conscription_gate_pass(bot, guild_id)
        except Exception:  # noqa: BLE001 — the pass never raises
            logger.warning("kingdom: conscription gate pass failed", exc_info=True)
        # liaison-roless-saison-v1 (Drasah 24/11) : les rôles de saison
        # convergent au cycle (la passe là-dessous, idempotente).
        await _season_roles_pass(bot, guild, guild_id)
        # hub-content-v2 (Drasah 20/11): the realm hubs are not declared
        # pins — this pass is their ONLY healing. A hub lost at founding
        # heals here (fingerprint guard: converged = one cheap fetch).
        from .realms import heal_realm_hubs

        try:
            await heal_realm_hubs(bot)
        except Exception:  # noqa: BLE001 — the pass never raises
            logger.warning("kingdom: realm hub heal failed", exc_info=True)
        # pins-fusion-v1 (Drasah 20/11): a RETIRED pin key's message (the
        # candidates/validation duplicate) is deleted by its registry id
        from .legacy_pins import sweep_legacy_pins

        try:
            await sweep_legacy_pins(bot, guild_id)
        except Exception:  # noqa: BLE001 — the pass never raises
            logger.warning("kingdom: legacy pin sweep failed", exc_info=True)
        # category-bottom (Drasah 20/11): the plumbing folders sink last —
        # re-asserted here so a category founded later heals down in 5 min
        from botforge.discord.ui.panels_provisioning import enforce_bottom_categories

        try:
            await enforce_bottom_categories(bot)
        except Exception:  # noqa: BLE001 — the pass never raises
            logger.warning("kingdom: bottom categories pass failed", exc_info=True)
        # ordres-royaumes (Drasah 24/11) : le refreshing pass RESSERRE aussi
        # le bandeau des royaumes — un royaume mal placé (ou une repair
        # à moitié faite) guérit dans le cycle, pas seulement au boot.
        from .realms import place_realm_categories

        try:
            band = await place_realm_categories(guild)
            if band:
                logger.info(
                    "kingdom: refresh placed %d realm categorie(s) above admin", band
                )
        except Exception:  # the pass never raises
            logger.warning(
                "kingdom: the realm band placement failed (guild %s)",
                guild_id,
                exc_info=True,
            )
    return touched


async def run_machine_refresh_pass(bot: Any) -> int:
    """machine-temps-v4 alias — the pass is MOD-WIDE since pins-heal-v1."""
    return await run_mod_pin_refresh_pass(bot)


def start_machine_refresher(bot: Any) -> None:
    """Start the mod pin auto-refresher (every REFRESH_MINUTES).

    pins-heal-v1 (Drasah 20/11): the loop is MOD-WIDE — every kingdom
    pin heals within one cycle (a boot lost to the provisioning storm
    no longer leaves an empty salon). Gated off in the test journeys
    (``BOTFORGE_KINGDOM_PIN_REFRESHER`` /
    ``BOTFORGE_KINGDOM_MACHINE_REFRESHER`` = off), same idiom as the
    attack phases loop.
    """
    import os

    def _gated() -> bool:
        for var in ("BOTFORGE_KINGDOM_PIN_REFRESHER", "BOTFORGE_KINGDOM_MACHINE_REFRESHER"):
            if os.environ.get(var, "").lower() in {"off", "0", "false"}:
                return True
        return False

    if _gated():
        return

    from discord.ext import tasks

    @tasks.loop(minutes=REFRESH_MINUTES)
    async def _loop() -> None:
        try:
            await run_mod_pin_refresh_pass(bot)
        except Exception:  # noqa: BLE001 — the loop never raises
            logger.warning("kingdom: pin refresher pass failed — best-effort", exc_info=True)

    # refresher-boot-v1 (Drasah 24/11): `.setup()` n'existe plus dans
    # discord.py servie (2.7.1) — l'appel levait AttributeError à CHAQUE
    # boot, gobé en silence : la boucle de guérison ne démarrait jamais
    # (hub fantôme jusqu'au geste manuel « Resynchroniser »). Le Loop est
    # désormais prêt dès sa construction — `start()` suffit.
    _loop.start()  # type: ignore[no-untyped-call]


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
    "REFRESH_MINUTES",
    "build_time_machine_panel",
    "machine_dynamic_items",
    "machine_strings",
    "run_machine_refresh_pass",
    "run_mod_pin_refresh_pass",
    "season_length_label",
    "setup_rhythm_phrase",
    "start_machine_refresher",
    "verdict_slot_label",
    "weekly_slot_label",
]
