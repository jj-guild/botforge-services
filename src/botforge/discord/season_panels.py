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
        # the read mode: the active season + its STORED config (the
        # modals' edits live there — the name, the validation, the
        # criteria, the dates) + the counts
        season_id = str(getattr(active, "id", ""))
        draft = await _load_season_config(bot, mod, guild_id, season_id)
        draft.setdefault("name", str(getattr(active, "name", "")))
        draft.setdefault("season_start", getattr(active, "start_at", None))
        draft.setdefault("season_end", getattr(active, "end_at", None))
        draft["season_id"] = season_id
        return await build_season_layout(bot, mod, guild_id, draft, read_mode=True)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(f"# 📅 {mod.capitalize()} — saisons"),
            discord.ui.TextDisplay("_Aucune saison active._"),
        )
    )
    from botforge.discord.ui.factory import split_action_rows
    from botforge.discord.ui.view_footer import add_view_footer

    for row in split_action_rows([SeasonCreateButton(mod).item]):
        view.add_item(row)

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


class SeasonManageButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:manage:(?P<mod>[a-z0-9_-]+):(?P<action>end|delete)",
):
    """The season's management: end it, or delete a never-started one."""

    def __init__(self, mod: str, action: str) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:manage:{mod}:{action}"[:100],
                label="Terminer la saison" if action == "end" else "Supprimer la saison",
                emoji="\U0001f3c1" if action == "end" else "\U0001f5d1\ufe0f",
                style=discord.ButtonStyle.danger,
            )
        )
        self.mod = mod
        self.action = action

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: Any,
        /,
    ) -> SeasonManageButton:
        """Rebuild the button at click time."""
        return cls(match["mod"], match["action"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """End or delete the season (guarded, ephemeral, the 3s rule)."""
        import time

        from botforge.discord.mod_beta import _beta_guard

        if not await _beta_guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id or "")
        stack = _stack(interaction.client, self.mod, guild_id)
        if stack is None:
            await interaction.followup.send(
                "The season stack is not wired on this guild.", ephemeral=True
            )
            return
        active = None
        try:
            active = await await_active(stack, guild_id)
        except Exception:
            logger.warning("SEASON MANAGE: the active lookup failed", exc_info=True)
        if active is None:
            await interaction.followup.send("Aucune saison active.", ephemeral=True)
            return
        season_id = str(getattr(active, "id", ""))
        try:
            if self.action == "end":
                await stack.seasons.end_season(season_id, now=int(time.time()))
                note = f"Saison **{getattr(active, 'name', season_id)}** termin\u00e9e."
            else:
                await stack.seasons.delete_season(season_id)
                note = f"Saison **{getattr(active, 'name', season_id)}** supprim\u00e9e."
        except Exception as exc:
            message = str(exc)
            if "cannot be deleted" in message:
                await interaction.followup.send(
                    "Seule une saison jamais activ\u00e9e peut \u00eatre supprim\u00e9e \u2014 "
                    "termine-la plut\u00f4t.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(f"L'action a refus\u00e9 : {message}", ephemeral=True)
            return
        await _refresh_seasons_pin(interaction.client, guild_id, self.mod)
        await interaction.followup.send(note, ephemeral=True)


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


class _SeasonValidationModal(discord.ui.Modal, title="La validation"):
    """The season's mode: the validation + the beta phase (re-openable).

    The BETA phase rides here as a CHECKBOX (owner direction
    2026-11-14) — the season's rules bend while the box is checked.
    """

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
    beta: Any = discord.ui.Label(
        text="Saison bêta (les règles se plient)",
        component=discord.ui.Checkbox(),
    )

    def __init__(self, bot: Any, mod: str, guild_id: str) -> None:
        super().__init__()
        self._bot = bot
        self._mod = mod
        self._guild = guild_id
        draft = _draft_of(bot, mod, guild_id)
        if draft.get("beta"):
            self.beta.component.default = True

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Record the mode + the beta flag, then update the post."""
        draft = _draft_of(self._bot, self._mod, self._guild)
        select: Any = getattr(self.validation, "component", self.validation)
        draft["validation"] = str(select.values[0]) if select.values else "manual"
        checkbox = getattr(self.beta, "component", None)
        if checkbox is not None:
            draft["_mod"] = self._mod
            await _sync_beta_flag(interaction, draft, bool(getattr(checkbox, "values", False)))
        await _persist_season_config(self._bot, self._mod, self._guild, draft)
        await interaction.response.defer(ephemeral=True)
        await _refresh_seasons_pin(self._bot, self._guild, self._mod)


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
    elo_min: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Elo min (vide = aucun plancher)", placeholder="1200", required=False, max_length=4
    )
    elo_max: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="Elo max (vide = aucun plafond)", placeholder="2000", required=False, max_length=4
    )
    min_matches: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="X matchs joués",
        placeholder="10",
        required=False,
        max_length=4,
    )
    matches_window_days: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="...dans les N derniers jours",
        placeholder="30",
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
        draft["elo_min"] = str(self.elo_min.value or "").strip()
        draft["elo_max"] = str(self.elo_max.value or "").strip()
        draft["min_matches"] = str(self.min_matches.value or "").strip()
        draft["matches_window_days"] = str(self.matches_window_days.value or "").strip()
        await _persist_season_config(self._bot, self._mod, self._guild, draft)
        await interaction.response.defer(ephemeral=True)
        await _refresh_seasons_pin(self._bot, self._guild, self._mod)


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
        await _persist_season_config(self._bot, self._mod, self._guild, draft)
        await interaction.response.defer(ephemeral=True)
        await _refresh_seasons_pin(self._bot, self._guild, self._mod)


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
        await _persist_season_config(self._bot, self._mod, self._guild, draft)
        await interaction.response.defer(ephemeral=True)
        await _refresh_seasons_pin(self._bot, self._guild, self._mod)


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


_EDIT_PARAMS = ("name", "validation", "criteria", "players", "map_pool")
_DATE_FIELDS = {
    "enrollment_start": "Début inscription",
    "enrollment_end": "Fin inscription",
    "season_start": "Début saison",
    "season_end": "Fin saison",
}


def _next_full_hour() -> str:
    """Return the next full hour, YYYY-MM-DD HH:MM (the guild's TZ, Paris default)."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("Europe/Paris"))
    nxt = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    return nxt.strftime("%Y-%m-%d %H:%M")


def _parse_date(raw: str) -> int:
    """Parse YYYY-MM-DD HH:MM in the guild's TZ into a unix ts (0 = empty)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    raw = (raw or "").strip()
    if not raw:
        return 0
    parsed = datetime.strptime(raw, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Europe/Paris"))
    return int(parsed.timestamp())


def _render_date_input(ts: Any) -> str:
    """Render a stored ts back to YYYY-MM-DD HH:MM (the modal's prefill)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    try:
        value = int(ts)
    except (TypeError, ValueError):
        return ""
    if value <= 0:
        return ""
    return datetime.fromtimestamp(value, ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d %H:%M")


def _fmt_rel(value: Any) -> str:
    """Format one stored ts as a RELATIVE Discord timestamp."""
    try:
        ts = int(value)
        if ts > 0:
            return f"<t:{ts}:R>"
    except (TypeError, ValueError):
        pass
    return "—"


class _SeasonDateModal(discord.ui.Modal, title="La date"):
    """One date's single-field modal (re-openable, pre-filled)."""

    value: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label="YYYY-MM-DD HH:MM (vide = effacer)",
        placeholder="2026-11-20 20:00",
        required=False,
        max_length=16,
    )

    def __init__(self, bot: Any, mod: str, guild_id: str, field_key: str) -> None:
        super().__init__(title=_DATE_FIELDS.get(field_key, "La date"))
        self._bot = bot
        self._mod = mod
        self._guild = guild_id
        self._field = field_key
        draft = _draft_of(bot, mod, guild_id)
        stored = _render_date_input(draft.get(field_key))
        self.value.default = stored or _next_full_hour()

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Parse + record the date, then update the pinned post."""
        draft = _draft_of(self._bot, self._mod, self._guild)
        draft[self._field] = _parse_date(str(self.value.value or ""))
        await _persist_season_config(self._bot, self._mod, self._guild, draft)
        await interaction.response.defer(ephemeral=True)
        await _refresh_seasons_pin(self._bot, self._guild, self._mod)


class SeasonDraftButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:draft:(?P<mod>[a-z0-9_-]+):(?P<param>[a-z_]+)",
):
    """One draft parameter's re-open button (the modal comes back)."""

    _PARAM_LABELS: ClassVar[dict[str, str]] = {
        "enrollment_start": "📅 Début inscription",
        "enrollment_end": "📅 Fin inscription",
        "season_start": "📅 Début saison",
        "season_end": "📅 Fin saison",
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
        }.get(self.param)
        if self.param in _DATE_FIELDS:
            await interaction.response.send_modal(
                _SeasonDateModal(interaction.client, self.mod, guild_id, self.param)
            )
            return
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
        await _refresh_seasons_pin(interaction.client, guild_id, self.mod)


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
            await interaction.followup.send("The season stack is not wired on this guild.", ephemeral=True)
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
                    "Une saison est déjà en cours — termine-la ou supprime-la avant d'en créer une nouvelle.",
                    ephemeral=True,
                )
            elif "season end must be after start" in message:
                await interaction.followup.send(
                    "Les dates sont incohérentes — la fin doit suivre le début.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(f"La création a refusé : {message}", ephemeral=True)
            return
        draft["season_id"] = str(season.id)
        await _persist_season_config(interaction.client, self.mod, guild_id, draft)
        _drafts(interaction.client).pop((self.mod, guild_id), None)
        await _refresh_seasons_pin(interaction.client, guild_id, self.mod)
        await interaction.followup.send(f"Saison **{season.name}** créée (`{season.id}`).", ephemeral=True)


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
        bounds = draft.get("elo_type")
        if draft.get("elo_min") or draft.get("elo_max"):
            bounds = f"{draft.get('elo_min') or '-'}-{draft.get('elo_max') or '-'} ({bounds})"
        criteria_bits.append(f"elo {bounds}")
    if draft.get("min_matches"):
        window = f" dans les {draft['matches_window_days']} derniers jours" if draft.get("matches_window_days") else ""
        criteria_bits.append(f"{draft['min_matches']} matchs{window}")
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
        f"**Inscription** : {_fmt_rel(draft.get('enrollment_start'))} \u2192 {_fmt_rel(draft.get('enrollment_end'))}"
    )
    lines.append(f"**Saison** : {_fmt_rel(draft.get('season_start'))} \u2192 {_fmt_rel(draft.get('season_end'))}")
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
    """Whether the enrollment window is DECLARED and open.

    An unconfigured season never accepts applications (the owner's
    rule: Postuler appears only when the dates are set and the
    window is open) — no default-open.
    """
    import time

    now = int(time.time())
    try:
        start = int(draft.get("enrollment_start") or 0)
        end = int(draft.get("enrollment_end") or 0)
    except (TypeError, ValueError):
        return False
    try:
        season_start = int(draft.get("season_start") or 0)
        season_end = int(draft.get("season_end") or 0)
    except (TypeError, ValueError):
        return False
    # the window must be DECLARED (the enrollment AND the season dates)
    # and open: now > début inscription, now < fin inscription
    if not start or not end or not season_start or not season_end:
        return False
    return start < now < end


async def _seasons_list_lines(bot: Any, mod: str, guild_id: str) -> list[str]:
    """List the ladder's seasons (the history under the active one)."""
    stack = _stack(bot, mod, guild_id)
    if stack is None:
        return []
    try:
        seasons = await stack.seasons.list_seasons(stack.scope)
    except Exception:
        logger.warning("SEASON VIEW: the seasons list unreadable", exc_info=True)
        return []
    lines = ["**Saisons** :"]
    for season in seasons[:10]:
        season_id = str(getattr(season, "id", "?"))
        name = str(getattr(season, "name", season_id))
        state = str(getattr(season, "state", "?"))
        marker = " \u25b8" if str(getattr(season, "state", "")) in ("scheduled", "active") else ""
        lines.append(f"\u2022 {name} (`{season_id}`) — {state}{marker}")
    return lines if len(lines) > 1 else []


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
    if season_id:
        # the #321 card contract: the resource id sits at the same
        # place on every card — the subtitle's first line, in backticks
        lines.insert(1, f"-# `{season_id}`")
    if read_mode:
        candidates, enrolled = await _enrollment_counts(bot, mod, guild_id)
        lines.append("")
        lines.append(f"\U0001f9e1 Candidats : **{candidates}** \u00b7 \U0001f465 Inscrits : **{enrolled}**")
    seasons_list = await _seasons_list_lines(bot, mod, guild_id)
    if seasons_list:
        lines.append("")
        lines.extend(seasons_list)
    view.add_item(discord.ui.Container(discord.ui.TextDisplay("\n".join(lines))))
    from botforge.discord.ui.factory import split_action_rows
    from botforge.discord.ui.view_footer import add_view_footer

    row_items: list[Any] = []
    if read_mode:
        # the Postuler button rides ONLY when the enrollment is open,
        # BEFORE the admin button (the owner's order)
        if _enrollment_open(draft):
            row_items.append(SeasonApplyButton(mod).item)
        row_items.append(SeasonAdminButton(mod).item)
    else:
        row_items.append(SeasonCreateConfirmButton(mod).item)
    for row in split_action_rows(row_items):
        view.add_item(row)

    # the footer id: the guild + the season's INDEX (the season id's
    # last segment) — no repeated mod, no implicit game key
    index = season_id.rsplit(":", 1)[-1] if season_id else ""
    footer_id = (
        f"panel:mod:{mod}:seasons:{guild_id}:{index}"
        if index
        else f"panel:mod:{mod}:seasons:{guild_id}"
    )
    add_view_footer(view, footer_id)
    return view


async def _send_edit_bar(
    interaction: discord.Interaction, bot: Any, mod: str, guild_id: str, has_season: bool = True
) -> None:
    """Send the season's EDIT action bar (ephemeral, the admin surface).

    The read post stays clean; the admin button reveals THIS bar: the
    parameter openers (each re-calls its modal), the create button
    (only when no season lives), the management (only when one does).
    No header — the panel id rides the footer.
    """
    draft = _draft_of(bot, mod, guild_id)
    view = discord.ui.LayoutView(timeout=None)
    from botforge.discord.ui.factory import split_action_rows

    edit_items: list[Any] = [
        *(SeasonDraftButton(mod, param).item for param in _EDIT_PARAMS),
        *(SeasonDraftButton(mod, key).item for key in _DATE_FIELDS),
        *( [SeasonCreateConfirmButton(mod).item] if not has_season else [] ),
        *( [SeasonManageButton(mod, "end").item, SeasonManageButton(mod, "delete").item] if has_season else [] ),
    ]
    for row in split_action_rows(edit_items):
        view.add_item(row)
    from botforge.discord.ui.view_footer import add_view_footer

    add_view_footer(view, f"panel:mod:{mod}:seasons:{guild_id}")
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
    client.add_dynamic_items(SeasonDraftButton)
    client.add_dynamic_items(SeasonCreateConfirmButton)
    client.add_dynamic_items(SeasonManageButton)
    client.add_dynamic_items(SeasonBetaButton)
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
    """
    from discord.ext import tasks

    @tasks.loop(minutes=5)
    async def _loop() -> None:
        try:
            await _refresh_all_season_pins(bot)
        except Exception:
            logger.warning("SEASON refresher: the pass failed — best-effort", exc_info=True)

    _loop.start()
    logger.info("SEASON refresher started (every 5 minutes)")
