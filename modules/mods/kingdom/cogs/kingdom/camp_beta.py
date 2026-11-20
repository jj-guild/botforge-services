"""The ⚔️ Roi ou Seigneur provisional door (camp-beta-v1, Drasah 19/11).

The founding/joining door the 3-tier model parks for LATER — but the
BETA seasons need it NOW so Drasah can pilot two kingdoms against each
other. The ruling (Drasah 19/11):

- a **BETA** season arms the PROVISIONAL system: this ephemeral window
  straight on the Postuler panel — found a kingdom (the name modal,
  auto-approved: a test season validates nobody) or join one (the
  picker of the approved kingdoms with free seats), queue fallback;
- a **NORMAL** season shows NOTHING provisional — the official flow
  (project account > season dossier > throne or vasselage) will come
  later, and this door never leaks into it.

Everything rides the service seams verbatim (``enroll``,
``approve_kingdom``, ``kingdoms``, ``lords``): the mod owns the shape,
the engine owns the rules. Announce-ready (#396): one declared window
id + restart-proof DynamicItem custom ids under ``kingdom:camp:``.
"""

from __future__ import annotations

import logging
from typing import Any

import discord

from .common import mod_catalog, open_unique_ephemeral, surface, wiring

logger = logging.getLogger("kingdom.camp")

CAMP_WINDOW_KEY = "panel:mod:kingdom:camp"
_NS = "kingdom:camp"

GOLD = discord.Colour(0xE6B800)


def camp_strings(locale: str) -> dict[str, str]:
    """The camp surfaces' strings (``kingdom.camp`` section)."""
    return dict(mod_catalog().section("kingdom.camp", str(locale)[:2]))


def _strings(interaction: discord.Interaction) -> dict[str, str]:
    from .common import locale_of

    return camp_strings(locale_of(interaction))


async def beta_armed() -> bool:
    """Whether the running season is a beta (the provisional door's gate).

    A NORMAL season shows no provisional door: ``beta_name`` is None
    and this returns False — the official flow (account > dossier >
    throne/vasselage) owns the normal seasons when it lands.
    """
    stack = wiring()
    if stack is None:
        return False
    try:
        season = await stack.kingdoms.current_season()
    except Exception:  # noqa: BLE001 — an unreadable season never arms the door
        logger.warning("kingdom: camp door season read failed", exc_info=True)
        return False
    return season is not None and getattr(season, "beta_name", None) is not None


async def season_door_open() -> bool:
    """Whether a season is LIVE — the ⚔️ door's gate (Drasah 20/11).

    camp-door-any-season (Drasah 20/11): the provisional door shows
    whenever a season RUNS — classical or beta alike. The compressed
    WEEKEND format is the season.TYPE (chosen at launch, it bends the
    clocks) while the door is the only founding path until the
    official flow (account > dossier > throne/vasselage) lands.
    """
    stack = wiring()
    if stack is None:
        return False
    try:
        season = await stack.kingdoms.current_season()
    except Exception:  # noqa: BLE001 — an unreadable season never opens the door
        logger.warning("kingdom: camp door season read failed", exc_info=True)
        return False
    return season is not None and not bool(getattr(season, "finished", False))


async def season_is_beta() -> bool:
    """Whether the LIVE season runs the compressed beta type (hors-saison-v1).

    The type is the SEASON's own data (``beta_name`` armed at launch by
    ``_arm_compressed_beta``), never a mode flag: the conscription rides
    on the season the players actually play. In beta the parcours skips
    the account step entirely (Drasah 20/11 — « on postule directement,
    sans compte »).
    """
    stack = wiring()
    if stack is None:
        return False
    try:
        season = await stack.kingdoms.current_season()
    except Exception:  # noqa: BLE001 — an unreadable season is never a beta
        logger.warning("kingdom: beta season read failed", exc_info=True)
        return False
    return (
        season is not None
        and not bool(getattr(season, "finished", False))
        and bool(getattr(season, "beta_name", None))
    )


def build_camp_button(strings: dict[str, str]) -> KingdomCampButton:
    """The camp door button, painted with the given locale's label."""
    return KingdomCampButton(
        str(strings.get("button", "⚔️ Choisir mon camp")),
        discord.ButtonStyle.primary,
    )


def _window(strings: dict[str, str], *rows: Any) -> discord.ui.LayoutView:
    """Build the camp layout (the declared window id + its footer)."""
    return surface(
        CAMP_WINDOW_KEY,
        discord.ui.Container(
            discord.ui.TextDisplay(f"# {strings['window_title']}"),
            *rows,
            accent_colour=GOLD,
        ),
    )


async def _current_lord(stack: Any, user_id: str) -> Any | None:
    """The user's ACTIVE lord document of the season (None otherwise).

    No admin hat here: the door answers the PLAYER's own record — an
    admin testing with a second account is treated as the plain player
    he is on it, and the first-click state reads his real engagement.
    """
    try:
        lords = await stack.kingdoms.lords()
    except Exception:  # noqa: BLE001 — the window reports, never raises
        logger.warning("kingdom: camp door lords read failed", exc_info=True)
        return None
    return next((lord for lord in lords if str(lord.id) == str(user_id) and not lord.left), None)


async def _state_lines(strings: dict[str, str], stack: Any, lord: Any | None) -> list[str]:
    """The human lines of one player's camp state ('' when unengaged)."""
    if lord is None:
        return []
    from .common import kingdom_name

    if getattr(lord, "in_queue", False) or getattr(lord, "kingdom_id", None) is None:
        return [str(strings["already_queue_line"])]
    name = await kingdom_name(stack.kingdoms, lord.kingdom_id)
    if str(getattr(lord, "role", "")) == "king":
        return [str(strings["already_king_line"]).format(name)]
    return [str(strings["already_lord_line"]).format(name)]


async def _joinable_kingdoms(stack: Any) -> list[tuple[Any, int]]:
    """The APPROVED player kingdoms with at least one free lord seat."""
    from botforge.mods.kingdom.models import KingdomValidation
    from botforge.mods.kingdom.service import TEST_KINGDOM_ID

    try:
        kingdoms = await stack.kingdoms.kingdoms()
        lords = await stack.kingdoms.lords()
        capacity = int(getattr(stack.kingdoms.config, "lords_per_kingdom", 0) or 0)
    except Exception:  # noqa: BLE001 — the window reports, never raises
        logger.warning("kingdom: camp door kingdoms read failed", exc_info=True)
        return []
    result: list[tuple[Any, int]] = []
    for kingdom in kingdoms:
        if kingdom.is_gaia or str(kingdom.id) == str(TEST_KINGDOM_ID):
            continue
        if kingdom.validation is not KingdomValidation.APPROVED:
            continue
        subjects = sum(
            1
            for lord in lords
            if lord.kingdom_id == kingdom.id
            and not lord.left
            and str(getattr(lord, "role", "")) != "king"
        )
        seats = capacity - subjects
        if seats > 0:
            result.append((kingdom, seats))
    return result


async def _camp_window(interaction: discord.Interaction) -> discord.ui.LayoutView:
    """Build the camp window: the state lines, the two doors (or nothing)."""
    strings = _strings(interaction)
    stack = wiring()
    rows: list[Any] = [discord.ui.TextDisplay(str(strings["window_help"]))]
    if stack is None:
        rows.append(discord.ui.TextDisplay(str(strings["none_note"])))
        return _window(strings, *rows)
    lord = await _current_lord(stack, str(interaction.user.id))
    lines = await _state_lines(strings, stack, lord)
    if lines:
        rows.append(discord.ui.Separator())
        rows.extend(discord.ui.TextDisplay(line) for line in lines)
        return _window(strings, *rows)
    rows.append(discord.ui.Separator())
    door_row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    door_row.add_item(
        KingdomCampFoundButton(strings["found_button"], discord.ButtonStyle.success).item
    )
    door_row.add_item(
        KingdomCampJoinButton(strings["join_button"], discord.ButtonStyle.primary).item
    )
    rows.append(door_row)
    return _window(strings, *rows)


async def _join_window(interaction: discord.Interaction) -> discord.ui.LayoutView:
    """Build the joining window: the picker, the queue fallback."""
    strings = _strings(interaction)
    stack = wiring()
    rows: list[Any] = [
        discord.ui.TextDisplay(f"## {strings['join_window_title']}"),
        discord.ui.TextDisplay(str(strings["join_help"])),
        discord.ui.Separator(),
    ]
    if stack is not None:
        joinable = await _joinable_kingdoms(stack)
        if joinable:
            picker = KingdomCampJoinSelect(str(strings["pick_placeholder"]))
            picker.item.options = KingdomCampJoinSelect.options_of(joinable, strings)
            picker_row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
            picker_row.add_item(picker.item)
            rows.append(picker_row)
            rows.append(discord.ui.Separator())
    else:
        rows.append(discord.ui.TextDisplay(str(strings["none_note"])))
    queue_row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    queue_row.add_item(
        KingdomCampQueueButton(str(strings["queue_button"]), discord.ButtonStyle.secondary).item
    )
    rows.append(queue_row)
    return _window(strings, *rows)


def _camp_failure(strings: dict[str, str], exc: Exception) -> str:
    """Map a service failure to its player-facing note (code-keyed first)."""
    from botforge.mods.kingdom.errors import KingdomError

    if isinstance(exc, KingdomError):
        code = str(getattr(exc, "code", "") or "")
        key = f"err_{code.lower()}"
        if strings.get(key):
            return str(strings[key])
    return str(strings["error"]).format(str(exc)[:150])


class KingdomCampButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:open$"
):
    """The ⚔️ Choisir mon camp door — pinned on the Postuler panel (beta only)."""

    def __init__(self, label: str, style: discord.ButtonStyle) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:open",
                style=style or discord.ButtonStyle.primary,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""
        return cls(_strings(interaction)["button"], discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the camp window (ephemeral, the state reads live)."""
        await open_unique_ephemeral(interaction, view=await _camp_window(interaction))


class KingdomCampFoundButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:found$"
):
    """« 👑 Fonder mon royaume » — the name modal, then the engine's enroll."""

    def __init__(self, label: str, style: discord.ButtonStyle) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:found",
                style=style or discord.ButtonStyle.success,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""
        return cls(_strings(interaction)["found_button"], discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Send the founding modal (the name, then the engine)."""
        await interaction.response.send_modal(KingdomCampNameModal(_strings(interaction)))


class KingdomCampJoinButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:join$"
):
    """« 🛡️ Rejoindre un royaume » — the picker of the approved kingdoms."""

    def __init__(self, label: str, style: discord.ButtonStyle) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:join",
                style=style or discord.ButtonStyle.primary,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""
        return cls(_strings(interaction)["join_button"], discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the joining window (picker + queue fallback)."""
        await open_unique_ephemeral(interaction, view=await _join_window(interaction))


class KingdomCampQueueButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:queue$"
):
    """« 🛡️ Rejoindre la file d'attente » — enroll as a queued Lord."""

    def __init__(self, label: str, style: discord.ButtonStyle) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:queue",
                style=style or discord.ButtonStyle.secondary,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""
        return cls(_strings(interaction)["queue_button"], discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Enroll as a queued Lord (the engine's own queue, D23)."""
        from .settings_panel import _safe_followup

        strings = _strings(interaction)
        await interaction.response.defer(ephemeral=True)
        stack = wiring()
        if stack is None:
            await interaction.followup.send(str(strings["none_note"]), ephemeral=True)
            return
        try:
            await stack.kingdoms.enroll(
                str(interaction.user.id), _display_name(interaction), _lord_role("lord")
            )
            note = str(strings["queue_done"])
        except Exception as exc:  # noqa: BLE001 — the window reports, never raises
            logger.warning("kingdom: camp queue enroll failed", exc_info=True)
            note = _camp_failure(strings, exc)
        await _safe_followup(interaction, note)


class KingdomCampJoinSelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]], template=rf"{_NS}:pick$"
):
    """The kingdom picker — the choice enrolls the player as a Lord."""

    def __init__(self, placeholder: str) -> None:
        super().__init__(
            discord.ui.Select(
                placeholder=placeholder[:100],
                custom_id=f"{_NS}:pick",
                min_values=1,
                max_values=1,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the picker from the wire (locale placeholder, stable id)."""
        return cls(_strings(interaction)["pick_placeholder"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Enroll the player as a Lord of the picked kingdom."""
        from .settings_panel import _safe_followup

        strings = _strings(interaction)
        await interaction.response.defer(ephemeral=True)
        stack = wiring()
        if stack is None:
            await interaction.followup.send(str(strings["none_note"]), ephemeral=True)
            return
        values = [str(v) for v in (self.item.values or [])]
        kingdom_id = values[0] if values else ""
        if not kingdom_id:
            return
        try:
            kingdom = next(
                (k for k, _seats in await _joinable_kingdoms(stack) if str(k.id) == kingdom_id),
                None,
            )
            if kingdom is None:
                raise ValueError(str(strings["no_kingdoms"]))
            await stack.kingdoms.enroll(
                str(interaction.user.id),
                _display_name(interaction),
                _lord_role("lord"),
                kingdom_name=str(kingdom.name),
            )
            note = str(strings["join_done"]).format(str(kingdom.name))
        except Exception as exc:  # noqa: BLE001 — the window reports, never raises
            logger.warning("kingdom: camp join enroll failed", exc_info=True)
            note = _camp_failure(strings, exc)
        await _safe_followup(interaction, note)

    @staticmethod
    def options_of(
        joinable: list[tuple[Any, int]], strings: dict[str, str]
    ) -> list[discord.SelectOption]:
        """Render the picker's options (one per kingdom, seats in description)."""
        options = [
            discord.SelectOption(
                label=str(getattr(kingdom, "name", ""))[:100],
                value=str(getattr(kingdom, "id", "")),
                description=str(strings["seats_left"]).format(seats)[:100],
            )
            for kingdom, seats in joinable
        ]
        return options[:25]


class KingdomCampNameModal(discord.ui.Modal):
    """The founding modal — the kingdom's name, then the engine's enroll."""

    name_input = discord.ui.TextInput(
        label="Nom du royaume",
        min_length=2,
        max_length=45,
        required=True,
    )

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(title=str(strings.get("modal_title", "👑 Fonder un royaume"))[:45])
        self.name_input.label = str(strings["modal_label"])[:45]
        self.strings = strings

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Found the PERSISTENT realm (royaume-persistant-v1, Drasah 20/11).

        « Créer un royaume n'engage pas » : founding provisions the
        realm's category in DORMANT mode (only 🏰 Le royaume shows) —
        the season entry is a SEPARATE act (the chez-soi window's
        « Voir la saison », an admin accepts).
        """
        from .settings_panel import _safe_followup

        strings = self.strings
        await interaction.response.defer(ephemeral=True)
        stack = wiring()
        if stack is None:
            await interaction.followup.send(str(strings["none_note"]), ephemeral=True)
            return
        proposed = str(self.name_input.value or "").strip()
        try:
            realm = await stack.realms.found_realm(
                str(interaction.user.id), _display_name(interaction), proposed
            )
            guild = getattr(interaction, "guild", None)
            if guild is not None:
                from .realms import deploy_realm_hub, ensure_realm_structure

                ids = await ensure_realm_structure(guild, realm, dormant=True)
                # hub-content-v2: the hub message id rides the shell's
                # discord ids (fetch → edit; a stale id recreates)
                hub_message = await deploy_realm_hub(guild, realm)
                if hub_message:
                    ids["hub_message"] = hub_message
                if ids:
                    realm = await stack.realms.save_habitat(str(realm.id), ids)
            note = str(strings["found_done"]).format(str(realm.name))
        except Exception as exc:  # noqa: BLE001 — the window reports, never raises
            logger.warning("kingdom: realm founding failed", exc_info=True)
            note = _camp_failure(strings, exc)
        await _safe_followup(interaction, note)


def _display_name(interaction: discord.Interaction) -> str:
    """The player's display name (the engine's enrollment field)."""
    user = getattr(interaction, "user", None)
    name = str(getattr(user, "display_name", "") or "") if user is not None else ""
    return name or str(getattr(user, "id", "unknown"))


def _lord_role(which: str) -> Any:
    """The engine's LordRole value (king or lord)."""
    from botforge.mods.kingdom.models import LordRole

    return LordRole.KING if which == "king" else LordRole.LORD


def camp_dynamic_items() -> tuple:
    """Every restart-proof DynamicItem of the camp surfaces."""
    return (
        KingdomCampButton,
        KingdomCampFoundButton,
        KingdomCampJoinButton,
        KingdomCampQueueButton,
        KingdomCampJoinSelect,
    )


__all__ = [
    "CAMP_WINDOW_KEY",
    "KingdomCampButton",
    "KingdomCampNameModal",
    "beta_armed",
    "build_camp_button",
    "camp_dynamic_items",
    "camp_strings",
    "season_door_open",
]
