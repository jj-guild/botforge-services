"""The seasonal mods' pinned panels — saisons, candidats, inscrits (P3).

The owner's spec (2026-11-14): every seasonal mod's folder carries
three pinned surfaces:

- **saisons** — the active season's state + the creation button (the
  wizard: the enrollment parameters, the validation mode, the player
  bounds, the dates); a new season only when the active is finished
  (the SeasonService's gate)
- **candidats** — admin-only: the pending queue, one validate/refuse
  pair per candidate; only the admins decide
- **inscrits** — the season's participants list

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
        """Move the phase, update the admin panel + the post in place."""
        from botforge.discord.mod_beta import _beta_guard

        if not await _beta_guard(interaction):
            return
        guild_id = str(interaction.guild_id or "")
        stack = _stack(interaction.client, self.mod, guild_id)
        if stack is None:
            await interaction.response.defer(ephemeral=True)
            return
        active = await await_active(stack, guild_id)
        if active is None:
            await interaction.response.defer(ephemeral=True)
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
        # the ADMIN PANEL edits ITSELF in place (the click rides it) +
        # the pinned post updates
        await interaction.response.edit_message(
            view=await build_admin_panel(interaction.client, guild_id, self.mod, season_id)
        )
        await _refresh_seasons_pin(interaction.client, guild_id, self.mod)


async def build_seasons_panel(bot: Any, guild_id: str, mod: str, locale: str = "fr") -> discord.ui.LayoutView:
    """Build the SAISONS panel (the owner's drastic simplification).

    The name, the season id, the phase, the TODO criteria, the
    counts — and the player's buttons: Je veux m'inscrire (when the
    inscriptions are open), the candidates list, the participants
    list, the admin door. The phase transitions live in the admin
    submenu, never here.
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

        # the public panel carries the ADMIN door only — the create
        # button lives in the ephemeral admin bar (no admin buttons in
        # public, the owner's rule)
        for row in split_action_rows([SeasonAdminButton(mod).item]):
            view.add_item(row)
        add_view_footer(view, f"panel:mod:{mod}:seasons")
        return view
    season_id = str(getattr(active, "id", ""))
    config = await _load_season_config(bot, mod, guild_id, season_id)
    name = str(config.get("name") or getattr(active, "name", season_id))
    phase = _phase_of(config)
    candidates, participants = await _enrollment_counts(bot, mod, guild_id)
    lines = [f"# {name}"]
    lines.append(f"`{season_id}`")
    lines.append(f"\u00c9tat : **{_PHASE_LABELS[phase]}**")
    lines.append("")
    lines.append("**Crit\u00e8res** : un compte AoE2 + validation dans le channel admin")
    lines.append(f"\U0001f9e1 Candidats : **{candidates}** \u00b7 \U0001f465 Participants : **{participants}**")
    view.add_item(discord.ui.Container(discord.ui.TextDisplay("\n".join(lines))))
    from botforge.discord.ui.factory import split_action_rows
    from botforge.discord.ui.view_footer import add_view_footer

    items: list[Any] = []
    if phase == "inscriptions":
        items.append(SeasonApplyButton(mod).item)
        # the candidates list rides only while the inscriptions are OPEN
        items.append(SeasonListButton(mod, "candidates").item)
    if phase != "preparation":
        # the participants list rides once the season is past preparation
        items.append(SeasonListButton(mod, "participants").item)
    # the admin door rides ALWAYS LAST (the owner's order)
    items.append(SeasonAdminButton(mod).item)
    for row in split_action_rows(items):
        view.add_item(row)
    # the panel id: panel:<season id> (panel:mod:<mod>:season:<guild>:<n>)
    add_view_footer(view, f"panel:{season_id}")
    return view


class SeasonListButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:list:(?P<mod>[a-z0-9_-]+):(?P<what>candidates|participants)",
):
    """The read post's list buttons: the candidates or the participants."""

    def __init__(self, mod: str, what: str) -> None:
        labels = {"candidates": "\U0001f9e1 Candidats", "participants": "\U0001f465 Participants"}
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:list:{mod}:{what}"[:100],
                label=labels.get(what, what),
                style=discord.ButtonStyle.secondary,
            )
        )
        self.mod = mod
        self.what = what

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: Any,
        /,
    ) -> SeasonListButton:
        """Rebuild the button at click time."""
        return cls(match["mod"], match["what"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Show the list (ephemeral, the live data)."""
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id or "")
        # the SAME builder as the pinned view (panel:mod:<mod>:<what>),
        # rendered ephemeral — rigorously the pinned view
        if self.what == "candidates":
            view = await build_candidates_panel(interaction.client, guild_id, self.mod)
        else:
            view = await build_participants_panel(interaction.client, guild_id, self.mod)
        await interaction.followup.send(view=view, ephemeral=True)


class SeasonAdminButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:admin:(?P<mod>[a-z0-9_-]+)",
):
    """The post's admin door: opens the admin action bar (ephemeral).

    The bar carries the settings (the name) and the PHASE
    TRANSITIONS — the read post stays clean (the owner's rule
    2026-11-15).
    """

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
        """Reveal the admin action bar (guarded, ephemeral)."""
        from botforge.discord.mod_beta import _beta_guard

        if not await _beta_guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
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
        await _send_admin_bar(interaction, interaction.client, self.mod, guild_id)


async def build_admin_panel(bot: Any, guild_id: str, mod: str, season_id: str) -> discord.ui.LayoutView:
    """Build the season's ADMIN panel (ephemeral, the owner's rule).

    NO header — the action rows only (the name, the phase transitions
    NAMED, the direct start) — the footer carries the admin panel id
    (panel:<season id>:admin). The panel EDITS ITSELF on every phase
    change.
    """
    # the STORED config is the truth (the draft lags one change
    # behind — the merlin finding: the transitions stayed stale after
    # a phase change)
    config = await _load_season_config(bot, mod, guild_id, season_id)
    phase = _phase_of(config)
    index = _PHASES.index(phase)
    view = discord.ui.LayoutView(timeout=None)
    from botforge.discord.ui.factory import split_action_rows
    from botforge.discord.ui.view_footer import add_view_footer

    if not season_id:
        # no season: the admin bar carries the CREATE door (the name
        # modal creates it on submit)
        for row in split_action_rows([SeasonCreateButton(mod).item]):
            view.add_item(row)
        add_view_footer(view, f"panel:mod:{mod}:seasons:admin")
        return view
    items: list[Any] = [SeasonNameButton(mod).item]
    if index > 0:
        # the previous state, NAMED (never a bare arrow)
        items.append(SeasonPhaseButton(mod, "prev", f"\u2190 {_PHASE_LABELS[_PHASES[index - 1]]}").item)
    next_label = _NEXT_LABELS.get(phase)
    if next_label:
        items.append(SeasonPhaseButton(mod, "next", next_label).item)
    if phase == "inscriptions":
        # the direct start: the season may open WITHOUT closing the
        # inscriptions (the owner's choice)
        items.append(SeasonPhaseButton(mod, "start", "D\u00e9marrer la saison").item)
    for row in split_action_rows(items):
        view.add_item(row)
    add_view_footer(view, f"panel:{season_id}:admin")
    return view


async def _send_admin_bar(interaction: discord.Interaction, bot: Any, mod: str, guild_id: str) -> None:
    """Send the admin panel (ephemeral, no header, self-editing)."""
    stack = _stack(bot, mod, guild_id)
    season_id = ""
    if stack is not None:
        try:
            active = await await_active(stack, guild_id)
        except Exception:
            active = None
        if active is not None:
            season_id = str(getattr(active, "id", ""))
    view = await build_admin_panel(bot, guild_id, mod, season_id)
    if interaction.response.is_done():
        await interaction.followup.send(view=view, ephemeral=True)
    else:
        await interaction.response.send_message(view=view, ephemeral=True)


class SeasonNameButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:name:(?P<mod>[a-z0-9_-]+)",
):
    """The admin bar's name button: opens the name modal."""

    def __init__(self, mod: str) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:name:{mod}"[:100],
                label="\u270f\ufe0f Nom",
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
    ) -> SeasonNameButton:
        """Rebuild the button at click time."""
        return cls(match["mod"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the name modal (guarded)."""
        from botforge.discord.mod_beta import _beta_guard

        if not await _beta_guard(interaction):
            return
        await interaction.response.send_modal(
            _SeasonNameModal(interaction.client, self.mod, str(interaction.guild_id or ""))
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


async def _season_subtitle(bot: Any, guild_id: str, mod: str) -> list[str]:
    """Render the active season's subtitle (name, id, phase)."""
    stack = _stack(bot, mod, guild_id)
    if stack is None:
        return []
    try:
        active = await await_active(stack, guild_id)
    except Exception:
        return []
    if active is None:
        return []
    season_id = str(getattr(active, "id", ""))
    config = await _load_season_config(bot, mod, guild_id, season_id)
    name = str(config.get("name") or getattr(active, "name", season_id))
    return [f"**{name}** · `{season_id}` · {_PHASE_LABELS[_phase_of(config)]}", ""]


async def build_candidates_panel(bot: Any, guild_id: str, mod: str, locale: str = "fr") -> discord.ui.LayoutView:
    """Build the CANDIDATS panel (public: NO admin buttons).

    The roster-style lines (the pseudo — the bold mention — the
    account links); the decisions live in the ADMIN announce message
    and the ephemeral admin bar, never on a public view.
    """
    view = discord.ui.LayoutView(timeout=None)
    stack = _stack(bot, mod, guild_id)
    lines = [f"# \U0001f9e1 {mod.capitalize()} — candidats"]
    lines.extend(await _season_subtitle(bot, guild_id, mod))
    pending: list[Any] = []
    if stack is not None:
        try:
            pending = list(await stack.enrollment.list_applications(guild_id, state="pending"))
        except Exception:
            logger.warning("SEASON PANEL: the queue unreadable", exc_info=True)
    lines.extend(await _roster_style_lines(bot, guild_id, mod, pending, "_Aucun candidat en attente._"))
    view.add_item(discord.ui.Container(discord.ui.TextDisplay("\n".join(lines))))
    from botforge.discord.ui.view_footer import add_view_footer

    add_view_footer(view, f"panel:mod:{mod}:candidates")
    return view


async def _profile_names(bot: Any, user_id: str, game_key: str) -> dict[str, str]:
    """Resolve the user's bound profile ids to their stored NAMES."""
    registration = getattr(bot, "registration_service", None)
    if registration is None:
        return {}
    try:
        bindings = await registration.list_bindings(user_id)
    except Exception:
        return {}
    names: dict[str, str] = {}
    for binding in bindings or ():
        if game_key and str(binding.get("game_key", "") or "") != game_key:
            continue
        pid = str(binding.get("profile_id", "") or "")
        profile = binding.get("profile") or {}
        stored = str(profile.get("profile_name") or "")
        if pid and stored:
            names[pid] = stored
    return names


async def _sync_season_roles(bot: Any, mod: str, guild_id: str, user_id: str, state: str) -> None:
    """Sync the mod's candidate/member roles with the application's state.

    pending -> +candidate; accepted -> +member -candidate (the seam
    also covers it); refused/withdrawn -> both drop. Best-effort.
    """
    mod_roles = getattr(bot, "mod_roles_service", None)
    if mod_roles is None:
        return
    try:
        candidate = await mod_roles.resolve_role_id(guild_id, mod, "candidate")
        member = await mod_roles.resolve_role_id(guild_id, mod, "member")
        if state == "pending":
            if candidate:
                await mod_roles.assign_platform_role(guild_id, user_id, candidate, "", "candidate")
        elif state == "accepted":
            if candidate:
                await mod_roles.remove_platform_role(guild_id, user_id, candidate, "", "candidate")
            if member:
                await mod_roles.assign_platform_role(guild_id, user_id, member, "", "member")
        else:
            if candidate:
                await mod_roles.remove_platform_role(guild_id, user_id, candidate, "", "candidate")
            if member:
                await mod_roles.remove_platform_role(guild_id, user_id, member, "", "member")
    except Exception:
        logger.warning("SEASON: the role sync failed — best-effort", exc_info=True)


async def _roster_style_lines(
    bot: Any, guild_id: str, mod: str, applications: list[Any], empty_note: str
) -> list[str]:
    """Render the applications like the aoe2 players list.

    ``• **Merlin** — **@Merlin Pinpin**: [JeanJack](url), [Merlin
    Pinpin](url)`` — the application's pseudo, the bold mention, the
    linked game accounts (the insights links). No raw discord ids.
    """
    if not applications:
        return [empty_note]
    game_key = _mod_game_key(bot, mod)
    by_user: dict[str, list[dict[str, Any]]] = {}
    for application in applications:
        user_id = str(getattr(application, "user_id", "?"))
        by_user.setdefault(user_id, [])
    lines: list[str] = []
    for application in applications:
        user_id = str(getattr(application, "user_id", "?"))
        pseudo = str(getattr(application, "display_name", "?"))
        names = await _profile_names(bot, user_id, game_key) if game_key else {}
        profiles: list[str] = []
        for pid in getattr(application, "profiles", ()) or ():
            pid = str(pid)
            label = names.get(pid) or pid
            url = _game_account_url(game_key, pid) if game_key else ""
            profiles.append(f"[{label}]({url})" if url else label)
        links = f": {', '.join(profiles)}" if profiles else ""
        lines.append(f"\u2022 **{pseudo}** — **<@{user_id}>**{links}")
    return lines


def _game_account_url(game_key: str, profile_id: str) -> str:
    """Return the profile's public account link (aoe2insights by default)."""
    from botforge.discord.home import _game_account_url as _url

    return _url(game_key, profile_id)


async def build_participants_panel(bot: Any, guild_id: str, mod: str, locale: str = "fr") -> discord.ui.LayoutView:
    """Build the PARTICIPANTS panel: the season's participants, roster-style."""
    view = discord.ui.LayoutView(timeout=None)
    stack = _stack(bot, mod, guild_id)
    lines = [f"# \U0001f465 {mod.capitalize()} — participants"]
    lines.extend(await _season_subtitle(bot, guild_id, mod))
    accepted: list[Any] = []
    if stack is not None:
        try:
            accepted = list(await stack.enrollment.list_applications(guild_id, state="accepted"))
        except Exception:
            logger.warning("SEASON PANEL: the participants list unreadable", exc_info=True)
    lines.extend(await _roster_style_lines(bot, guild_id, mod, accepted, "_Aucun participant._"))
    view.add_item(discord.ui.Container(discord.ui.TextDisplay("\n".join(lines))))
    from botforge.discord.ui.view_footer import add_view_footer

    add_view_footer(view, f"panel:mod:{mod}:participants")
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




async def _current_season_config(bot: Any, mod: str, guild_id: str) -> dict[str, Any]:
    """Load the active season's config (empty when none)."""
    stack = _stack(bot, mod, guild_id)
    if stack is None:
        return {}
    try:
        active = await await_active(stack, guild_id)
    except Exception:
        return {}
    if active is None:
        return {}
    season_id = str(getattr(active, "id", ""))
    config = await _load_season_config(bot, mod, guild_id, season_id)
    config["season_id"] = season_id
    return config


async def _announce_application(
    bot: Any, guild_id: str, mod: str, user_id: str, display_name: str, profiles: list[str]
) -> None:
    """Post the new application in the mod's admin channel (roster format)."""
    from botforge.discord.ui.panels_provisioning import stored_channel_id

    try:
        admin_channel = await stored_channel_id(guild_id, f"mod/{mod}", "admin")
        if not admin_channel:
            return
        guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        channel = guild.get_channel(int(admin_channel)) if guild and admin_channel.isdigit() else None
        if channel is None:
            return
        from botforge.discord.ui.factory import split_action_rows

        game_key = _mod_game_key(bot, mod)
        names = await _profile_names(bot, user_id, game_key) if game_key else {}
        links: list[str] = []
        for pid in profiles:
            pid = str(pid)
            label = names.get(pid) or pid
            url = _game_account_url(game_key, pid) if game_key else ""
            links.append(f"[{label}]({url})" if url else label)
        suffix = f": {', '.join(links)}" if links else ""
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    f"\U0001f9e1 Nouvelle candidature : **{display_name}** — **<@{user_id}>**{suffix}"
                )
            )
        )
        for row in split_action_rows(
            [
                CandidateDecideButton(mod, str(user_id), True).item,
                CandidateDecideButton(mod, str(user_id), False).item,
            ]
        ):
            view.add_item(row)
        await channel.send(view=view)
    except Exception:
        logger.warning("SEASON: the admin announce failed — best-effort", exc_info=True)


async def _refresh_all_season_posts(bot: Any, guild_id: str, mod: str) -> None:
    """Update the seasons, candidates and participants posts in place."""
    await _refresh_seasons_pin(bot, guild_id, mod)
    await _refresh_season_pin(bot, guild_id, mod, "candidates")
    await _refresh_season_pin(bot, guild_id, mod, "participants")


async def _refresh_season_pin(bot: Any, guild_id: str, mod: str, pin_key: str) -> None:
    """Update one seasonal post in place (create when missing).

    A freshly provisioned channel carries no pinned view yet: the
    refresh falls back to the ensure path (the pin is CREATED), then
    the later passes edit it in place.
    """
    from botforge.discord.static_pins import ensure_static_pin, registered_static_pins

    key = f"view:mod:{mod}:{pin_key}"
    spec = next((s for s in registered_static_pins() if s.key == key), None)
    if spec is None:
        return
    try:
        channel_id = await spec.resolve_channel(guild_id)
        message_id = await spec.resolve_message_id(guild_id)
        if not channel_id:
            return
        if not message_id:
            # a fresh channel: the pin is CREATED (the ensure path)
            await ensure_static_pin(bot, spec, guild_id)
            return
        guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        channel = guild.get_channel(int(channel_id)) if guild and channel_id.isdigit() else None
        if channel is None:
            return
        message = await channel.fetch_message(int(message_id))
        layout = await spec.build_layout(guild_id)
        await message.edit(view=layout)
    except Exception:
        logger.warning("SEASON: the %s post update failed — best-effort", pin_key, exc_info=True)


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
        """Record the name — CREATE the season when none lives."""
        draft = _draft_of(self._bot, self._mod, self._guild)
        draft["name"] = str(self.name.value or "").strip()
        stack = _stack(self._bot, self._mod, self._guild)
        active = None
        if stack is not None:
            try:
                active = await await_active(stack, self._guild)
            except Exception:
                active = None
        if active is None and stack is not None:
            # no season: the name CREATES it (the direct flow, the
            # confirm button is gone)
            try:
                season = await stack.seasons.create_season(
                    stack.scope, draft.get("name") or "Saison", None, start_at=0
                )
            except Exception as exc:
                message = str(exc)
                if "already has a live season" in message:
                    note = "Une saison est déjà en cours — termine-la avant d'en créer une nouvelle."
                else:
                    note = f"La création a refusé : {message}"
                await interaction.response.defer(ephemeral=True)
                await interaction.followup.send(note, ephemeral=True)
                return
            draft["season_id"] = str(season.id)
            draft["phase"] = "preparation"
            await _persist_season_config(self._bot, self._mod, self._guild, draft)
            await interaction.response.defer(ephemeral=True)
            # NOTHING new stacks: the pinned post updates in place —
            # that IS the answer (no create menu, no note above
            # buttons; the admin bar stays a bare bar of buttons)
            await _refresh_seasons_pin(self._bot, self._guild, self._mod)
            return
        # a season lives: the name RENAMES it (persist + the post updates)
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
                label="Je veux m'inscrire",
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
        """Apply (or WITHDRAW when already in) — anyone may click.

        The pseudo and the linked game profile ids resolve from the
        core — never asked in a form. A player already
        candidate/participant on an unstarted season may DESIST: the
        same click withdraws them.
        """
        await interaction.response.defer(ephemeral=True)
        bot = interaction.client
        guild_id = str(interaction.guild_id or "")
        user_id = str(interaction.user.id)
        stack = _stack(bot, self.mod, guild_id)
        if stack is None or stack.enrollment is None:
            await interaction.followup.send("The enrollment is not wired on this guild.", ephemeral=True)
            return
        # the désistement: already in + the season not started — a
        # CONFIRMATION modal first (the owner's rule, never a silent drop)
        existing = await _find_application(stack, guild_id, user_id)
        if existing is not None and str(getattr(existing, "state", "")) in ("pending", "accepted"):
            config = await _current_season_config(bot, self.mod, guild_id)
            if _phase_of(config) != "ouverte":
                await interaction.followup.send(
                    view=_withdraw_confirm_view(self.mod, guild_id, user_id),
                    ephemeral=True,
                )
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
            await _announce_application(bot, guild_id, self.mod, user_id, display_name, profiles)
            await _sync_season_roles(bot, self.mod, guild_id, user_id, "pending")
            await interaction.followup.send(
                f"Candidature **en attente** — les admins décident.{linked}", ephemeral=True
            )
        await _refresh_all_season_posts(bot, guild_id, self.mod)


class SeasonWithdrawConfirmButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:withdraw:(?P<mod>[a-z0-9_-]+):(?P<user>\d+)",
):
    """The désistement's confirm button: the withdrawal runs."""

    def __init__(self, mod: str, user_id: str) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:withdraw:{mod}:{user_id}"[:100],
                label="Se désinscrire",
                style=discord.ButtonStyle.danger,
            )
        )
        self.mod = mod
        self.user_id = user_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: Any,
        /,
    ) -> SeasonWithdrawConfirmButton:
        """Rebuild the button at click time."""
        return cls(match["mod"], match["user"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Withdraw after the confirmation (the player's own click)."""
        await interaction.response.defer(ephemeral=True)
        bot = interaction.client
        guild_id = str(interaction.guild_id or "")
        stack = _stack(bot, self.mod, guild_id)
        if stack is None:
            return
        existing = await _find_application(stack, guild_id, self.user_id)
        if existing is None:
            return
        try:
            await stack.enrollment.withdraw(str(getattr(existing, "application_id", "")))
        except Exception as exc:
            await interaction.followup.send(f"Le désistement a échoué : {exc}", ephemeral=True)
            return
        await _sync_season_roles(bot, self.mod, guild_id, self.user_id, "withdrawn")
        await _refresh_all_season_posts(bot, guild_id, self.mod)
        await interaction.followup.send(
            "Désinscription **enregistrée** — à bientôt !", ephemeral=True
        )


def _withdraw_confirm_view(mod: str, guild_id: str, user_id: str) -> discord.ui.LayoutView:
    """Build the désistement's confirmation (a modal-shaped ephemeral)."""
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay("Se désinscrire de la saison ?"),
            discord.ui.TextDisplay("_Ton retrait est immédiat — tu pourras re-candidater._"),
        )
    )
    row: Any = discord.ui.ActionRow()
    row.add_item(SeasonWithdrawConfirmButton(mod, user_id))
    view.add_item(row)
    return view




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
                await stack.enrollment.accept(str(application.application_id))
            else:
                await stack.enrollment.refuse(str(application.application_id))
        except Exception:
            logger.warning("SEASON PANEL: the decision failed", exc_info=True)
            await interaction.followup.send("La décision a échoué — voir les logs.", ephemeral=True)
            return
        decision = "acceptée" if self.accept else "refusée"
        # the ANNOUNCE message (the buttons ride it) becomes the
        # resolution — the Y/N disappears
        resolution = await _decision_resolution(
            interaction, self.mod, application, self.user_id, decision
        )
        await _apply_decision_resolution(interaction, resolution, self.user_id)
        if not self.accept:
            await _sync_season_roles(
                interaction.client, self.mod, str(interaction.guild_id or ""), self.user_id, "refused"
            )
        # the ack already rode the START defer (the 3s rule) — never twice
        await _refresh_all_season_posts(interaction.client, str(interaction.guild_id or ""), self.mod)





async def _apply_decision_resolution(
    interaction: discord.Interaction, resolution: str, user_id: str
) -> None:
    """Edit the announce in place + DM the player (both best-effort)."""
    try:
        resolved = discord.ui.LayoutView(timeout=None)
        resolved.add_item(discord.ui.Container(discord.ui.TextDisplay(resolution)))
        if interaction.message is not None:
            await interaction.message.edit(view=resolved)
    except Exception:
        logger.info("SEASON: the announce edit skipped — best-effort", exc_info=True)
    try:
        target = interaction.client.get_user(int(user_id))
        if target is not None:
            await target.send(resolution)
    except Exception:
        logger.info("SEASON: the decision DM failed — best-effort", exc_info=True)


async def _decision_resolution(
    interaction: discord.Interaction, mod: str, application: Any, user_id: str, decision: str
) -> str:
    """Render the decision's resolution line (the roster format)."""
    pseudo = str(getattr(application, "display_name", "?"))
    game_key = _mod_game_key(interaction.client, mod)
    user_id = str(getattr(application, "user_id", "?"))
    names = await _profile_names(interaction.client, user_id, game_key) if game_key else {}
    links: list[str] = []
    for pid in getattr(application, "profiles", ()) or ():
        pid = str(pid)
        label = names.get(pid) or pid
        url = _game_account_url(game_key, pid) if game_key else ""
        links.append(f"[{label}]({url})" if url else label)
    suffix = f": {', '.join(links)}" if links else ""
    return (
        f"La candidature de **{pseudo}** — **<@{user_id}>**{suffix} "
        f"a été **{decision}** par <@{interaction.user.id}>."
    )


async def _find_application(stack: Any, guild_id: str, user_id: str) -> Any:
    """Find the user's pending OR accepted application (both may desist)."""
    list_applications = getattr(stack.enrollment, "list_applications", None)
    if list_applications is None:
        return None
    for state in ("pending", "accepted"):
        for application in await list_applications(guild_id, state=state):
            if str(getattr(application, "user_id", "")) == user_id:
                return application
    return None


__all__ = [
    "CandidateDecideButton",
    "SeasonApplyButton",
    "SeasonCreateButton",
    "build_candidates_panel",
    "build_participants_panel",
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
            ("participants", build_participants_panel, "participants"),
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
    client.add_dynamic_items(SeasonNameButton)
    client.add_dynamic_items(SeasonListButton)
    client.add_dynamic_items(SeasonWithdrawConfirmButton)
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
            await _refresh_all_season_posts(bot, guild_id, mod)


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
