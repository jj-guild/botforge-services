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

    validation: discord.ui.Select[Any] = discord.ui.Select(
        placeholder="La validation des candidatures",
        options=[
            discord.SelectOption(label="Manuelle (les admins décident)", value="manual"),
            discord.SelectOption(label="Automatique (les critères décident)", value="auto"),
        ],
        min_values=0,
    )

    def __init__(self, bot: Any, mod: str, guild_id: str) -> None:
        super().__init__()
        self._bot = bot
        self._mod = mod
        self._guild = guild_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Record the mode, then re-render the recap."""
        draft = _draft_of(self._bot, self._mod, self._guild)
        draft["validation"] = str(self.validation.values[0]) if self.validation.values else "manual"
        await interaction.response.defer(ephemeral=True)
        await _send_draft(interaction, self._bot, self._mod, self._guild)


class _SeasonCriteriaModal(discord.ui.Modal, title="Les critères de validation"):
    """The draft's validation criteria (re-openable; the provider work is planned)."""

    elo_type: discord.ui.Select[Any] = discord.ui.Select(
        placeholder="Le leaderboard qui compte",
        options=[
            discord.SelectOption(label="Elo 1v1", value="1v1"),
            discord.SelectOption(label="Elo TG", value="tg"),
        ],
        min_values=0,
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
        draft["elo_type"] = str(self.elo_type.values[0]) if self.elo_type.values else ""
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
    """The draft's map pool (re-openable; the pool picker is planned)."""

    map_pool: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Map pool (nom ou id)", placeholder="pool-base", required=False, max_length=64
    )

    def __init__(self, bot: Any, mod: str, guild_id: str) -> None:
        super().__init__()
        self._bot = bot
        self._mod = mod
        self._guild = guild_id
        draft = _draft_of(bot, mod, guild_id)
        if draft.get("map_pool"):
            self.map_pool.default = str(draft["map_pool"])

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Record the pool, then re-render the view."""
        draft = _draft_of(self._bot, self._mod, self._guild)
        draft["map_pool"] = str(self.map_pool.value or "").strip()
        await interaction.response.defer(ephemeral=True)
        await _send_draft(interaction, self._bot, self._mod, self._guild)


class _SeasonDatesModal(discord.ui.Modal, title="Les dates"):
    """The draft's enrollment + season dates (re-openable)."""

    enrollment_start: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Début inscription (unix ts, vide = tout de suite)", required=False, max_length=12
    )
    enrollment_end: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Fin inscription (unix ts, vide = à la création)", required=False, max_length=12
    )
    season_start: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Début saison (unix ts, vide = tout de suite)", required=False, max_length=12
    )
    season_end: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Fin saison (unix ts, vide = indéterminée)", required=False, max_length=12
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


async def build_season_layout(
    bot: Any, mod: str, guild_id: str, draft: dict[str, Any], read_mode: bool
) -> discord.ui.LayoutView:
    """Build the season's view: a section per config group (P3, owner spec).

    Each section carries its current value in the body and its
    modal-opening button as the accessory (editable one by one); the
    status derives from the dates (never materialized); the read mode
    adds the candidates/enrolled counts and the Postuler button.
    """
    view = discord.ui.LayoutView(timeout=None)
    name = str(draft.get("name") or "Nouvelle saison")
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {name}"),
        discord.ui.TextDisplay(f"Statut : **{_derive_status(draft)}**"),
    ]
    if read_mode:
        candidates, enrolled = await _enrollment_counts(bot, mod, guild_id)
        blocks.append(
            discord.ui.TextDisplay(
                f"\U0001f9e1 Candidats : **{candidates}** \u00b7 \U0001f465 Inscrits : **{enrolled}**"
            )
        )
    view.add_item(discord.ui.Container(*blocks))
    validation = draft.get("validation") or "manual"
    validation_label = (
        "Manuelle (les admins d\u00e9cident)"
        if validation == "manual"
        else "Automatique (les crit\u00e8res d\u00e9cident)"
    )
    criteria_bits = []
    if draft.get("elo_type"):
        criteria_bits.append(f"elo {draft['elo_type']}")
    if draft.get("elo_max"):
        criteria_bits.append(f"elo max {draft['elo_max']}")
    if draft.get("min_matches"):
        criteria_bits.append(f"{draft['min_matches']} derniers matchs")
    players_bits = []
    if draft.get("min_players"):
        players_bits.append(f"min {draft['min_players']}")
    if draft.get("max_players"):
        players_bits.append(f"max {draft['max_players']}")
    sections: list[tuple[str, str]] = [
        ("name", str(draft.get("name") or "\u2014")),
        ("validation", validation_label),
        ("criteria", ", ".join(criteria_bits) if criteria_bits else "\u2014"),
        ("players", ", ".join(players_bits) if players_bits else "\u2014"),
        ("map_pool", str(draft.get("map_pool") or "\u2014")),
        (
            "dates",
            (
                f"Inscription : {_fmt_date(draft.get('enrollment_start'))} \u2192 "
                f"{_fmt_date(draft.get('enrollment_end'))}\n"
                f"Saison : {_fmt_date(draft.get('season_start'))} \u2192 "
                f"{_fmt_date(draft.get('season_end'))}"
            ),
        ),
    ]
    for param, value in sections:
        view.add_item(_config_section(mod, param, value))
    row: Any = discord.ui.ActionRow()
    if read_mode:
        row.add_item(SeasonApplyButton(mod))
    else:
        row.add_item(SeasonCreateConfirmButton(mod))
    view.add_item(row)
    from botforge.discord.ui.view_footer import add_view_footer

    add_view_footer(view, f"panel:mod:{mod}:seasons")
    return view


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


def _config_section(mod: str, param: str, value: str) -> Any:
    """Build one config group's Section: the value + the edit accessory."""
    label = SeasonDraftButton._PARAM_LABELS.get(param, param)
    return discord.ui.Section(
        discord.ui.TextDisplay(f"**{label}**\n{value}"),
        accessory=SeasonDraftButton(mod, param),
    )


async def _send_draft(interaction: discord.Interaction, bot: Any, mod: str, guild_id: str) -> None:
    """Send the draft's sectioned view (ephemeral)."""
    draft = _draft_of(bot, mod, guild_id)
    view = await build_season_layout(bot, mod, guild_id, draft, read_mode=False)
    if interaction.response.is_done():
        await interaction.followup.send(view=view, ephemeral=True)
    else:
        await interaction.response.send_message(view=view, ephemeral=True)



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
    client.add_dynamic_items(CandidateDecideButton)


__all__.extend(["register_season_items"])
