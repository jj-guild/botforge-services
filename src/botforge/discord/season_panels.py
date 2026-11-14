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
from typing import Any, ClassVar

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
    """Build the SAISONS panel: the active season's view + the creation button."""
    stack = _stack(bot, mod, guild_id)
    active = None
    if stack is not None:
        try:
            active = await await_active(stack, guild_id)
        except Exception:
            logger.warning("SEASON PANEL: the active season unreadable", exc_info=True)
    if active is not None:
        # the read mode: the active season's sectioned view + the counts
        draft = {
            "name": str(getattr(active, "name", "")),
            "season_start": getattr(active, "start_at", None),
            "season_end": getattr(active, "end_at", None),
        }
        return await build_season_layout(bot, mod, guild_id, draft, read_mode=True)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(f"# 📅 {mod.capitalize()} — saisons"),
            discord.ui.TextDisplay("_Aucune saison active._"),
        )
    )
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

    name: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Nom", placeholder="Saison 2", max_length=64
    )

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
        await interaction.response.defer(ephemeral=True)
        await _send_draft(interaction, self._bot, self._mod, self._guild)


class _SeasonValidationModal(discord.ui.Modal, title="La validation"):
    """The draft's validation parameter: manual or automatic (re-openable)."""

    validation: Any = discord.ui.Label(
        text="La validation des candidatures",
        component=discord.ui.Select(
            options=[
                discord.SelectOption(label="Manuelle (les admins décident)", value="manual"),
                discord.SelectOption(label="Automatique (les critères décident)", value="auto"),
            ],
            required=False,
            min_values=0,
        ),
    )

    def __init__(self, bot: Any, mod: str, guild_id: str) -> None:
        super().__init__()
        self._bot = bot
        self._mod = mod
        self._guild = guild_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Record the mode, then re-render the recap."""
        draft = _draft_of(self._bot, self._mod, self._guild)
        select: Any = getattr(self.validation, "component", self.validation)
        draft["validation"] = str(select.values[0]) if select.values else "manual"
        await interaction.response.defer(ephemeral=True)
        await _send_draft(interaction, self._bot, self._mod, self._guild)


class _SeasonCriteriaModal(discord.ui.Modal, title="Les critères de validation"):
    """The draft's validation criteria (re-openable; the provider work is planned)."""

    elo_type: Any = discord.ui.Label(
        text="Le leaderboard qui compte",
        component=discord.ui.Select(
            options=[
                discord.SelectOption(label="Elo 1v1", value="1v1"),
                discord.SelectOption(label="Elo TG", value="tg"),
            ],
            required=False,
            min_values=0,
        ),
    )
    elo_max: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Elo max (vide = aucun plafond)", placeholder="2000", required=False, max_length=4
    )
    min_matches: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Historique : X derniers matchs (vide = aucun)",
        placeholder="10",
        required=False,
        max_length=4,
    )

    def __init__(self, bot: Any, mod: str, guild_id: str) -> None:
        super().__init__()
        self._bot = bot
        self._mod = mod
        self._guild = guild_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Record the criteria, then re-render the view."""
        draft = _draft_of(self._bot, self._mod, self._guild)
        elo_select = getattr(self.elo_type, "component", self.elo_type)
        draft["elo_type"] = str(elo_select.values[0]) if elo_select.values else ""
        draft["elo_max"] = str(self.elo_max.value or "").strip()
        draft["min_matches"] = str(self.min_matches.value or "").strip()
        await interaction.response.defer(ephemeral=True)
        await _send_draft(interaction, self._bot, self._mod, self._guild)


class _SeasonPlayersModal(discord.ui.Modal, title="Le nombre de joueurs"):
    """The draft's player bounds (re-openable)."""

    min_players: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Joueurs min (vide = aucun)", placeholder="8", required=False, max_length=4
    )
    max_players: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Joueurs max (vide = illimité)", placeholder="64", required=False, max_length=4
    )

    def __init__(self, bot: Any, mod: str, guild_id: str) -> None:
        super().__init__()
        self._bot = bot
        self._mod = mod
        self._guild = guild_id
        draft = _draft_of(bot, mod, guild_id)
        if draft.get("min_players"):
            self.min_players.default = str(draft["min_players"])
        if draft.get("max_players"):
            self.max_players.default = str(draft["max_players"])

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Record the bounds, then re-render the view."""
        draft = _draft_of(self._bot, self._mod, self._guild)
        draft["min_players"] = str(self.min_players.value or "").strip()
        draft["max_players"] = str(self.max_players.value or "").strip()
        await interaction.response.defer(ephemeral=True)
        await _send_draft(interaction, self._bot, self._mod, self._guild)


class _SeasonMapPoolModal(discord.ui.Modal, title="Le map pool"):
    """The draft's map pool: a SELECT of the active pools (owner spec).

    The active (non-archived, non-deleted) pools stay under Discord's
    25-option cap — a select, never a free-text id. The pool list comes
    from the game service; without it the section degrades to a
    manual id field.
    """

    map_pool: Any = None  # built per instance (the pools are runtime data)

    def __init__(self, bot: Any, mod: str, guild_id: str) -> None:
        super().__init__()
        self._bot = bot
        self._mod = mod
        self._guild = guild_id
        draft = _draft_of(bot, mod, guild_id)
        options = _map_pool_options(bot)
        if options:
            select: discord.ui.Select[discord.ui.Modal] = discord.ui.Select(
                options=options[:25],
                required=False,
                min_values=0,
            )
            self.map_pool = discord.ui.Label(text="Le pool de la saison", component=select)
            self.add_item(self.map_pool)
        else:
            field: discord.ui.TextInput[Any] = discord.ui.TextInput(
                label="Map pool (id)", placeholder="pool-base", required=False, max_length=64
            )
            if draft.get("map_pool"):
                field.default = str(draft["map_pool"])
            self.map_pool = field
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Record the pool, then re-render the view."""
        draft = _draft_of(self._bot, self._mod, self._guild)
        item = self.map_pool
        select = getattr(item, "component", None)
        if select is not None:
            draft["map_pool"] = str(select.values[0]) if select.values else ""
        else:
            draft["map_pool"] = str(getattr(item, "value", "") or "").strip()
        await interaction.response.defer(ephemeral=True)
        await _send_draft(interaction, self._bot, self._mod, self._guild)


def _map_pool_options(bot: Any) -> list[discord.SelectOption]:
    """List the game's active map pools as select options (<25 by design)."""
    from botforge.discord.wiring import build_games_service

    service = build_games_service()
    options: list[discord.SelectOption] = []
    if service is None:
        return options
    try:
        pools = service.list_map_pools()
    except Exception:
        logger.warning("SEASON VIEW: the pool list unreadable", exc_info=True)
        return options
    for pool in pools or ():
        pool_id = str(getattr(pool, "id", "") or "")
        name = str(getattr(pool, "name", "") or pool_id)
        state = str(getattr(pool, "state", "") or "")
        if not pool_id or state in {"archived", "closed", "deleted"}:
            continue
        options.append(discord.SelectOption(label=name[:100], value=pool_id, description=state))
        if len(options) >= 25:
            break
    return options


class _SeasonDatesModal(discord.ui.Modal, title="Les dates"):
    """The draft's enrollment + season dates (re-openable)."""

    enrollment_start: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Début inscription (unix ts)", required=False, max_length=12
    )
    enrollment_end: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Fin inscription (unix ts)", required=False, max_length=12
    )
    season_start: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Début saison (unix ts)", required=False, max_length=12
    )
    season_end: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Fin saison (unix ts)", required=False, max_length=12
    )

    def __init__(self, bot: Any, mod: str, guild_id: str) -> None:
        super().__init__()
        self._bot = bot
        self._mod = mod
        self._guild = guild_id
        draft = _draft_of(bot, mod, guild_id)
        for field_key in ("enrollment_start", "enrollment_end", "season_start", "season_end"):
            if draft.get(field_key):
                getattr(self, field_key).default = str(draft[field_key])

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Record the dates, then re-render the view."""
        draft = _draft_of(self._bot, self._mod, self._guild)
        for field_key in ("enrollment_start", "enrollment_end", "season_start", "season_end"):
            draft[field_key] = str(getattr(self, field_key).value or "").strip()
        await interaction.response.defer(ephemeral=True)
        await _send_draft(interaction, self._bot, self._mod, self._guild)


class SeasonDraftButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:draft:(?P<mod>[a-z0-9_-]+):(?P<param>[a-z_]+)",
):
    """One draft parameter's re-open button (the modal comes back)."""

    _PARAM_LABELS: ClassVar[dict[str, str]] = {
        "name": "✏️ Nom",
        "validation": "⚙️ Validation",
        "criteria": "🎯 Critères",
        "players": "👥 Joueurs",
        "map_pool": "🗺️ Map pool",
        "dates": "📅 Dates",
    }

    def __init__(self, mod: str, param: str) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:draft:{mod}:{param}"[:100],
                label=self._PARAM_LABELS.get(param, param),
                style=discord.ButtonStyle.secondary,
            )
        )
        self.mod = mod
        self.param = param

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: Any,
        /,
    ) -> SeasonDraftButton:
        """Rebuild the button at click time."""
        return cls(match["mod"], match["param"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Re-open the parameter's modal (guarded)."""
        from botforge.discord.mod_beta import _beta_guard

        if not await _beta_guard(interaction):
            return
        guild_id = str(interaction.guild_id or "")
        modal = {
            "name": _SeasonNameModal,
            "validation": _SeasonValidationModal,
            "criteria": _SeasonCriteriaModal,
            "players": _SeasonPlayersModal,
            "map_pool": _SeasonMapPoolModal,
            "dates": _SeasonDatesModal,
        }.get(self.param)
        if modal is None:
            return
        await interaction.response.send_modal(modal(interaction.client, self.mod, guild_id))


class SeasonBetaButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:beta:(?P<mod>[a-z0-9_-]+)",
):
    """The season's BETA phase toggle (a season parameter, owner spec).

    The beta is per season: the toggle flips the draft's flag AND the
    mod's beta state (the core's ``is_beta`` — the rules bend when the
    flag is on).
    """

    def __init__(self, mod: str, active: bool) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:beta:{mod}"[:100],
                label="Quitter la phase b\u00eata" if active else "Entrer en phase b\u00eata",
                emoji="\U0001f9ea",
                style=discord.ButtonStyle.danger if active else discord.ButtonStyle.success,
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
    ) -> SeasonBetaButton:
        """Rebuild the toggle at click time."""
        return cls(match["mod"], False)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Flip the season's beta phase (guarded, ephemeral)."""
        from botforge.core.services.beta import enter_beta, exit_beta, is_beta
        from botforge.core.services.mod_storage import ModStateCache
        from botforge.discord.mod_beta import _beta_guard

        if not await _beta_guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id or "")
        draft = _draft_of(interaction.client, self.mod, guild_id)
        state_service = getattr(interaction.client, "state_service", None)
        cache = ModStateCache(state_service, self.mod) if state_service is not None else None
        active = await is_beta(cache, guild_id, self.mod)
        if active:
            await exit_beta(cache, guild_id, self.mod)
            draft["beta"] = False
            note = "Phase b\u00eata quitt\u00e9e \u2014 les r\u00e8gles se redressent."
        else:
            await enter_beta(cache, guild_id, self.mod)
            draft["beta"] = True
            note = "Phase b\u00eata activ\u00e9e \u2014 les r\u00e8gles se plient."
        await interaction.followup.send(note, ephemeral=True)
        await _send_edit_bar(interaction, interaction.client, self.mod, guild_id)


class SeasonCreateConfirmButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:confirm:(?P<mod>[a-z0-9_-]+)",
):
    """The draft's CREATE button: the service's gate decides."""

    def __init__(self, mod: str) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:confirm:{mod}"[:100],
                label="Créer la saison",
                emoji="\u2705",
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
    ) -> SeasonCreateConfirmButton:
        """Rebuild the button at click time."""
        return cls(match["mod"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Create the season (guarded, deferred, the 3s rule)."""
        from botforge.discord.mod_beta import _beta_guard

        if not await _beta_guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id or "")
        draft = _draft_of(interaction.client, self.mod, guild_id)
        stack = _stack(interaction.client, self.mod, guild_id)
        if stack is None:
            await interaction.followup.send(
                "The season stack is not wired on this guild.", ephemeral=True
            )
            return
        try:
            season = await stack.seasons.create_season(
                stack.scope,
                str(draft.get("name") or "Saison"),
                None,
                start_at=int(draft.get("start_at") or 0),
            )
        except Exception as exc:
            message = str(exc)
            if "already has a live season" in message:
                await interaction.followup.send(
                    "Une saison est déjà en cours — termine-la ou supprime-la "
                    "avant d'en créer une nouvelle.",
                    ephemeral=True,
                )
            elif "season end must be after start" in message:
                await interaction.followup.send(
                    "Les dates sont incohérentes — la fin doit suivre le début.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    f"La création a refusé : {message}", ephemeral=True
                )
            return
        _drafts(interaction.client).pop((self.mod, guild_id), None)
        await interaction.followup.send(
            f"Saison **{season.name}** créée (`{season.id}`).", ephemeral=True
        )


def _fmt_date(value: Any) -> str:
    """Format one draft date (a unix ts) for display."""
    try:
        ts = int(value)
        if ts > 0:
            return f"<t:{ts}:f>"
    except (TypeError, ValueError):
        pass
    return "\u2014"


def _derive_status(draft: dict[str, Any]) -> str:
    """Derive the season's status from the dates (never materialized)."""
    import time

    now = int(time.time())
    try:
        enrollment_start = int(draft.get("enrollment_start") or 0)
        enrollment_end = int(draft.get("enrollment_end") or 0)
        season_start = int(draft.get("season_start") or 0)
        season_end = int(draft.get("season_end") or 0)
    except (TypeError, ValueError):
        return "inconnu"
    if season_end and now > season_end:
        return "termin\u00e9e"
    if season_start and now >= season_start:
        return "en cours"
    if enrollment_end and now > enrollment_end:
        return "inscription close"
    if enrollment_start and now >= enrollment_start:
        return "inscription ouverte"
    if enrollment_start and now < enrollment_start:
        return "planifi\u00e9e"
    return "\u00e0 planifier"


def _season_body(draft: dict[str, Any]) -> list[str]:
    """Render the season's config values as the read panel's body."""
    lines = [f"# {draft.get('name') or 'Nouvelle saison'}"]
    lines.append(f"Statut : **{_derive_status(draft)}**")
    lines.append("")
    validation = draft.get("validation") or "manual"
    validation_label = (
        "Manuelle (les admins d\u00e9cident)"
        if validation == "manual"
        else "Automatique (les crit\u00e8res d\u00e9cident)"
    )
    lines.append(f"**Validation** : {validation_label}")
    criteria_bits = []
    if draft.get("elo_type"):
        criteria_bits.append(f"elo {draft['elo_type']}")
    if draft.get("elo_max"):
        criteria_bits.append(f"plafond {draft['elo_max']}")
    if draft.get("min_matches"):
        criteria_bits.append(f"{draft['min_matches']} derniers matchs")
    if criteria_bits:
        lines.append(f"**Crit\u00e8res** : {', '.join(criteria_bits)}")
    players_bits = []
    if draft.get("min_players") and draft.get("max_players"):
        players_bits.append(f"Entre {draft['min_players']} et {draft['max_players']} joueurs")
    elif draft.get("min_players"):
        players_bits.append(f"Au moins {draft['min_players']} joueurs")
    elif draft.get("max_players"):
        players_bits.append(f"Au plus {draft['max_players']} joueurs")
    if players_bits:
        lines.append(f"**Joueurs** : {' '.join(players_bits)}")
    if draft.get("map_pool"):
        lines.append(f"**Map pool** : {draft['map_pool']}")
    lines.append(
        f"**Inscription** : {_fmt_date(draft.get('enrollment_start'))} \u2192 "
        f"{_fmt_date(draft.get('enrollment_end'))}"
    )
    lines.append(
        f"**Saison** : {_fmt_date(draft.get('season_start'))} \u2192 "
        f"{_fmt_date(draft.get('season_end'))}"
    )
    return lines


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


def _enrollment_open(draft: dict[str, Any]) -> bool:
    """Whether the enrollment window is open (derived from the dates)."""
    import time

    now = int(time.time())
    try:
        start = int(draft.get("enrollment_start") or 0)
        end = int(draft.get("enrollment_end") or 0)
    except (TypeError, ValueError):
        return False
    if end and now > end:
        return False
    if start and now < start:
        return False
    return True


async def build_season_layout(
    bot: Any, mod: str, guild_id: str, draft: dict[str, Any], read_mode: bool
) -> discord.ui.LayoutView:
    """Build the season's READ panel (P3, owner spec 2026-11-14).

    A clean reading surface — no sections: the title (the name + the
    season id in the footer), the derived status, the config values
    as a body, the candidates/enrolled counts; the Postuler button
    rides ONLY when the enrollment window is open, before the admin
    button. The admin button reveals the edit action bar (the modal
    openers) as an ephemeral view.
    """
    view = discord.ui.LayoutView(timeout=None)
    season_id = str(draft.get("season_id") or "")
    lines = _season_body(draft)
    if read_mode:
        candidates, enrolled = await _enrollment_counts(bot, mod, guild_id)
        lines.append("")
        lines.append(f"\U0001f9e1 Candidats : **{candidates}** \u00b7 \U0001f465 Inscrits : **{enrolled}**")
    view.add_item(discord.ui.Container(discord.ui.TextDisplay("\n".join(lines))))
    row: Any = discord.ui.ActionRow()
    if read_mode:
        # the Postuler button rides ONLY when the enrollment is open,
        # BEFORE the admin button (the owner's order)
        if _enrollment_open(draft):
            row.add_item(SeasonApplyButton(mod))
        row.add_item(SeasonAdminButton(mod))
    else:
        row.add_item(SeasonCreateConfirmButton(mod))
    view.add_item(row)
    from botforge.discord.ui.view_footer import add_view_footer

    footer_id = f"panel:mod:{mod}:seasons:{season_id}" if season_id else f"panel:mod:{mod}:seasons"
    add_view_footer(view, footer_id)
    return view


async def _send_edit_bar(interaction: discord.Interaction, bot: Any, mod: str, guild_id: str) -> None:
    """Send the season's EDIT action bar (ephemeral, the admin surface).

    The read post stays clean; the admin button reveals THIS bar: the
    parameter openers (each re-calls its modal), the beta phase toggle,
    the create button.
    """
    draft = _draft_of(bot, mod, guild_id)
    view = discord.ui.LayoutView(timeout=None)
    lines = [f"# {draft.get('name') or 'Nouvelle saison'} \u2014 \u00e9dition"]
    lines.append("_Rappelle une modal pour red\u00e9finir un param\u00e8tre._")
    view.add_item(discord.ui.Container(discord.ui.TextDisplay("\n".join(lines))))
    row: Any = discord.ui.ActionRow()
    for param in ("name", "validation", "criteria", "players", "map_pool", "dates"):
        row.add_item(SeasonDraftButton(mod, param))
    view.add_item(row)
    row2: Any = discord.ui.ActionRow()
    row2.add_item(SeasonBetaButton(mod, bool(draft.get("beta"))))
    row2.add_item(SeasonCreateConfirmButton(mod))
    view.add_item(row2)
    if interaction.response.is_done():
        await interaction.followup.send(view=view, ephemeral=True)
    else:
        await interaction.response.send_message(view=view, ephemeral=True)


class SeasonAdminButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:admin:(?P<mod>[a-z0-9_-]+)",
):
    """The read post's admin button: reveals the edit action bar."""

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
        """Reveal the edit action bar (guarded, ephemeral)."""
        from botforge.discord.mod_beta import _beta_guard

        if not await _beta_guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id or "")
        # the active season's values seed the draft (the edits target it)
        stack = _stack(interaction.client, self.mod, guild_id)
        if stack is not None:
            try:
                active = await await_active(stack, guild_id)
            except Exception:
                active = None
            if active is not None:
                draft = _draft_of(interaction.client, self.mod, guild_id)
                draft["season_id"] = str(getattr(active, "id", ""))
                draft["name"] = str(getattr(active, "name", draft.get("name", "")))
                draft["season_start"] = getattr(active, "start_at", None)
                draft["season_end"] = getattr(active, "end_at", None)
        await _send_edit_bar(interaction, interaction.client, self.mod, guild_id)


async def _send_draft(interaction: discord.Interaction, bot: Any, mod: str, guild_id: str) -> None:
    """Send the draft's edit action bar (ephemeral, the admin surface)."""
    await _send_edit_bar(interaction, bot, mod, guild_id)



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
        """Open the apply modal (anyone may apply)."""
        await interaction.response.send_modal(_SeasonApplyModal(self.mod))


class _SeasonApplyModal(discord.ui.Modal, title="Postuler"):
    """The apply modal: the display name, then the enrollment decides."""

    display_name: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Pseudo", placeholder="Ton pseudo de jeu", max_length=64
    )

    def __init__(self, mod: str) -> None:
        super().__init__()
        self._mod = mod

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Apply through the season stack's enrollment (the 3s rule)."""
        await interaction.response.defer(ephemeral=True)
        stack = _stack(interaction.client, self._mod, str(interaction.guild_id or ""))
        if stack is None or stack.enrollment is None:
            await interaction.followup.send(
                "The enrollment is not wired on this guild.", ephemeral=True
            )
            return
        guild_id = str(interaction.guild_id or "")
        try:
            application = await stack.enrollment.apply(
                guild_id,
                str(interaction.user.id),
                str(self.display_name.value or "").strip(),
            )
        except Exception as exc:
            await interaction.followup.send(f"La candidature a \u00e9chou\u00e9 : {exc}", ephemeral=True)
            return
        state = str(getattr(application, "state", "pending"))
        if state == "accepted":
            await interaction.followup.send(
                "Candidature **accept\u00e9e** \u2014 bienvenue !", ephemeral=True
            )
        elif state == "refused":
            reasons = ", ".join(str(r) for r in getattr(application, "reasons", ()) or ())
            await interaction.followup.send(
                f"Candidature **refus\u00e9e**{(' (' + reasons + ')') if reasons else ''}.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "Candidature **en attente** \u2014 les admins d\u00e9cident.", ephemeral=True
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
    client.add_dynamic_items(SeasonDraftButton)
    client.add_dynamic_items(SeasonCreateConfirmButton)
    client.add_dynamic_items(SeasonBetaButton)
    client.add_dynamic_items(SeasonAdminButton)
    client.add_dynamic_items(CandidateDecideButton)


__all__.extend(["register_season_items"])
