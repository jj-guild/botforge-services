"""The 🛠️ admin console — the admin season cockpit (epic #412 T1).

The reference's 12-button settings panel (``kingdom_panels.py`` /
``kingdom_persistent.py``, capture image-12), ported onto the platform
seams — the mod re-implements NOTHING:

- season actions ride the §7 service contract (``launch``,
  ``start_season``, ``set_imposed_mode``, ``assign``, ``add_kingdom``,
  ``leave``, ``ensure_test_kingdom``) and the admin-hat bypass
  (``admin_debug``);
- « Déployer / Resynchroniser / Réinitialiser les salons » ride the
  catalog's provisioning seams (``provision_mod_roles`` +
  ``provision_mod_channels`` + ``ensure_mod_pins`` — the exact Repair
  path, ``delete_mod_scope`` for the reset);
- « Démarrer la beta » rides the platform's beta phase toggle
  (``enter_beta``/``exit_beta`` — the BetaPhaseButton contract);
- the click guard is the platform's ``require_admin`` (roles resolve
  live, never assumed at render time).

Announce-ready (#396): the panel is ONE named template
(``panel:mod:kingdom:admin:console``) instantiated by parameters (the
``SETTINGS_ACTIONS`` table); the destructive ops wear the inline
confirm card (one ephemeral window, never a stacked surface).
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord

from botforge.discord.console import mod_console_view_id

from .common import locale_of, open_unique_ephemeral, service_failure_note, surface, wiring

logger = logging.getLogger("kingdom.settings")

_MOD = "kingdom"
# the mod console surface id is OWNED BY THE SDK (auto-declared for every
# mod by mod_views.declare_mod_views) — this constant is the mod's anchor
CONSOLE_VIEW_KEY = mod_console_view_id(_MOD)
_ADMIN_COLOUR = discord.Colour(0x5865F2)

# The designer's 12 actions, verbatim order (capture image-12):
# (action, string key, button style).
_SETTINGS_ACTIONS: tuple[tuple[str, str, discord.ButtonStyle], ...] = (
    ("launch", "settings_launch_button", discord.ButtonStyle.success),
    ("start-season", "settings_start_season_button", discord.ButtonStyle.success),
    ("start-beta", "settings_start_beta_button", discord.ButtonStyle.success),
    ("status", "settings_status_button", discord.ButtonStyle.secondary),
    ("deploy", "settings_deploy_button", discord.ButtonStyle.primary),
    ("sync", "settings_sync_button", discord.ButtonStyle.secondary),
    ("reset", "settings_reset_button", discord.ButtonStyle.danger),
    ("assign", "settings_assign_button", discord.ButtonStyle.primary),
    ("add-kingdom", "settings_add_kingdom_button", discord.ButtonStyle.primary),
    ("season-mode", "settings_season_mode_button", discord.ButtonStyle.secondary),
    ("remove", "settings_remove_button", discord.ButtonStyle.danger),
)
# casquette-removal-v1 (Drasah 19/11): the hat op RETIRES from the
# console (11 actions) — the bypass lives in the code's own seams and
# the test kingdom rides the Distributeur's dedicated button.

_CONFIRM_ACTIONS = frozenset({"deploy", "sync", "reset"})

_ALL_ACTIONS = tuple(action for action, _key, _style in _SETTINGS_ACTIONS)


async def _safe_send(interaction: discord.Interaction, content: str) -> None:
    """Answer once, whatever the dispatch path (never a 40060)."""
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(content, ephemeral=True)
        else:
            await interaction.followup.send(content, ephemeral=True)
    except Exception:
        logger.info("kingdom: console note lost", exc_info=True)


async def _safe_followup(interaction: discord.Interaction, content: str) -> None:
    """Send an ephemeral followup, tolerating a vanished channel.

    The destructive ops (reset) may delete the very salon the console
    window lives in: the followup webhook then targets an unknown
    channel (10003) while the action itself SUCCEEDED — a clean warning,
    never a traceback (same seam as the platform console's safe followup).
    """
    try:
        await interaction.followup.send(content, ephemeral=True)
    except discord.HTTPException as exc:
        if getattr(exc, "code", None) == 10003:
            logger.warning(
                "kingdom: console verdict undeliverable "
                "(the channel was deleted by the action itself) — the action succeeded"
            )
            return
        raise
    except Exception:
        logger.info("kingdom: console verdict lost", exc_info=True)

def settings_strings(locale: str) -> dict[str, str]:
    """Return the console's strings for one locale — pure data i18n.

    Every string lives in the mod's ``conf/locales/*.yaml`` under
    ``kingdom.settings`` (the catalog's English fallback fills the gaps);
    nothing user-facing is hardcoded in this module anymore.
    """
    from .common import mod_catalog

    return dict(mod_catalog().section("kingdom.settings", str(locale)[:2]))



def strings_of(interaction: discord.Interaction) -> dict[str, str]:
    """Return the panel's strings in the interaction's locale."""
    return settings_strings(locale_of(interaction))


def console_buttons(strings: dict[str, str], disabled: bool = False) -> tuple[Any, ...]:
    """The three console ops, in ONE given locale (recette 19/11: FR).

    The registry's builders render the EN defaults (the platform's
    home/SDK surfaces); the panel here re-instantiates the SAME
    restart-proof DynamicItems with the GUILD locale's labels — the
    buttons keep their stable custom ids, only the visible text is
    localized.
    """
    from .console import KingdomClockButton, KingdomRelaunchButton, KingdomResetButton

    return (
        KingdomRelaunchButton(str(strings["console_relaunch_label"]), disabled),
        KingdomResetButton(str(strings["console_reset_label"]), disabled),
        KingdomClockButton(str(strings["console_clock_label"]), disabled),
    )


async def build_settings_panel(guild_id: str) -> discord.ui.LayoutView:
    """Build the mod admin console panel (the admin cockpit)."""
    from .apply_flow import _guild_locale

    locale = await _guild_locale(guild_id)
    strings = settings_strings(locale)
    rows: list[discord.ui.ActionRow[discord.ui.LayoutView]] = []
    for index, (action, key, style) in enumerate(_SETTINGS_ACTIONS):
        if index % 5 == 0:
            rows.append(discord.ui.ActionRow())
        rows[index // 5].add_item(
            SettingsActionButton(action, str(strings[key]), style).item
        )

    # the mod-scoped console ops (relaunch / reset / clock): the SAME
    # restart-proof DynamicItems the registry owns, re-rendered in the
    # GUILD's locale (the registry's own builder is EN-only — recette
    # 19/11: the panel's buttons read in French)
    from .common import strings_by_locale

    ops = strings_by_locale(locale)
    for button in console_buttons(ops, False):
        if not rows or len(rows[-1].children) >= 5:
            rows.append(discord.ui.ActionRow())
        rows[-1].add_item(button.item)

    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.TextDisplay(f"# {strings['settings_title']}"),
        discord.ui.Separator(),
        *rows,
        discord.ui.Separator(),
        accent_colour=_ADMIN_COLOUR,
    )
    return surface(CONSOLE_VIEW_KEY, container)


async def _panel_guard(interaction: discord.Interaction) -> bool:
    """Guard the panel behind the platform admin check (live, never assumed)."""
    from botforge.discord.guards import require_admin

    admins = tuple(
        getattr(getattr(interaction.client, "status_service", None), "bot_admins", ())
        or ()
    )
    return await require_admin(
        interaction,
        admins,
        getattr(interaction.client, "roles_service", None),
        denied_message=str(strings_of(interaction)["settings_denied"]),
    )


def _confirm_card(strings: dict[str, str], action: str) -> discord.ui.LayoutView:
    """Build the inline confirm card of a destructive op (one ephemeral window).

    The yes/no buttons carry their OWN custom-id namespace
    (``kingdom:confirm:<action>:<choice>``) — never the settings actions'
    ``kingdom:settings:`` template: discord.py 2.7 dispatches a click to
    every registered dynamic template that fullmatches the id AND to the
    message's stored view, so a colliding id fires the handler twice (the
    second response dies with 40060 "already acknowledged").
    """
    yes: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings[f"settings_{action}_confirm_button"])[:80],
        custom_id=f"kingdom:confirm:{action}:yes",
        style=discord.ButtonStyle.danger,
    )
    no: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings[f"settings_{action}_cancel_button"])[:80],
        custom_id=f"kingdom:confirm:{action}:no",
        style=discord.ButtonStyle.secondary,
    )

    async def on_yes(target: discord.Interaction) -> None:
        if not target.response.is_done():
            await target.response.defer(ephemeral=True)
        note = await _run_provisioning(target, action)
        await _safe_followup(target, note)

    async def on_no(target: discord.Interaction) -> None:
        await _safe_send(target, strings["settings_cancelled"])

    yes.callback = on_yes
    no.callback = on_no
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.TextDisplay(
            f"**{strings[f'settings_{action}_confirm_title']}**\n"
            f"{strings[f'settings_{action}_confirm_hint']}"
        ),
        accent_colour=discord.Colour(0xED4245),
    )
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row.add_item(yes)
    row.add_item(no)
    container.add_item(row)
    return surface("panel:mod:kingdom:admin:console:confirm", container)


async def _run_provisioning(interaction: discord.Interaction, action: str) -> str:
    """Deploy / resync / reset the mod's salons through the catalog seams."""
    strings = strings_of(interaction)
    bot = interaction.client
    guild_id = str(interaction.guild_id or "")
    try:
        from botforge.discord.mods_forum import (
            delete_mod_scope,
            provision_mod_channels,
            provision_mod_roles,
        )
        from botforge.discord.scope_pins import ensure_mod_pins

        deleted = 0
        if action == "reset":
            deleted = await delete_mod_scope(bot, guild_id, _MOD)
        roles = await provision_mod_roles(bot, guild_id, _MOD)
        channels = (
            await provision_mod_channels(bot, guild_id, _MOD)
            if action in {"deploy", "reset"}
            else 0
        )
        pins = await ensure_mod_pins(bot, guild_id, _MOD)
    except Exception as exc:  # the panel reports, never raises
        logger.warning("kingdom: settings %s failed", action, exc_info=True)
        return str(strings["settings_error"]).format(str(exc)[:150])
    if action == "deploy":
        return str(strings["settings_deploy_done"]).format(
            channels=channels, roles=roles, pins=pins
        )
    if action == "sync":
        return str(strings["settings_sync_done"]).format(pins=pins)
    return str(strings["settings_reset_done"]).format(channels=deleted)


class SettingsActionButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:settings:(?P<action>[a-z0-9-]+)",
):
    """One restart-proof admin action of the 🛠️ console."""

    def __init__(
        self, action: str, label: str, style: discord.ButtonStyle | None = None
    ) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"kingdom:settings:{action}"[:100],
                style=style or discord.ButtonStyle.secondary,
            )
        )
        self.action = action

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> SettingsActionButton:
        """Rebuild the button from the wire (label from the live locale)."""
        strings = strings_of(interaction)
        action = match["action"]
        styles: dict[str, discord.ButtonStyle] = {
            action: style for action, _key, style in _SETTINGS_ACTIONS
        }
        style = styles.get(action, discord.ButtonStyle.secondary)
        label = strings.get(f"settings_{action}_button", "⚙️")
        return cls(action, str(label), style)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Run the chosen admin action (guarded, ephemeral, best-effort)."""
        strings = strings_of(interaction)
        if self.action not in _ALL_ACTIONS:
            await _safe_send(interaction, strings["settings_denied"])
            return
        if not await _panel_guard(interaction):
            return
        if self.action in _CONFIRM_ACTIONS:
            await open_unique_ephemeral(
                interaction, view=_confirm_card(strings, self.action)
            )
            return
        await _SETTINGS_HANDLERS[self.action](interaction, strings)


# ---------------------------------------------------------------------------
# The season actions (§7 contract only — never the mod's internals)
# ---------------------------------------------------------------------------


def _needs_stack(strings: dict[str, str]) -> tuple[Any | None, str | None]:
    """Resolve the service stack, or the refusal note when it's absent."""
    stack = wiring()
    if stack is None or getattr(stack, "kingdoms", None) is None:
        return None, strings["settings_no_service"]
    return stack, None


async def _start_season(interaction: discord.Interaction, strings: dict[str, str]) -> None:
    await interaction.response.defer(ephemeral=True)
    stack, busy = _needs_stack(strings)
    if busy:
        await interaction.followup.send(busy, ephemeral=True)
        return
    try:
        await stack.kingdoms.start_season()
        note = str(strings["settings_start_season_done"])
    except Exception as exc:  # the panel reports, never raises
        logger.warning("kingdom: start_season failed", exc_info=True)
        note = service_failure_note(strings, "settings_start_season_failed", exc)
    await interaction.followup.send(note, ephemeral=True)


async def _season_mode(interaction: discord.Interaction, strings: dict[str, str]) -> None:
    """Toggle the imposed/free mode of the running season (no data loss)."""
    await interaction.response.defer(ephemeral=True)
    stack, busy = _needs_stack(strings)
    if busy:
        await interaction.followup.send(busy, ephemeral=True)
        return
    try:
        season = await stack.kingdoms.current_season()
        imposed = bool(getattr(season, "imposed_kingdoms", False)) if season else False
        await stack.kingdoms.set_imposed_mode(not imposed)
        note = str(
            strings["settings_mode_imposed" if not imposed else "settings_mode_free"]
        )
    except Exception as exc:  # the panel reports, never raises
        logger.warning("kingdom: season-mode toggle failed", exc_info=True)
        note = service_failure_note(strings, "settings_failed", exc)
    await interaction.followup.send(note, ephemeral=True)


async def _start_beta(interaction: discord.Interaction, strings: dict[str, str]) -> None:
    """Flip the platform's beta phase (enter or leave — the operator's call)."""
    from botforge.core.services.beta import enter_beta, exit_beta, is_beta
    from botforge.core.services.mod_storage import ModStateCache

    await interaction.response.defer(ephemeral=True)
    state_service = getattr(interaction.client, "state_service", None)
    cache = ModStateCache(state_service, _MOD) if state_service is not None else None
    guild_id = str(interaction.guild_id or "")
    try:
        if await is_beta(cache, guild_id, _MOD):
            await exit_beta(cache, guild_id, _MOD)
            note = str(strings["settings_beta_exited"])
        else:
            await enter_beta(cache, guild_id, _MOD)
            note = str(strings["settings_beta_started"])
    except Exception as exc:  # the panel reports, never raises
        logger.warning("kingdom: beta toggle failed", exc_info=True)
        note = service_failure_note(strings, "settings_failed", exc)
    await interaction.followup.send(note, ephemeral=True)


async def _status(interaction: discord.Interaction, strings: dict[str, str]) -> None:
    """Answer with the season status card (kingdoms, queue, players)."""
    lines = [f"# {strings['settings_status_title']}"]
    stack = wiring()
    kingdoms: list[str] = []
    queued = 0
    enrolled = 0
    phase = str(strings["settings_phase_unknown"])
    mode = str(strings["settings_mode_free"])
    if stack is not None and getattr(stack, "kingdoms", None) is not None:
        try:
            all_kingdoms = await stack.kingdoms.kingdoms()
            kingdoms = sorted(k.name for k in all_kingdoms if not k.is_gaia)
            lords = await stack.kingdoms.lords()
            active = [lord for lord in lords if not lord.left]
            queued = sum(1 for lord in active if lord.in_queue)
            enrolled = len(active) - queued
        except Exception:
            logger.warning("kingdom: status read failed", exc_info=True)
        try:
            season = await stack.kingdoms.current_season()
            if season is not None:
                phase = str(strings.get(
                    f"settings_phase_{getattr(season, 'phase', 'started')}",
                    strings["settings_phase_unknown"],
                ))
                mode = str(
                    strings["settings_mode_imposed"]
                    if season.imposed_kingdoms
                    else strings["settings_mode_free"]
                )
        except Exception:
            logger.warning("kingdom: season read failed", exc_info=True)
    lines.extend(
        [
            f"**{strings['settings_status_phase']}** : {phase}",
            f"**{strings['settings_status_mode']}** : {mode}",
            f"**{strings['settings_status_kingdoms']}** : "
            f"{', '.join(kingdoms) if kingdoms else strings['settings_status_empty']}",
            f"**{strings['settings_status_lords']}** : "
            f"{enrolled or strings['settings_status_empty']}",
            f"**{strings['settings_status_queue']}** : "
            f"{queued or strings['settings_status_empty']}",
        ]
    )
    await open_unique_ephemeral(interaction, "\n".join(lines))


class _LaunchModal(discord.ui.Modal):
    """Lancer la saison — optional comma-separated imposed kingdom names."""

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(title=str(strings["settings_launch_modal_title"])[:45])
        self._strings = strings
        # discord.py 2.7: a TextInput rides a discord.ui.Label (the label
        # property is deprecated); the Label text caps at 45 chars (50035)
        self.names = discord.ui.TextInput(
            placeholder=str(strings["settings_launch_modal_names_placeholder"])[:100],
            required=False,
            max_length=200,
            custom_id="kingdom:settings:launch:names",
        )
        self.add_item(
            discord.ui.Label(
                text=str(strings["settings_launch_modal_names_label"])[:45],
                component=self.names,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        strings = self._strings
        stack, busy = _needs_stack(strings)
        if busy:
            await interaction.followup.send(busy, ephemeral=True)
            return
        imposed = [
            name.strip() for name in str(self.names.value or "").split(",") if name.strip()
        ] or None
        try:
            await stack.kingdoms.launch(imposed)
            note = str(strings["settings_launch_done"])
        except Exception as exc:  # the panel reports, never raises
            logger.warning("kingdom: launch failed", exc_info=True)
            note = service_failure_note(strings, "settings_launch_failed", exc)
        await interaction.followup.send(note, ephemeral=True)


class _AssignModal(discord.ui.Modal):
    """Affecter un joueur en attente — id, royaume, rôle."""

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(title=str(strings["settings_assign_modal_title"])[:45])
        self._strings = strings
        # discord.py 2.7: TextInputs ride discord.ui.Label wrappers
        self.player_id = discord.ui.TextInput(required=True, max_length=32, custom_id="kingdom:settings:assign:player")
        self.kingdom = discord.ui.TextInput(required=True, max_length=64, custom_id="kingdom:settings:assign:kingdom")
        self.role = discord.ui.TextInput(
            placeholder="king", required=True, max_length=8, custom_id="kingdom:settings:assign:role"
        )
        self.add_item(
            discord.ui.Label(
                text=str(strings["settings_assign_modal_player_label"])[:45],
                component=self.player_id,
            )
        )
        self.add_item(
            discord.ui.Label(
                text=str(strings["settings_assign_modal_kingdom_label"])[:45],
                component=self.kingdom,
            )
        )
        self.add_item(
            discord.ui.Label(
                text=str(strings["settings_assign_modal_role_label"])[:45],
                component=self.role,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        strings = self._strings
        stack, busy = _needs_stack(strings)
        if busy:
            await interaction.followup.send(busy, ephemeral=True)
            return
        from botforge.mods.kingdom.models import LordRole

        try:
            role = LordRole(str(self.role.value).strip().lower())
        except ValueError:
            await interaction.followup.send(
                str(strings["settings_assign_bad_role"]), ephemeral=True
            )
            return
        try:
            await stack.kingdoms.assign(
                str(self.player_id.value).strip(), str(self.kingdom.value).strip(), role
            )
            note = str(strings["settings_assign_done"])
        except Exception as exc:  # the panel reports, never raises
            logger.warning("kingdom: assign failed", exc_info=True)
            note = service_failure_note(strings, "settings_assign_failed", exc)
        await interaction.followup.send(note, ephemeral=True)


class _AddKingdomModal(discord.ui.Modal):
    """Ajouter un royaume manuellement."""

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(title=str(strings["settings_add_kingdom_modal_title"])[:45])
        self._strings = strings
        self.name = discord.ui.TextInput(
            required=True, max_length=64, custom_id="kingdom:settings:add-kingdom:name"
        )
        self.add_item(
            discord.ui.Label(
                text=str(strings["settings_add_kingdom_modal_name_label"])[:45],
                component=self.name,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        strings = self._strings
        stack, busy = _needs_stack(strings)
        if busy:
            await interaction.followup.send(busy, ephemeral=True)
            return
        try:
            await stack.kingdoms.add_kingdom(str(self.name.value).strip())
            note = str(strings["settings_add_kingdom_done"]).format(
                str(self.name.value).strip()
            )
        except Exception as exc:  # the panel reports, never raises
            logger.warning("kingdom: add_kingdom failed", exc_info=True)
            note = service_failure_note(strings, "settings_add_kingdom_failed", exc)
        await interaction.followup.send(note, ephemeral=True)


class _RemoveModal(discord.ui.Modal):
    """Retirer un joueur/candidat — id + motif."""

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(title=str(strings["settings_remove_modal_title"])[:45])
        self._strings = strings
        self.player_id = discord.ui.TextInput(
            required=True, max_length=32, custom_id="kingdom:settings:remove:player"
        )
        self.reason = discord.ui.TextInput(
            placeholder="ss", required=False, max_length=200, custom_id="kingdom:settings:remove:reason"
        )
        self.add_item(
            discord.ui.Label(
                text=str(strings["settings_remove_modal_player_label"])[:45],
                component=self.player_id,
            )
        )
        self.add_item(
            discord.ui.Label(
                text=str(strings["settings_remove_modal_reason_label"])[:45],
                component=self.reason,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        strings = self._strings
        stack, busy = _needs_stack(strings)
        if busy:
            await interaction.followup.send(busy, ephemeral=True)
            return
        try:
            await stack.kingdoms.leave(
                str(self.player_id.value).strip(), str(self.reason.value or "").strip()
            )
            note = str(strings["settings_remove_done"]).format(
                str(self.player_id.value).strip()
            )
        except Exception as exc:  # the panel reports, never raises
            logger.warning("kingdom: leave failed", exc_info=True)
            note = service_failure_note(strings, "settings_remove_failed", exc)
        await interaction.followup.send(note, ephemeral=True)


async def _open_launch(interaction: discord.Interaction, strings: dict[str, str]) -> None:
    await interaction.response.send_modal(_LaunchModal(strings))


async def _open_assign(interaction: discord.Interaction, strings: dict[str, str]) -> None:
    await interaction.response.send_modal(_AssignModal(strings))


async def _open_add_kingdom(
    interaction: discord.Interaction, strings: dict[str, str]
) -> None:
    await interaction.response.send_modal(_AddKingdomModal(strings))


async def _open_remove(interaction: discord.Interaction, strings: dict[str, str]) -> None:
    await interaction.response.send_modal(_RemoveModal(strings))


_SETTINGS_HANDLERS: dict[str, Any] = {
    "launch": _open_launch,
    "start-season": _start_season,
    "start-beta": _start_beta,
    "status": _status,
    "season-mode": _season_mode,
    "assign": _open_assign,
    "add-kingdom": _open_add_kingdom,
    "remove": _open_remove,
}


__all__ = [
    "CONSOLE_VIEW_KEY",
    "SettingsActionButton",
    "console_buttons",
    "build_settings_panel",
    "settings_strings",
]
