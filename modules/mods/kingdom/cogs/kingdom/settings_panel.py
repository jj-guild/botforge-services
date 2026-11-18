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
- « Démarrer la beta » rides the platform's beta phase toggle
  (``enter_beta``/``exit_beta`` — the BetaPhaseButton contract);
- the click guard is the platform's ``require_admin`` (roles resolve
  live, never assumed at render time).

Announce-ready (#396): the panel is ONE named template
(``view:mod:kingdom:settings``) instantiated by parameters (the
``SETTINGS_ACTIONS`` table); the destructive ops wear the inline
confirm card (one ephemeral window, never a stacked surface).
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord

from .common import locale_of, open_unique_ephemeral, surface, wiring

logger = logging.getLogger("kingdom.settings")

SETTINGS_VIEW_KEY = "view:mod:kingdom:settings"
_MOD = "kingdom"
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
    ("hat", "settings_hat_button", discord.ButtonStyle.secondary),
)

_CONFIRM_ACTIONS = frozenset({"deploy", "sync", "reset"})

_ALL_ACTIONS = tuple(
    action for action, _key, _style in _SETTINGS_ACTIONS
) + tuple(
    f"{action}{suffix}"
    for action in _CONFIRM_ACTIONS
    for suffix in ("-yes", "-no")
)

# The panel's own strings (the reference's wording, fr first like the
# mod's other surfaces); the ``kingdom.settings`` catalog section
# overrides them key by key — the code fallback keeps every action
# alive without it.
_SETTINGS_STRINGS: dict[str, dict[str, str]] = {
    "fr": {
        "settings_title": "⚙️ Kingdoms — paramètres",
        "settings_denied": "❌ Réservé aux admins du bot.",
        "settings_error": "❌ L'action a échoué — {0}",
        "settings_failed": "❌ L'action a échoué — {0}",
        "settings_no_service": "❌ Le service Kingdoms n'est pas prêt.",
        "settings_cancelled": "❌ Annulé — rien n'a été touché.",
        "settings_launch_button": "▶️ Lancer la saison",
        "settings_launch_modal_title": "▶️ Lancer la saison",
        "settings_launch_done": (
            "✅ Saison lancée — les royaumes imposés (le cas échéant) sont créés."
        ),
        "settings_launch_failed": "❌ Le lancement a échoué — {0}",
        "settings_start_season_button": "🎯 Démarrer la saison",
        "settings_start_season_done": "✅ Saison démarrée — que l'aventure commence !",
        "settings_start_season_failed": "❌ Le démarrage a échoué — {0}",
        "settings_start_beta_button": "🚀 Démarrer la beta",
        "settings_beta_started": "✅ Phase bêta activée — les règles se plient.",
        "settings_beta_exited": "✅ Phase bêta quittée — les règles se redressent.",
        "settings_status_button": "📊 Statut de la saison",
        "settings_status_title": "📊 Statut de la saison",
        "settings_status_phase": "Phase",
        "settings_status_mode": "Mode",
        "settings_status_kingdoms": "Royaumes",
        "settings_status_lords": "Seigneurs engagés",
        "settings_status_queue": "En file d'attente",
        "settings_status_empty": "—",
        "settings_phase_unknown": "inconnue",
        "settings_deploy_button": "🚀 Déployer salons + panels",
        "settings_deploy_confirm_title": "Déployer les salons et les panels ?",
        "settings_deploy_confirm_hint": (
            "Les salons et rôles du mod se (re)provisionnent, les panels se réépinglent."
        ),
        "settings_deploy_confirm_button": "✅ Oui, déployer",
        "settings_deploy_cancel_button": "❌ Annuler",
        "settings_deploy_done": (
            "✅ Déployé : {channels} salons, {roles} rôles, {pins} panels épinglés."
        ),
        "settings_sync_button": "🔄 Resynchroniser les panels",
        "settings_sync_confirm_title": "Resynchroniser les panels ?",
        "settings_sync_confirm_hint": (
            "Les panels épinglés du mod se reconstruisent à l'état courant."
        ),
        "settings_sync_confirm_button": "✅ Oui, resynchroniser",
        "settings_sync_cancel_button": "❌ Annuler",
        "settings_sync_done": "✅ Resynchronisé : {pins} panels épinglés.",
        "settings_reset_button": "♻️ Réinitialiser les salons",
        "settings_reset_confirm_title": "Réinitialiser les salons ?",
        "settings_reset_confirm_hint": (
            "⚠️ Tous les salons du mod sont supprimés puis recréés —"
            " les données de jeu ne sont PAS touchées."
        ),
        "settings_reset_confirm_button": "✅ Oui, réinitialiser",
        "settings_reset_cancel_button": "❌ Annuler",
        "settings_reset_done": (
            "✅ Salons réinitialisés ({channels} supprimés, tout est recréé)."
        ),
        "settings_assign_button": "📥 Affecter un joueur en attente",
        "settings_assign_modal_title": "📥 Affecter un joueur",
        "settings_assign_done": "✅ Joueur affecté au royaume.",
        "settings_assign_failed": "❌ L'affectation a échoué — {0}",
        "settings_assign_bad_role": "❌ Le rôle doit être « king » ou « lord ».",
        "settings_add_kingdom_button": "+ Ajouter un royaume manuellement",
        "settings_add_kingdom_modal_title": "Ajouter un royaume",
        "settings_add_kingdom_done": "✅ Royaume **{0}** ajouté.",
        "settings_add_kingdom_failed": "❌ L'ajout a échoué — {0}",
        "settings_season_mode_button": "🔄 Mode de saison",
        "settings_mode_imposed": (
            "Mode de saison : **imposé** — les Rois ne peuvent plus fonder de royaume."
        ),
        "settings_mode_free": (
            "Mode de saison : **libre** — les Rois peuvent fonder leurs royaumes."
        ),
        "settings_remove_button": "🧹 Retirer un joueur/candidat",
        "settings_remove_modal_title": "🧹 Retirer un joueur",
        "settings_remove_done": "✅ Joueur {0} retiré de la saison.",
        "settings_remove_failed": "❌ Le retrait a échoué — {0}",
        "settings_hat_button": "🧪 Casquette test",
        "settings_hat_on": (
            "🧪 Casquette ENFILÉE — tu pilotes le royaume TEST (Nilrem)"
            " et les contrôles joueurs sont court-circuités."
        ),
        "settings_hat_off": "🧪 Casquette RETIRÉE — de retour sur ton royaume joueur.",
    },
    "en": {
        "settings_title": "⚙️ Kingdoms — settings",
        "settings_denied": "❌ Reserved for the bot admins.",
        "settings_error": "❌ The action failed — {0}",
        "settings_failed": "❌ The action failed — {0}",
        "settings_no_service": "❌ The Kingdoms service is not ready.",
        "settings_cancelled": "❌ Cancelled — nothing was touched.",
        "settings_launch_button": "▶️ Launch the season",
        "settings_launch_modal_title": "▶️ Launch the season",
        "settings_launch_done": (
            "✅ Season launched — the imposed kingdoms (if any) are created."
        ),
        "settings_launch_failed": "❌ The launch failed — {0}",
        "settings_start_season_button": "🎯 Start the season",
        "settings_start_season_done": "✅ Season started — let the adventure begin!",
        "settings_start_season_failed": "❌ The start failed — {0}",
        "settings_start_beta_button": "🚀 Start the beta",
        "settings_beta_started": "✅ Beta phase entered — the rules bend.",
        "settings_beta_exited": "✅ Beta phase left — the rules straighten back.",
        "settings_status_button": "📊 Season status",
        "settings_status_title": "📊 Season status",
        "settings_status_phase": "Phase",
        "settings_status_mode": "Mode",
        "settings_status_kingdoms": "Kingdoms",
        "settings_status_lords": "Enrolled lords",
        "settings_status_queue": "In queue",
        "settings_status_empty": "—",
        "settings_phase_unknown": "unknown",
        "settings_deploy_button": "🚀 Deploy salons + panels",
        "settings_deploy_confirm_title": "Deploy the salons and the panels?",
        "settings_deploy_confirm_hint": (
            "The mod's salons and roles (re)provision, the panels repin."
        ),
        "settings_deploy_confirm_button": "✅ Yes, deploy",
        "settings_deploy_cancel_button": "❌ Cancel",
        "settings_deploy_done": (
            "✅ Deployed: {channels} salons, {roles} roles, {pins} pinned panels."
        ),
        "settings_sync_button": "🔄 Resync the panels",
        "settings_sync_confirm_title": "Resynchronize the panels?",
        "settings_sync_confirm_hint": "The mod's pinned panels rebuild to the current state.",
        "settings_sync_confirm_button": "✅ Yes, resync",
        "settings_sync_cancel_button": "❌ Cancel",
        "settings_sync_done": "✅ Resynchronized: {pins} pinned panels.",
        "settings_reset_button": "♻️ Reset the salons",
        "settings_reset_confirm_title": "Reset the salons?",
        "settings_reset_confirm_hint": (
            "⚠️ Every mod salon is deleted then recreated — the game data is NOT touched."
        ),
        "settings_reset_confirm_button": "✅ Yes, reset",
        "settings_reset_cancel_button": "❌ Cancel",
        "settings_reset_done": "✅ Salons reset ({channels} deleted, everything recreated).",
        "settings_assign_button": "📥 Assign a waiting player",
        "settings_assign_modal_title": "📥 Assign a player",
        "settings_assign_done": "✅ Player assigned to the kingdom.",
        "settings_assign_failed": "❌ The assignment failed — {0}",
        "settings_assign_bad_role": "❌ The role must be 'king' or 'lord'.",
        "settings_add_kingdom_button": "+ Add a kingdom manually",
        "settings_add_kingdom_modal_title": "Add a kingdom",
        "settings_add_kingdom_done": "✅ Kingdom **{0}** added.",
        "settings_add_kingdom_failed": "❌ The add failed — {0}",
        "settings_season_mode_button": "🔄 Season mode",
        "settings_mode_imposed": (
            "Season mode: **imposed** — the Kings cannot found a kingdom anymore."
        ),
        "settings_mode_free": "Season mode: **free** — the Kings found their kingdoms.",
        "settings_remove_button": "🧹 Remove a player/candidate",
        "settings_remove_modal_title": "🧹 Remove a player",
        "settings_remove_done": "✅ Player {0} removed from the season.",
        "settings_remove_failed": "❌ The removal failed — {0}",
        "settings_hat_button": "🧪 Test hat",
        "settings_hat_on": (
            "🧪 Hat ON — you pilot the TEST kingdom (Nilrem) and the player gates are bypassed."
        ),
        "settings_hat_off": "🧪 Hat OFF — back on your player kingdom.",
    },
}


def settings_strings(locale: str) -> dict[str, str]:
    """Return the panel's strings for one locale (defaults + catalog)."""
    base: dict[str, str] = dict(
        _SETTINGS_STRINGS["fr"] if str(locale).lower().startswith("fr")
        else _SETTINGS_STRINGS["en"]
    )
    try:
        from botforge.core.services.mod_catalog import mod_catalog

        base.update(
            {
                key: value
                for key, value in mod_catalog()
                .section("kingdom.settings", str(locale)[:2])
                .items()
                if value
            }
        )
    except Exception:  # the catalog override won't kill the panel
        logger.info("kingdom: settings catalog override skipped", exc_info=True)
    return base


def strings_of(interaction: discord.Interaction) -> dict[str, str]:
    """Return the panel's strings in the interaction's locale."""
    return settings_strings(locale_of(interaction))


async def build_settings_panel(guild_id: str) -> discord.ui.LayoutView:
    """Build the pinned ⚙️ Paramètres panel (the admin cockpit)."""
    from .apply_flow import _guild_locale

    strings = settings_strings(await _guild_locale(guild_id))
    rows: list[discord.ui.ActionRow[discord.ui.LayoutView]] = []
    for index, (action, key, style) in enumerate(_SETTINGS_ACTIONS):
        if index % 5 == 0:
            rows.append(discord.ui.ActionRow())
        rows[index // 5].add_item(
            SettingsActionButton(action, str(strings[key]), style).item
        )

    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.TextDisplay(f"# {strings['settings_title']}"),
        discord.ui.Separator(),
        *rows,
        discord.ui.Separator(),
        accent_colour=_ADMIN_COLOUR,
    )
    return surface(SETTINGS_VIEW_KEY, container)


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
    """Build the inline confirm card of a destructive op (one ephemeral window)."""
    yes: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings[f"settings_{action}_confirm_button"])[:80],
        custom_id=f"kingdom:settings:{action}-yes",
        style=discord.ButtonStyle.danger,
    )
    no: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings[f"settings_{action}_cancel_button"])[:80],
        custom_id=f"kingdom:settings:{action}-no",
        style=discord.ButtonStyle.secondary,
    )

    async def on_yes(target: discord.Interaction) -> None:
        await target.response.defer()
        note = await _run_provisioning(target, action)
        try:
            await target.followup.send(note, ephemeral=True)
        except Exception:  # a vanished window is fine — log it and move on
            logger.info("kingdom: settings confirm note lost", exc_info=True)

    async def on_no(target: discord.Interaction) -> None:
        await open_unique_ephemeral(target, strings["settings_cancelled"])

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
    return surface("surface:mod:kingdom:settings:confirm", container)


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
    """One restart-proof admin action of the ⚙️ Paramètres panel."""

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
        style = styles.get(_base(action), discord.ButtonStyle.secondary)
        if action.endswith("-yes"):
            style = discord.ButtonStyle.danger
        elif action.endswith("-no"):
            style = discord.ButtonStyle.secondary
        if action.endswith("-yes"):
            label = strings.get(f"settings_{_base(action)}_confirm_button", "✅")
        elif action.endswith("-no"):
            label = strings.get(f"settings_{_base(action)}_cancel_button", "❌")
        else:
            label = strings.get(f"settings_{action}_button", "⚙️")
        return cls(action, str(label), style)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Run the chosen admin action (guarded, ephemeral, best-effort)."""
        strings = strings_of(interaction)
        if self.action not in _ALL_ACTIONS:
            await interaction.response.send_message(
                strings["settings_denied"], ephemeral=True
            )
            return
        if not await _panel_guard(interaction):
            return
        if self.action in _CONFIRM_ACTIONS:
            await open_unique_ephemeral(
                interaction, view=_confirm_card(strings, self.action)
            )
            return
        if self.action.endswith("-no"):
            await open_unique_ephemeral(interaction, strings["settings_cancelled"])
            return
        if self.action.endswith("-yes"):
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(
                await _run_provisioning(interaction, _base(self.action)), ephemeral=True
            )
            return
        await _SETTINGS_HANDLERS[self.action](interaction, strings)


# ---------------------------------------------------------------------------
# The season actions (§7 contract only — never the mod's internals)
# ---------------------------------------------------------------------------


def _base(action: str) -> str:
    """Return the confirm card's base action (« deploy-yes » → « deploy »)."""
    return re.sub(r"-(yes|no)$", "", action)


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
        note = str(strings["settings_start_season_failed"]).format(str(exc)[:150])
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
        note = str(strings["settings_failed"]).format(str(exc)[:150])
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
        note = str(strings["settings_failed"]).format(str(exc)[:150])
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


async def _hat(interaction: discord.Interaction, strings: dict[str, str]) -> None:
    """Toggle the admin hat (Nilrem): the bypass + the test kingdom."""
    await interaction.response.defer(ephemeral=True)
    from botforge.mods.kingdom.admin_debug import (
        admin_bypass_enabled,
        set_admin_bypass,
    )

    stack, _busy = _needs_stack(strings)
    enabled = not admin_bypass_enabled()
    try:
        set_admin_bypass(enabled, source="settings-panel")
        if enabled:
            if stack is not None:
                await stack.kingdoms.ensure_test_kingdom()
            note = str(strings["settings_hat_on"])
        else:
            note = str(strings["settings_hat_off"])
    except Exception as exc:  # the panel reports, never raises
        logger.warning("kingdom: hat toggle failed", exc_info=True)
        note = str(strings["settings_failed"]).format(str(exc)[:150])
    await interaction.followup.send(note, ephemeral=True)


class _LaunchModal(discord.ui.Modal):
    """Lancer la saison — optional comma-separated imposed kingdom names."""

    names = discord.ui.TextInput(
        label="Noms imposés (optionnel, séparés par des virgules)",
        placeholder="Royaume A, Royaume B",
        required=False,
        max_length=200,
    )

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(title=str(strings["settings_launch_modal_title"])[:45])
        self._strings = strings

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
            note = str(strings["settings_launch_failed"]).format(str(exc)[:150])
        await interaction.followup.send(note, ephemeral=True)


class _AssignModal(discord.ui.Modal):
    """Affecter un joueur en attente — id, royaume, rôle."""

    player_id = discord.ui.TextInput(label="ID du joueur", required=True, max_length=32)
    kingdom = discord.ui.TextInput(label="Nom du royaume", required=True, max_length=64)
    role = discord.ui.TextInput(
        label="Rôle (king ou lord)", placeholder="king", required=True, max_length=8
    )

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(title=str(strings["settings_assign_modal_title"])[:45])
        self._strings = strings

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
            note = str(strings["settings_assign_failed"]).format(str(exc)[:150])
        await interaction.followup.send(note, ephemeral=True)


class _AddKingdomModal(discord.ui.Modal):
    """Ajouter un royaume manuellement."""

    name = discord.ui.TextInput(label="Nom du royaume", required=True, max_length=64)

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(title=str(strings["settings_add_kingdom_modal_title"])[:45])
        self._strings = strings

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
            note = str(strings["settings_add_kingdom_failed"]).format(str(exc)[:150])
        await interaction.followup.send(note, ephemeral=True)


class _RemoveModal(discord.ui.Modal):
    """Retirer un joueur/candidat — id + motif."""

    player_id = discord.ui.TextInput(label="ID du joueur", required=True, max_length=32)
    reason = discord.ui.TextInput(
        label="Motif", placeholder="ss", required=False, max_length=200
    )

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(title=str(strings["settings_remove_modal_title"])[:45])
        self._strings = strings

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
            note = str(strings["settings_remove_failed"]).format(str(exc)[:150])
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
    "hat": _hat,
}


__all__ = [
    "SETTINGS_VIEW_KEY",
    "SettingsActionButton",
    "build_settings_panel",
    "settings_strings",
]
