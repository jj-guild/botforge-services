"""The golden Postuler panel + the adaptive enrollment window (postuler-hybride-v1).

The players' enrollment door (Drasah 18/11): one PUBLIC salon in the
Conscription group (``apply``, declared in ``mod.yaml``) carrying the
designer's golden panel — and the 3-tier model the panel fronts:

1. the PROJECT account (pseudo + linked AoE2 profile) is free,
   self-service, never admin-gated (generic, OAuth-ready #182);
2. entering the Kingdom SEASON is the admin gate (the platform's
   enrollment engine, the validation dashboard decides);
3. joining/founding a kingdom comes LATER, in the kingdom flow — the
   camp choice no longer lives here.

The panel is the fixed poster (Discord panels are static); the single
button opens the ADAPTIVE ephemeral window — the intelligence lives at
click time, on the platform seams, and every branch reuses the
platform's engine (SeasonApplyButton, the withdraw confirm, the
profile panel router): the mod owns the shape, the core owns the
mechanics. The player NEVER leaves the ephemeral flow — the hidden
machine-room categories (Kingdom, Game/AoE2) stay admin-only.

camp-beta-v1 (Drasah 19/11): the 3rd tier shows PROVISIONALLY on BETA
seasons only — the ⚔️ camp door button rides the pinned panel (see
camp_beta.py); a normal season shows nothing provisional.
"""

from __future__ import annotations

import logging
from typing import Any

import discord

from .common import mod_catalog, open_unique_ephemeral, surface, wiring

logger = logging.getLogger("kingdom.apply")

APPLY_VIEW_KEY = "panel:mod:kingdom:apply"
REGISTER_VIEW_KEY = "panel:mod:kingdom:register"
APPLY_WINDOW_KEY = "panel:mod:kingdom:apply"

_NS = "kingdom:apply"

GOLD = discord.Colour(0xE6B800)

MOD = "kingdom"

# the platform's generic profile-panel route (views_routing): any
# button carrying this id opens the OFFICIAL account surface in the
# same ephemeral flow — never a link to a hidden category, never a
# re-implemented registration.
PROFILE_ROUTE = "view:open:panel:profile"


async def _guild_locale(guild_id: str) -> str:
    """The guild's effective locale (stored choice first, fr fallback)."""
    from .panel import _guild_locale as _panel_locale

    return await _panel_locale(guild_id)


async def _strings_async(guild_id: str) -> dict[str, str]:
    """The apply strings in the guild's locale."""
    return mod_catalog().section("kingdom.apply", await _guild_locale(guild_id))


async def _kingdoms_in_play() -> int | None:
    """Count the APPROVED player kingdoms (the panel's counter)."""
    stack = wiring()
    if stack is None:
        return None
    try:
        from botforge.mods.kingdom.models import KingdomValidation

        kingdoms = await stack.kingdoms.kingdoms()
        return sum(
            1 for kingdom in kingdoms if not kingdom.is_gaia and kingdom.validation is KingdomValidation.APPROVED
        )
    except Exception:
        logger.warning("kingdom: the apply counter read failed", exc_info=True)
        return None


async def build_apply_panel(guild_id: str) -> discord.ui.LayoutView:
    """Build the pinned golden Postuler panel (guild-locale strings)."""
    strings = await _strings_async(guild_id)
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = []
    artwork = str(strings.get("artwork", "") or "")
    if artwork:
        # the designer's illustration, HEAD of the poster (data-driven:
        # the URL lives in the locales, swapping art is a data change)
        blocks.append(discord.ui.MediaGallery(discord.MediaGalleryItem(artwork)))
    blocks.extend(
        [
            discord.ui.TextDisplay(f"# {strings['panel_title']}"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(str(strings["tagline"])),
        ]
    )
    count = await _kingdoms_in_play()
    if count:
        blocks.append(discord.ui.TextDisplay(strings["kingdoms_line"].format(count=count, s="s" if count > 1 else "")))
    else:
        blocks.append(discord.ui.TextDisplay(str(strings["kingdoms_none"])))
    join_row: Any = discord.ui.ActionRow()
    join_row.add_item(KingdomApplyOpenButton(str(strings["join_button"])).item)
    blocks.append(discord.ui.Separator())
    blocks.append(join_row)
    # camp-beta-v1 (Drasah 19/11) + camp-door-any-season (Drasah 20/11):
    # the PROVISIONAL Roi/Seigneur door shows whenever a season is LIVE —
    # classical or beta. It is the only founding path until the
    # official flow (account > dossier > throne/vasselage) lands.
    from .camp_beta import build_camp_button, camp_strings, season_door_open

    if await season_door_open():
        camp_row: Any = discord.ui.ActionRow()
        camp_row.add_item(build_camp_button(camp_strings(await _guild_locale(guild_id))).item)
        blocks.append(camp_row)
    return surface(
        APPLY_VIEW_KEY,
        discord.ui.Container(*blocks, accent_colour=GOLD),
    )


async def build_register_panel(guild_id: str) -> discord.ui.LayoutView:
    """Build the pinned « s'enregistrer » panel (the parcours' first door).

    salon-parcours-v2 (Drasah 18/11): the enrollment door is TWO salons
    — the public « register » salon carries THIS poster (one CTA: create
    the project account via the platform's official profile route), the
    gated « apply » salon carries the Postuler panel (visible once the
    player's account exists — the access role is granted by the
    registration event, see registration_gate).
    """
    strings = await _strings_async(guild_id)
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = []
    artwork = str(strings.get("artwork", "") or "")
    if artwork:
        blocks.append(discord.ui.MediaGallery(discord.MediaGalleryItem(artwork)))
    blocks.extend(
        [
            discord.ui.TextDisplay(f"# {strings['register_title']}"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(str(strings["register_text"])),
            discord.ui.Separator(),
            discord.ui.TextDisplay(str(strings["register_hint"])),
        ]
    )
    row: Any = discord.ui.ActionRow()
    row.add_item(
        discord.ui.Button(
            style=discord.ButtonStyle.success,
            label=str(strings.get("account_button", "🪙 Créer mon compte"))[:80],
            custom_id=PROFILE_ROUTE,
        )
    )
    blocks.append(row)
    return surface(
        REGISTER_VIEW_KEY,
        discord.ui.Container(*blocks, accent_colour=GOLD),
    )


def _window(strings: dict[str, str], *rows: Any, title: str = "") -> discord.ui.LayoutView:
    """Build the adaptive window's layout (the declared surface id)."""
    return surface(
        APPLY_WINDOW_KEY,
        discord.ui.Container(
            discord.ui.TextDisplay(f"# {title or strings['w_title']}"),
            *rows,
            accent_colour=GOLD,
        ),
    )


def _apply_button_row() -> Any:
    """The platform's own apply button, riding in the mod's window."""
    from botforge.discord.season_panels import SeasonApplyButton

    row: Any = discord.ui.ActionRow()
    row.add_item(SeasonApplyButton(MOD).item)
    return row


def _withdraw_button_row(user_id: str) -> Any:
    """The platform's own withdraw confirm button (the engine's, verbatim)."""
    from botforge.discord.season_panels import SeasonWithdrawConfirmButton

    row: Any = discord.ui.ActionRow()
    row.add_item(SeasonWithdrawConfirmButton(MOD, user_id).item)
    return row


def _state_button_row(strings: dict[str, str], *, account_ready: bool, postuler_ready: bool) -> Any:
    """The window's call-to-actions, painted BY STATE (Drasah 18/11).

    salon-parcours-v2 rule: an IMPOSSIBLE action is NOT clickable — a red
    button is DISABLED (never a dead click, never a waiting timeout). «
    Créer mon compte » is green+enabled when the account is MISSING, red
    +disabled when it exists; « Postuler » green+enabled only when the
    season takes applications, red+disabled otherwise. The withdraw
    stays its own possible action (the already branch's row).
    """
    row: Any = discord.ui.ActionRow()
    row.add_item(
        discord.ui.Button(
            style=discord.ButtonStyle.success if not account_ready else discord.ButtonStyle.danger,
            disabled=account_ready,
            label=str(strings.get("account_button", "🪙 Créer mon compte"))[:80],
            custom_id=PROFILE_ROUTE,
        )
    )
    label = str(strings.get("postuler_button", "📜 Postuler"))
    row.add_item(KingdomPostulerButton(MOD, label, active=postuler_ready, disabled=not postuler_ready).item)
    return row


class KingdomPostulerButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:postuler:(?P<mod>[a-z0-9_-]+)",
):
    """The Postuler shape (green when ready) — the MECHANIC is the platform's.

    postuler-dead-click-v1 (Drasah 20/11, live regression): the template
    lacked the ``:(?P<mod>...)`` tail while the built custom_id carries
    ``:{mod}`` — discord.py dispatches on ``pattern.fullmatch``, so the
    wire button rendered fine but NO click ever reached the callback
    (« le bouton ne répond pas »). The template now mirrors the built id.
    The callback delegates verbatim to the platform's SeasonApplyButton
    (self-guarding: no account, already-in, unwired — every case is the
    engine's own answer): zero local enrollment logic, the button only
    carries the look.
    """

    def __init__(self, mod: str, label: str, active: bool, disabled: bool = False) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:postuler:{mod}"[:100],
                label=label[:80],
                style=discord.ButtonStyle.success if active else discord.ButtonStyle.danger,
                disabled=disabled,
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
    ) -> KingdomPostulerButton:
        """Rebuild at click time — the state re-reads live anyway."""
        del interaction
        from .common import locale_of  # noqa: F401 — the label keeps the wire's

        button = item if isinstance(item, discord.ui.Button) else None
        label = (button.label if button is not None else None) or "📜 Postuler"
        match_dict = match.groupdict() if hasattr(match, "groupdict") else {}
        return cls(str(match_dict.get("mod", MOD)), label, active=False)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Delegate the WHOLE click, degrading gracefully (never a dead click).

        The engine (SeasonApplyButton) owns the flow; the mod rehearses
        nothing. But its platform reads (the applications, the linked
        profiles, the identity seams) can stall or fail: the click then
        ends in an EXPLICIT note — never Discord's « le bot ne répond
        pas » (the salon-parcours-v2 rule: no dead clicks).
        """
        from botforge.discord.season_panels import SeasonApplyButton

        from .common import locale_of

        try:
            await SeasonApplyButton(self.mod).callback(interaction)
        except Exception:
            logger.warning("kingdom: the Postuler delegation failed", exc_info=True)
            strings = mod_catalog().section("kingdom.apply", locale_of(interaction))
            note = str(strings.get("w_postuler_failed", "❌ L'inscription n'a pas abouti — réessaie dans un instant."))
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(note, ephemeral=True)
                else:
                    await interaction.response.send_message(note, ephemeral=True)
            except Exception:
                logger.info("kingdom: the Postuler failure note was lost", exc_info=True)


def decide_apply_branch(
    *,
    account_ok: bool,
    enrollment_wired: bool,
    already: bool,
    season_id: str,
    phase: str,
) -> str:
    """The adaptive window's pure branch decision (one answer, always).

    The 3-tier model as data: the free account first, the admin-gated
    season second, the kingdom later (never here). The branch names are
    the window's contract — the callback maps them, the tests pin them.
    """
    if not account_ok:
        # tier 1: the free project account comes first
        return "no_account"
    if not enrollment_wired:
        # unwired: the platform button reports it — never a dead end
        return "unwired"
    if already and phase != "ouverte":
        # the SAME click offers the withdraw (never a silent drop)
        return "already"
    if not season_id:
        return "no_season"
    if phase != "inscriptions":
        return "closed"
    return "ready"


def render_apply_branch(
    branch: str,
    strings: dict[str, str],
    *,
    user_id: str = "",
    season_name: str = "—",
    phase: str = "",
    phase_label: str = "",
) -> discord.ui.LayoutView:
    """Render the branch's window (pure — the tests pin every branch).

    ONE window, ONE parcours: the call-to-actions stay visible and the
    branch paints them (Drasah 18/11) — but an IMPOSSIBLE action is
    DISABLED, never clickable (the salon-parcours-v2 rule: no dead
    clicks, no waiting timeouts; the engines keep the possible ones).
    """
    account_ready = branch != "no_account"
    postuler_ready = branch == "ready"
    row = _state_button_row(strings, account_ready=account_ready, postuler_ready=postuler_ready)

    if branch == "no_account":
        # the WELCOME window: the parcours text + the two buttons
        return _window(
            strings,
            discord.ui.TextDisplay(str(strings["w_no_account"])),
            discord.ui.Separator(),
            row,
            title=strings["w_welcome_title"],
        )
    if branch == "unwired":
        # the platform's own button reports it (never a dead end)
        return _window(strings, row)
    if branch == "already":
        return _window(
            strings,
            discord.ui.TextDisplay(str(strings["w_already"])),
            row,
            _withdraw_button_row(user_id),
        )
    if branch == "no_season":
        return _window(
            strings,
            discord.ui.TextDisplay(str(strings["w_no_season"])),
            row,
        )
    if branch == "closed":
        return _window(
            strings,
            discord.ui.TextDisplay(
                str(strings["w_closed"]).format(season=season_name, phase=phase_label or phase)
            ),
            row,
        )
    # ready: the account exists, the season takes applications
    return _window(
        strings,
        discord.ui.TextDisplay(str(strings["w_account_ready"]).format(season=season_name)),
        row,
    )


class KingdomApplyOpenButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:open",
):
    """The panel's single call-to-action — the adaptive window's opener."""

    def __init__(self, label: str = "⚔️ Rejoins l'aventure") -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:open",
                label=label[:80],
                style=discord.ButtonStyle.primary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: Any,
        /,
    ) -> KingdomApplyOpenButton:
        """Rebuild the button at click time (locale-aware label)."""
        from .common import locale_of

        strings = mod_catalog().section("kingdom.apply", locale_of(interaction))
        return cls(str(strings.get("join_button", "⚔️ Rejoins l'aventure")))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open the ADAPTIVE window — the branches reuse the engine.

        The mod owns the shape (which window opens); the platform owns
        the mechanics — the final action is always the platform's own
        SeasonApplyButton (or its withdraw confirm, or the profile
        route), never a local re-implementation.
        """
        from .common import locale_of

        bot = interaction.client
        guild_id = str(interaction.guild_id or "")
        user_id = str(interaction.user.id)
        strings = mod_catalog().section("kingdom.apply", locale_of(interaction))

        # the platform's enrollment seams (private helpers — the graceful
        # degrade hands the whole click to the platform button, which
        # re-checks everything itself; never a silent dead click)
        try:
            from botforge.discord import season_panels as _sp
        except Exception:  # pragma: no cover — the platform always ships
            logger.warning("kingdom: the season panels seam is unreachable", exc_info=True)
            await open_unique_ephemeral(
                interaction,
                view=render_apply_branch("unwired", strings),
            )
            return

        core_name = await _sp._core_display_name(bot, user_id)
        profiles = await _sp._linked_profile_ids(bot, user_id, _sp._mod_game_key(bot, MOD))
        account_ok = bool(core_name and profiles)

        from botforge.core.services.season_stack import season_stack_for

        stack = season_stack_for(bot, MOD, guild_id)
        enrollment_wired = stack is not None and stack.enrollment is not None

        season_id = ""
        phase = "preparation"
        season_name = "—"
        already = False
        if enrollment_wired:
            config = await _sp._current_season_config(bot, MOD, guild_id)
            season_id = str(config.get("season_id", "") or "")
            phase = _sp._phase_of(config)
            season_name = str(config.get("name") or season_id or "—")
            existing = await _sp._find_application(stack, guild_id, user_id)
            already = existing is not None

        branch = decide_apply_branch(
            account_ok=account_ok,
            enrollment_wired=enrollment_wired,
            already=already,
            season_id=season_id,
            phase=phase,
        )
        await open_unique_ephemeral(
            interaction,
            view=render_apply_branch(
                branch,
                strings,
                user_id=user_id,
                season_name=season_name,
                phase=phase,
                phase_label=str(_sp._PHASE_LABELS.get(phase, phase)),
            ),
        )


__all__ = [
    "APPLY_VIEW_KEY",
    "KingdomApplyOpenButton",
    "build_apply_panel",
    "decide_apply_branch",
    "KingdomPostulerButton",
    "render_apply_branch",
]
