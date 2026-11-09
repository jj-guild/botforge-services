"""The generic mod surfaces: enroll, manage, run seasons — zero plumbing.

Every mod that declares an enrollment gets the whole parcours with ONE
call (``register_mod_surfaces``): the player panel (apply, unregister,
list the enrolled), the admin channel validation (a manual candidate
lands as a message with Accepter/Refuser buttons in the mod's declared
admin channel), the admin panel (suspend/resume, the season lifecycle
for a seasonal mod, the section's Synchroniser) — all on the platform's
gates: a suspended mod refuses the players' flows, the enrollment
window and the declared criteria decide, the admins keep every
management surface whatever the state.

The design goal (botforge-services#267): a game designer writes a
``mod.yaml`` and one ``register`` line; this module is the plumbing the
mods never re-implement.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import discord

from botforge.core.services.enrollment import (
    EnrollmentClosedError,
    EnrollmentService,
    parse_criteria,
)
from botforge.core.services.membership import MembershipService
from botforge.core.services.mod_lifecycle import ModLifecycleService, ModSuspendedError
from botforge.core.services.mod_ops_mongo import (
    ModLifecycleMongo,
    ModMembershipMongo,
    ModSeasonMongo,
)
from botforge.core.services.season import SeasonService
from botforge.discord.guards import require_admin

logger = logging.getLogger("botforge.discord.mod_surfaces")

_NS = "modops"


def _database() -> Any | None:
    """Return the shared async Mongo database; None when not wired (tests)."""
    try:
        from botforge.core.models.db import get_async_database

        return get_async_database()
    except Exception:
        return None


@dataclass
class _Services:
    """One guild's wired service stack (built lazily, degraded quietly)."""

    enrollment: EnrollmentService | None
    membership: MembershipService
    lifecycle: ModLifecycleService
    members: ModMembershipMongo
    seasons: SeasonService | None
    season_db: ModSeasonMongo | None


class ModSurfaces:
    """The per-mod surface stack: player panel + admin channel + admin panel."""

    def __init__(
        self,
        bot: Any,
        mod_name: str,
        *,
        seasonal: bool,
        criteria: dict[str, Any] | None,
        game_key: str = "",
        admin_channel_key: str = "admin",
    ) -> None:
        """Bind the bot, the mod's declaration-derived settings."""
        self._bot = bot
        self._mod = mod_name
        self._seasonal = seasonal
        self._criteria = criteria or {}
        self._game_key = game_key
        self._admin_channel_key = admin_channel_key

    # ── services ────────────────────────────────────────────────────────

    def _services(self, guild_id: str) -> _Services | None:
        """Wire this guild's stack (None when the database is not wired)."""
        database = _database()
        if database is None:
            return None
        members = ModMembershipMongo(database, self._mod)
        membership = MembershipService(self._mod, hooks=members)
        lifecycle = ModLifecycleService(ModLifecycleMongo(database))
        seasons: SeasonService | None = None
        season_db: ModSeasonMongo | None = None
        if self._seasonal:
            from botforge.core.ids import mod_scope

            season_db = ModSeasonMongo(database, mod_scope(self._mod, self._game_key, guild_id))
            try:
                from botforge.core.services.game_data import GameDataService
                from botforge.game_aoe2.seed import MongoAoE2Database

                game_data = GameDataService(MongoAoE2Database(database))
            except Exception:
                logger.warning("MOD %s: game data unavailable — seasons without pools", self._mod)
                game_data = None
            seasons = SeasonService(season_db, game_data)  # type: ignore[arg-type]
        enrollment_db = _EnrollmentCollection(database, self._enrollment_scope(guild_id))
        enrollment = EnrollmentService(
            self._mod,
            enrollment_db,
            game_key=self._game_key,
            criteria=self._criteria,
            lifecycle=lifecycle,
        )
        return _Services(
            enrollment=enrollment,
            membership=membership,
            lifecycle=lifecycle,
            members=members,
            seasons=seasons,
            season_db=season_db,
        )

    def _enrollment_scope(self, guild_id: str) -> str:
        """Return the enrollment store's scope: the mod + the guild."""
        return f"{self._mod}:{guild_id}"

    async def _active_season(self, services: _Services) -> Any | None:
        """Return the guild's active season (seasonal mods; None otherwise)."""
        if services.seasons is None or services.season_db is None:
            return None
        return await services.seasons.get_active_season(services.season_db._ladder) 

    # ── guards ──────────────────────────────────────────────────────────

    async def _is_admin(self, interaction: discord.Interaction) -> bool:
        """Bot admins and the mod's admin roles pass; everyone else is denied."""
        admins = getattr(getattr(self._bot, "status_service", None), "bot_admins", ()) or ()
        roles_service = getattr(self._bot, "roles_service", None)
        return await require_admin(
            interaction, tuple(admins), roles_service, denied_message="Réservé aux admins du mod."
        )

    # ── the player panel ────────────────────────────────────────────────

    async def open_player_panel(self, interaction: discord.Interaction) -> None:
        """Answer the /<mod> command with the ephemeral player panel."""
        guild_id = str(interaction.guild_id or "")
        services = self._services(guild_id)
        if services is None:
            await interaction.response.send_message("Le mod n'est pas configuré.", ephemeral=True)
            return
        suspended = await services.lifecycle.is_suspended(guild_id, self._mod)
        view = discord.ui.LayoutView(timeout=None)
        lines = [f"# {self._mod}"]
        if suspended:
            lines.append("_Le mod est suspendu — les inscriptions sont fermées._")
        view.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay("\n".join(lines)),
                accent_colour=discord.Colour(0x5865F2),
            )
        )
        row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        disabled = suspended
        row.add_item(ApplyButton(self._mod, disabled=disabled))
        row.add_item(UnregisterButton(self._mod))
        row.add_item(MembersButton(self._mod))
        view.add_item(row)
        await interaction.response.send_message(view=view, ephemeral=True)

    # ── enrollment flows ────────────────────────────────────────────────

    async def apply(self, interaction: discord.Interaction) -> None:
        """One player applies; the criteria and the window decide."""
        guild_id = str(interaction.guild_id or "")
        services = self._services(guild_id)
        if services is None or services.enrollment is None:
            await interaction.response.send_message("Le mod n'est pas configuré.", ephemeral=True)
            return
        user_id = str(interaction.user.id)
        display = str(getattr(interaction.user, "display_name", "") or user_id)
        season = None
        season_start = None
        if self._seasonal:
            active = await self._active_season(services)
            if active is None:
                await interaction.response.send_message(
                    "Aucune saison active — les inscriptions attendront la prochaine saison.",
                    ephemeral=True,
                )
                return
            season = active.id
            season_start = active.start_at
        try:
            application = await services.enrollment.apply(
                guild_id, user_id, display, season=season, season_start=season_start
            )
        except ModSuspendedError as error:
            await interaction.response.send_message(
                f"Le mod est suspendu{(' — ' + error.reason) if error.reason else ''}.",
                ephemeral=True,
            )
            return
        except EnrollmentClosedError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        if application.state == "accepted":
            await interaction.response.send_message("✅ Inscription acceptée — bienvenue !", ephemeral=True)
            return
        if application.state == "refused":
            reasons = "\n".join(f"• {r}" for r in application.reasons) or "critères non remplis"
            await interaction.response.send_message(f"❌ Inscription refusée :\n{reasons}", ephemeral=True)
            return
        # pending: the manual review — the admins hear about it
        await interaction.response.send_message(
            "⏳ Candidature enregistrée — un admin va la valider.", ephemeral=True
        )
        await self._notify_admin_channel(guild_id, services, application.application_id, display)

    async def unregister(self, interaction: discord.Interaction) -> None:
        """One player leaves (idempotent)."""
        guild_id = str(interaction.guild_id or "")
        services = self._services(guild_id)
        if services is None:
            await interaction.response.send_message("Le mod n'est pas configuré.", ephemeral=True)
            return
        await services.membership.unregister(guild_id, str(interaction.user.id))
        await interaction.response.send_message("👋 Désinscription enregistrée.", ephemeral=True)

    async def list_members(self, interaction: discord.Interaction) -> None:
        """List the enrolled players, one line each (ephemeral)."""
        guild_id = str(interaction.guild_id or "")
        services = self._services(guild_id)
        if services is None:
            await interaction.response.send_message("Le mod n'est pas configuré.", ephemeral=True)
            return
        members = await services.members.list_members(guild_id)
        if not members:
            await interaction.response.send_message("Aucun inscrit pour l'instant.", ephemeral=True)
            return
        lines = [f"# 👥 {self._mod} — {len(members)} inscrits"]
        lines.extend(f"• {m.get('display_name')}" for m in members[:80])
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    # ── the admin channel validation ────────────────────────────────────

    async def _notify_admin_channel(
        self, guild_id: str, services: _Services, application_id: str, display_name: str
    ) -> None:
        """Post one candidate in the mod's declared admin channel (best-effort)."""
        channel_service = getattr(self._bot, "channel_service", None)
        if channel_service is None:
            return
        try:
            channel = await channel_service.get_channel_for_category(
                guild_id, f"{self._mod}:{self._admin_channel_key}"
            )
        except Exception:
            logger.warning(
                "MOD %s: admin channel unresolved — candidate %s not notified",
                self._mod,
                application_id,
                exc_info=True,
            )
            return
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## 📥 Nouvelle candidature — {display_name}\n"
                    f"Valider l'inscription de {display_name} au mod {self._mod} ?"
                ),
                accent_colour=discord.Colour(0xF1C40F),
            )
        )
        row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        row.add_item(CandidateDecideButton(self._mod, "accept", application_id, "✅ Accepter"))
        row.add_item(CandidateDecideButton(self._mod, "refuse", application_id, "❌ Refuser"))
        view.add_item(row)
        try:
            channel_obj = self._bot.get_channel(int(channel.id))
            if channel_obj is not None:
                await channel_obj.send(view=view)
        except Exception:
            logger.warning(
                "MOD %s: admin channel post failed — candidate %s",
                self._mod,
                application_id,
                exc_info=True,
            )

    async def decide_candidate(self, interaction: discord.Interaction, decision: str, application_id: str) -> None:
        """Let an admin accept or refuse a candidate from the channel message."""
        if not await self._is_admin(interaction):
            return
        guild_id = str(interaction.guild_id or "")
        services = self._services(guild_id)
        if services is None or services.enrollment is None:
            await interaction.response.send_message("Le mod n'est pas configuré.", ephemeral=True)
            return
        try:
            if decision == "accept":
                application = await services.enrollment.accept(application_id)
            else:
                application = await services.enrollment.refuse(application_id)
        except Exception:
            await interaction.response.send_message("Candidature introuvable ou déjà décidée.", ephemeral=True)
            return
        emoji = "✅" if application.state == "accepted" else "❌"
        await interaction.response.send_message(
            f"{emoji} {application.display_name} — {'inscrit' if application.state == 'accepted' else 'refusé'}.",
            ephemeral=True,
        )

    # ── the admin panel ─────────────────────────────────────────────────

    async def open_admin_panel(self, interaction: discord.Interaction) -> None:
        """Open the mod's admin panel: state, candidates, seasons, sync."""
        if not await self._is_admin(interaction):
            return
        guild_id = str(interaction.guild_id or "")
        services = self._services(guild_id)
        if services is None:
            await interaction.response.send_message("Le mod n'est pas configuré.", ephemeral=True)
            return
        suspended = await services.lifecycle.is_suspended(guild_id, self._mod)
        state_line = "🛑 Suspendu" if suspended else "🟢 Actif"
        lines = [f"# ⚙️ {self._mod} — administration", f"État : {state_line}"]
        if self._seasonal and services.seasons is not None and services.season_db is not None:
            seasons = await services.seasons.list_seasons(services.season_db._ladder) 
            active = next((s for s in seasons if s.state == "active"), None)
            scheduled = next((s for s in seasons if s.state == "scheduled"), None)
            if active is not None:
                lines.append(f"Saison active : **{active.name}** (`{active.id}`)")
            if scheduled is not None:
                lines.append(f"Saison planifiée : **{scheduled.name}** (`{scheduled.id}`)")
            if active is None and scheduled is None:
                lines.append("Aucune saison — créez-en une.")
        if services.enrollment is not None:
            dashboard = await services.enrollment.dashboard(guild_id)
            lines.append(f"Candidatures : {len(dashboard['pending'])} en attente")
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay("\n".join(lines)),
                accent_colour=discord.Colour(0xE74C3C),
            )
        )
        row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        row.add_item(SuspendResumeButton(self._mod, suspend=not suspended))
        if self._seasonal:
            row.add_item(NewSeasonButton(self._mod))
            row.add_item(StartSeasonButton(self._mod))
            row.add_item(EndSeasonButton(self._mod))
        row.add_item(SyncModButton(self._mod))
        view.add_item(row)
        await interaction.response.send_message(view=view, ephemeral=True)

    async def suspend_resume(self, interaction: discord.Interaction, suspend: bool) -> None:
        """Suspend or resume the mod on this guild (admins)."""
        if not await self._is_admin(interaction):
            return
        guild_id = str(interaction.guild_id or "")
        services = self._services(guild_id)
        if services is None:
            await interaction.response.send_message("Le mod n'est pas configuré.", ephemeral=True)
            return
        if suspend:
            await services.lifecycle.suspend(guild_id, self._mod, reason="Suspension admin")
            await interaction.response.send_message(
                "🛑 Mod suspendu — les joueurs ne peuvent plus l'utiliser.", ephemeral=True
            )
        else:
            await services.lifecycle.resume(guild_id, self._mod)
            await interaction.response.send_message("🟢 Mod repris — les joueurs peuvent l'utiliser.", ephemeral=True)

    async def new_season(self, interaction: discord.Interaction, name: str) -> None:
        """Create a scheduled season (seasonal mods; admins)."""
        if not await self._is_admin(interaction):
            return
        guild_id = str(interaction.guild_id or "")
        services = self._services(guild_id)
        if services is None or services.seasons is None or services.season_db is None:
            await interaction.response.send_message("Le mod n'est pas configuré.", ephemeral=True)
            return
        import time

        try:
            season = await services.seasons.create_season(
                services.season_db._ladder, 
                name=name,
                map_pool_id=None,
                start_at=int(time.time()),
            )
        except Exception as error:
            await interaction.response.send_message(f"Création impossible : {error}", ephemeral=True)
            return
        await interaction.response.send_message(
            f"📅 Saison **{season.name}** créée (`{season.id}`) — cliquez Démarrer pour l'activer.",
            ephemeral=True,
        )

    async def start_season(self, interaction: discord.Interaction) -> None:
        """Activate the scheduled season (seasonal mods; admins)."""
        if not await self._is_admin(interaction):
            return
        guild_id = str(interaction.guild_id or "")
        services = self._services(guild_id)
        if services is None or services.seasons is None or services.season_db is None:
            await interaction.response.send_message("Le mod n'est pas configuré.", ephemeral=True)
            return
        import time

        seasons = await services.seasons.list_seasons(services.season_db._ladder) 
        scheduled = next((s for s in seasons if s.state == "scheduled"), None)
        if scheduled is None:
            await interaction.response.send_message("Aucune saison planifiée.", ephemeral=True)
            return
        try:
            season = await services.seasons.activate_season(scheduled.id, now=int(time.time()))
        except Exception as error:
            await interaction.response.send_message(f"Démarrage impossible : {error}", ephemeral=True)
            return
        await interaction.response.send_message(f"🚀 Saison **{season.name}** démarrée.", ephemeral=True)

    async def end_season(self, interaction: discord.Interaction) -> None:
        """End the active season (seasonal mods; admins)."""
        if not await self._is_admin(interaction):
            return
        guild_id = str(interaction.guild_id or "")
        services = self._services(guild_id)
        if services is None or services.seasons is None or services.season_db is None:
            await interaction.response.send_message("Le mod n'est pas configuré.", ephemeral=True)
            return
        import time

        seasons = await services.seasons.list_seasons(services.season_db._ladder) 
        active = next((s for s in seasons if s.state == "active"), None)
        if active is None:
            await interaction.response.send_message("Aucune saison active.", ephemeral=True)
            return
        season = await services.seasons.end_season(active.id, now=int(time.time()))
        await interaction.response.send_message(
            f"🏁 Saison **{season.name}** terminée — créez la suivante.", ephemeral=True
        )

    async def sync(self, interaction: discord.Interaction) -> None:
        """Re-provision the mod's channels and roles (the section's Synchroniser)."""
        if not await self._is_admin(interaction):
            return
        guild_id = str(interaction.guild_id or "")
        channel_service = getattr(self._bot, "channel_service", None)
        mod_roles_service = getattr(self._bot, "mod_roles_service", None)
        if channel_service is None or mod_roles_service is None:
            await interaction.response.send_message("Provisioning non câblé.", ephemeral=True)
            return
        try:
            await channel_service.setup_mod_channels(guild_id, self._mod)
            await mod_roles_service.setup_mod_roles(guild_id, self._mod)
        except Exception as error:
            await interaction.response.send_message(f"Synchronisation échouée : {error}", ephemeral=True)
            return
        await interaction.response.send_message("♻️ Salons et rôles du mod re-provisionnés.", ephemeral=True)


# ── the persistent items ─────────────────────────────────────────────────


class ApplyButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:(?P<mod>[a-z0-9_-]+):apply",
):
    """Let one player apply to the mod (click-time gates inside)."""

    def __init__(self, mod: str, disabled: bool = False) -> None:
        """Build with the mod's namespace in the custom id."""
        self.mod = mod
        super().__init__(
            discord.ui.Button(
                label="📝 S'inscrire",
                style=discord.ButtonStyle.primary,
                custom_id=f"{_NS}:{mod}:apply",
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
    ) -> ApplyButton:
        """Rebuild from the wire."""
        del interaction, item
        return cls(match.group("mod"))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Route to the mod's surfaces (registered at boot)."""
        surfaces = _SURFACES.get(self.mod)
        if surfaces is None:
            await interaction.response.send_message("Mod inconnu.", ephemeral=True)
            return
        await surfaces.apply(interaction)


class UnregisterButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:(?P<mod>[a-z0-9_-]+):unregister",
):
    """Let one player leave the mod."""

    def __init__(self, mod: str) -> None:
        """Build with the mod's namespace in the custom id."""
        self.mod = mod
        super().__init__(
            discord.ui.Button(
                label="👋 Se désinscrire",
                style=discord.ButtonStyle.secondary,
                custom_id=f"{_NS}:{mod}:unregister",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> UnregisterButton:
        """Rebuild from the wire."""
        del interaction, item
        return cls(match.group("mod"))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Route to the mod's surfaces."""
        surfaces = _SURFACES.get(self.mod)
        if surfaces is None:
            await interaction.response.send_message("Mod inconnu.", ephemeral=True)
            return
        await surfaces.unregister(interaction)


class MembersButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:(?P<mod>[a-z0-9_-]+):members",
):
    """List the enrolled players of the mod."""

    def __init__(self, mod: str) -> None:
        """Build with the mod's namespace in the custom id."""
        self.mod = mod
        super().__init__(
            discord.ui.Button(
                label="👥 Inscrits",
                style=discord.ButtonStyle.secondary,
                custom_id=f"{_NS}:{mod}:members",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> MembersButton:
        """Rebuild from the wire."""
        del interaction, item
        return cls(match.group("mod"))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Route to the mod's surfaces."""
        surfaces = _SURFACES.get(self.mod)
        if surfaces is None:
            await interaction.response.send_message("Mod inconnu.", ephemeral=True)
            return
        await surfaces.list_members(interaction)


class CandidateDecideButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:(?P<mod>[a-z0-9_-]+):cand:(?P<decision>accept|refuse):(?P<application_id>[a-zA-Z0-9:_-]+)",
):
    """An admin decides one candidate from the admin channel's message."""

    def __init__(self, mod: str, decision: str, application_id: str, label: str) -> None:
        """Build with the decision and the candidate's application id."""
        self.mod = mod
        self.decision = decision
        self.application_id = application_id
        style = discord.ButtonStyle.success if decision == "accept" else discord.ButtonStyle.danger
        super().__init__(
            discord.ui.Button(
                label=label,
                style=style,
                custom_id=f"{_NS}:{mod}:cand:{decision}:{application_id}"[:100],
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> CandidateDecideButton:
        """Rebuild from the wire."""
        del interaction, item
        label = "✅ Accepter" if match.group("decision") == "accept" else "❌ Refuser"
        return cls(match.group("mod"), match.group("decision"), match.group("application_id"), label)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Route to the mod's surfaces (admin-guarded inside)."""
        surfaces = _SURFACES.get(self.mod)
        if surfaces is None:
            await interaction.response.send_message("Mod inconnu.", ephemeral=True)
            return
        await surfaces.decide_candidate(interaction, self.decision, self.application_id)


class SuspendResumeButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:(?P<mod>[a-z0-9_-]+):suspend:(?P<action>suspend|resume)",
):
    """Suspend or resume the mod (admins)."""

    def __init__(self, mod: str, suspend: bool) -> None:
        """Build with the target action."""
        self.mod = mod
        self.suspend = suspend
        super().__init__(
            discord.ui.Button(
                label="🛑 Suspendre" if suspend else "🟢 Reprendre",
                style=discord.ButtonStyle.danger if suspend else discord.ButtonStyle.success,
                custom_id=f"{_NS}:{mod}:suspend:{'suspend' if suspend else 'resume'}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> SuspendResumeButton:
        """Rebuild from the wire."""
        del interaction, item
        return cls(match.group("mod"), match.group("action") == "suspend")

    async def callback(self, interaction: discord.Interaction) -> None:
        """Route to the mod's surfaces (admin-guarded inside)."""
        surfaces = _SURFACES.get(self.mod)
        if surfaces is None:
            await interaction.response.send_message("Mod inconnu.", ephemeral=True)
            return
        await surfaces.suspend_resume(interaction, suspend=self.suspend)


class NewSeasonButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:(?P<mod>[a-z0-9_-]+):season:new",
):
    """Create a new season (seasonal mods; admins; opens the name modal)."""

    def __init__(self, mod: str) -> None:
        """Build with the mod's namespace in the custom id."""
        self.mod = mod
        super().__init__(
            discord.ui.Button(
                label="📅 Nouvelle saison",
                style=discord.ButtonStyle.primary,
                custom_id=f"{_NS}:{mod}:season:new",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> NewSeasonButton:
        """Rebuild from the wire."""
        del interaction, item
        return cls(match.group("mod"))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the season-name modal (admin-guarded on submit)."""
        surfaces = _SURFACES.get(self.mod)
        if surfaces is None:
            await interaction.response.send_message("Mod inconnu.", ephemeral=True)
            return
        await interaction.response.send_modal(NewSeasonModal(surfaces, self.mod))


class NewSeasonModal(discord.ui.Modal):
    """The new season's name."""

    def __init__(self, surfaces: ModSurfaces, mod: str) -> None:
        """Bind the mod's surfaces."""
        super().__init__(title=f"Nouvelle saison — {mod}", timeout=300.0)
        self._surfaces = surfaces
        self.name_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label="Nom de la saison", placeholder="Saison III — la revanche", max_length=80
        )
        self.add_item(discord.ui.Label(text="Nom", component=self.name_input))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Create the scheduled season."""
        await self._surfaces.new_season(interaction, str(self.name_input.value or "").strip())


class StartSeasonButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:(?P<mod>[a-z0-9_-]+):season:start",
):
    """Start the scheduled season (seasonal mods; admins)."""

    def __init__(self, mod: str) -> None:
        """Build with the mod's namespace in the custom id."""
        self.mod = mod
        super().__init__(
            discord.ui.Button(
                label="🚀 Démarrer la saison",
                style=discord.ButtonStyle.success,
                custom_id=f"{_NS}:{mod}:season:start",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> StartSeasonButton:
        """Rebuild from the wire."""
        del interaction, item
        return cls(match.group("mod"))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Route to the mod's surfaces (admin-guarded inside)."""
        surfaces = _SURFACES.get(self.mod)
        if surfaces is None:
            await interaction.response.send_message("Mod inconnu.", ephemeral=True)
            return
        await surfaces.start_season(interaction)


class EndSeasonButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:(?P<mod>[a-z0-9_-]+):season:end",
):
    """End the active season (seasonal mods; admins)."""

    def __init__(self, mod: str) -> None:
        """Build with the mod's namespace in the custom id."""
        self.mod = mod
        super().__init__(
            discord.ui.Button(
                label="🏁 Terminer la saison",
                style=discord.ButtonStyle.secondary,
                custom_id=f"{_NS}:{mod}:season:end",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> EndSeasonButton:
        """Rebuild from the wire."""
        del interaction, item
        return cls(match.group("mod"))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Route to the mod's surfaces (admin-guarded inside)."""
        surfaces = _SURFACES.get(self.mod)
        if surfaces is None:
            await interaction.response.send_message("Mod inconnu.", ephemeral=True)
            return
        await surfaces.end_season(interaction)


class SyncModButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:(?P<mod>[a-z0-9_-]+):sync",
):
    """The mod's section Synchroniser: re-provision its channels and roles."""

    def __init__(self, mod: str) -> None:
        """Build with the mod's namespace in the custom id."""
        self.mod = mod
        super().__init__(
            discord.ui.Button(
                label="♻️ Synchroniser",
                style=discord.ButtonStyle.secondary,
                custom_id=f"{_NS}:{mod}:sync",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> SyncModButton:
        """Rebuild from the wire."""
        del interaction, item
        return cls(match.group("mod"))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Route to the mod's surfaces (admin-guarded inside)."""
        surfaces = _SURFACES.get(self.mod)
        if surfaces is None:
            await interaction.response.send_message("Mod inconnu.", ephemeral=True)
            return
        await surfaces.sync(interaction)


# ── the registration seam ────────────────────────────────────────────────

_SURFACES: dict[str, ModSurfaces] = {}
_PERSISTENT_ITEMS = (
    ApplyButton,
    UnregisterButton,
    MembersButton,
    CandidateDecideButton,
    SuspendResumeButton,
    NewSeasonButton,
    StartSeasonButton,
    EndSeasonButton,
    SyncModButton,
)


def register_mod_surfaces(
    bot: Any,
    mod_name: str,
    *,
    seasonal: bool,
    settings: dict[str, Any] | None = None,
    game_key: str = "",
    admin_channel_key: str = "admin",
) -> ModSurfaces:
    """Give one mod the whole player+admin parcours (idempotent).

    Wires the ``/<mod>`` command (the player panel) and registers the
    persistent items; the criteria come from the declaration's
    ``settings.enrollment`` (parsed and validated here — a broken
    declaration fails loudly at boot, never silently disables).
    """
    criteria = parse_criteria(settings)
    surfaces = ModSurfaces(
        bot,
        mod_name,
        seasonal=seasonal,
        criteria=criteria,
        game_key=game_key,
        admin_channel_key=admin_channel_key,
    )
    _SURFACES[mod_name] = surfaces
    for item_cls in _PERSISTENT_ITEMS:
        bot.add_dynamic_items(item_cls)

    @discord.app_commands.command(
        name=mod_name,
        description=f"{mod_name} — inscriptions et panel du mod",
    )
    async def _mod_command(interaction: discord.Interaction) -> None:
        """Answer with the mod's player panel (ephemeral)."""
        await surfaces.open_player_panel(interaction)

    existing = {command.name for command in bot.tree.get_commands()}
    if _mod_command.name not in existing:
        bot.tree.add_command(_mod_command)
    logger.info(
        "MOD SURFACES registered: %s (seasonal=%s, criteria=%s)",
        mod_name,
        seasonal,
        sorted(criteria),
    )
    return surfaces


def registered_mod_surfaces() -> tuple[str, ...]:
    """Return the mods carrying the generic surfaces (diagnostics, tests)."""
    return tuple(sorted(_SURFACES))


def mod_surfaces_of(mod_name: str) -> ModSurfaces | None:
    """One mod's surfaces; None when the mod has none (tests)."""
    return _SURFACES.get(mod_name)


class _EnrollmentCollection:
    """The EnrollmentDatabase protocol over one Mongo collection per scope."""

    def __init__(self, database: Any, scope: str) -> None:
        """Bind the shared database and the scope's collection name."""
        self._db = database
        self._scope = scope

    async def _collection(self) -> Any:
        """Return the scope's applications collection."""
        return self._db[f"{self._scope}:applications"]

    async def upsert_application(self, document: dict[str, Any]) -> None:
        """Insert or replace one application by ``_id``."""
        await (await self._collection()).update_one(
            {"_id": document["_id"]}, {"$set": document}, upsert=True
        )

    async def find_application(self, application_id: str) -> dict[str, Any] | None:
        """Return one application; None when absent."""
        doc = await (await self._collection()).find_one({"_id": application_id})
        return dict(doc) if doc else None

    async def find_active_application(self, mod: str, guild_id: str, user_id: str) -> dict[str, Any] | None:
        """Return the user's pending application; None when none."""
        doc = await (await self._collection()).find_one(
            {"mod": mod, "guild_id": guild_id, "user_id": user_id, "state": "pending"}
        )
        return dict(doc) if doc else None

    async def list_applications(self, mod: str, guild_id: str, state: str | None = None) -> list[dict[str, Any]]:
        """List the guild's applications (one state or all)."""
        query: dict[str, Any] = {"mod": mod, "guild_id": guild_id}
        if state is not None:
            query["state"] = state
        cursor = (await self._collection()).find(query)
        return [doc async for doc in cursor]

    async def count_members(self, mod: str, guild_id: str) -> int:
        """Return the enrolled count (the dashboard's header)."""
        count = await (await self._collection()).count_documents(
            {"mod": mod, "guild_id": guild_id, "state": "accepted"}
        )
        return int(count)


__all__ = [
    "ModSurfaces",
    "mod_surfaces_of",
    "register_mod_surfaces",
    "registered_mod_surfaces",
]
