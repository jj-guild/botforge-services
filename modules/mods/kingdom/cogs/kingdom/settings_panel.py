"""The ⚙️ Paramètres panel — the admin season cockpit (epic #412 T1).

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
- depart-fourche-v1 (Drasah 22/11): the FORMAT fork moved from the
  launch to the START — « Lancer » just prepares a setup season (+
  the sas question), then the cycle row offers BOTH departures:
  « Démarrer la saison classique » and « Démarrer la bêta ». Both
  distribute the sas's admitted realms; the beta departure arms the
  compressed weekend on the setup season, raises the parcours flag
  and starts the game. The flag follows the season — it never blocks
  a departure again (the 21/11 mutex trap Drasah hit live).
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

from .common import (
    close_window_if_unmoved,
    live_unique_window,
    locale_of,
    open_unique_ephemeral,
    service_failure_note,
    surface,
    wiring,
)

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
    # console-etats-regie-v1 (Drasah 21/11) : le faux départ — le
    # dernier recours de l'organisateur (demande sa confirmation).
    ("false-start", "settings_false_start_button", discord.ButtonStyle.danger),
    # fin-saison-v1 (Drasah 21/11) : « Terminer la saison » — la boucle
    # de test se referme proprement (archivage moteur + royaumes dormants).
    ("end-season", "settings_end_season_button", discord.ButtonStyle.danger),
)
# casquette-removal-v1 (Drasah 19/11): the hat op RETIRES from the
# console (11 actions) — the bypass lives in the code's own seams and
# the test kingdom rides the Distributeur's dedicated button.

_CONFIRM_ACTIONS = frozenset({"deploy", "sync", "reset"})
# console-etats-regie-v1 / depart-fourche-v1 : les gestes du CYCLE qui
# demandent leur confirmation (l'envoi de la saison, le départ bêta, le
# faux départ) — jamais le même namespace que la table : chaque carte
# porte ses propres ids.
_CYCLE_CONFIRM_ACTIONS = frozenset(
    {"start-season", "start-beta", "false-start", "end-season"}
)

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


async def _queued_lords() -> list[str]:
    """The season's QUEUED lords (display lines), best-effort.

    conscription-4-salons (Drasah 20/11): the seigneurerie reports the
    PEOPLE — the queue is the salon's heart, never an action surface.
    """
    stack = wiring()
    if stack is None:
        return []
    try:
        lords = await stack.kingdoms.lords()
    except Exception:  # noqa: BLE001 — the desk reports, never raises
        logger.warning("kingdom: the seigneurerie queue read failed", exc_info=True)
        return []
    return [
        f"• **{str(lord.display_name)}** (<@{str(lord.id)}>)"
        for lord in lords
        if not getattr(lord, "left", False)
        and (bool(getattr(lord, "in_queue", False)) or getattr(lord, "kingdom_id", None) is None)
    ]


async def build_seigneurerie_panel(guild_id: str) -> discord.ui.LayoutView:
    """Build the pinned seigneurerie panel — the lords' desk (admin only).

    conscription-4-salons (Drasah 20/11): salon 3 of the parcours —
    the PEOPLE (queue, candidates, assignments). A LIST + the existing
    assign/remove seams, no new mechanic: the actions are the SAME
    SettingsActionButton registrations the admin cockpit owns (one
    template, many surfaces — #395's direction).
    """
    from .apply_flow import _guild_locale

    strings = settings_strings(await _guild_locale(guild_id))
    lines = await _queued_lords()
    queue_block = (
        "\n".join(lines) if lines else str(strings["seigneurerie_queue_empty"])
    )
    row: Any = discord.ui.ActionRow()
    row.add_item(SettingsActionButton("assign", str(strings["settings_assign_button"]), discord.ButtonStyle.primary).item)
    row.add_item(SettingsActionButton("remove", str(strings["settings_remove_button"]), discord.ButtonStyle.danger).item)
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.TextDisplay(f"# {strings['seigneurerie_title']}"),
        discord.ui.TextDisplay(str(strings["seigneurerie_help"])),
        discord.ui.Separator(),
        discord.ui.TextDisplay(f"## {strings['seigneurerie_queue_header']}"),
        discord.ui.TextDisplay(queue_block),
        discord.ui.Separator(),
        row,
    )
    return surface("panel:mod:kingdom:seigneurerie", container)


async def build_settings_panel(guild_id: str) -> discord.ui.LayoutView:
    """Build the mod admin console — the v2 COCKPIT (Drasah 21/11).

    console-v2 (the approved mockup): the flat 11-button list becomes
    a contextual cockpit — the season state at a glance, ONE contextual
    « Le cycle » row (what makes sense NOW), and the fixed drawer rows
    (régie / atelier / beta) that open the ephemeral drawers. Every
    existing action survives: the actions table is unchanged, the
    buttons just moved into the cockpit or its drawers.

    console-etats-regie-v1 (Drasah 21/11): the header becomes the FIRST
    repère — the PARCOURS badge (bêta/normal, previously invisible)
    rides first, and the sas rides its own line; the started cycle row
    goes sober (the running ops stay in the 🧪 Beta & outils drawer),
    the launch wizard asks « ouvres-tu le sas ? » and the season's
    departure shuts the sas by itself.
    """
    from .apply_flow import _guild_locale

    locale = await _guild_locale(guild_id)
    strings = settings_strings(locale)
    from .panel import current_bot

    bot = current_bot()
    status_lines, phase = await _season_state(strings, bot=bot, guild_id=guild_id)

    # LE CYCLE — ONE contextual row, the phase decides (console-v2)
    cycle_row: Any = discord.ui.ActionRow()
    if phase == "off":
        # no season: prepare one — the launch modal creates a SETUP
        # season and starts NOTHING (Drasah 21/11: no more auto-start,
        # the season opens an admissions sas instead). The FORMAT is
        # no longer asked here (depart-fourche-v1): the departure
        # buttons own it — « Lancer » just prepares.
        cycle_row.add_item(
            SettingsActionButton(
                "launch", str(strings["settings_launch_button"]), discord.ButtonStyle.success
            ).item
        )
    elif phase == "setup":
        # depart-fourche-v1 (Drasah 22/11): the setup cycle row shows
        # BOTH departures — classic and beta. Each distributes the
        # sas's admitted realms; the beta one arms the compressed
        # weekend and the parcours flag rides the season. The beta
        # flag NEVER blocks a departure (the retired mutex could leave
        # the panel with NO working departure — Drasah hit it live).
        pending = await _pending_admissions()
        cycle_row.add_item(
            KingdomSettingsNavButton(
                "admissions", str(strings["settings_nav_admissions_button"]), len(pending)
            ).item
        )
        cycle_row.add_item(
            SettingsActionButton(
                "start-season",
                str(strings["settings_start_season_button"]),
                discord.ButtonStyle.success,
            ).item
        )
        cycle_row.add_item(
            SettingsActionButton(
                "start-beta",
                str(strings["settings_start_beta_button"]),
                discord.ButtonStyle.primary,
            ).item
        )
    else:
        # running season: a SOBER cycle (console-etats-regie-v1). Drawers
        # deconsolidation (Drasah 22/11) : le faux départ (le rembobinage
        # de secours, classique OU bêta) et « Terminer la saison » vivent
        # ICI, dans Le cycle — le tiroir 🧪 Bêta est retiré (l'état du
        # parcours se lit sur le badge du cockpit).
        cycle_row.add_item(
            KingdomSettingsNavButton(
                "admissions", str(strings["settings_nav_admissions_button"])
            ).item
        )
        cycle_row.add_item(
            SettingsActionButton(
                "false-start", str(strings["settings_false_start_button"]),
                discord.ButtonStyle.secondary,
            ).item
        )
        cycle_row.add_item(
            SettingsActionButton(
                "end-season", str(strings["settings_end_season_button"]),
                discord.ButtonStyle.danger,
            ).item
        )

    # LA RÉGIE / L'ATELIER — the fixed drawers, a click away
    regie_row: Any = discord.ui.ActionRow()
    regie_row.add_item(
        KingdomSettingsNavButton("regie", str(strings["settings_nav_regie_button"])).item
    )
    atelier_row: Any = discord.ui.ActionRow()
    atelier_row.add_item(
        KingdomSettingsNavButton("atelier", str(strings["settings_nav_atelier_button"])).item
    )

    # cockpit-lisible-v1 (Drasah 21/11) : une zone = UN titre + UNE
    # ligne qui dit à quoi ça sert (données, clé manquante = pas de
    # ligne — la leçon console-crash-v1 reste : .get, jamais [])
    def _zone_hint(key: str) -> discord.ui.Item[discord.ui.LayoutView]:
        return discord.ui.TextDisplay(str(strings.get(key) or ""))

    items: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['settings_title']}"),
        # parametres-restore-v1 (Drasah 20/11): the panel wears its
        # original section header under the title.
        discord.ui.TextDisplay(f"## {strings['settings_section']}"),
        discord.ui.Separator(),
        discord.ui.TextDisplay("\n".join(status_lines)),
        discord.ui.Separator(),
        discord.ui.TextDisplay(f"## {strings['settings_zone_cycle_label']}"),
        _zone_hint("settings_zone_cycle_hint"),
        # console-crash-v1 (Drasah 21/11): a missing hint key ONCE
        # emptied the whole console salon — the render crashed, the
        # refresh marked the live pin "unreadable — recreating", and
        # the superseded cleanup DELETED it before the recreate died
        # on the same crash. The cycle hint is DATA (#369): a missing
        # key degrades to a known-good line, never to an empty salon.
        discord.ui.TextDisplay(str(
            strings.get(f"settings_cycle_{phase}_hint")
            or strings.get("settings_cycle_running_hint")
            or strings.get("settings_cycle_off_hint")
            or ""
        )),
        cycle_row,
        # depart-fourche-v1: no mutex hint anymore — the departures are
        # exclusive with a RUNNING season by their own guards, never
        # with the beta state.
        discord.ui.Separator(),
        discord.ui.TextDisplay(f"## {strings['settings_zone_regie_label']}"),
        _zone_hint("settings_zone_regie_hint"),
        regie_row,
        discord.ui.Separator(),
        discord.ui.TextDisplay(f"## {strings['settings_zone_atelier_label']}"),
        _zone_hint("settings_zone_atelier_hint"),
        atelier_row,
    ]
    container = discord.ui.Container(*items, accent_colour=_ADMIN_COLOUR)
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
        before = live_unique_window(target)
        note = await _run_provisioning(target, action)
        await _safe_followup(target, note)
        # autoclose: the card retires, the note stays alone
        await close_window_if_unmoved(target, before)

    async def on_no(target: discord.Interaction) -> None:
        before = live_unique_window(target)
        await _safe_send(target, strings["settings_cancelled"])
        await close_window_if_unmoved(target, before)

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

        from .time_machine import run_mod_pin_refresh_pass

        deleted = 0
        swept_realms = 0
        if action == "reset":
            deleted = await delete_mod_scope(bot, guild_id, _MOD)
            # reset-convergence (Drasah 22/11) — le reset SDK ne touche
            # QUE les salons déclarés du mod : les catégories de royaumes
            # (hors scope, portées par l'habitat) vivaient leurs doublons
            # sans que rien ne les balaye jamais. La passe sweep ci-dessous
            # (realms.py) converge chaque famille : adoption + dédoublonnage
            # des salons déclarés + ordre + dormancy — best-effort, jamais
            # bloquant pour la reconstruction des salons du mod.
            from .realms import sweep_realm_structures

            try:
                swept_realms = await sweep_realm_structures(bot)
            except Exception:  # noqa: BLE001 — le reset ne rate jamais pour un sweep
                logger.warning("kingdom: the reset's realm sweep failed", exc_info=True)
                swept_realms = 0
        if swept_realms:
            logger.info("kingdom: the reset swept %d realm families", swept_realms)
        roles = await provision_mod_roles(bot, guild_id, _MOD)
        channels = (
            await provision_mod_channels(bot, guild_id, _MOD)
            if action in {"deploy", "reset"}
            else 0
        )
        pins = await ensure_mod_pins(bot, guild_id, _MOD)
        # reset-repins-v1 (Drasah 20/11): the reset re-lands the MOD's
        # pins too, not only the SDK menus — before this, the salons
        # came back EMPTY and the pins waited on the 5-min refresher
        # (« la catégorie admin est vide, rien n'a été remis »).
        # The pass is idempotent (fingerprint guard), so deploy and
        # sync simply heal early.
        pins += await run_mod_pin_refresh_pass(bot)
        # pins-diag-wired (Drasah 20/11): the diagnostic names, in plain
        # French, the failing step of every pinned surface — the admin
        # reads a diagnosis, never a silent empty salon again.
        from .pins_diag import admin_pin_lines

        diag = await admin_pin_lines(bot, guild_id)
    except Exception as exc:  # the panel reports, never raises
        logger.warning("kingdom: settings %s failed", action, exc_info=True)
        return str(strings["settings_error"]).format(str(exc)[:150])
    # the diagnostic rides every provisioning answer (pins-diag-wired)
    diag_block = "\n".join(diag) if diag else ""
    if action == "deploy":
        note = str(strings["settings_deploy_done"]).format(
            channels=channels, roles=roles, pins=pins
        )
    elif action == "sync":
        note = str(strings["settings_sync_done"]).format(pins=pins)
    else:
        note = str(strings["settings_reset_done"]).format(channels=deleted)
    if diag_block:
        note = f"{note}\n{diag_block}"
    return note


class SettingsActionButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:settings:(?P<action>[a-z0-9-]+)",
):
    """One restart-proof admin action of the 🛠️ console."""

    def __init__(
        self, action: str, label: str, style: discord.ButtonStyle | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"kingdom:settings:{action}"[:100],
                style=style or discord.ButtonStyle.secondary,
                disabled=disabled,
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
        # fin-saison-v1 : le geste ne vit que sur une saison LANCÉE —
        # un id cliqué depuis un écran périmé est refusé avant la carte
        if self.action == "end-season" and not await _season_live(wiring()):
            await _safe_send(interaction, str(strings["settings_end_season_not_running"]))
            return
        if self.action in _CONFIRM_ACTIONS:
            await open_unique_ephemeral(
                interaction, view=_confirm_card(strings, self.action)
            )
            return
        if self.action in _CYCLE_CONFIRM_ACTIONS:
            await open_unique_ephemeral(
                interaction, view=_cycle_confirm_card(strings, self.action)
            )
            return
        # settings-window-autoclose (Drasah 21/11): a direct action that
        # produced its note from inside a window RETIRES the window —
        # the note stays alone on screen (« sinon, ça me pollue trop »).
        before = live_unique_window(interaction)
        await _SETTINGS_HANDLERS[self.action](interaction, strings)
        await close_window_if_unmoved(interaction, before)


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
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    stack, busy = _needs_stack(strings)
    if busy:
        await interaction.followup.send(busy, ephemeral=True)
        return
    # depart-fourche-v1 (Drasah 22/11): the CLASSIC departure owns its
    # own format — a beta armed on the season (an older fork launch)
    # is disarmed NOW (the season rides at its normal pace), and the
    # parcours flag lowers with it (best-effort, the departure stands).
    try:
        season = await stack.kingdoms.current_season()
        if season is not None and bool(getattr(season, "beta_name", None)):
            events = getattr(stack, "events", None)
            if events is not None and hasattr(events, "deactivate_beta"):
                await events.deactivate_beta()
                logger.info("kingdom: the classic departure disarmed a leftover beta type")
    except Exception:  # noqa: BLE001 — a disarm failure never blocks the start
        logger.warning("kingdom: the classic departure disarm failed", exc_info=True)
    try:
        if await _lower_beta_flag(interaction):
            logger.info("kingdom: the classic departure lowered a lingering beta flag")
    except Exception:  # noqa: BLE001 — the flag is best-effort, the start stands
        logger.warning("kingdom: the classic departure flag lowering failed", exc_info=True)
    try:
        await stack.kingdoms.start_season()
        note = str(strings["settings_start_season_done"])
    except Exception as exc:  # the panel reports, never raises
        logger.warning("kingdom: start_season failed", exc_info=True)
        note = service_failure_note(strings, "settings_start_season_failed", exc)
    else:
        # console-etats-regie-v1 (Drasah 21/11) : « de base, oui, le sas
        # se ferme » — le départ de la saison ferme le sas LUI-MÊME (le
        # casting part avec les royaumes validés). Les retardataires
        # passent par la régie (ré-ouverture ponctuelle) ou le geste
        # « Ajouter un royaume » (injection directe).
        from .regie import set_switch

        if not await set_switch(
            interaction.client, str(interaction.guild_id or ""), "season_entry_open", False
        ):
            logger.warning("kingdom: the departure's sas close could not be stored")
        # live-pin-v1: the cockpit's sas line flips with the departure
        await refresh_live_pins_after(interaction)
        # realm-content-v1 (Drasah 21/11) : au DÉPART, les fiches
        # réelles remplacent les états d'attente — chaque royaume
        # engagé reçoit la passe (best-effort, jamais bloquante).
        try:
            from .realm_content import deploy_all_realms_content

            touched = await deploy_all_realms_content(interaction.client)
            logger.info("kingdom: season departure fed %d realm salons", touched)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom: season departure content pass failed", exc_info=True)
    await interaction.followup.send(note, ephemeral=True)


async def _false_start(interaction: discord.Interaction, strings: dict[str, str]) -> None:
    """🚫 Faux départ — rebasculer dans l'état d'ORIGINE (Drasah 21/11).

    « ça rebascule dans l'état d'origine : saison ouverte (préparation),
    sas ouvert, et les royaumes DOIVENT REDEMANDER leur inscription » —
    par sécurité le royaume reconfirme lui-même (le chemin normal
    dormant → sas → validation), jamais un état hybride : le moteur
    revient en setup (le seam ``set_phase`` — les royaumes moteurs
    restent), chaque royaume ENGAGÉ est libéré (dormant, engagement et
    demande remis à zéro), le sas s'ouvre.
    """
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    stack, busy = _needs_stack(strings)
    if busy:
        await interaction.followup.send(busy, ephemeral=True)
        return
    released = 0
    try:
        season = await stack.kingdoms.current_season()
        if season is None:
            await interaction.followup.send(str(strings["settings_false_start_no_season"]), ephemeral=True)
            return
        await stack.kingdoms.set_phase("setup")
        realms_service = getattr(stack, "realms", None)
        if realms_service is not None:
            for realm in await realms_service.realms():
                if getattr(realm, "engagement", None):
                    await realms_service.release_engagement(str(realm.id))
                    released += 1
        note = str(strings["settings_false_start_done"]).format(released=released)
    except Exception as exc:  # the panel reports, never raises
        logger.warning("kingdom: false start failed", exc_info=True)
        note = service_failure_note(strings, "settings_false_start_failed", exc)
    else:
        # le sas se RÉ-OUVRE au faux départ (l'état d'origine)
        from .regie import set_switch

        if not await set_switch(
            interaction.client, str(interaction.guild_id or ""), "season_entry_open", True
        ):
            logger.warning("kingdom: the false start's sas reopen could not be stored")
        # live-pin-v1: the cockpit reflects the false start at once
        await refresh_live_pins_after(interaction)
    await interaction.followup.send(note, ephemeral=True)


async def _drain_sas(stack: Any, bot: Any, locale: str, dm_key: str) -> int:
    """sas-cycle-v1 (Drasah 21/11) : fermer le SAS VIDE la salle d'attente.

    « On vide le sas — les royaumes qui ont demandé sont prévenus en
    MP automatiquement ; pas de motif, la fermeture EST l'information. »
    Chaque demande d'entrée est retirée et le Roi reçoit la note neutre
    (best-effort TOTAL via le seam DM : un Roi aux MP fermés ne câble
    jamais la fermeture). Le même moteur sert la fermeture MANUELLE du
    tiroir 🎚️ et « 🏁 Terminer la saison » (le texte change, pas la
    mécanique) — le SAS est la volonté de l'admin, jamais un état qui
    traîne (annonce-ready : une note paramétrable, zéro send ad hoc).
    """
    service = getattr(stack, "realms", None)
    if service is None:
        return 0
    from .common import dm_user_safe, mod_catalog

    try:
        strings = dict(mod_catalog().section("kingdom.settings", locale))
    except Exception:  # noqa: BLE001 — unreadable catalog = the fr default
        strings = {}
    dm_text = str(strings.get(dm_key, str(dm_key)))
    try:
        realms = await service.realms()
    except Exception:  # noqa: BLE001 — an unreadable room stays, loudly
        logger.warning("kingdom: the sas drain read failed", exc_info=True)
        return 0
    drained = 0
    for realm in realms:
        if not getattr(realm, "join_request", None):
            continue
        try:
            await service.clear_join_request(str(realm.id))
        except Exception:  # noqa: BLE001 — one realm never stops the sweep
            logger.warning("kingdom: sas drain failed (%s)", realm.id, exc_info=True)
            continue
        drained += 1
        await dm_user_safe(bot, str(realm.king_id), dm_text)
    if drained:
        logger.info("kingdom: the sas drained %d waiting realm(s)", drained)
    return drained


async def _end_season(interaction: discord.Interaction, strings: dict[str, str]) -> None:
    """🏁 Terminer la saison — fermer la boucle de test proprement.

    fin-saison-v1 (Drasah 21/11) : « je ne peux plus rien refaire,
    Blanc est en saison et je n'ai aucun bouton pour terminer ». Le
    moteur sait déjà faire (l'archive + le rembobinage du §3.3) ; ce
    geste les enchaîne : les royaumes repartent DORMANT (habitat
    rendormi, hub basculé), la donnée moteur est archivée puis
    essuyée, la console repasse à l'état vierge. Le Palmarès complet
    reste couvert par la file (fin de saison « pour de vrai »).
    """
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    stack, busy = _needs_stack(strings)
    if busy:
        await interaction.followup.send(busy, ephemeral=True)
        return
    try:
        season = await stack.kingdoms.current_season()
        if season is None or str(getattr(season, "phase", "")) != "started":
            await interaction.followup.send(
                str(strings["settings_end_season_not_running"]), ephemeral=True
            )
            return
        from .apply_flow import _guild_locale

        locale = await _guild_locale(str(interaction.guild_id or ""))
        guild = getattr(interaction, "guild", None)
        realms_service = getattr(stack, "realms", None)
        released = 0
        if guild is not None and realms_service is not None:
            from .realms import deploy_realm_hub, ensure_realm_structure

            for realm in await realms_service.realms():
                if not getattr(realm, "engagement", None):
                    continue
                # l'habitat se rendort AVANT le rembobinage moteur (la
                # coquille est pérenne, seule sa saison part) — best-effort
                try:
                    ids = await ensure_realm_structure(guild, realm, dormant=True)
                    hub_message = await deploy_realm_hub(guild, realm, locale=locale)
                    if hub_message:
                        ids["hub_message"] = hub_message
                    if ids:
                        await realms_service.save_habitat(str(realm.id), ids)
                except Exception:  # noqa: BLE001 — le sommeil d'un royaume n'arrête jamais la fin
                    logger.warning(
                        "kingdom: realm habitat sleep failed (%s)", realm.id, exc_info=True
                    )
                await realms_service.release_engagement(str(realm.id))
                released += 1
        # le rembobinage moteur EN DERNIER : archive puis essuie la
        # saison (royaumes, seigneurs, attaques — le §3.3 du contrat)
        await stack.kingdoms.reset()
        note = str(strings["settings_end_season_done"]).format(released=released)
        # depart-fourche-v1 : une saison qui finit baisse le drapeau
        # parcours — la bêta est finie, le parcours redevient normal
        # (la boucle bêta, si elle vient, le relèvera elle-même).
        try:
            if await _lower_beta_flag(interaction):
                logger.info("kingdom: the end of season lowered the beta flag")
        except Exception:  # noqa: BLE001 — la fin ne rate jamais pour un drapeau
            logger.warning("kingdom: the end-of-season flag lowering failed", exc_info=True)
        # sas-cycle-v1 (Drasah 21/11) : la fin de saison FERME le sas —
        # le seul geste AUTOMATIQUE du cycle (la réouverture restera
        # manuelle) — et vidange la salle d'attente avec le MP de
        # prévention aux Rois (best-effort, jamais bloquant).
        try:
            from .regie import set_switch

            await set_switch(
                interaction.client,
                str(interaction.guild_id or ""),
                "season_entry_open",
                False,
            )
            await _drain_sas(
                stack, interaction.client, locale, "settings_sas_drain_season_dm"
            )
        except Exception:  # noqa: BLE001 — la fin ne rate jamais pour un MP
            logger.warning("kingdom: the end-of-season sas close failed", exc_info=True)
    except Exception as exc:  # the panel reports, never raises
        logger.warning("kingdom: end season failed", exc_info=True)
        note = service_failure_note(strings, "settings_failed", exc)
    else:
        # live-pin-v1: le cockpit repasse à l'état vierge à l'instant
        await refresh_live_pins_after(interaction)
    await interaction.followup.send(note, ephemeral=True)


def _cycle_confirm_card(strings: dict[str, str], action: str) -> discord.ui.LayoutView:
    """The cycle's confirm card (les départs de la saison, le faux départ).

    Same one-window rule as the provisioning card; the ids live in
    ``kingdom:cycle-confirm:`` — their OWN namespace, never the
    settings table's (the double-click lesson of the first card).
    """
    yes_label = (
        strings["settings_start_beta_confirm_button"]
        if action == "start-beta"
        else strings["settings_start_season_confirm_button"]
        if action == "start-season"
        else strings["settings_false_start_confirm_button"]
        if action == "false-start"
        else strings["settings_end_season_confirm_button"]
    )
    yes: discord.ui.Button[Any] = discord.ui.Button(
        label=str(yes_label)[:80],
        custom_id=f"kingdom:cycle-confirm:{action}:yes",
        style=discord.ButtonStyle.danger,
    )
    no: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["settings_cycle_cancel_button"])[:80],
        custom_id=f"kingdom:cycle-confirm:{action}:no",
        style=discord.ButtonStyle.secondary,
    )

    async def on_yes(target: discord.Interaction) -> None:
        if not target.response.is_done():
            await target.response.defer(ephemeral=True)
        before = live_unique_window(target)
        await _CYCLE_CONFIRM_HANDLERS[action](target, strings_of(target))
        # autoclose: the confirm card retires with its verdict
        await close_window_if_unmoved(target, before)

    async def on_no(target: discord.Interaction) -> None:
        before = live_unique_window(target)
        await _safe_send(target, strings["settings_cancelled"])
        await close_window_if_unmoved(target, before)

    yes.callback = on_yes
    no.callback = on_no
    key = (
        "settings_start_beta_confirm" if action == "start-beta"
        else "settings_start_season_confirm" if action == "start-season"
        else "settings_false_start_confirm" if action == "false-start"
        else "settings_end_season_confirm"
    )
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.TextDisplay(
            f"**{strings[f'{key}_title']}**\n{strings[f'{key}_hint']}"
        ),
        accent_colour=discord.Colour(0xED4245),
    )
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row.add_item(yes)
    row.add_item(no)
    container.add_item(row)
    surface_key = (
        "panel:mod:kingdom:cycle:confirm-start-beta"
        if action == "start-beta"
        else "panel:mod:kingdom:cycle:confirm-start"
        if action == "start-season"
        else "panel:mod:kingdom:cycle:confirm-false-start"
        if action == "false-start"
        else "panel:mod:kingdom:cycle:confirm-end-season"
    )
    return surface(surface_key, container)


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
    """🚀 Démarrer la bêta — the BETA departure (depart-fourche-v1).

    Drasah 22/11 : « quand j'appuie sur Démarrer la bêta, ça devrait
    envoyer les personnes dans le SAS dans la saison ». The gesture is
    a DISTRIBUTION, not a parcours toggle: it arms the compressed
    weekend on the setup season, raises the parcours flag, starts the
    game (the sas's admitted realms depart) and closes the sas — the
    same engine as the classic departure, with the beta format on.
    A season that already runs refuses (Drasah : « il faut finir
    d'abord »).
    """
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    stack, busy = _needs_stack(strings)
    if busy:
        await interaction.followup.send(busy, ephemeral=True)
        return
    try:
        season = await stack.kingdoms.current_season()
    except Exception:  # noqa: BLE001 — the panel reports, never raises
        logger.warning("kingdom: the beta departure season read failed", exc_info=True)
        season = None
    if season is None:
        await interaction.followup.send(str(strings["settings_false_start_no_season"]), ephemeral=True)
        return
    if str(getattr(season, "phase", "")) != "setup":
        await interaction.followup.send(str(strings["settings_start_blocked_running"]), ephemeral=True)
        return
    try:
        await _arm_compressed_beta(stack)
    except Exception as exc:  # the panel reports, never raises
        logger.warning("kingdom: the beta departure arming failed", exc_info=True)
        await interaction.followup.send(
            service_failure_note(strings, "settings_launch_beta_failed", exc), ephemeral=True
        )
        return
    # ONE beta (Drasah 21/11): the departure raises the parcours flag —
    # a beta season runs under beta rules (the gate bends NOW)
    try:
        await _raise_beta_flag(interaction)
    except Exception:  # noqa: BLE001 — the flag is best-effort
        logger.warning("kingdom: the beta departure flag arming failed", exc_info=True)
    try:
        await stack.kingdoms.start_season()
        note = str(strings["settings_beta_started_season"])
    except Exception as exc:  # the panel reports, never raises
        logger.warning("kingdom: the beta departure start failed", exc_info=True)
        note = service_failure_note(strings, "settings_start_season_failed", exc)
    else:
        # depart-fourche-v1: the beta departure closes the sas and
        # feeds the realm content — the SAME engine as the classic one
        from .regie import set_switch

        if not await set_switch(
            interaction.client, str(interaction.guild_id or ""), "season_entry_open", False
        ):
            logger.warning("kingdom: the beta departure's sas close could not be stored")
        await refresh_live_pins_after(interaction)
        try:
            from .realm_content import deploy_all_realms_content

            touched = await deploy_all_realms_content(interaction.client)
            logger.info("kingdom: beta departure fed %d realm salons", touched)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom: the beta departure content pass failed", exc_info=True)
        try:
            from .conscription_gate import run_conscription_gate_pass

            await run_conscription_gate_pass(interaction.client, str(interaction.guild_id or ""))
        except Exception:  # noqa: BLE001 — the gate heals on the next pass
            logger.warning("kingdom: the beta departure gate pass failed", exc_info=True)
    await interaction.followup.send(note, ephemeral=True)


_CYCLE_CONFIRM_HANDLERS: dict[str, Any] = {
    "start-season": _start_season,
    "start-beta": _start_beta,
    "false-start": _false_start,
    "end-season": _end_season,
}


async def _season_state(
    strings: dict[str, str],
    bot: Any | None = None,
    guild_id: str = "",
) -> tuple[list[str], str]:
    """The season header lines + the cycle state, one best-effort read.

    console-v2 (Drasah 21/11): the cockpit and the old status card
    share ONE read — the lines render in the panel's header, and the
    state (``off`` / ``setup`` / ``started``) picks the cycle row.
    ``setup`` = the admissions sas (launch preps, start_season starts).

    console-etats-regie-v1: the header answers Drasah's first question
    (« j'arrive pas à déterminer mon mode ») — the PARCOURS badge
    (🧪 Bêta / normal) rides FIRST, and the sas rides its own line
    (open/closed, the latecomers' régie switch).
    """
    stack = wiring()
    kingdoms: list[str] = []
    queued = 0
    enrolled = 0
    phase = str(strings["settings_phase_unknown"])
    mode = str(strings["settings_mode_free"])
    state = "off"
    beta = False
    if stack is not None and getattr(stack, "kingdoms", None) is not None:
        try:
            season = await stack.kingdoms.current_season()
            if season is not None:
                beta = bool(getattr(season, "beta_name", None))
        except Exception:
            logger.warning("kingdom: season read failed", exc_info=True)
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
                raw = str(getattr(season, "phase", "started"))
                state = "setup" if raw == "setup" else "started"
                phase = str(strings.get(
                    f"settings_phase_{raw}",
                    strings["settings_phase_unknown"],
                ))
                mode = str(
                    strings["settings_mode_imposed"]
                    if season.imposed_kingdoms
                    else strings["settings_mode_free"]
                )
                beta = beta or bool(getattr(season, "beta_name", None))
        except Exception:
            logger.warning("kingdom: season read failed", exc_info=True)
    if bot is not None:
        try:
            from .camp_beta import kingdom_is_beta

            beta = beta or await kingdom_is_beta(bot, guild_id)
        except Exception:  # noqa: BLE001 — the badge never breaks the cockpit
            logger.warning("kingdom: the beta badge read failed", exc_info=True)
    lines = [
        str(strings["settings_status_parcours_beta" if beta else "settings_status_parcours_normal"]),
        f"📍 **{strings['settings_status_phase']} : {phase}**",
        mode,
    ]
    if bot is not None and guild_id:
        # the sas line — the latecomers' régie switch, live (best-effort)
        try:
            from .regie import regie_open

            sas_open = await regie_open(bot, guild_id, "season_entry_open")
            lines.append(str(
                strings["settings_status_sas_open" if sas_open else "settings_status_sas_closed"]
            ))
        except Exception:  # noqa: BLE001
            logger.warning("kingdom: the sas line read failed", exc_info=True)
    # cockpit-lisible-v1 (Drasah 21/11 « tout est compressé, ça donne pas
    # envie d'être lu ») : la MATIÈRE a ses lignes dédiées — un titre
    # qui compte, puis les noms, puis l'équipage sur UNE ligne.
    lines.append(str(strings["settings_status_kingdoms_header"]).format(count=len(kingdoms)))
    lines.append(str(strings["settings_status_kingdoms_names"]).format(
        names=", ".join(kingdoms) if kingdoms else strings["settings_status_empty"]
    ))
    lines.append(str(strings["settings_status_crew_line"]).format(
        enrolled=enrolled if enrolled else strings["settings_status_empty"],
        queued=queued if queued else strings["settings_status_empty"],
    ))
    return lines, state


async def _status(interaction: discord.Interaction, strings: dict[str, str]) -> None:
    """Answer with the season status card (kingdoms, queue, players)."""
    lines, _state = await _season_state(strings)
    await open_unique_ephemeral(interaction, "\n".join([
        f"# {strings['settings_status_title']}", *lines
    ]))


async def _pending_admissions() -> list[Any]:
    """The realms waiting on the admin's season-entry gesture (t2a).

    The admissions drawer and the cockpit's badge share ONE read — the
    realm service owns the truth, the console only reports.
    """
    stack = wiring()
    if stack is None:
        return []
    from .validation import _realms_with_join_request

    return list(await _realms_with_join_request(stack))


# ---------------------------------------------------------------------------
# console-v2 (Drasah 21/11): the drawers — ONE nav button, four
# ephemeral windows. Nothing new under the hood: every button inside is
# an EXISTING registration (SettingsActionButton, the realm-entry
# decisions), the drawer only lays them out where the mockup put them.
# ---------------------------------------------------------------------------

_DRAWERS: dict[str, str] = {
    "admissions": "panel:mod:kingdom:admin:admissions",
    "regie": "panel:mod:kingdom:admin:regie",
    "atelier": "panel:mod:kingdom:admin:atelier",
}


def _admissions_drawer(
    strings: dict[str, str],
    vstrings: dict[str, str],
    realms: list[Any],
    admitted: list[Any] | None = None,
    ejectable: bool = False,
    dormant: list[Any] | None = None,
) -> discord.ui.LayoutView:
    """The sas — every join request with its decision buttons (t2a).

    cockpit-lisible-v1 (Drasah 21/11): a request disappears from the
    pending on ✅, but the operator must SEE what he already let in —
    the « ✅ Admis en saison » block sits right under the requests.

    eject-sas-v1 (Drasah 21/11) : un royaume admis à tort se corrige
    AVANT le départ — chaque admis porte « 🗑️ Éjecter » PENDANT la
    fenêtre du sas (préparation). La saison lancée, LE SAS EST FERMÉ :
    la section passe en lecture et la ligne dit pourquoi.
    ``admitted`` = les COQUILLES engagées (objets realm, le nom se lit
    dessus).
    """
    from .validation import ValidationEjectButton, ValidationRealmEntryButton, fmt_paris

    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['settings_admissions_title']}"),
        discord.ui.TextDisplay(str(strings["settings_admissions_hint"])),
        discord.ui.Separator(),
    ]
    if realms:
        for realm in realms:
            requested = int(
                (getattr(realm, "join_request", {}) or {}).get("requested_at", 0) or 0
            )
            blocks.append(
                discord.ui.TextDisplay(
                    str(vstrings["realm_request_row"]).format(
                        name=getattr(realm, "name", "?"),
                        king=getattr(realm, "king_name", "?"),
                        when=fmt_paris(requested),
                    )
                )
            )
            excerpt = str(getattr(realm, "presentation", "") or "").strip()
            if excerpt:
                blocks.append(
                    discord.ui.TextDisplay(
                        str(vstrings["realm_request_presentation"]).format(
                            excerpt=excerpt[:280] + ("…" if len(excerpt) > 280 else "")
                        )
                    )
                )
            row: Any = discord.ui.ActionRow()
            row.add_item(
                ValidationRealmEntryButton(
                    str(realm.slug), "ok", str(vstrings["realm_accept_button"])[:80],
                    discord.ButtonStyle.success,
                )
            )
            row.add_item(
                ValidationRealmEntryButton(
                    str(realm.slug), "no", str(vstrings["realm_refuse_button"])[:80],
                    discord.ButtonStyle.danger,
                )
            )
            blocks.append(row)
            blocks.append(discord.ui.Separator())
    else:
        blocks.append(discord.ui.TextDisplay(str(strings["settings_admissions_empty"])))
    # what is already IN (the names — one per line, no ceremony)
    blocks.append(discord.ui.Separator())
    blocks.append(discord.ui.TextDisplay(f"## {strings['settings_admissions_admitted_title']}"))
    if admitted:
        for realm in admitted:
            name = str(getattr(realm, "name", "?"))
            if ejectable:
                blocks.append(discord.ui.TextDisplay(f"- **{name}**"))
                row: Any = discord.ui.ActionRow()
                row.add_item(
                    ValidationEjectButton(
                        str(getattr(realm, "slug", "")), str(vstrings["realm_eject_button"])[:80]
                    )
                )
                blocks.append(row)
            else:
                blocks.append(discord.ui.TextDisplay(f"- {name}"))
        # la saison partie : le sas est FERMÉ, la section devient lecture
        if not ejectable:
            blocks.append(
                discord.ui.TextDisplay(str(strings["settings_admissions_eject_closed_hint"]))
            )
    else:
        blocks.append(
            discord.ui.TextDisplay(str(strings["settings_admissions_admitted_empty"]))
        )
    # ejection-archive-v1 (22/11) : les coquilles DORMANTES — libérées
    # par une éjection, jamais encore demandées, ou refusées — avec le
    # geste 📦 Archiver (sortir du jeu sans rien détruire)
    dormant = list(dormant or [])
    blocks.append(discord.ui.Separator())
    blocks.append(discord.ui.TextDisplay(f"## {strings['settings_admissions_dormant_title']}"))
    blocks.append(discord.ui.TextDisplay(str(strings["settings_admissions_dormant_hint"])))
    if dormant:
        from .validation import ValidationArchiveButton

        for realm in dormant:
            name = str(getattr(realm, "name", "?"))
            blocks.append(discord.ui.TextDisplay(f"- **{name}**"))
            row: Any = discord.ui.ActionRow()
            row.add_item(
                ValidationArchiveButton(
                    str(getattr(realm, "id", "")),
                    str(vstrings.get("archive_button", "📦 Archiver"))[:80],
                )
            )
            blocks.append(row)
    else:
        blocks.append(discord.ui.TextDisplay(str(strings["settings_admissions_dormant_empty"])))
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        *blocks, accent_colour=_ADMIN_COLOUR
    )
    return surface(_DRAWERS["admissions"], container)


def _regie_drawer(
    strings: dict[str, str],
    states: dict[str, bool] | None = None,
    season_live: bool = True,
    archived: list[Any] | None = None,
    guild_id: str = "",
    dormant: list[Any] | None = None,
) -> discord.ui.LayoutView:
    """Les interrupteurs + les gestes ponctuels — un tiroir.

    console-etats-regie-v1 (Drasah 21/11) : la RÉGIE au sens propre —
    les ON/OFF de la vie des joueurs (données #369, défaut = OUVERT),
    puis les modals moteur existants (le tiroir de la console-v2).
    """
    states = states or {}
    switch_blocks: list[discord.ui.Item[discord.ui.LayoutView]] = []
    from .regie import REGIE_SWITCHES, SWITCH_LABEL_KEYS

    for key in REGIE_SWITCHES:
        open_ = bool(states.get(key, True))
        style = discord.ButtonStyle.success if open_ else discord.ButtonStyle.danger
        row: Any = discord.ui.ActionRow()
        row.add_item(
            KingdomRegieSwitchButton(
                key, str(strings[SWITCH_LABEL_KEYS[key]]), open_, style
            ).item
        )
        switch_blocks.append(row)
    # lancement-fourche-v1 (Drasah 21/11 « le sas dit ouvert mais Blanc ne
    # voit rien ») : sans saison, le sas ne s'applique à RIEN — la ligne
    # le dit, le flou disparaît (le switch garde sa valeur pour la suite)
    if not season_live:
        switch_blocks.append(
            discord.ui.TextDisplay(str(strings["settings_regie_sas_idle_hint"]))
        )
    row_button: Any = discord.ui.ActionRow()
    row_button.add_item(
        SettingsActionButton(
            "assign", str(strings["settings_assign_button"]), discord.ButtonStyle.primary
        ).item
    )
    row_button.add_item(
        SettingsActionButton(
            "add-kingdom", str(strings["settings_add_kingdom_button"]), discord.ButtonStyle.primary
        ).item
    )
    row_button.add_item(
        SettingsActionButton(
            "remove", str(strings["settings_remove_button"]), discord.ButtonStyle.danger
        ).item
    )
    row_button.add_item(
        SettingsActionButton(
            "season-mode", str(strings["settings_season_mode_button"]), discord.ButtonStyle.secondary
        ).item
    )
    # reset-joueurs-v1 (Drasah 22/11) : l'outillage de test — les joueurs
    # sortent des royaumes hors saison, les coquilles partent archivées
    row_button.add_item(
        KingdomRegieResetPlayersButton(
            "-players",
            guild_id or "0",  # un tiroir sans guilde reste un id valide
            str(strings["settings_regie_reset_button"])[:80],
            discord.ButtonStyle.danger,
        ).item
    )
    # ejection-archive-v1 (22/11) : le vestibule des royaumes ARCHIVÉS —
    # ♻️ Restaurer (MP au Roi fondateur) ou 🗑️ Supprimer définitivement
    archived = list(archived or [])
    archive_blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.Separator(),
        discord.ui.TextDisplay(f"## {strings['settings_regie_archived_title']}"),
        discord.ui.TextDisplay(str(strings["settings_regie_archived_hint"])),
    ]
    if archived:
        for realm in archived:
            name = str(getattr(realm, "name", "?"))
            archive_blocks.append(discord.ui.TextDisplay(f"- **{name}**"))
            row = _realm_button_row(
                "restore", strings["settings_regie_restore_button"],
                discord.ButtonStyle.success,
                "purge", strings["settings_regie_purge_button"],
                discord.ButtonStyle.danger,
                str(getattr(realm, "id", "")), guild_id,
            )
            archive_blocks.append(row)
    else:
        archive_blocks.append(
            discord.ui.TextDisplay(str(strings["settings_regie_archived_empty"]))
        )
    # drain-coquilles-v1 (Drasah 22/11, Check 135) : les coquilles
    # DORMANTES (hors saison, hors sas) exposent la purge DIRECTE — le
    # fondateur y est attaché à vie (king-cannot-leave), détruire la
    # coquille est sa seule porte de sortie ; l'admin la tient ici,
    # carte rouge de confirmation incluse (le même geste que les
    # archivées, UN seul bloc réutilisé).
    dormant_blocks: list[discord.ui.Item[discord.ui.LayoutView]] = []
    dormant = list(dormant or [])
    if dormant:
        dormant_blocks.append(discord.ui.Separator())
        dormant_blocks.append(
            discord.ui.TextDisplay(f"## {strings['settings_regie_dormant_title']}")
        )
        dormant_blocks.append(
            discord.ui.TextDisplay(str(strings["settings_regie_dormant_hint"]))
        )
        for realm in dormant:
            name = str(getattr(realm, "name", "?"))
            dormant_blocks.append(discord.ui.TextDisplay(f"- **{name}**"))
            row = _realm_button_row(
                "purge", strings["settings_regie_purge_button"],
                discord.ButtonStyle.danger,
                "purge-no", strings["settings_regie_purge_cancel_button"],
                discord.ButtonStyle.secondary,
                str(getattr(realm, "id", "")), guild_id,
            )
            dormant_blocks.append(row)
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.TextDisplay(f"# {strings['settings_regie_title']}"),
        discord.ui.TextDisplay(str(strings["settings_regie_hint"])),
        discord.ui.Separator(),
        discord.ui.TextDisplay(f"## {strings['settings_regie_switches_label']}"),
        *switch_blocks,
        discord.ui.Separator(),
        discord.ui.TextDisplay(f"## {strings['settings_regie_actions_label']}"),
        row_button,
        *archive_blocks,
        *dormant_blocks,
        accent_colour=_ADMIN_COLOUR,
    )
    return surface(_DRAWERS["regie"], container)


def _atelier_drawer(strings: dict[str, str], ops_strings: dict[str, str]) -> discord.ui.LayoutView:
    """The server's emergency hand — provisioning + the game clock.

    The 5-min healing pass keeps running whatever the drawer does: the
    atelier is only the deliberate hand overruled on top.
    """
    row: Any = discord.ui.ActionRow()
    row.add_item(
        SettingsActionButton(
            "deploy", str(strings["settings_deploy_button"]), discord.ButtonStyle.primary
        ).item
    )
    row.add_item(
        SettingsActionButton(
            "sync", str(strings["settings_sync_button"]), discord.ButtonStyle.secondary
        ).item
    )
    row.add_item(
        SettingsActionButton(
            "reset", str(strings["settings_reset_button"]), discord.ButtonStyle.danger
        ).item
    )
    # the mod-scoped console ops (relaunch / reset / clock): the SAME
    # restart-proof DynamicItems the registry owns, re-rendered with
    # the GUILD locale's labels (stable custom ids, localized text)
    second_row: Any = discord.ui.ActionRow()
    for button in console_buttons(ops_strings, False):
        second_row.add_item(button.item)
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.TextDisplay(f"# {strings['settings_atelier_title']}"),
        discord.ui.TextDisplay(str(strings["settings_atelier_hint"])),
        discord.ui.Separator(),
        row,
        second_row,
        discord.ui.Separator(),
        discord.ui.TextDisplay(str(strings["settings_atelier_heal_note"])),
        accent_colour=_ADMIN_COLOUR,
    )
    return surface(_DRAWERS["atelier"], container)


async def _season_live(stack: Any | None) -> bool:
    """Whether a classic season is LAUNCHED (mutex-beta-saison)."""
    if stack is None or getattr(stack, "kingdoms", None) is None:
        return False
    try:
        season = await stack.kingdoms.current_season()
        return season is not None and str(getattr(season, "phase", "started")) == "started"
    except Exception:  # noqa: BLE001 — a read, never a crash
        logger.warning("kingdom: the season phase read failed", exc_info=True)
        return False


async def _build_drawer(
    drawer: str, locale: str, bot: Any | None = None, guild_id: str = ""
) -> discord.ui.LayoutView:
    """Assemble the asked drawer in the guild's locale."""
    from .common import mod_catalog

    strings = settings_strings(locale)
    if drawer == "admissions":
        realms = await _pending_admissions()
        admitted = await _admitted_realms()
        vstrings = dict(mod_catalog().section("kingdom.validation", str(locale)[:2]))
        # eject-sas-v1 : l'éjection ne vit QUE dans la fenêtre du sas
        # (préparation) — la saison lancée, la section devient lecture
        ejectable = False
        try:
            stack = wiring()
            season = await stack.kingdoms.current_season() if stack is not None else None
            ejectable = season is not None and str(getattr(season, "phase", "")) == "setup"
        except Exception:  # noqa: BLE001 — a read, never a crash
            logger.warning("kingdom: the admissions phase read failed", exc_info=True)
        view = _admissions_drawer(
            strings, vstrings, realms, admitted, ejectable=ejectable,
            dormant=await _dormant_realms(),
        )
    elif drawer == "regie":
        states: dict[str, bool] = {}
        season_live = False
        if bot is not None and guild_id:
            from .regie import read_regie

            try:
                states = await read_regie(bot, guild_id)
            except Exception:  # noqa: BLE001 — the drawer reads defaults
                logger.warning("kingdom: the régie drawer read failed", exc_info=True)
        # le hint du sas ne vit QUE sans saison (réglé pour l'avenir)
        try:
            stack = wiring()
            season_live = stack is not None and (
                await stack.kingdoms.current_season() is not None
            )
        except Exception:  # noqa: BLE001 — a read, never a crash
            season_live = False
        # drawer-build-v1 (22/11, incident « n'a pas répondu à temps ») :
        # archivés et dormants puisent dans LA MÊME liste de coquilles —
        # UNE lecture, deux filtres (avant : deux parcours complets de
        # la base, et la pile de lectures regardait le chrono de 3 s).
        shells = await _all_shells()

        def _by_name(realm: Any) -> str:
            return str(getattr(realm, "name", "?"))

        view = _regie_drawer(
            strings, states, season_live=season_live,
            archived=sorted(
                (r for r in shells if getattr(r, "archived_at", 0)), key=_by_name
            ),
            guild_id=guild_id,
            dormant=sorted(
                (
                    r
                    for r in shells
                    if not getattr(r, "engagement", None)
                    and not getattr(r, "join_request", None)
                    and not getattr(r, "archived_at", 0)
                ),
                key=_by_name,
            ),
        )
    elif drawer == "atelier":
        from .common import strings_by_locale

        view = _atelier_drawer(strings, strings_by_locale(locale))
    else:  # pragma: no cover — the registry and the nav share the keys
        raise KeyError(f"kingdom: unknown drawer {drawer!r}")
    return view


async def _admitted_realms() -> list[Any]:
    """The realm SHELLS already in the season (engaged, the name rides).

    cockpit-lisible-v1: Drasah admitted AEGIS and NOTHING showed it —
    the drawer only lists the pending. The admin needs the confirms on
    record, one name per line, right under the requests.
    eject-sas-v1: the drawer needs the SHELLS (slug + engagement), not
    the bare names — the éjection rides the same objects.
    """
    stack = wiring()
    if stack is None:
        return []
    service = None
    try:
        from .validation import _realms_service

        service = _realms_service(stack)
        if service is None:
            return []
        realms = await service.realms()
    except Exception:  # noqa: BLE001 — a read, never a crash
        logger.warning("kingdom: the admitted realms read failed", exc_info=True)
        return []
    return sorted(
        (realm for realm in realms if getattr(realm, "engagement", None)),
        key=lambda realm: str(getattr(realm, "name", "?")),
    )


async def _all_shells() -> list[Any]:
    """Every realm shell, ONE read of the base (the callers filter offline).

    drawer-build-v1 (Check 136) : archivés, dormants, admis — la même
    liste, jamais deux fois le même parcours de la base dans un clic.
    """
    stack = wiring()
    if stack is None:
        return []
    try:
        from .validation import _realms_service

        service = _realms_service(stack)
        if service is None:
            return []
        return list(await service.realms() or [])
    except Exception:  # noqa: BLE001 — a read, never a crash
        logger.warning("kingdom: the realm shells read failed", exc_info=True)
        return []


def _dormant_filter(realm: Any) -> bool:
    """A dormant shell: free of season, free of pending request, not archived."""
    return (
        not getattr(realm, "engagement", None)
        and not getattr(realm, "join_request", None)
        and not getattr(realm, "archived_at", 0)
    )


async def _dormant_realms() -> list[Any]:
    """The persistent realms OUT of the season — dormant shells.

    ejection-archive-v1 (Drasah 22/11) : la 🗑️ du sas ne DETRUIT plus
    une coquille, elle la libère DORMANTE — l'admin doit les VOIR
    (onglet Admissions) avec le geste 📦 Archiver à la main. Hors
    engagés, hors demandes en cours, hors archivés.
    """
    # drawer-build-v1 : le filtre vit dans _dormant_filter, la lecture
    # partagée dans _all_shells (une seule passe de la base par clic)
    return sorted(
        (realm for realm in await _all_shells() if _dormant_filter(realm)),
        key=lambda realm: str(getattr(realm, "name", "?")),
    )





async def refresh_live_pins_after(interaction: discord.Interaction) -> None:
    """live-pin-v1 (Drasah 21/11) — re-render the live pins NOW.

    The designer's rule: the gesture that flips a state refreshes the
    surfaces that mirror it — the console pin must show the new sas in
    the same breath as the flip, not at the next boot. The 5-minute
    surface pass stays the safety net; this is the feedback loop.
    """
    from botforge.discord.static_pins import refresh_live_pins

    try:
        await refresh_live_pins(interaction.client, str(interaction.guild_id or ""))
    except Exception:  # noqa: BLE001 — the mirrors heal on the next pass
        logger.warning("kingdom: live pins refresh after the gesture failed", exc_info=True)


class KingdomSettingsNavButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:console-nav:(?P<drawer>[a-z-]+)",
):
    """One restart-proof drawer-opener of the console-v2 cockpit.

    The template lives in its OWN namespace (``kingdom:console-nav:``)
    — never ``kingdom:settings:``: discord.py 2.7 dispatches a click to
    EVERY registered dynamic template that fullmatches the id, so a
    colliding id would fire two handlers (the second dies with 40060).
    """

    def __init__(self, drawer: str, label: str, badge: int = 0) -> None:
        text = f"{label[:74]} ({badge})" if badge else label[:80]
        super().__init__(
            discord.ui.Button(
                label=text,
                custom_id=f"kingdom:console-nav:{drawer}"[:100],
                style=discord.ButtonStyle.secondary,
            )
        )
        self.drawer = drawer

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomSettingsNavButton:
        strings = strings_of(interaction)
        drawer = match["drawer"]
        label = str(strings.get(f"settings_nav_{drawer}_button", "⚙️"))
        return cls(drawer, label)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the drawer's ephemeral window (guarded like the panel)."""
        # windows-v2 review (Drasah 21/11): no ↩️ Console back button —
        # the cockpit is a PIN, it never left the screen; the drawer
        # is a parenthèse, ✖️ Fermer closes it.
        if self.drawer not in _DRAWERS:
            await _safe_send(interaction, strings_of(interaction)["settings_denied"])
            return
        if not await _panel_guard(interaction):
            return
        # drawer-build-v1 (Check 136, incident « n'a pas répondu à temps ») :
        # le fast-ack du core — le clic est acquitté IMMÉDIATEMENT (le
        # chrono de 3 s de Discord appartient à l'ack), la construction
        # du tiroir prend son temps, et la fenêtre vit dans le followup
        # (``open_ephemeral_window`` route déjà le cas « réponse faite »).
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:  # noqa: BLE001 — an already-acked click
            logger.debug("kingdom: the drawer defer skipped", exc_info=True)
        view = await _build_drawer(
            self.drawer, locale_of(interaction), interaction.client, str(interaction.guild_id or "")
        )
        await open_unique_ephemeral(interaction, view=view)


class KingdomRegieSwitchButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:console-regie:(?P<switch>[a-z_]+)",
):
    """One restart-proof ON/OFF switch of the 🎚️ régie drawer.

    The template lives in its OWN namespace (``kingdom:console-regie:``)
    — the double-dispatch lesson of the nav button applies here too.
    The label carries the switch's live state (✅ ouvert / ⛔ fermé) so
    the drawer re-reads like a dashboard after every flip.
    """

    def __init__(self, switch: str, label: str, open_: bool, style: discord.ButtonStyle) -> None:
        text = f"{str(label)[:72]} — {'✅' if open_ else '⛔'}"
        super().__init__(
            discord.ui.Button(
                label=text[:80],
                custom_id=f"kingdom:console-regie:{switch}"[:100],
                style=style,
            )
        )
        from .regie import REGIE_SWITCHES

        if switch not in REGIE_SWITCHES:
            raise ValueError(switch)
        self.switch = switch

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomRegieSwitchButton:
        strings = strings_of(interaction)
        from .regie import REGIE_SWITCHES, SWITCH_LABEL_KEYS, regie_open

        key = match["switch"]
        label = str(strings.get(SWITCH_LABEL_KEYS.get(key, ""), key))
        open_ = False
        try:
            open_ = await regie_open(interaction.client, str(interaction.guild_id or ""), key)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom: a régie switch re-read failed", exc_info=True)
        style = discord.ButtonStyle.success if open_ else discord.ButtonStyle.danger
        return cls(key, label, open_, style)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Flip the switch, then re-open the drawer with the fresh states."""
        strings = strings_of(interaction)
        if not await _panel_guard(interaction):
            return
        # drawer-build-v1 (Check 136) : fast-ack — le flip puis la
        # reconstruction du tiroir peuvent prendre leur temps, l'ack
        # part immédiatement (les notes d'échec vivent en followup).
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:  # noqa: BLE001 — an already-acked click
            logger.debug("kingdom: the switch defer skipped", exc_info=True)
        new_value = False
        try:
            from .regie import toggle_switch

            new_value = await toggle_switch(
                interaction.client, str(interaction.guild_id or ""), self.switch
            )
        except Exception:  # noqa: BLE001 — the drawer reports, never raises
            logger.warning("kingdom: a régie toggle failed", exc_info=True)
            await _safe_send(interaction, strings["settings_failed"])
            return
        # sas-cycle-v1 (Drasah 21/11) : fermer le SAS VIDE la salle
        # d'attente — chaque Roi candidat apprend par MP que sa demande
        # est retirée (best-effort total, jamais bloquant).
        if self.switch == "season_entry_open" and not new_value:
            try:
                from .apply_flow import _guild_locale

                await _drain_sas(
                    wiring(),
                    interaction.client,
                    await _guild_locale(str(interaction.guild_id or "")),
                    "settings_sas_drain_closed_dm",
                )
            except Exception:  # noqa: BLE001 — la fermeture ne rate jamais
                logger.warning("kingdom: the manual sas close drain failed", exc_info=True)
        # live-pin-v1: the flip shows on the console pin immediately
        await refresh_live_pins_after(interaction)
        view = await _build_drawer(
            "regie", locale_of(interaction), interaction.client, str(interaction.guild_id or "")
        )
        await open_unique_ephemeral(interaction, view=view)


# drain-coquilles-v1 (Drasah 22/11, Check 135) : les ids de coquille
# contiennent un ":" ("realm:aegis-123") — le moule les accepte
# (segments séparés par ":", non-avides pour laisser le guild_id)
_REGIE_REALM = r"kingdom:console-regie:(?P<kind>restore|purge|restore-yes|restore-no|purge-yes|purge-no):(?P<realm_id>[a-zA-Z0-9_:-]+?):(?P<guild_id>\d+)$"


def _realm_service_of(bot: Any) -> Any:
    stack = wiring()
    return getattr(stack, "realms", None) if stack is not None else None


async def _realm_by_id(realm_id: str) -> Any | None:
    service = _realm_service_of(None)
    if service is None:
        return None
    try:
        return await service.realm_by_id(str(realm_id))
    except Exception:  # noqa: BLE001 — a read, never a crash
        logger.warning("kingdom: realm resolve failed (%s)", realm_id, exc_info=True)
        return None


class KingdomRegieRealmButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=_REGIE_REALM,
):
    """One restart-proof archivist button of the 📦 régie block.

    ejection-archive-v1 (Drasah 22/11) : une SEULE classe, le ``kind``
    du custom_id route le geste — ♻️ Restaurer (MP au Roi fondateur
    avec la question Oui/Non), 🗑️ Supprimer définitivement (carte
    rouge), puis les jambes DM/confirmation. Le custom_id porte le
    realm_id ET le guild_id : après un redémarrage, le MP de
    restauration doit retrouver le guild pour re-provisionner
    l'habitat — l'interaction DM ne porte pas de guild.
    """

    def __init__(
        self, kind: str, realm_id: str, guild_id: str, label: str, style: Any
    ) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"kingdom:console-regie:{kind}:{realm_id}:{guild_id}"[:100],
                style=style,  # type: ignore[arg-type]
            )
        )
        if kind not in (
            "restore", "purge", "restore-yes", "restore-no", "purge-yes", "purge-no",
        ):
            raise ValueError(kind)
        self.kind = kind
        self.realm_id = realm_id
        self.guild_id = guild_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "KingdomRegieRealmButton":
        button = item if isinstance(item, discord.ui.Button) else None
        label = (button.label or "?") if button is not None else "?"
        return cls(
            match["kind"], match["realm_id"], match["guild_id"], label,
            discord.ButtonStyle.primary,
        )

    # -- the drawer's legs ------------------------------------------------

    async def _restore(self, interaction: discord.Interaction) -> None:
        """Verify the shell, then MP the King with the Oui/Non question."""
        strings = strings_of(interaction)
        if not await _panel_guard(interaction):
            return
        realm = await _realm_by_id(self.realm_id)
        if realm is None or not getattr(realm, "archived_at", 0):
            await _safe_send(interaction, strings["settings_regie_archived_gone_note"])
            return
        from .common import dm_user_safe

        # layoutview-v1 (Check 138) : discord.py 2.7.1 LayoutView ne
        # prend AUCUN enfant positionnel — le rendu passait par le
        # build_view des surfaces déclarées (le reste du mod), ces
        # DEUX cartes régie arrivaient ici en crash silencieux.
        question_container = discord.ui.Container(
            discord.ui.TextDisplay(
                str(strings["settings_restore_dm_question"]).format(
                    name=str(getattr(realm, "name", "?"))
                )
            ),
            _realm_button_row(
                "restore-yes", strings["settings_restore_dm_yes"],
                discord.ButtonStyle.success,
                "restore-no", strings["settings_restore_dm_no"],
                discord.ButtonStyle.secondary,
                self.realm_id, self.guild_id,
            ),
            accent_colour=_ADMIN_COLOUR,
        )
        question = surface(
            "panel:mod:kingdom:admin:regie:restore-dm", question_container
        )
        sent = await dm_user_safe(
            interaction.client, str(getattr(realm, "king_id", "")),
            f"**{strings['settings_restore_dm_title']}**", question,
        )
        if sent is None:
            await _safe_send(interaction, strings["settings_restore_dm_unreachable"])
            return
        await _safe_send(interaction, strings["settings_restore_sent_note"])

    async def _purge_card(self, interaction: discord.Interaction) -> None:
        """Open the red confirm card of the definitive deletion."""
        strings = strings_of(interaction)
        if not await _panel_guard(interaction):
            return
        realm = await _realm_by_id(self.realm_id)
        # drain-coquilles-v1 (Check 135) : la purge vit AUSSI pour une
        # coquille DORMANTE (le fondateur y est coincé — Roi qui ne peut
        # ni quitter ni être éjecté : détruire la coquille est la SEULE
        # porte). Restent exclus : une saison vivante (engagement) ou
        # une demande d'entrée en cours — jamais touchées.
        if (
            realm is None
            or getattr(realm, "engagement", None)
            or getattr(realm, "join_request", None)
        ):
            await _safe_send(interaction, strings["settings_regie_archived_gone_note"])
            return
        name = str(getattr(realm, "name", "?"))[:80]
        # layoutview-v1 (Check 138) : idem restauration — la carte passe
        # par la surface déclarée (LayoutView d2.py 2.7.1 = zéro enfant
        # positionnel, l'ancienne écriture crashait le clic en silence).
        card_container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {strings['settings_regie_purge_confirm_title']}\n"
                + str(strings["settings_regie_purge_confirm_hint"]).format(name=name)
            ),
            _realm_button_row(
                "purge-yes", strings["settings_regie_purge_confirm_button"],
                discord.ButtonStyle.danger,
                "purge-no", strings["settings_regie_purge_cancel_button"],
                discord.ButtonStyle.secondary,
                self.realm_id, self.guild_id,
            ),
            accent_colour=discord.Colour(0xED4245),
        )
        card = surface("panel:mod:kingdom:admin:regie:confirm", card_container)
        await open_unique_ephemeral(interaction, view=card)

    async def _purge_yes(self, interaction: discord.Interaction) -> None:
        """The definitive deletion — shell destroyed, NAME FREED."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        strings = strings_of(interaction)
        service = _realm_service_of(interaction.client)
        if service is None:
            await interaction.followup.send(
                str(strings["settings_failed"]), ephemeral=True
            )
            return
        try:
            gone = await service.destroy_realm(str(self.realm_id))
            # filet de sécurité : l'habitat Discord ne survit pas à la
            # coquille (les archivés n'en portent plus d'ancres, mais une
            # famille orpheline traînerait)
            from .realms import dismantle_realm_category

            await dismantle_realm_category(interaction.client, gone)
            await interaction.followup.send(
                str(strings["settings_regie_purged_note"]).format(
                    name=str(getattr(gone, "name", "?"))
                ),
                ephemeral=True,
            )
            await refresh_live_pins_after(interaction)
        except Exception as exc:  # noqa: BLE001 — the card reports
            logger.warning("kingdom: realm purge failed", exc_info=True)
            await interaction.followup.send(
                str(strings["settings_regie_purge_failed"]).format(str(exc)[:150]),
                ephemeral=True,
            )

    async def _restore_yes(self, interaction: discord.Interaction) -> None:
        """The King said Oui — the hot re-check first, then a rebuild."""
        strings = strings_of(interaction)
        realm = await _realm_by_id(self.realm_id)
        if realm is None:
            await _safe_send(interaction, strings["settings_restore_gone_note"])
            return
        if not getattr(realm, "archived_at", 0):
            await _safe_send(interaction, strings["settings_restore_already_note"])
            return
        service = _realm_service_of(interaction.client)
        guild = None
        try:
            guild = interaction.client.get_guild(int(self.guild_id))
        except Exception:  # noqa: BLE001 — a lookup, never a crash
            guild = None
        if service is None or guild is None:
            await _safe_send(interaction, strings["settings_restore_failed_note"])
            return
        try:
            restored = await service.restore_realm(str(self.realm_id))
            from .realms import ensure_realm_structure

            ids = await ensure_realm_structure(guild, restored, dormant=True)
            if ids:
                await service.save_habitat(str(restored.id), ids)
            await _safe_send(interaction, strings["settings_restore_done_note"])
        except Exception:  # noqa: BLE001 — the gesture reports, never raises
            logger.warning("kingdom: realm restore failed", exc_info=True)
            await _safe_send(interaction, strings["settings_restore_failed_note"])

    async def _noop(self, interaction: discord.Interaction) -> None:
        """Non / annuler — the realm stays exactly where it is."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

    async def callback(self, interaction: discord.Interaction) -> None:
        # drawer-build-v1 (Check 137, « Supprimer n'a pas répondu à
        # temps ») : le fast-ack du core sur TOUTES les jambes du
        # bouton royaume — le chrono de 3 s de Discord appartient à
        # l'ack, la lecture de coquille puis la carte (ou le MP du
        # Roi) prennent leur temps en followup (toutes les jambes
        # parlent déjà _safe_send / followup — zéro 40060 possible).
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        handler = {
            "restore": self._restore,
            "purge": self._purge_card,
            "purge-yes": self._purge_yes,
            "purge-no": self._noop,
            "restore-yes": self._restore_yes,
            "restore-no": self._noop,
        }[self.kind]
        await handler(interaction)


def _realm_button_row(
    yes_kind: str,
    yes_label: str,
    yes_style: Any,
    no_kind: str,
    no_label: str,
    no_style: Any,
    realm_id: str,
    guild_id: str,
) -> discord.ui.ActionRow[discord.ui.LayoutView]:
    """The two-button row of one archivist card (DM or confirm)."""
    row: Any = discord.ui.ActionRow()
    row.add_item(
        KingdomRegieRealmButton(
            yes_kind, realm_id, guild_id, str(yes_label)[:80], yes_style
        ).item
    )
    row.add_item(
        KingdomRegieRealmButton(
            no_kind, realm_id, guild_id, str(no_label)[:80], no_style
        ).item
    )
    return row


class KingdomRegieResetPlayersButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:console-regie:reset(?P<kind>-players|-yes|-no)?:(?P<guild_id>\d+)",
):
    """🧹 Réinitialiser les joueurs — the test gauntlet's one big sweep.

    reset-joueurs-v1 (Drasah 22/11) : les MEMBRES sortent de tous les
    royaumes hors saison (ils récupèrent leur parcours), les coquilles
    partent ARCHIVÉES automatiquement (jamais détruites : nom réservé,
    données conservées, restaurables une par une). Les royaumes
    ENGAGÉS ne se touchent jamais — une saison vivante ne se vide pas.
    Une seule classe route ses trois jambes (le bouton, le Oui, le Non)
    — la leçon dispatch du bouton royaume s'applique ici aussi.
    """

    def __init__(self, kind: str, guild_id: str, label: str, style: Any) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"kingdom:console-regie:reset{kind}:{guild_id}"[:100],
                style=style,  # type: ignore[arg-type]
            )
        )
        if kind not in ("-players", "-yes", "-no"):
            raise ValueError(kind)
        self.kind = kind
        self.guild_id = guild_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "KingdomRegieResetPlayersButton":
        button = item if isinstance(item, discord.ui.Button) else None
        label = (button.label or "?") if button is not None else "?"
        kind = match["kind"] or "-players"
        style = (
            discord.ButtonStyle.danger
            if kind in ("-players", "-yes")
            else discord.ButtonStyle.secondary
        )
        return cls(kind, match["guild_id"], label, style)

    async def _card(self, interaction: discord.Interaction) -> None:
        """Open the red confirm card of the great reset."""
        strings = strings_of(interaction)
        if not await _panel_guard(interaction):
            return
        container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {strings['settings_regie_reset_confirm_title']}\n"
                + str(strings["settings_regie_reset_confirm_hint"])
            ),
            accent_colour=discord.Colour(0xED4245),
        )
        container.add_item(_reset_button_row(self.guild_id, strings))
        await open_unique_ephemeral(
            interaction, view=surface("panel:mod:kingdom:admin:console:confirm", container)
        )

    async def _reset_yes(self, interaction: discord.Interaction) -> None:
        """The sweep itself — members out, shells archived, nobody destroyed."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        strings = strings_of(interaction)
        service = _realm_service_of(interaction.client)
        if service is None:
            await interaction.followup.send(
                str(strings["settings_failed"]), ephemeral=True
            )
            return
        realms: list[Any] = []
        engaged = 0
        try:
            realms = list(await service.realms() or [])
        except Exception:  # noqa: BLE001 — the sweep reports, never raises
            logger.warning("kingdom: the reset read failed", exc_info=True)
        freed = 0
        archived: list[str] = []
        from .realms import archive_realm_habitat

        for realm in realms:
            if getattr(realm, "engagement", None):
                engaged += 1  # une saison vivante ne se vide jamais
                continue
            if getattr(realm, "archived_at", 0):
                continue  # déjà en boîte — rien à vider
            freed += len(getattr(realm, "member_ids", []) or [])
            try:
                gone = await service.dissolve_realm(
                    str(realm.id), reason="régie: reset joueurs"
                )
                await archive_realm_habitat(interaction.client, gone)
                archived.append(str(gone.name))
            except Exception:  # noqa: BLE001 — one realm never blocks
                logger.warning(
                    "kingdom: realm reset failed (%s)", realm.id, exc_info=True
                )
        # les joueurs libérés récupèrent la conscription tout de suite
        try:
            from .conscription_gate import run_conscription_gate_pass

            await run_conscription_gate_pass(interaction.client, self.guild_id)
        except Exception:  # noqa: BLE001 — le masque se répare à la passe
            logger.warning("kingdom: the conscription gate pass failed", exc_info=True)
        if not archived:
            note = str(strings["settings_regie_reset_empty"])
        else:
            note = str(strings["settings_regie_reset_done"]).format(
                realms=len(archived), players=freed
            )
        await interaction.followup.send(note, ephemeral=True)
        await refresh_live_pins_after(interaction)

    async def _noop(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

    async def callback(self, interaction: discord.Interaction) -> None:
        # drawer-build-v1 (Check 137) : même fast-ack pour la 🧹 —
        # l'ack part immédiatement, la carte aussi lente soit la
        # passe de lecture derrière.
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        handler = {
            "-players": self._card,
            "-yes": self._reset_yes,
            "-no": self._noop,
        }[self.kind]
        await handler(interaction)


def _reset_button_row(
    guild_id: str, strings: dict[str, str]
) -> discord.ui.ActionRow[discord.ui.LayoutView]:
    """The confirm row of the great reset's card."""
    row: Any = discord.ui.ActionRow()
    row.add_item(
        KingdomRegieResetPlayersButton(
            "-yes", guild_id,
            str(strings["settings_regie_reset_confirm_button"])[:80],
            discord.ButtonStyle.danger,
        ).item
    )
    row.add_item(
        KingdomRegieResetPlayersButton(
            "-no", guild_id,
            str(strings["settings_regie_reset_cancel_button"])[:80],
            discord.ButtonStyle.secondary,
        ).item
    )
    return row


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
        # season-type-at-launch is RETIRED (lancement-fourche-v1): the
        # fork card owns the format — this modal is the CLASSIC path.
        # console-etats-regie-v1 (Drasah 21/11): the wizard's 2nd
        # question — « ouvres-tu le sas ? » The season opens NOTHING by
        # itself: answering no arms a CLOSED sas the régie re-opens.
        self.sas = discord.ui.TextInput(
            placeholder=str(strings["settings_launch_modal_sas_placeholder"])[:100],
            required=False,
            max_length=8,
            custom_id="kingdom:settings:launch:sas",
        )
        self.add_item(
            discord.ui.Label(
                text=str(strings["settings_launch_modal_sas_label"])[:45],
                component=self.sas,
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
        except Exception as exc:  # the panel reports, never raises
            logger.warning("kingdom: launch failed", exc_info=True)
            await interaction.followup.send(
                service_failure_note(strings, "settings_launch_failed", exc), ephemeral=True
            )
            return
        # The TYPE applies right after the fresh launch — activate_beta
        # (the compressed weekend) rides a FRESH setup-phase season only.
        # lancement-fourche-v1: the classic path owns the flag — a
        # lingering beta flag lowers NOW (the mutex trap at « Démarrer »).
        try:
            if await _lower_beta_flag(interaction):
                logger.info("kingdom: a lingering beta flag was lowered by the classic launch")
        except Exception:  # noqa: BLE001 — the flag is best-effort, the launch stands
            logger.warning("kingdom: the classic launch flag lowering failed", exc_info=True)
        note = str(strings["settings_launch_done"])
        sas_answer = str(self.sas.value or "").strip().lower() or "oui"
        await _finish_launch(interaction, sas_answer)
        await interaction.followup.send(note, ephemeral=True)


async def _arm_compressed_beta(stack: Any) -> None:
    """Arm the compressed weekend onto a FRESH season (the « beta » type)."""
    from datetime import UTC, datetime

    from botforge.mods.kingdom.game_clock import game_now

    start_at = game_now() if game_now().tzinfo else datetime.now(UTC)
    await stack.events.activate_beta("now", start_at=start_at)


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
    """Lancer la saison — the PREPARATION only (depart-fourche-v1).

    Drasah 22/11 : « Lancer » prépare (noms imposés éventuels + la
    question du sas), il ne choisit PLUS le format — le départ lève
    la fourche dans la zone Le cycle (« Démarrer la saison classique »
    ou « Démarrer la bêta »), et chaque départ distribue les royaumes
    admis du sas.

    sas-cycle-v1 (Drasah 21/11) : le SAS ouvert est un PRÉREQUIS du
    lancement — « le SAS n'a de sens que si l'admin l'a ouvert pour
    préparer sa saison ». Fermé : le geste refuse poliment, la régie
    🎚️ l'ouvre (la réouverture n'est jamais automatique).
    """
    from .regie import regie_open

    if not await regie_open(
        interaction.client, str(interaction.guild_id or ""), "season_entry_open"
    ):
        await open_unique_ephemeral(
            interaction, content=strings["settings_launch_sas_closed"]
        )
        return
    await interaction.response.send_modal(_LaunchModal(strings))


async def _finish_launch(interaction: discord.Interaction, sas_answer: str) -> None:
    """The shared launch tail: the sas answer, the parcours gate, the pins.

    Drasah's rule (21/11): the sas is OPEN unless he says no — an EMPTY
    answer keeps the sas OPEN, a refusal is explicit.
    """
    from .regie import set_switch

    if not await set_switch(
        interaction.client, str(interaction.guild_id or ""), "season_entry_open",
        sas_answer in ("oui", "yes", "y", "o", "1", "true", "open"),
    ):
        logger.warning("kingdom: the launch's sas answer could not be stored")
    # the conscription bends the moment the season launches — not at the
    # next 5-min pass
    try:
        from .conscription_gate import run_conscription_gate_pass

        await run_conscription_gate_pass(interaction.client, str(interaction.guild_id or ""))
    except Exception:  # noqa: BLE001 — the gate heals on the next pass
        logger.warning("kingdom: the launch gate pass failed", exc_info=True)
    await refresh_live_pins_after(interaction)


async def _lower_beta_flag(interaction: discord.Interaction) -> bool:
    """Best-effort: lower a lingering beta flag (classic owns it).

    depart-fourche-v1: the CLASSIC departure owns the parcours flag
    (and the end of season lowers one left by a finished beta) — a
    stale flag never bars a departure again (the mutex trap Drasah hit
    live on 22/11 is retired).
    """
    from botforge.core.services.beta import exit_beta, is_beta
    from botforge.core.services.mod_storage import ModStateCache

    state_service = getattr(interaction.client, "state_service", None)
    if state_service is None:
        return False
    cache = ModStateCache(state_service, _MOD)
    guild_id = str(interaction.guild_id or "")
    if not await is_beta(cache, guild_id, _MOD):
        return False
    await exit_beta(cache, guild_id, _MOD)
    return True


async def _raise_beta_flag(interaction: discord.Interaction) -> bool:
    """Best-effort: raise the beta flag (the beta format owns it)."""
    from botforge.core.services.beta import enter_beta, is_beta
    from botforge.core.services.mod_storage import ModStateCache

    state_service = getattr(interaction.client, "state_service", None)
    if state_service is None:
        return False
    cache = ModStateCache(state_service, _MOD)
    guild_id = str(interaction.guild_id or "")
    if await is_beta(cache, guild_id, _MOD):
        return False
    await enter_beta(cache, guild_id, _MOD)
    return True


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
