"""The persistent realm's DISCORD habitat (royaume-persistant-v1).

Drasah 20/11 — « créer un royaume n'engage pas » : founding provisions
the realm's category in DORMANT mode (only 🏰 Le royaume shows), and
the chez-soi window (the 🏰 Entrée button) reads the realm: Ma
seigneurie (fondation line + crown transfer inside), 📝 Présentation
(the Roi writes), 📺 Voir la saison (recap + s'inscrire — an admin
accepts the entry), 🏆 Palmarès, 🚪 Quitter.

Architecture: the SHELL lives in the service (src/kingdom/realms.py),
the habitat rides the platform seams — dynamic channels (#408) for
provisioning, ONE declared surface per window (#381), single-pass
overwrites (the 2026-10-10 rate-limit incident), adoption by slug
(never a duplicate salon).
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord

from .common import (
    fmt_paris,
    locale_of,
    open_unique_ephemeral,
    strings_for,
    surface,
    wiring,
)

logger = logging.getLogger("kingdom.realms")

_NS = "kingdom:realm"

# The realm's salons — the designer's capture (20/11) fait foi.
REALM_SALONS: tuple[tuple[str, str], ...] = (
    ("discussions", "🔒 Discussions"),
    ("hub", "🏰 Le royaume"),
    ("territory", "🌍 Territoire"),
    ("alliances", "🏆 Alliances"),
)
# The salon keys MASKED while the realm is dormant (hors saison) —
# masked, never destroyed (royaume-persistant-v1).
DORMANT_HIDDEN_KEYS = ("discussions", "territory", "alliances")

REALM_ADMIN_ROLE = "Kingdom Admin"  # conf/mod.yaml display_name

HUB_SURFACE = "panel:mod:kingdom:realm"
HOME_SURFACE = "panel:mod:kingdom:realm:home"
SEIGNEURIE_SURFACE = "panel:mod:kingdom:realm:home:seigneurie"
PRESENTATION_SURFACE = "panel:mod:kingdom:realm:presentation"
SEASON_SURFACE = "panel:mod:kingdom:realm:season"
PALMARES_SURFACE = "panel:mod:kingdom:realm:palmares"

_GOLD = discord.Colour(0xE6B800)
_DORMANT_GREY = discord.Colour(0x99AAB5)


def _slug(name: str) -> str:
    """Flatten a name to its adoption anchor (decoration-blind)."""
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")


def realm_strings(interaction: discord.Interaction) -> dict[str, str]:
    """The realm strings for one interaction (the mod's catalog)."""
    from .realm_strings import realm_strings as catalog

    return catalog(locale_of(interaction))


def category_name(realm_name: str) -> str:
    """The realm category's display name (« 🏰 Nom »)."""
    return f"🏰 {realm_name}"


def _realm_service(stack: Any) -> Any:
    return getattr(stack, "realms", None) if stack is not None else None


# ---------------------------------------------------------------------------
# The habitat: category + salons, single-pass overwrites, adoption by slug
# ---------------------------------------------------------------------------


def _member_ids(realm: Any) -> list[int]:
    """The realm's humans (Roi first) as Discord ids, ids as int."""
    raw = [str(realm.king_id), *list(getattr(realm, "member_ids", []) or [])]
    out: list[int] = []
    for item in raw:
        try:
            value = int(item)
        except (TypeError, ValueError):
            continue
        if value not in out:
            out.append(value)
    return out


def _realm_overwrites(guild: Any, member_ids: list[int]) -> dict[Any, discord.PermissionOverwrite]:
    """The realm category's overwrite set — ONE pass, no API crawl.

    The 2026-10-10 live incident: separate set_permissions PATCHes left
    a category with no salons while the bot crawled the rate limits.
    Everything is applied in a single edit call, bot + admin included
    (the everyone-deny otherwise locks the bot out: 403 / 50001), and
    members get view + history both (the 2026-10-12 finding).
    """
    overwrites: dict[Any, discord.PermissionOverwrite] = {}
    everyone = getattr(guild, "default_role", None)
    if everyone is not None:
        overwrites[everyone] = discord.PermissionOverwrite(view_channel=False)
    bot_member = getattr(guild, "me", getattr(guild, "self", None))
    if bot_member is not None:
        overwrites[bot_member] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            manage_messages=True,
            embed_links=True,
            attach_files=True,
        )
    for role in getattr(guild, "roles", []) or []:
        if getattr(role, "name", "") == REALM_ADMIN_ROLE:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, manage_channels=True, read_message_history=True
            )
            break
    for member_id in member_ids:
        overwrites[member_id] = discord.PermissionOverwrite(
            view_channel=True, read_message_history=True
        )
    return overwrites


async def _resolve_member(guild: Any, member_id: int) -> Any | None:
    member = getattr(guild, "get_member", lambda _id: None)(member_id)
    if member is None:
        fetch = getattr(guild, "fetch_member", None)
        if fetch is not None:
            try:
                member = await fetch(member_id)
            except Exception:  # noqa: BLE001 — unresolvable, never a raise
                member = None
    return member


async def realm_overwrites(guild: Any, member_ids: list[int]) -> dict[Any, discord.PermissionOverwrite]:
    """_realm_overwrites, with REAL member objects resolved.

    The overwrite keys must be Discord objects (Member/Role), never raw
    ids — an unresolved member is logged loudly (the 2026-10-18 silent
    King incident) and skipped, never a blocker.
    """
    raw = _realm_overwrites(guild, member_ids)
    resolved: dict[Any, discord.PermissionOverwrite] = {}
    for key, overwrite in raw.items():
        if isinstance(key, int):
            member = await _resolve_member(guild, key)
            if member is None:
                logger.warning(
                    "kingdom realms: member %s skipped (unresolvable in guild %s)",
                    key,
                    getattr(guild, "id", "?"),
                )
                continue
            resolved[member] = overwrite
        else:
            resolved[key] = overwrite
    return resolved


async def _apply_category_overwrites(guild: Any, category: Any, member_ids: list[int]) -> None:
    overwrites = await realm_overwrites(guild, member_ids)
    edit = getattr(category, "edit", None)
    applied = False
    if edit is not None:
        try:
            await edit(overwrites=overwrites)
            applied = True
        except TypeError:
            applied = False
    if not applied:
        set_permissions = getattr(category, "set_permissions", None)
        if set_permissions is not None:
            for target, overwrite in overwrites.items():
                await set_permissions(target, overwrite=overwrite)


def _find_realm_category(guild: Any, realm_name: str) -> Any | None:
    wanted = _slug(category_name(realm_name))
    for category in getattr(guild, "categories", []) or []:
        if _slug(getattr(category, "name", "")) == wanted:
            return category
    return None


async def _adopt_realm_salon(guild: Any, category: Any, name: str) -> Any | None:
    """Find the salon by slug (adoption never duplicates), rename to charte."""
    existing = next(
        (c for c in getattr(category, "channels", []) or [] if _slug(getattr(c, "name", "")) == _slug(name)),
        None,
    )
    if existing is not None and str(getattr(existing, "name", "")) != name:
        try:
            await existing.edit(name=name)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom realms: charte rename failed (%s)", name, exc_info=True)
    return existing


async def _apply_dormancy(guild: Any, channel: Any, key: str, member_ids: list[int], dormant: bool) -> None:
    """Mask (or unmask) one salon while the realm is dormant.

    Dormant: every realm member is DENIED on the non-hub salons —
    masked, never destroyed. The hub stays the realm's front door.
    Awake (t2a — the admin accepted the season entry): the member
    denials are CLEARED (overwrite=None → the member inherits the
    category's allow), the halls reopen without any crawl.
    """
    if key not in DORMANT_HIDDEN_KEYS:
        return
    for member_id in member_ids:
        member = await _resolve_member(guild, member_id)
        if member is None:
            continue
        try:
            if dormant:
                await channel.set_permissions(member, view_channel=False, read_message_history=False)
            else:
                await channel.set_permissions(member, overwrite=None)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom realms: dormancy edit failed (%s)", getattr(channel, "id", "?"))


async def ensure_realm_structure(guild: Any, realm: Any, *, dormant: bool = True) -> dict[str, Any]:
    """Provision (idempotently) the realm's category + salons.

    Returns the habitat's Discord ids by key (stored on the shell).
    Adopts existing salons by slug, single-pass category overwrites,
    then applies dormancy. Best-effort per step; the shell ids win.
    """
    member_ids = _member_ids(realm)
    display = category_name(str(realm.name))
    category = _find_realm_category(guild, str(realm.name))
    created = False
    if category is None:
        create = getattr(guild, "create_category", None)
        overwrites = await realm_overwrites(guild, member_ids)
        if create is not None:
            try:
                category = await create(display, overwrites=overwrites)
                created = True
            except TypeError:
                category = await create(display)
        if category is None:
            logger.warning("kingdom realms: category creation failed (%s)", display)
            return {}
    if not created:
        try:
            if str(getattr(category, "name", "")) != display:
                await category.edit(name=display)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom realms: category rename failed", exc_info=True)
        await _apply_category_overwrites(guild, category, member_ids)

    ids: dict[str, Any] = {"category": str(getattr(category, "id", "") or "")}
    for key, name in REALM_SALONS:
        channel = await _adopt_realm_salon(guild, category, name)
        if channel is None:
            create_channel = getattr(guild, "create_text_channel", None)
            if create_channel is None:
                continue
            try:
                channel = await create_channel(name, category=category)
            except Exception:  # noqa: BLE001
                logger.warning("kingdom realms: salon creation failed (%s)", name, exc_info=True)
                continue
        ids[key] = str(getattr(channel, "id", "") or "")
        await _apply_dormancy(guild, channel, key, member_ids, dormant)
    return ids


# ---------------------------------------------------------------------------
# The hub salon's panel — the designer's capture (illustration +Entrée)
# ---------------------------------------------------------------------------


def _hub_marker() -> str:
    return f"[{HUB_SURFACE}]"


def hub_layout(realm: Any, strings: dict[str, str], *, dormant: bool) -> discord.ui.LayoutView:
    """The 🏰 Le royaume panel — one template, two states (dormant/vivant)."""
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = []
    artwork = str(strings.get("realm_artwork", "") or "")
    if artwork:
        blocks.append(discord.ui.MediaGallery(discord.MediaGalleryItem(artwork)))
    blocks.extend(
        [
            discord.ui.TextDisplay(f"# {strings['realm_hub_title'].format(realm.name)}"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(str(strings["realm_hub_flavor"])),
        ]
    )
    if dormant:
        blocks.append(discord.ui.TextDisplay(str(strings["realm_hub_dormant_note"])))
    row: Any = discord.ui.ActionRow()
    row.add_item(
        RealmHomeButton(
            str(strings["realm_enter_button"]),
            discord.ButtonStyle.secondary if dormant else discord.ButtonStyle.primary,
            str(realm.slug),
        ).item
    )
    blocks.append(discord.ui.Separator())
    blocks.append(row)
    # the permanent hors-jeu zone — both states (the designer's capture)
    blocks.append(discord.ui.Separator())
    blocks.append(discord.ui.TextDisplay(str(strings["realm_hors_jeu_zone"])))
    settings_row: Any = discord.ui.ActionRow()
    settings_row.add_item(
        discord.ui.Button(
            label=str(strings["realm_user_settings_button"])[:80],
            style=discord.ButtonStyle.secondary,
            custom_id=f"{_NS}:user-settings:{getattr(realm, 'slug', '')}"[:100],
            disabled=True,  # informatif — the hors-jeu user settings seam lands later
        )
    )
    blocks.append(settings_row)
    return surface(
        HUB_SURFACE,
        discord.ui.Container(*blocks, accent_colour=_DORMANT_GREY if dormant else _GOLD),
    )


async def deploy_realm_hub(guild: Any, realm: Any, locale: str = "fr") -> bool:
    """Post/refresh the hub panel in 🏰 Le royaume (idempotent by marker)."""
    category = _find_realm_category(guild, str(realm.name))
    channel = next(
        (c for c in (getattr(category, "channels", []) or []) if _slug(getattr(c, "name", "")) == _slug("🏰 Le royaume")),
        None,
    )
    if category is None or channel is None:
        logger.warning("kingdom realms: hub salon not found for %s", getattr(realm, "name", "?"))
        return False
    from .realm_strings import realm_strings as catalog

    strings = catalog(locale)
    dormant = getattr(realm, "engagement", None) is None  # t2a — the season link decides
    marker = _hub_marker()
    history = getattr(channel, "history", None)
    existing = None
    if history is not None:
        try:
            async for message in channel.history(limit=25):
                if marker in str(getattr(message, "content", "")):
                    existing = message
                    break
        except Exception:  # noqa: BLE001
            existing = None
    layout = hub_layout(realm, strings, dormant=dormant)
    try:
        if existing is not None:
            await existing.edit(content=marker, view=layout)
        else:
            await channel.send(content=marker, view=layout)
        return True
    except Exception:  # noqa: BLE001
        logger.warning("kingdom realms: hub deploy failed", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# The chez-soi window and its sub-windows (one declared surface each)
# ---------------------------------------------------------------------------


async def _realm_of(interaction: discord.Interaction, slug: str) -> Any | None:
    stack = wiring()
    service = _realm_service(stack)
    if service is None:
        return None
    return await service.realm_of_slug(slug)


async def home_layout(interaction: discord.Interaction, realm: Any, strings: dict[str, str]) -> discord.ui.LayoutView:
    """The chez-soi window — the realm seen from home."""
    members_line = strings["home_members_line"].format(
        count=1 + len(getattr(realm, "member_ids", []) or [])
    )
    blocks = [
        discord.ui.TextDisplay(f"# {strings['home_title'].format(realm.name)}"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(
            strings["home_intro"].format(
                king=str(getattr(realm, "king_name", "")),
                count=members_line,
            )
        ),
    ]
    for line in _home_lines(realm, strings):
        blocks.append(discord.ui.TextDisplay(line))
    row: Any = discord.ui.ActionRow()
    for label, view_key in (
        (strings["seigneurie_button"], "seigneurie"),
        (strings["presentation_button"], "presentation"),
        (strings["season_button"], "season"),
        (strings["palmares_button"], "palmares"),
    ):
        row.add_item(RealmNavButton(label, view_key, str(realm.slug)).item)
    blocks.append(discord.ui.Separator())
    blocks.append(row)
    quit_row: Any = discord.ui.ActionRow()
    king = str(realm.king_id) == str(interaction.user.id)
    quit_row.add_item(
        RealmQuitButton(strings["quit_button"], str(realm.slug), disabled=king).item
    )
    blocks.append(quit_row)
    return surface(
        HOME_SURFACE, discord.ui.Container(*blocks, accent_colour=_GOLD)
    )


def _home_lines(realm: Any, strings: dict[str, str]) -> list[str]:
    lines: list[str] = []
    presentation = str(getattr(realm, "presentation", "") or "")
    if presentation:
        excerpt = presentation[:180] + ("…" if len(presentation) > 180 else "")
        lines.append(strings["home_presentation_excerpt"].format(excerpt))
    request = getattr(realm, "join_request", None)
    if request:
        lines.append(strings["home_join_pending"])
    return lines


def seigneurie_layout(realm: Any, strings: dict[str, str], *, king: bool) -> discord.ui.LayoutView:
    """Ma seigneurie — the members list is BUILT by the caller (async):
    ``seigneurie_window`` resolves the names, this function renders.
    """
    blocks = [
        discord.ui.TextDisplay(f"# {strings['seigneurie_title'].format(realm.name)}"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(
            strings["seigneurie_foundation"].format(
                when=fmt_paris(int(getattr(realm, "founded_at", 0) or 0)),
                king=str(getattr(realm, "king_name", "")),
            )
        ),
        discord.ui.Separator(),
    ]
    member_lines = [f"👑 **{realm.king_name}**"]
    for line in getattr(realm, "_member_lines", []) or []:
        member_lines.append(line)
    blocks.append(discord.ui.TextDisplay("\n".join(member_lines)))
    if king and (getattr(realm, "member_ids", None)):
        blocks.append(discord.ui.Separator())
        blocks.append(discord.ui.TextDisplay(strings["seigneurie_crown_hint"]))
        crown_row: Any = discord.ui.ActionRow()
        select = RealmCrownSelect(
            strings["seigneurie_crown_placeholder"], str(realm.slug)
        )
        for member_id in getattr(realm, "member_ids", []) or []:
            select.add_option(
                discord.SelectOption(
                    label=getattr(realm, "_member_names", {}).get(str(member_id), str(member_id))[:100],
                    value=str(member_id)[:100],
                )
            )
        crown_row.add_item(select.item)
        blocks.append(crown_row)
    return surface(SEIGNEURIE_SURFACE, discord.ui.Container(*blocks, accent_colour=_GOLD))


async def seigneurie_window(interaction: discord.Interaction, realm: Any, strings: dict[str, str]) -> discord.ui.LayoutView:
    """Resolve the member display names, then render Ma seigneurie."""
    realm._member_lines = []
    realm._member_names = {}
    stack = wiring()
    names: dict[str, str] = {}
    if stack is not None:
        try:
            for lord in await stack.kingdoms.lords():
                names[str(getattr(lord, "player_id", ""))] = str(
                    getattr(lord, "display_name", "") or getattr(lord, "player_id", "")
                )
        except Exception:  # noqa: BLE001 — names are a courtesy, never a blocker
            names = {}
    guild = getattr(interaction, "guild", None)
    for member_id in getattr(realm, "member_ids", []) or []:
        display = names.get(str(member_id), f"<@{member_id}>")
        realm._member_names[str(member_id)] = display
        realm._member_lines.append(f"• {display}")
    return seigneurie_layout(realm, strings, king=str(interaction.user.id) == str(realm.king_id))


def presentation_layout(realm: Any, strings: dict[str, str], *, king: bool) -> discord.ui.LayoutView:
    """📝 Présentation — the Roi writes, everyone reads."""
    text = str(getattr(realm, "presentation", "") or "") or strings["presentation_empty"]
    blocks = [
        discord.ui.TextDisplay(f"# {strings['presentation_title'].format(realm.name)}"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(text),
    ]
    if king:
        blocks.append(discord.ui.Separator())
        blocks.append(discord.ui.TextDisplay(strings["presentation_king_hint"]))
        row: Any = discord.ui.ActionRow()
        row.add_item(
            RealmPresentationEditButton(strings["presentation_edit_button"], str(realm.slug)).item
        )
        blocks.append(row)
    return surface(PRESENTATION_SURFACE, discord.ui.Container(*blocks, accent_colour=_GOLD))


async def season_layout(realm: Any, strings: dict[str, str], *, king: bool) -> discord.ui.LayoutView:
    """📺 Voir la saison — the recap + the (Roi-only) entry request."""
    blocks = [discord.ui.TextDisplay(f"# {strings['season_title']}"), discord.ui.Separator()]
    stack = wiring()
    season = None
    phase = "none"
    if stack is not None:
        try:
            season = await stack.kingdoms.current_season()
            phase = str(getattr(season, "phase", "running")) if season else "none"
        except Exception:  # noqa: BLE001
            phase = "error"
    if season is None:
        blocks.append(discord.ui.TextDisplay(strings["season_none"]))
    else:
        blocks.append(
            discord.ui.TextDisplay(
                strings["season_running"].format(
                    when=fmt_paris(int(getattr(season, "started_at", 0) or 0))
                )
            )
        )
    request = getattr(realm, "join_request", None)
    engagement = getattr(realm, "engagement", None)
    if engagement:
        blocks.append(discord.ui.Separator())
        kingdom_name = str(engagement.get("kingdom_name", "") or realm.name)
        blocks.append(
            discord.ui.TextDisplay(
                strings["season_engaged_line"].format(
                    kingdom=kingdom_name,
                    season=str(engagement.get("season_id", "?")),
                )
            )
        )
    elif request:
        blocks.append(discord.ui.Separator())
        blocks.append(discord.ui.TextDisplay(strings["season_join_pending"]))
    elif season is not None and king:
        blocks.append(discord.ui.Separator())
        blocks.append(discord.ui.TextDisplay(strings["season_join_hint"]))
        row: Any = discord.ui.ActionRow()
        row.add_item(RealmJoinButton(strings["season_join_button"], str(realm.slug)).item)
        blocks.append(row)
    return surface(SEASON_SURFACE, discord.ui.Container(*blocks, accent_colour=_GOLD))


def palmares_layout(realm: Any, strings: dict[str, str]) -> discord.ui.LayoutView:
    """🏆 Palmarès — the realm's past seasons."""
    history = list(getattr(realm, "season_history", []) or [])
    blocks = [
        discord.ui.TextDisplay(f"# {strings['palmares_title'].format(realm.name)}"),
        discord.ui.Separator(),
    ]
    if not history:
        blocks.append(discord.ui.TextDisplay(strings["palmares_empty"]))
    else:
        lines = []
        for entry in history:
            lines.append(
                strings["palmares_line"].format(
                    season=str(entry.get("season", "?")),
                    note=str(entry.get("note", "")),
                )
            )
        blocks.append(discord.ui.TextDisplay("\n".join(lines)))
    return surface(PALMARES_SURFACE, discord.ui.Container(*blocks, accent_colour=_GOLD))


# ---------------------------------------------------------------------------
# The dynamic items (restart-proof, slug-keyed)
# ---------------------------------------------------------------------------


class RealmHomeButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:home:(?P<slug>[a-z0-9-]+)$"
):
    """« 🏰 Entrée » — the chez-soi window's door (both states)."""

    def __init__(self, label: str, style: discord.ButtonStyle, slug: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id=f"{_NS}:home:{slug}"[:100], style=style
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        strings = strings_for(interaction)
        return cls(strings["realm_enter_button"], discord.ButtonStyle.primary, match["slug"])

    async def callback(self, interaction: discord.Interaction) -> None:
        slug = str(getattr(self, "custom_id", "")).rsplit(":", 1)[-1]
        realm = await _realm_of(interaction, slug)
        strings = realm_strings(interaction)
        if realm is None:
            await open_unique_ephemeral(interaction, content=strings["realm_gone_note"])
            return
        if str(interaction.user.id) != str(realm.king_id) and str(interaction.user.id) not in [
            str(m) for m in (getattr(realm, "member_ids", []) or [])
        ]:
            await open_unique_ephemeral(interaction, content=strings["home_not_member"])
            return
        await open_unique_ephemeral(interaction, view=await home_layout(interaction, realm, strings))


class RealmNavButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:nav:(?P<view>seigneurie|presentation|season|palmares):(?P<slug>[a-z0-9-]+)$",
):
    """ONE nav button for the four sub-windows (the template rule)."""

    def __init__(self, label: str, view_key: str, slug: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:nav:{view_key}:{slug}"[:100],
                style=discord.ButtonStyle.secondary,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        strings = strings_for(interaction)
        label = {
            "seigneurie": strings["seigneurie_button"],
            "presentation": strings["presentation_button"],
            "season": strings["season_button"],
            "palmares": strings["palmares_button"],
        }[match["view"]]
        return cls(label, match["view"], match["slug"])

    async def callback(self, interaction: discord.Interaction) -> None:
        parts = str(getattr(self, "custom_id", "")).split(":")
        view_key, slug = parts[-2], parts[-1]
        realm = await _realm_of(interaction, slug)
        strings = realm_strings(interaction)
        if realm is None:
            await open_unique_ephemeral(interaction, content=strings["realm_gone_note"])
            return
        king = str(interaction.user.id) == str(realm.king_id)
        if view_key == "seigneurie":
            view = await seigneurie_window(interaction, realm, strings)
        elif view_key == "presentation":
            view = presentation_layout(realm, strings, king=king)
        elif view_key == "season":
            view = await season_layout(realm, strings, king=king)
        else:
            view = palmares_layout(realm, strings)
        await open_unique_ephemeral(interaction, view=view)


class RealmPresentationEditButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:presentation-edit:(?P<slug>[a-z0-9-]+)$"
):
    """« ✏️ Modifier » — the Roi edits the realm's presentation (modal)."""

    def __init__(self, label: str, slug: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:presentation-edit:{slug}"[:100],
                style=discord.ButtonStyle.primary,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(strings_for(interaction)["presentation_edit_button"], match["slug"])

    async def callback(self, interaction: discord.Interaction) -> None:
        slug = str(getattr(self, "custom_id", "")).rsplit(":", 1)[-1]
        await interaction.response.send_modal(RealmPresentationModal(slug, realm_strings(interaction)))


class RealmPresentationModal(discord.ui.Modal):
    """The Roi's presentation editor (Roi ONLY, guarded in on_submit)."""

    text_input = discord.ui.TextInput(
        label="Présentation",
        style=discord.TextStyle.paragraph,
        min_length=0,
        max_length=2000,
        required=False,
    )

    def __init__(self, slug: str, strings: dict[str, str]) -> None:
        super().__init__(title=str(strings["presentation_modal_title"])[:45])
        self.slug = slug
        self.strings = strings

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        stack = wiring()
        service = _realm_service(stack)
        realm = await _realm_of(interaction, self.slug) if service else None
        if realm is None:
            await interaction.followup.send(self.strings["realm_gone_note"], ephemeral=True)
            return
        try:
            realm = await service.set_presentation(
                str(realm.id), str(interaction.user.id), str(self.text_input.value or "")
            )
        except Exception as exc:  # noqa: BLE001 — reports, never raises
            logger.warning("kingdom realms: presentation refused", exc_info=True)
            await interaction.followup.send(self.strings["presentation_error"], ephemeral=True)
            return
        await interaction.followup.send(
            self.strings["presentation_saved"], ephemeral=True
        )


class RealmJoinButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:join:(?P<slug>[a-z0-9-]+)$"
):
    """« S'inscrire à la saison » — the Roi manifests the realm's entry wish."""

    def __init__(self, label: str, slug: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:join:{slug}"[:100],
                style=discord.ButtonStyle.success,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(strings_for(interaction)["season_join_button"], match["slug"])

    async def callback(self, interaction: discord.Interaction) -> None:
        strings = realm_strings(interaction)
        slug = str(getattr(self, "custom_id", "")).rsplit(":", 1)[-1]
        await interaction.response.defer(ephemeral=True)
        stack = wiring()
        service = _realm_service(stack)
        realm = await _realm_of(interaction, slug) if service else None
        if realm is None or stack is None:
            await interaction.followup.send(strings["realm_gone_note"], ephemeral=True)
            return
        season = None
        try:
            season = await stack.kingdoms.current_season()
        except Exception:  # noqa: BLE001
            season = None
        if season is None:
            await interaction.followup.send(strings["season_none"], ephemeral=True)
            return
        try:
            await service.request_season_entry(
                str(realm.id), str(interaction.user.id), str(getattr(season, "id", ""))
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("kingdom realms: join request refused (%s)", exc)
            await interaction.followup.send(strings["season_join_error"], ephemeral=True)
            return
        await interaction.followup.send(strings["season_join_requested"], ephemeral=True)


class RealmQuitButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:quit:(?P<slug>[a-z0-9-]+)$"
):
    """« 🚪 Quitter le royaume » — a non-Roi member leaves (between seasons)."""

    def __init__(self, label: str, slug: str, *, disabled: bool = False) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:quit:{slug}"[:100],
                style=discord.ButtonStyle.danger,
                disabled=disabled,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(strings_for(interaction)["quit_button"], match["slug"])

    async def callback(self, interaction: discord.Interaction) -> None:
        strings = realm_strings(interaction)
        slug = str(getattr(self, "custom_id", "")).rsplit(":", 1)[-1]
        await interaction.response.defer(ephemeral=True)
        stack = wiring()
        service = _realm_service(stack)
        realm = await _realm_of(interaction, slug) if service else None
        if realm is None:
            await interaction.followup.send(strings["realm_gone_note"], ephemeral=True)
            return
        try:
            await service.leave_realm(str(realm.id), str(interaction.user.id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("kingdom realms: leave refused (%s)", exc)
            await interaction.followup.send(strings["quit_error"], ephemeral=True)
            return
        await interaction.followup.send(strings["quit_done"], ephemeral=True)


class RealmCrownSelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]], template=rf"{_NS}:crown:(?P<slug>[a-z0-9-]+)$"
):
    """The crown transfer's member picker — the Roi picks the next Roi."""

    def __init__(self, placeholder: str, slug: str) -> None:
        super().__init__(discord.ui.Select(placeholder=placeholder[:100], custom_id=f"{_NS}:crown:{slug}"[:100]))
        self.slug = slug

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(strings_for(interaction)["seigneurie_crown_placeholder"], match["slug"])

    async def callback(self, interaction: discord.Interaction) -> None:
        strings = realm_strings(interaction)
        await interaction.response.defer(ephemeral=True)
        stack = wiring()
        service = _realm_service(stack)
        realm = await _realm_of(interaction, self.slug) if service else None
        if realm is None:
            await interaction.followup.send(strings["realm_gone_note"], ephemeral=True)
            return
        values = list(getattr(self, "values", []) or [])
        if not values:
            return
        target = str(values[0])
        try:
            await service.transfer_crown(str(realm.id), str(interaction.user.id), target)
        except Exception as exc:  # noqa: BLE001
            logger.warning("kingdom realms: crown transfer refused (%s)", exc)
            await interaction.followup.send(strings["crown_error"], ephemeral=True)
            return
        await interaction.followup.send(strings["crown_done"], ephemeral=True)


def realm_dynamic_items() -> tuple:
    """Every restart-proof DynamicItem of the realm surfaces."""
    return (
        RealmHomeButton,
        RealmNavButton,
        RealmPresentationEditButton,
        RealmJoinButton,
        RealmQuitButton,
        RealmCrownSelect,
    )
