"""The seasonal mods' pinned panels — saisons, candidats, inscrits (P3).

The owner's spec (2026-11-14): every seasonal mod's folder carries
three pinned surfaces:

- **saisons** — the active season's state + the creation button (the
  wizard: the enrollment parameters, the validation mode, the player
  bounds, the dates); a new season only when the active is finished
  (the SeasonService's gate)
- **candidats** — admin-only: the pending queue, one validate/refuse
  pair per candidate; only the admins decide
- **inscrits** — the enrolled members list

The panels ride the per-mod season stack (SeasonService +
EnrollmentService + SeasonRolesService); the ids resolve through the
stored mappings; every string localizes.
"""

from __future__ import annotations

import logging
from typing import Any

import discord

logger = logging.getLogger("botforge.discord.season_panels")

_NS = "season"


def _stack(bot: Any, mod: str, guild_id: str = "") -> Any:
    """Return the mod's season stack on the guild (lazily built, cached)."""
    from botforge.core.services.season_stack import season_stack_for

    return season_stack_for(bot, mod, guild_id)


def _fmt_ts(value: Any) -> str:
    """Format one timestamp as a Discord timestamp (or a dash)."""
    try:
        ts = int(value)
        if ts > 0:
            return f"<t:{ts}:D>"
    except (TypeError, ValueError):
        pass
    return "—"


async def build_seasons_panel(bot: Any, guild_id: str, mod: str, locale: str = "fr") -> discord.ui.LayoutView:
    """Build the SAISONS panel: the active season + the creation button."""
    view = discord.ui.LayoutView(timeout=None)
    stack = _stack(bot, mod, guild_id)
    lines = [f"# \U0001f4c5 {mod.capitalize()} — saisons"]
    active = None
    if stack is not None:
        try:
            active = await await_active(stack, guild_id)
        except Exception:
            logger.warning("SEASON PANEL: the active season unreadable", exc_info=True)
    if active is None:
        lines.append("_Aucune saison active._")
    else:
        season_id = str(getattr(active, "id", "?"))
        name = str(getattr(active, "name", season_id))
        state = str(getattr(active, "state", "?"))
        lines.append(f"## {name} (`{season_id}`)")
        lines.append(f"\u2022 État : **{state}**")
        lines.append(f"\u2022 Début : {_fmt_ts(getattr(active, 'start_at', None))}")
        lines.append(f"\u2022 Fin : {_fmt_ts(getattr(active, 'end_at', None))}")
    view.add_item(discord.ui.Container(discord.ui.TextDisplay("\n".join(lines))))
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row.add_item(SeasonCreateButton(mod))
    view.add_item(row)
    from botforge.discord.ui.view_footer import add_view_footer

    add_view_footer(view, f"panel:mod:{mod}:seasons")
    return view


async def build_candidates_panel(bot: Any, guild_id: str, mod: str, locale: str = "fr") -> discord.ui.LayoutView:
    """Build the CANDIDATS panel: the pending queue, admin-only decisions."""
    view = discord.ui.LayoutView(timeout=None)
    stack = _stack(bot, mod, guild_id)
    lines = [f"# \U0001f9e1 {mod.capitalize()} — candidats", "_File d'attente (admin only)._"]
    pending: list[Any] = []
    if stack is not None:
        try:
            pending = list(await stack.enrollment.list_applications(guild_id, state="pending"))
        except Exception:
            logger.warning("SEASON PANEL: the queue unreadable", exc_info=True)
    for application in pending[:20]:
        user_id = str(getattr(application, "user_id", "?"))
        display = str(getattr(application, "display_name", "?"))
        lines.append(f"\u2022 **{display}** (<@{user_id}>) — `{user_id}`")
    if not pending:
        lines.append("_Aucun candidat en attente._")
    view.add_item(discord.ui.Container(discord.ui.TextDisplay("\n".join(lines))))
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    for application in pending[:5]:
        user_id = str(getattr(application, "user_id", ""))
        row.add_item(CandidateDecideButton(mod, user_id, True))
        row.add_item(CandidateDecideButton(mod, user_id, False))
    view.add_item(row)
    from botforge.discord.ui.view_footer import add_view_footer

    add_view_footer(view, f"panel:mod:{mod}:candidates")
    return view


async def build_enrolled_panel(bot: Any, guild_id: str, mod: str, locale: str = "fr") -> discord.ui.LayoutView:
    """Build the INSCRITS panel: the enrolled members list."""
    view = discord.ui.LayoutView(timeout=None)
    stack = _stack(bot, mod, guild_id)
    lines = [f"# \U0001f465 {mod.capitalize()} — inscrits"]
    accepted: list[Any] = []
    if stack is not None:
        try:
            accepted = list(await stack.enrollment.list_applications(guild_id, state="accepted"))
        except Exception:
            logger.warning("SEASON PANEL: the enrolled list unreadable", exc_info=True)
    for application in accepted[:40]:
        user_id = str(getattr(application, "user_id", "?"))
        display = str(getattr(application, "display_name", "?"))
        lines.append(f"\u2022 **{display}** (<@{user_id}>)")
    if not accepted:
        lines.append("_Aucun inscrit._")
    view.add_item(discord.ui.Container(discord.ui.TextDisplay("\n".join(lines))))
    from botforge.discord.ui.view_footer import add_view_footer

    add_view_footer(view, f"panel:mod:{mod}:enrolled")
    return view


async def await_active(stack: Any, guild_id: str) -> Any:
    """Return the mod's active season (the stack's own resolver)."""
    del guild_id
    return await stack.active_season()


class SeasonCreateButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:create:(?P<mod>[a-z0-9_-]+)",
):
    """The creation button: the wizard walks the owner's parameters."""

    def __init__(self, mod: str) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:create:{mod}"[:100],
                label="Créer une saison",
                emoji="\U0001f513",
                style=discord.ButtonStyle.success,
            )
        )
        self.mod = mod

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: Any,
        /,
    ) -> SeasonCreateButton:
        """Rebuild the button at click time."""
        return cls(match["mod"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Run the creation wizard (guarded, ephemeral)."""
        from botforge.discord.mod_beta import _beta_guard
        from botforge.discord.ui.wizard import WizardState

        if not await _beta_guard(interaction):
            return
        if _stack(interaction.client, self.mod) is None:
            await interaction.response.send_message(
                "The mod's season stack is not wired.", ephemeral=True
            )
            return
        state = WizardState(subject_id=self.mod)
        await interaction.response.send_modal(_SeasonNameModal(state))


class _SeasonNameModal(discord.ui.Modal, title="Le nom de la saison"):
    """The wizard's first step; the flow rides closures over the state."""

    name: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Nom", placeholder="Saison 2", max_length=64
    )

    def __init__(self, state: Any) -> None:
        super().__init__()
        self._state = state

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Record the name, then the validation mode (the wizard continues)."""
        from botforge.discord.ui.wizard import ask_confirm, ask_select

        state = self._state
        state.name = str(self.name.value or "").strip()
        await interaction.response.defer(ephemeral=True)

        async def _on_mode(inner: discord.Interaction, value: str, label: str) -> None:
            state.set("validation", value, label)

            async def _create(inner2: discord.Interaction) -> None:
                await _create_season(inner2, state)

            await ask_confirm(
                inner,
                content=(
                    f"# {state.name or 'Nouvelle saison'}\n"
                    f"Validation : **{label}**\n\nCréer la saison maintenant ?"
                ),
                button_label="Créer",
                on_confirm=_create,
            )

        await ask_select(
            interaction,
            placeholder="La validation des candidatures",
            options=[
                discord.SelectOption(label="Manuelle (les admins décident)", value="manual"),
                discord.SelectOption(label="Automatique (les critères décident)", value="auto"),
            ],
            content=f"# Nouvelle saison — {state.name}\nLa validation ?",
            on_pick=_on_mode,
            empty_label="Manuelle",
        )


async def _create_season(interaction: discord.Interaction, state: Any) -> None:
    """Create the season (the service's gate refuses a live one)."""
    stack = _stack(interaction.client, str(state.subject_id or ""), str(interaction.guild_id or ""))
    if stack is None:
        await interaction.followup.send("The season stack is not wired.", ephemeral=True)
        return
    try:
        season = await stack.seasons.create_season(
            stack.scope,
            str(state.name or "Saison"),
            None,
            start_at=int(state.get("start_at") or 0),
        )
    except Exception as exc:
        await interaction.followup.send(f"La création a refusé : {exc}", ephemeral=True)
        return
    await interaction.followup.send(
        f"Saison **{season.name}** créée (`{season.id}`).", ephemeral=True
    )


class CandidateDecideButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:decide:(?P<mod>[a-z0-9_-]+):(?P<user>\d+):(?P<accept>yes|no)",
):
    """One candidate's validate/refuse button (admin-only)."""

    def __init__(self, mod: str, user_id: str, accept: bool) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:decide:{mod}:{user_id}:{'yes' if accept else 'no'}"[:100],
                label="\u2713" if accept else "\u2717",
                style=discord.ButtonStyle.success if accept else discord.ButtonStyle.danger,
            )
        )
        self.mod = mod
        self.user_id = user_id
        self.accept = accept

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: Any,
        /,
    ) -> CandidateDecideButton:
        """Rebuild the button at click time."""
        return cls(match["mod"], match["user"], match["accept"] == "yes")

    async def callback(self, interaction: discord.Interaction) -> None:
        """Validate or refuse the candidate (guarded, ephemeral, 3s rule)."""
        from botforge.discord.mod_beta import _beta_guard

        if not await _beta_guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        stack = _stack(interaction.client, self.mod, str(interaction.guild_id or ""))
        if stack is None:
            await interaction.followup.send("The season stack is not wired.", ephemeral=True)
            return
        guild_id = str(interaction.guild_id or "")
        application = await _find_application(stack, guild_id, self.user_id)
        if application is None:
            await interaction.followup.send("Candidature introuvable (déjà traitée ?).", ephemeral=True)
            return
        try:
            if self.accept:
                await stack.enrollment.accept(str(application.id))
            else:
                await stack.enrollment.refuse(str(application.id))
        except Exception:
            logger.warning("SEASON PANEL: the decision failed", exc_info=True)
            await interaction.followup.send("La décision a échoué — voir les logs.", ephemeral=True)
            return
        await interaction.followup.send(
            f"{'Validé' if self.accept else 'Refusé'} : <@{self.user_id}>.", ephemeral=True
        )


async def _find_application(stack: Any, guild_id: str, user_id: str) -> Any:
    """Find one pending application by user id."""
    for application in await stack.enrollment.list_applications(guild_id, state="pending"):
        if str(getattr(application, "user_id", "")) == user_id:
            return application
    return None


__all__ = [
    "CandidateDecideButton",
    "SeasonCreateButton",
    "build_candidates_panel",
    "build_enrolled_panel",
    "build_seasons_panel",
]


# --- the seasonal mods' pinned panels (the install pins them) ---------


def register_season_pins(bot: Any, registry: Any) -> list[Any]:
    """Register the three season panels' pins for every enabled seasonal mod.

    Idempotent (the static-pin store keeps the first per key); the
    install's scope refresh re-renders them (the pins carry the mod's
    scope), and the boot's ensure pass heals them.
    """
    from botforge.discord.static_pins import StaticPinnedView, register_static_pin
    from botforge.discord.ui.panels_provisioning import stored_channel_id

    mods = getattr(registry, "enabled", None)
    if mods is None:
        return []
    specs: list[Any] = []
    message_registry = getattr(bot, "message_registry", None)
    for mod in mods():
        definition = registry.get(mod)
        if definition is None or not getattr(definition, "seasonal", False):
            continue
        for channel_key, panel_builder, pin_key in (
            ("seasons", build_seasons_panel, "seasons"),
            ("candidates", build_candidates_panel, "candidates"),
            ("enrolled", build_enrolled_panel, "enrolled"),
        ):
            scope = f"mod/{mod}"

            async def _resolve_channel(guild_id: str, _scope: str = scope, _key: str = channel_key) -> str:
                return await stored_channel_id(guild_id, _scope, _key) or ""

            async def _build(guild_id: str, _mod: str = mod, _builder: Any = panel_builder) -> Any:
                return await _builder(bot, guild_id, _mod)

            specs.append(
                register_static_pin(
                    StaticPinnedView(
                        key=f"view:mod:{mod}:{pin_key}",
                        mark_suffix=f"view:mod:{mod}:{pin_key}",
                        resolve_channel=_resolve_channel,
                        build_layout=_build,
                        registry=message_registry,
                        scope=scope,
                    )
                )
            )
    return specs


__all__.extend(["register_season_pins"])
