"""Kingdoms mod — the Nilrem test kingdom controls (kingdom-test-v1).

Drasah's test rule (2026-11-01): a reserved, admin-only kingdom
« Nilrem » (Merlin à l'envers) where the admin pilots the game without
touching the player kingdoms — its refonte lands there first, then
propagates. Three restart-proof DynamicItems ride the surfaces:

- the 🧪 create button (the pinned Distributeur panel): idempotent
  creation + standard realm provisioning (admin-only visibility comes
  free from the seam — @everyone deny + kingdoms_admin allow);
- the 🧪 red autodestruct (the Le-Royaume view of Nilrem): a
  confirmation, then the full kingdom deletion (service) + the
  Discord structure sweep;
- the 🔄 blue refresh (same view): re-renders every Nilrem view after
  a code change — the data is never touched.

Every label is rebuilt from THIS module's strings at ``from_custom_id``
time (the Check 30 lesson: a rebuilt item that cannot find its label
stays mute forever).
"""
from __future__ import annotations

import logging
import re
from time import monotonic
from typing import Any

import discord

logger = logging.getLogger("kingdoms.kingdom_test")

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "create_button": "🧪 Create the test kingdom",
        "not_allowed": "The test kingdom is admin-only.",
        "no_service": "The Kingdoms service is not wired.",
        "no_season": "No season is running — launch one first.",
        "create_done": (
            "🧪 **Nilrem** is ready — its salons are provisioned "
            "(visible to the admins only)."
        ),
        "failed": "The test kingdom action failed: `{0}`.",
        "destruct_button": "🧪 Autodestruct",
        "refresh_button": "🔄 Refresh",
        "destruct_title": "🧪 Destroy the Nilrem test kingdom?",
        "destruct_hint": (
            "This deletes the kingdom, its fictional king and its Discord "
            "salons. The 🧪 button of the Distributeur recreates it at any time."
        ),
        "destruct_confirm": "🧪 Destroy for good",
        "destruct_cancel": "Cancel",
        "cancelled": "Cancelled.",
        "destruct_done": "🧪 **Nilrem** destroyed.",
        "refresh_done": "🔄 **Nilrem** views re-rendered.",
    },
    "fr": {
        "create_button": "🧪 Créer le royaume test",
        "not_allowed": "Le royaume test est réservé aux admins.",
        "no_service": "Le service Kingdoms n'est pas câblé.",
        "no_season": "Aucune saison en cours — lancez-en une d'abord.",
        "create_done": (
            "🧪 **Nilrem** est prêt — ses salons sont provisionnés "
            "(visibles des admins uniquement)."
        ),
        "failed": "L'action royaume test a échoué : `{0}`.",
        "destruct_button": "🧪 Autodestruction",
        "refresh_button": "🔄 Actualiser",
        "destruct_title": "🧪 Détruire le royaume test Nilrem ?",
        "destruct_hint": (
            "Cela supprime le royaume, son roi fictif et ses salons Discord. "
            "Le bouton 🧪 du Distributeur le recrée à tout moment."
        ),
        "destruct_confirm": "🧪 Détruire définitivement",
        "destruct_cancel": "Annuler",
        "cancelled": "Annulé.",
        "destruct_done": "🧪 **Nilrem** détruit.",
        "refresh_done": "🔄 Vues de **Nilrem** actualisées.",
    },
}


def _strings(locale: str) -> dict[str, str]:
    return STRINGS["fr"] if str(locale).lower().startswith("fr") else STRINGS["en"]


def _locale(interaction: discord.Interaction) -> str:
    return str(interaction.locale) if interaction.locale else "fr"


def _error_line(exc: Exception, strings: dict[str, str]) -> str:
    """The standard failure line (the localized message_key wins)."""
    return strings["failed"].format(getattr(exc, "message", None) or exc)


async def _provision_test_realm(guild: discord.Guild | None, kingdom: Any, service: Any) -> None:
    """Provision/repair the Nilrem salons (best effort, idempotent)."""
    try:
        from kingdoms.mods.kingdoms.kingdom_persistent import _deploy_realm_content_safe
        from kingdoms.mods.kingdoms.kingdom_realms import (
            _announce_realm_alliances,
            ensure_realm_structure,
        )

        # member_ids stays EMPTY: the standard seam grants @everyone deny
        # + kingdoms_admin allow only — the test realm is admin-only by
        # construction, and the fictional king id never resolves to a
        # real member anyway.
        await ensure_realm_structure(guild, kingdom, [])
        await _announce_realm_alliances(guild, kingdom, service)
        await _deploy_realm_content_safe(guild, kingdom)
    except Exception:
        logger.warning("KINGDOM TEST: realm provisioning failed", exc_info=True)


class KingdomTestCreateButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:test:create",
):
    """The restart-proof 🧪 create button of the Distributeur panel."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdoms:test:create",
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
    ) -> KingdomTestCreateButton:
        """Rebuild the button from the wire — THIS module's strings only."""
        return cls(_strings(_locale(interaction))["create_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Admin-only, idempotent: ensure Nilrem, provision its salons."""
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _is_admin,
            _log_admin_action_safe,
            _refresh_realms_panel_safe,
            _wiring,
        )

        strings = _strings(_locale(interaction))
        wiring = _wiring()
        if not _is_admin(interaction, wiring.bot_admins):
            await interaction.response.send_message(strings["not_allowed"], ephemeral=True)
            return
        service = wiring.kingdoms_service
        if service is None:
            await interaction.response.send_message(strings["no_service"], ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            kingdom = await service.ensure_test_kingdom()
        except Exception as exc:  # NoSeasonError and friends
            await interaction.followup.send(_error_line(exc, strings), ephemeral=True)
            return
        await _provision_test_realm(interaction.guild, kingdom, service)
        await _log_admin_action_safe(
            interaction.guild,
            f"🧪 <@{interaction.user.id}> a créé le royaume test **{kingdom.name}**",
        )
        # Nilrem appears on the admin Royaumes panel — refresh it.
        await _refresh_realms_panel_safe(interaction.guild, _locale(interaction))
        await interaction.followup.send(strings["create_done"], ephemeral=True)


class KingdomTestDestructButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:test:destruct",
):
    """The restart-proof red 🧪 autodestruct of the Nilrem Le-Royaume view."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdoms:test:destruct",
                style=discord.ButtonStyle.danger,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomTestDestructButton:
        """Rebuild the button from the wire — THIS module's strings only."""
        return cls(_strings(_locale(interaction))["destruct_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Admin-only: open the confirmation view (fenêtre unique)."""
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _is_admin,
            _open_unique_ephemeral,
            _wiring,
        )

        strings = _strings(_locale(interaction))
        if not _is_admin(interaction, _wiring().bot_admins):
            await interaction.response.send_message(strings["not_allowed"], ephemeral=True)
            return
        await _open_unique_ephemeral(
            interaction,
            f"**{strings['destruct_title']}**\n\n{strings['destruct_hint']}",
            view=_TestDestructConfirmView(_locale(interaction)),
        )


class _TestDestructConfirmView(discord.ui.View):
    """The ephemeral confirmation of the Nilrem autodestruct."""

    def __init__(self, locale: str) -> None:
        super().__init__(timeout=600)
        self.strings = _strings(locale)

    @discord.ui.button(label="🧪", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _log_admin_action_safe,
            _refresh_realms_panel_safe,
            _wiring,
        )
        from kingdoms.mods.kingdoms.kingdom_realms import delete_realm_structure
        from kingdoms.mods.kingdoms.service import TEST_KINGDOM_ID, TEST_KINGDOM_NAME

        strings = self.strings
        wiring = _wiring()
        service = wiring.kingdoms_service
        if service is None:
            await interaction.response.edit_message(content=strings["no_service"], view=None)
            return
        await interaction.response.defer()
        try:
            kingdom = await service.delete_kingdom(TEST_KINGDOM_ID)
            await delete_realm_structure(interaction.guild, kingdom.name)
        except Exception:
            logger.warning("KINGDOM TEST: autodestruct failed", exc_info=True)
            await interaction.followup.send(
                _error_line(Exception("delete failed"), strings), ephemeral=True
            )
            return
        await _log_admin_action_safe(
            interaction.guild,
            f"🧪 <@{interaction.user.id}> a détruit le royaume test **{TEST_KINGDOM_NAME}**",
        )
        await _refresh_realms_panel_safe(interaction.guild, _locale(interaction))
        await interaction.followup.send(strings["destruct_done"], ephemeral=True)

    @discord.ui.button(label="❌", style=discord.ButtonStyle.secondary)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        await interaction.response.edit_message(content=self.strings["cancelled"], view=None)


class KingdomTestRefreshButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:test:refresh",
):
    """The restart-proof blue 🔄 refresh of the Nilrem Le-Royaume view."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdoms:test:refresh",
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
    ) -> KingdomTestRefreshButton:
        """Rebuild the button from the wire — THIS module's strings only."""
        return cls(_strings(_locale(interaction))["refresh_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Admin-only: re-render every Nilrem view (data untouched)."""
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _EPHEMERAL_WINDOWS,
            _close_previous_ephemeral,
            _is_admin,
            _refresh_realm_views_for_kingdom_safe,
            _wiring,
        )
        from kingdoms.mods.kingdoms.service import TEST_KINGDOM_ID

        strings = _strings(_locale(interaction))
        if not _is_admin(interaction, _wiring().bot_admins):
            await interaction.response.send_message(strings["not_allowed"], ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await _refresh_realm_views_for_kingdom_safe(interaction.guild, TEST_KINGDOM_ID)
        user_id = str(getattr(interaction.user, "id", ""))
        await _close_previous_ephemeral(user_id)
        window = await interaction.followup.send(strings["refresh_done"], ephemeral=True)
        _EPHEMERAL_WINDOWS[user_id] = (interaction, monotonic(), window)


def register_kingdom_test_items(bot: discord.Client) -> None:
    """Re-register the test kingdom items on the bot (restart-proof)."""
    bot.add_dynamic_items(
        KingdomTestCreateButton,
        KingdomTestDestructButton,
        KingdomTestRefreshButton,
    )
