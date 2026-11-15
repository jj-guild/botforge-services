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



# --- the season's PHASE machine (the owner's drastic simplification) ----
# préparation -> inscriptions ouvertes -> en attente d'ouverture -> ouverte -> fermée
_PHASES = ("preparation", "inscriptions", "attente", "ouverte", "fermee")
_PHASE_LABELS = {
    "preparation": "Préparation",
    "inscriptions": "Inscriptions ouvertes",
    "attente": "En attente d'ouverture",
    "ouverte": "Ouverte",
    "fermee": "Fermée",
}
_NEXT_LABELS = {
    "preparation": "Ouvrir les inscriptions",
    "inscriptions": "Fermer les inscriptions",
    "attente": "Démarrer la saison",
    "ouverte": "Fermer la saison",
}


def _phase_of(config: dict[str, Any]) -> str:
    """Return the season's phase (the preparation by default)."""
    phase = str(config.get("phase") or "preparation")
    return phase if phase in _PHASES else "preparation"


class SeasonPhaseButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:phase:(?P<mod>[a-z0-9_-]+):(?P<direction>next|prev|start)",
):
    """The season's phase transition: next or previous (the owner's flow).

    One linear machine: préparation -> inscriptions ouvertes -> en
    attente d'ouverture -> ouverte -> fermée — and back. The post
    updates in place; no message, nothing else.
    """

    def __init__(self, mod: str, direction: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:phase:{mod}:{direction}"[:100],
                label=label,
                style=discord.ButtonStyle.success if direction == "next" else discord.ButtonStyle.secondary,
            )
        )
        self.mod = mod
        self.direction = direction

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: Any,
        /,
    ) -> SeasonPhaseButton:
        """Rebuild the button at click time (the label rides the state)."""
        return cls(match["mod"], match["direction"], match["direction"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Move the phase, persist, update the post (guarded)."""
        from botforge.discord.mod_beta import _beta_guard

        if not await _beta_guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id or "")
        stack = _stack(interaction.client, self.mod, guild_id)
        if stack is None:
            return
        active = await await_active(stack, guild_id)
        if active is None:
            return
        season_id = str(getattr(active, "id", ""))
        config = await _load_season_config(interaction.client, self.mod, guild_id, season_id)
        phase = _phase_of(config)
        index = _PHASES.index(phase)
        if self.direction == "start":
            # the owner's shortcut: start the season WITHOUT closing the
            # inscriptions (inscriptions -> ouverte directly)
            index = _PHASES.index("ouverte") if phase == "inscriptions" else index
        elif self.direction == "next":
            index = min(index + 1, len(_PHASES) - 1)
        else:
            index = max(index - 1, 0)
        config["phase"] = _PHASES[index]
        config["season_id"] = season_id
        await _persist_season_config(interaction.client, self.mod, guild_id, config)
        await _refresh_seasons_pin(interaction.client, guild_id, self.mod)


async def build_seasons_panel(bot: Any, guild_id: str, mod: str, locale: str = "fr") -> discord.ui.LayoutView:
    """Build the SAISONS panel (the owner's drastic simplification).

    The name, the phase, the TODO criteria, the counts, the transitions.
    """
    stack = _stack(bot, mod, guild_id)
    active = None
    if stack is not None:
        try:
            active = await await_active(stack, guild_id)
        except Exception:
            logger.warning("SEASON PANEL: the active season unreadable", exc_info=True)
    view = discord.ui.LayoutView(timeout=None)
    if active is None:
        view.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"# \U0001f4c5 {mod.capitalize()} — saisons"),
                discord.ui.TextDisplay("_Aucune saison active._"),
            )
        )
        from botforge.discord.ui.factory import split_action_rows
        from botforge.discord.ui.view_footer import add_view_footer

        for row in split_action_rows([SeasonCreateButton(mod).item]):
            view.add_item(row)
        add_view_footer(view, f"panel:mod:{mod}:seasons")
        return view
    season_id = str(getattr(active, "id", ""))
    config = await _load_season_config(bot, mod, guild_id, season_id)
    name = str(config.get("name") or getattr(active, "name", season_id))
    phase = _phase_of(config)
    candidates, enrolled = await _enrollment_counts(bot, mod, guild_id)
    lines = [f"# {name}"]
    lines.append(f"\u00c9tat : **{_PHASE_LABELS[phase]}**")
    lines.append("")
    lines.append("**Crit\u00e8res** (\u00e0 venir) : un compte AoE2 + la validation admin dans le channel admin")
    lines.append(f"\U0001f9e1 Candidats : **{candidates}** \u00b7 \U0001f465 Inscrits : **{enrolled}**")
    view.add_item(discord.ui.Container(discord.ui.TextDisplay("\n".join(lines))))
    from botforge.discord.ui.factory import split_action_rows
    from botforge.discord.ui.view_footer import add_view_footer

    items: list[Any] = []
    index = _PHASES.index(phase)
    if index > 0:
        items.append(
            discord.ui.Button(
                custom_id=f"{_NS}:phase:{mod}:prev"[:100],
                label="\u2190",
                style=discord.ButtonStyle.secondary,
            )
        )
    next_label = _NEXT_LABELS.get(phase)
    if next_label:
        items.append(SeasonPhaseButton(mod, "next", next_label).item)
    if phase == "inscriptions":
        # the direct start: the season may open WITHOUT closing the
        # inscriptions (the owner's choice, 2026-11-15)
        items.append(SeasonPhaseButton(mod, "start", "Démarrer la saison").item)
        items.append(SeasonApplyButton(mod).item)
    items.append(SeasonAdminButton(mod).item)
    for row in split_action_rows(items):
        view.add_item(row)
    add_view_footer(view, f"panel:mod:{mod}:seasons:{season_id}")
    return view


class SeasonAdminButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:admin:(?P<mod>[a-z0-9_-]+)",
):
    """The post's admin button: opens the NAME modal (the only edit)."""

    def __init__(self, mod: str) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:admin:{mod}"[:100],
                label="Admin",
                emoji="\U0001f513",
                style=discord.ButtonStyle.secondary,
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
    ) -> SeasonAdminButton:
        """Rebuild the button at click time."""
        return cls(match["mod"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the name modal (guarded)."""
        from botforge.discord.mod_beta import _beta_guard

        if not await _beta_guard(interaction):
            return
        guild_id = str(interaction.guild_id or "")
        stack = _stack(interaction.client, self.mod, guild_id)
        if stack is not None:
            try:
                active = await await_active(stack, guild_id)
            except Exception:
                active = None
            if active is not None:
                season_id = str(getattr(active, "id", ""))
                config = await _load_season_config(interaction.client, self.mod, guild_id, season_id)
                config["season_id"] = season_id
                config.setdefault("name", str(getattr(active, "name", "")))
                _draft_of(interaction.client, self.mod, guild_id).update(config)
        await interaction.response.send_modal(
            _SeasonNameModal(interaction.client, self.mod, guild_id)
        )




async def _enrollment_counts(bot: Any, mod: str, guild_id: str) -> tuple[int, int]:
    """Count the guild's pending candidates and accepted members."""
    stack = _stack(bot, mod, guild_id)
    if stack is None or stack.enrollment is None:
        return (0, 0)
    try:
        candidates = len(await stack.enrollment.list_applications(guild_id, state="pending"))
        enrolled = len(await stack.enrollment.list_applications(guild_id, state="accepted"))
        return (candidates, enrolled)
    except Exception:
        logger.warning("SEASON VIEW: the counts unreadable", exc_info=True)
        return (0, 0)



async def _seasons_list_lines(bot: Any, mod: str, guild_id: str) -> list[str]:
    """List the mod's seasons (the name + the phase) for the side panels."""
    stack = _stack(bot, mod, guild_id)
    if stack is None:
        return []
    try:
        seasons = await stack.seasons.list_seasons(stack.scope)
    except Exception:
        return []
    lines: list[str] = []
    for season in seasons or ():
        season_id = str(getattr(season, "id", "?"))
        name = str(getattr(season, "name", season_id))
        config = await _load_season_config(bot, mod, guild_id, season_id)
        phase = _PHASE_LABELS[_phase_of(config)]
        lines.append(f"\u2022 {name} — {phase}")
    return lines


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
    seasons_list = await _seasons_list_lines(bot, mod, guild_id)
    if seasons_list:
        lines.append("")
        lines.extend(seasons_list)
    view.add_item(discord.ui.Container(discord.ui.TextDisplay("\n".join(lines))))
    buttons: list[Any] = []
    for application in pending[:5]:
        user_id = str(getattr(application, "user_id", ""))
        buttons.append(CandidateDecideButton(mod, user_id, True).item)
        buttons.append(CandidateDecideButton(mod, user_id, False).item)
    from botforge.discord.ui.factory import split_action_rows
    from botforge.discord.ui.view_footer import add_view_footer

    for row in split_action_rows(buttons):
        view.add_item(row)

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
    seasons_list = await _seasons_list_lines(bot, mod, guild_id)
    if seasons_list:
        lines.append("")
        lines.extend(seasons_list)
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
    """The creation button: the name modal opens the draft flow."""

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
        """Open the name modal (guarded, the draft flow follows)."""
        from botforge.discord.mod_beta import _beta_guard

        if not await _beta_guard(interaction):
            return
        await interaction.response.send_modal(
            _SeasonNameModal(interaction.client, self.mod, str(interaction.guild_id or ""))
        )




def _season_config_cache(bot: Any, mod: str) -> Any:
    """Return the mod's state cache (the season config's persistence door)."""
    from botforge.core.services.mod_storage import ModStateCache

    state_service = getattr(bot, "state_service", None)
    return ModStateCache(state_service, mod) if state_service is not None else None


async def _persist_season_config(bot: Any, mod: str, guild_id: str, draft: dict[str, Any]) -> None:
    """Persist the season's config (the enrollment dates drive Postuler)."""
    season_id = str(draft.get("season_id") or "")
    if not season_id:
        return
    cache = _season_config_cache(bot, mod)
    if cache is None:
        return
    try:
        payload = {k: v for k, v in draft.items() if not k.startswith("_")}
        await cache.set(f"season-config:{season_id}", payload)
    except Exception:
        logger.warning("SEASON: the config persist failed — best-effort", exc_info=True)


async def _load_season_config(bot: Any, mod: str, guild_id: str, season_id: str) -> dict[str, Any]:
    """Load the season's stored config (empty when none)."""
    cache = _season_config_cache(bot, mod)
    if cache is None or not season_id:
        return {}
    try:
        entry = await cache.get(f"season-config:{season_id}")
        return dict(entry or {})
    except Exception:
        logger.warning("SEASON: the config load failed — best-effort", exc_info=True)
        return {}


async def _sync_beta_flag(interaction: discord.Interaction, draft: dict[str, Any], active: bool) -> None:
    """Sync the season's beta flag with the core's phase state."""
    from botforge.core.services.beta import enter_beta, exit_beta
    from botforge.core.services.mod_storage import ModStateCache

    draft["beta"] = active
    state_service = getattr(interaction.client, "state_service", None)
    if state_service is None:
        return
    mod = str(draft.get("_mod") or "")
    guild_id = str(interaction.guild_id or "")
    cache = ModStateCache(state_service, mod)
    if active:
        await enter_beta(cache, guild_id, mod)
    else:
        await exit_beta(cache, guild_id, mod)




async def _refresh_seasons_pin(bot: Any, guild_id: str, mod: str) -> None:
    """Update the seasons channel's pinned post IN PLACE (directly).

    The modals' submits edit THE POST — the pinned read surface —
    directly: no fingerprint gate, no ephemeral note, nothing else.
    The post is the single source of truth; the user sees it change.
    """
    from botforge.discord.static_pins import registered_static_pins

    key = f"view:mod:{mod}:seasons"
    spec = next((s for s in registered_static_pins() if s.key == key), None)
    if spec is None:
        return
    try:
        channel_id = await spec.resolve_channel(guild_id)
        message_id = await spec.resolve_message_id(guild_id)
        if not channel_id or not message_id:
            return
        guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        channel = guild.get_channel(int(channel_id)) if guild and channel_id.isdigit() else None
        if channel is None:
            return
        message = await channel.fetch_message(int(message_id))
        layout = await spec.build_layout(guild_id)
        await message.edit(view=layout)
    except Exception:
        logger.warning("SEASON: the post update failed — best-effort", exc_info=True)




def _drafts(bot: Any) -> dict[tuple[str, str], dict[str, Any]]:
    """Return the per-(mod, guild) season drafts (the wizard's state store)."""
    drafts = getattr(bot, "season_drafts", None)
    if drafts is None:
        drafts = {}
        bot.season_drafts = drafts
    return drafts


def _draft_of(bot: Any, mod: str, guild_id: str) -> dict[str, Any]:
    """Return (or start) the mod's guild draft."""
    drafts = _drafts(bot)
    return drafts.setdefault((mod, guild_id), {"name": ""})




class _SeasonNameModal(discord.ui.Modal, title="Le nom de la saison"):
    """The draft's first parameter: the name (re-openable)."""

    name: discord.ui.TextInput[Any] = discord.ui.TextInput(label="Nom", placeholder="Saison 2", max_length=64)

    def __init__(self, bot: Any, mod: str, guild_id: str) -> None:
        super().__init__()
        self._bot = bot
        self._mod = mod
        self._guild = guild_id
        draft = _draft_of(bot, mod, guild_id)
        if draft.get("name"):
            self.name.default = str(draft["name"])

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Record the name, then show the draft's recap."""
        draft = _draft_of(self._bot, self._mod, self._guild)
        draft["name"] = str(self.name.value or "").strip()
        await _persist_season_config(self._bot, self._mod, self._guild, draft)
        await interaction.response.defer(ephemeral=True)
        await _refresh_seasons_pin(self._bot, self._guild, self._mod)




def _mod_game_key(bot: Any, mod: str) -> str:
    """Return the mod's bound game key (its first required game); "" when none."""
    registry = getattr(bot, "registry", None)
    definition = registry.get(mod) if registry is not None else None
    games = getattr(definition, "required_games", ()) or ()
    return str(games[0]) if games else ""


async def _core_display_name(bot: Any, user_id: str) -> str:
    """Resolve the player's pseudo from the core identity service ("" when unknown)."""
    identity = getattr(bot, "identity_service", None)
    if identity is not None:
        try:
            user = await identity.get_user(f"discord:{user_id}")
            if user is not None and str(getattr(user, "display_name", "") or ""):
                return str(user.display_name)
        except Exception:
            logger.warning("SEASON PANEL: the identity lookup failed", exc_info=True)
    return ""


async def _linked_profile_ids(bot: Any, user_id: str, game_key: str) -> list[str]:
    """List the bound-game profile ids linked to the Discord user — the core knows them."""
    registration = getattr(bot, "registration_service", None)
    if registration is None:
        return []
    try:
        bindings = await registration.list_bindings(str(user_id))
    except Exception:
        logger.warning("SEASON PANEL: the bindings lookup failed", exc_info=True)
        return []
    ids: list[str] = []
    for binding in bindings or ():
        if game_key and str(binding.get("game_key", "") or "") != game_key:
            continue
        profile_id = str(binding.get("profile_id", "") or "")
        if profile_id and profile_id not in ids:
            ids.append(profile_id)
    return ids




class SeasonApplyButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:apply:(?P<mod>[a-z0-9_-]+)",
):
    """The player's Postuler button: the enrollment's entry point."""

    def __init__(self, mod: str) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:apply:{mod}"[:100],
                label="Postuler",
                emoji="\U0001f4dd",
                style=discord.ButtonStyle.primary,
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
    ) -> SeasonApplyButton:
        """Rebuild the button at click time."""
        return cls(match["mod"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Apply directly (anyone may apply).

        The pseudo and the linked game profile ids resolve from the core —
        never asked in a form.
        """
        await interaction.response.defer(ephemeral=True)
        bot = interaction.client
        guild_id = str(interaction.guild_id or "")
        user_id = str(interaction.user.id)
        stack = _stack(bot, self.mod, guild_id)
        if stack is None or stack.enrollment is None:
            await interaction.followup.send("The enrollment is not wired on this guild.", ephemeral=True)
            return
        core_name = await _core_display_name(bot, user_id)
        profiles = await _linked_profile_ids(bot, user_id, _mod_game_key(bot, self.mod))
        if not core_name or not profiles:
            # a missing pseudo OR a missing bound game profile: the player
            # registers first — the /register flow lives in #general
            from botforge.discord.ui.panels_provisioning import stored_channel_id

            general = await stored_channel_id(guild_id, "root", "general")
            mention = f"<#{general}>" if general else "#général"
            await interaction.followup.send(
                f"Pseudo ou profil de jeu manquant — inscris-toi d'abord dans {mention} avec `/register`.",
                ephemeral=True,
            )
            return
        display_name = core_name
        try:
            application = await stack.enrollment.apply(guild_id, user_id, display_name, profiles=profiles)
        except Exception as exc:
            await interaction.followup.send(f"La candidature a échoué : {exc}", ephemeral=True)
            return
        linked = " — profils liés : " + ", ".join(f"`{p}`" for p in profiles) if profiles else ""
        state = str(getattr(application, "state", "pending"))
        if state == "accepted":
            await interaction.followup.send(f"Candidature **acceptée** — bienvenue !{linked}", ephemeral=True)
        elif state == "refused":
            reasons = ", ".join(str(r) for r in getattr(application, "reasons", ()) or ())
            await interaction.followup.send(
                f"Candidature **refusée**{(' (' + reasons + ')') if reasons else ''}.{linked}",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"Candidature **en attente** — les admins décident.{linked}", ephemeral=True
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
        await interaction.followup.send(f"{'Validé' if self.accept else 'Refusé'} : <@{self.user_id}>.", ephemeral=True)




async def _find_application(stack: Any, guild_id: str, user_id: str) -> Any:
    """Find one pending application by user id."""
    for application in await stack.enrollment.list_applications(guild_id, state="pending"):
        if str(getattr(application, "user_id", "")) == user_id:
            return application
    return None


__all__ = [
    "CandidateDecideButton",
    "SeasonApplyButton",
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


def register_season_items(client: Any) -> None:
    """Register the season panels' dynamic items (the bot's wiring)."""
    client.add_dynamic_items(SeasonCreateButton)
    client.add_dynamic_items(SeasonApplyButton)
    client.add_dynamic_items(SeasonPhaseButton)
    client.add_dynamic_items(SeasonAdminButton)
    client.add_dynamic_items(CandidateDecideButton)


__all__.extend(["register_season_items"])


async def _refresh_all_season_pins(bot: Any) -> None:
    """Re-render every guild's seasonal posts (the refresher's body)."""
    for guild in getattr(bot, "guilds", ()) or ():
        guild_id = str(guild.id)
        registry = getattr(bot, "registry", None)
        if registry is None:
            continue
        for mod in registry.enabled():
            definition = registry.get(mod)
            if definition is None or not getattr(definition, "seasonal", False):
                continue
            await _refresh_seasons_pin(bot, guild_id, mod)


def start_season_refresher(bot: Any) -> None:
    """Start the pinned season posts' refresher (every 5 minutes).

    The Postuler button's visibility derives from the dates; the post
    is a snapshot — the refresher re-renders it so the button appears
    when the enrollment window opens and disappears when it closes,
    without anyone clicking anything.

    Gated off in the test journeys (``BOTFORGE_SEASON_REFRESHER=off``):
    a background loop never settles, and the journeys' runner waits
    for the bot's outstanding work to drain.
    """
    import os

    if os.environ.get("BOTFORGE_SEASON_REFRESHER", "").lower() in {"off", "0", "false"}:
        return

    from discord.ext import tasks

    @tasks.loop(minutes=5)
    async def _loop() -> None:
        try:
            await _refresh_all_season_pins(bot)
        except Exception:
            logger.warning("SEASON refresher: the pass failed — best-effort", exc_info=True)

    _loop.start()
    logger.info("SEASON refresher started (every 5 minutes)")
