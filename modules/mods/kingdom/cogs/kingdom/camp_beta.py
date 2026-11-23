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


async def kingdom_is_beta(bot: Any, guild_id: str) -> bool:
    """ONE beta (Drasah 21/11) : le drapeau de phase OU le type de saison.

    The operator's door is Paramètres → « Démarrer la beta » (the
    phase flag, per guild); the launch modal's « beta » type arms the
    compressed weekend on the season. BOTH say the same thing — « on
    postule directement, sans compte » — so the parcours bends on
    EITHER. A None bot or an unreadable state degrades to the season
    type alone (a missing service never bends the rules).
    """
    if await season_is_beta():
        return True
    state_service = getattr(bot, "state_service", None)
    if state_service is None or not str(guild_id).strip().isdigit():
        return False
    from botforge.core.services.beta import is_beta
    from botforge.core.services.mod_storage import ModStateCache

    return bool(await is_beta(ModStateCache(state_service, "kingdom"), str(guild_id), "kingdom"))


async def mod_is_beta(guild_id: str) -> bool:
    """``kingdom_is_beta`` on the registered bot (the panels' entry)."""
    from .panel import current_bot

    return await kingdom_is_beta(current_bot(), guild_id)


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
    """Build the camp window: the state lines, the two doors (or nothing).

    console-etats-regie-v1 (Drasah 21/11) : DEUX mondes. Une saison
    VIT → les portes de la saison (fonder/rejoindre un ROYAUME moteur,
    le flux d'avant). HORS saison → la VIE PERSISTANTE des joueurs :
    « 👑 Prendre le Trône » (fonder son royaume persistant, dormant —
    « ils peuvent le créer sans même jouer ») et « Joindre un royaume »
    (le picker des royaumes persistants). Les interrupteurs de la
    régie ferment chaque porte une par une (défaut : ouvert).
    """
    strings = _strings(interaction)
    stack = wiring()
    rows: list[Any] = [discord.ui.TextDisplay(str(strings["window_help"]))]
    if stack is None:
        rows.append(discord.ui.TextDisplay(str(strings["none_note"])))
        return _window(strings, *rows)
    from .regie import regie_open

    guild_id = str(interaction.guild_id or "")
    creation_open = await regie_open(interaction.client, guild_id, "realm_creation_open")
    join_open = await regie_open(interaction.client, guild_id, "realm_join_open")
    live = await season_door_open()
    if not live:
        # hors saison : les joueurs vivent — les portes persistantes
        rows.append(discord.ui.TextDisplay(str(strings["window_help_off_season"])))
    lord = await _current_lord(stack, str(interaction.user.id))
    lines = await _state_lines(strings, stack, lord)
    if lines and live:
        rows.append(discord.ui.Separator())
        rows.extend(discord.ui.TextDisplay(line) for line in lines)
        return _window(strings, *rows)
    rows.append(discord.ui.Separator())
    door_row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    if live:
        # les portes de la saison — le flux moteur d'avant
        if creation_open:
            door_row.add_item(
                KingdomCampFoundButton(strings["found_button"], discord.ButtonStyle.success).item
            )
        if join_open:
            door_row.add_item(
                KingdomCampJoinButton(strings["join_button"], discord.ButtonStyle.primary).item
            )
    else:
        # la vie persistante (royaume-persistant T2) — fondre reprend
        # le MÊME modal (le royaume persistant naît dormant, sans moteur)
        if creation_open:
            door_row.add_item(
                KingdomCampFoundButton(strings["throne_button"], discord.ButtonStyle.success).item
            )
        if join_open:
            door_row.add_item(
                KingdomCampJoinButton(strings["realms_join_button"], discord.ButtonStyle.primary).item
            )
    if not door_row.children:
        rows.append(discord.ui.TextDisplay(str(strings["regie_closed_line"])))
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
        """Open the joining window (picker + queue fallback).

        Hors saison (console-etats-regie-v1) : le ROYAUME persistant
        remplace le royaume moteur — le picker des royaumes vivants.
        """
        if not await season_door_open():
            await open_unique_ephemeral(
                interaction, view=await _realms_join_window(interaction)
            )
            return
        await open_unique_ephemeral(interaction, view=await _join_window(interaction))


async def _realms_join_window(interaction: discord.Interaction) -> discord.ui.LayoutView:
    """« Joindre un royaume » HORS saison — the persistent realms' picker."""
    strings = _strings(interaction)
    stack = wiring()
    rows: list[Any] = [
        discord.ui.TextDisplay(f"## {strings['realms_join_title']}"),
        discord.ui.TextDisplay(str(strings["realms_join_help"])),
        discord.ui.Separator(),
    ]
    if stack is None or getattr(stack, "realms", None) is None:
        rows.append(discord.ui.TextDisplay(str(strings["none_note"])))
        return _window(strings, *rows)
    try:
        realms = list(await stack.realms.realms())
    except Exception:  # noqa: BLE001 — the window reports, never raises
        logger.warning("kingdom: the realms picker read failed", exc_info=True)
        realms = []
    my_id = str(interaction.user.id)
    # reset-joueurs-v1 (Drasah 22/11) : le FONDATEUR voit son royaume
    # ARCHIVÉ en premier — c'est le sien, il peut le réveiller d'un clic ;
    # les archivés des AUTRES rois restent invisibles (chacun réveille
    # sa maison, pas celle du voisin).
    mine_archived = [
        realm
        for realm in realms
        if getattr(realm, "archived_at", 0)
        and str(getattr(realm, "king_id", "")) == my_id
    ]
    # a player belongs to ONE realm: the picker skips his own home
    options = [
        realm
        for realm in realms
        if not getattr(realm, "archived_at", 0)
        and str(getattr(realm, "king_id", "")) != my_id
        and my_id not in [str(m) for m in (getattr(realm, "member_ids", []) or [])]
    ]
    if options or mine_archived:
        picker = KingdomCampRealmSelect(
            str(
                strings["realms_pick_restore_placeholder"]
                if mine_archived and not options
                else strings["realms_pick_placeholder"]
            )
        )
        archived_options = [
            discord.SelectOption(
                label=str(strings["realms_pick_archived_label"]).format(
                    name=str(getattr(realm, "name", "?"))[:80]
                )[:100],
                value=str(getattr(realm, "slug", ""))[:100],
                description=str(strings["realms_pick_archived_hint"])[:100],
                emoji="📦",
            )
            for realm in mine_archived[:25]
        ]
        joinable_options = [
            discord.SelectOption(
                label=str(getattr(realm, "name", "?"))[:100],
                value=str(getattr(realm, "slug", ""))[:100],
                description=str(strings["realms_pick_seats"]).format(
                    members=len(getattr(realm, "member_ids", []) or []) + 1
                )[:100],
            )
            for realm in options[: 25 - len(archived_options)]
        ]
        picker.item.options = archived_options + joinable_options
        picker_row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        picker_row.add_item(picker.item)
        rows.append(picker_row)
    else:
        rows.append(discord.ui.TextDisplay(str(strings["realms_join_empty"])))
    return _window(strings, *rows)


class KingdomCampRealmSelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]], template=rf"{_NS}:realm-pick$"
):
    """The persistent realm picker (hors saison) — one realm, one click."""

    def __init__(self, placeholder: str) -> None:
        super().__init__(discord.ui.Select(
            placeholder=placeholder[:100],
            custom_id=f"{_NS}:realm-pick",
            min_values=1,
            max_values=1,
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(_strings(interaction)["realms_pick_placeholder"])

    async def callback(self, interaction: discord.Interaction) -> None:
        from .settings_panel import _safe_followup

        strings = _strings(interaction)
        guild_id = str(interaction.guild_id or "")
        await interaction.response.defer(ephemeral=True)
        stack = wiring()
        from .regie import regie_open

        if not await regie_open(interaction.client, guild_id, "realm_join_open"):
            await interaction.followup.send(str(strings["regie_closed_line"]), ephemeral=True)
            return
        if stack is None or getattr(stack, "realms", None) is None:
            await interaction.followup.send(str(strings["none_note"]), ephemeral=True)
            return
        values = [str(v) for v in (self.item.values or [])]
        slug = values[0] if values else ""
        realm = await stack.realms.realm_of_slug(slug)
        if realm is None:
            await interaction.followup.send(str(strings["realms_join_error"]), ephemeral=True)
            return
        # un pick ARCHIVÉ ne se rejoint pas : seul le Roi fondateur peut
        # le réveiller, et seulement depuis sa propre confirmation.
        if getattr(realm, "archived_at", 0):
            if str(getattr(realm, "king_id", "")) != str(interaction.user.id):
                await interaction.followup.send(
                    str(strings["realms_restore_not_yours"]), ephemeral=True
                )
                return
            await open_unique_ephemeral(
                interaction, view=_realm_restore_card(interaction, realm, guild_id)
            )
            return
        try:
            realm = await stack.realms.join_realm(str(realm.id), str(interaction.user.id))
            # le membre voit son royaume tout de suite (best-effort :
            # la passe de guérison rattrape un rate-limit perdu)
            guild = getattr(interaction, "guild", None)
            if guild is not None:
                from .realms import ensure_realm_structure

                await ensure_realm_structure(guild, realm, dormant=True)
            note = str(strings["realms_join_done"]).format(str(realm.name))
        except Exception as exc:  # noqa: BLE001 — the window reports, never raises
            logger.warning("kingdom: realm join failed", exc_info=True)
            note = str(strings["realms_join_error"])
        await _safe_followup(interaction, note)


def _realm_restore_card(
    interaction: discord.Interaction, realm: Any, guild_id: str
) -> discord.ui.LayoutView:
    """The founder's confirmation card — one archived home, one wake-up call."""
    strings = _strings(interaction)
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.TextDisplay(
            f"## {strings['realms_restore_confirm_title']}\n"
            + str(strings["realms_restore_confirm_hint"]).format(
                name=str(getattr(realm, "name", "?"))
            )
        ),
        accent_colour=discord.Colour(0xFEE75C),
    )
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row.add_item(
        KingdomCampRestoreButton(
            "-yes", str(getattr(realm, "slug", ""))[:60], guild_id,
            str(strings["realms_restore_yes"])[:80], discord.ButtonStyle.success,
        ).item
    )
    row.add_item(
        KingdomCampRestoreButton(
            "-no", str(getattr(realm, "slug", ""))[:60], guild_id,
            str(strings["realms_restore_no"])[:80], discord.ButtonStyle.secondary,
        ).item
    )
    container.add_item(row)
    return surface("panel:mod:kingdom:note", container)


class KingdomCampRestoreButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:camp:restore(?P<kind>-yes|-no):(?P<slug>[a-z0-9-]+):(?P<guild_id>\d+)",
):
    """♻️ The founder's wake-up call — restart-proof DM-independent restore."""

    def __init__(
        self, kind: str, slug: str, guild_id: str,
        label: str, style: discord.ButtonStyle,
    ) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"kingdom:camp:restore{kind}:{slug}:{guild_id}"[:100],
                style=style,
            )
        )
        self.kind = kind
        self.slug = slug
        self.guild_id = guild_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        button = item if isinstance(item, discord.ui.Button) else None
        label = (button.label or "?") if button is not None else "?"
        kind = match["kind"] or "-yes"
        style = (
            discord.ButtonStyle.success if kind == "-yes"
            else discord.ButtonStyle.secondary
        )
        return cls(kind, match["slug"], match["guild_id"], label, style)

    async def callback(self, interaction: discord.Interaction) -> None:
        from .settings_panel import _safe_followup

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        strings = _strings(interaction)
        if self.kind == "-no":
            await _safe_followup(interaction, str(strings["settings_cancelled"]))
            return
        stack = wiring()
        if stack is None or getattr(stack, "realms", None) is None:
            await _safe_followup(interaction, str(strings["realms_restore_failed"]))
            return
        # re-vérification À CHAUD : la coquille a pu être réveillée
        # (ou détruite) entre le pick et le clic — on ne restaure jamais
        # deux fois, et le fondateur ne peut réveiller que sa maison.
        realm = await stack.realms.realm_of_slug(self.slug)
        if (
            realm is None
            or not getattr(realm, "archived_at", 0)
            or str(getattr(realm, "king_id", "")) != str(interaction.user.id)
        ):
            await _safe_followup(interaction, str(strings["realms_restore_gone"]))
            return
        try:
            realm = await stack.realms.restore_realm(str(realm.id))
            guild = interaction.client.get_guild(int(self.guild_id))
            if guild is not None:
                # import-restore-fix (Merlin's logs 23/11): ``save_habitat``
                # is a SERVICE method, never a cog symbol — the old
                # ``from .realms import … save_habitat`` ImportError'd and
                # the restore button failed EVERY time. The seam already
                # used 200 lines below: stack.realms.save_habitat.
                from .realms import ensure_realm_structure

                await ensure_realm_structure(guild, realm, dormant=True)
                await stack.realms.save_habitat(str(realm.id), {})
            note = str(strings["realms_restore_done"]).format(str(realm.name))
        except Exception:  # noqa: BLE001 — the card reports, never raises
            logger.warning("kingdom: realm restore failed", exc_info=True)
            note = str(strings["realms_restore_failed"])
        await _safe_followup(interaction, note)


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
        # la régie relit la porte AU CLIC (un interrupteur basculé depuis
        # le rendu ne laisse jamais passer une fondation en retard)
        from .regie import regie_open

        if not await regie_open(
            interaction.client, str(interaction.guild_id or ""), "realm_creation_open"
        ):
            await interaction.followup.send(str(strings["regie_closed_line"]), ephemeral=True)
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
        KingdomCampRealmSelect,
        KingdomCampRestoreButton,
    )


__all__ = [
    "CAMP_WINDOW_KEY",
    "KingdomCampButton",
    "KingdomCampNameModal",
    "beta_armed",
    "build_camp_button",
    "camp_dynamic_items",
    "camp_strings",
    "kingdom_is_beta",
    "mod_is_beta",
    "season_door_open",
    "season_is_beta",
]
