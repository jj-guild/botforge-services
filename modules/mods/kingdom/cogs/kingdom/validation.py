"""The kingdom-validation dashboard (#339, the detailed candidates view).

The generic admin lists the count; the mod's validation flow needs the
FULL view — this is it, pinned in the declared ``realms`` salon
(``mod.yaml``'s « 👑 royaumes — Kingdom validation panel », admin
only): one row per PENDING kingdom with its King and the ✅ Valider /
❌ Refuser buttons, then the accepted and refused tables (the
dashboard shape — #380's candidates-table form rendered as the pin's
own blocks, the decision rides D70 rule 35).

The template rule (#396): the whole surface is the declared
``panel:mod:kingdom:candidates`` id + its data — a pinned layout, not a
hand-rolled render; the decisions are restart-proof DynamicItems with
stable custom ids, guarded at click time (the runtime check is the
security boundary, the salon's visibility is only convenience).
"""

from __future__ import annotations

import logging
from typing import Any

import discord

from .common import (
    _bot_admins,
    fmt_paris,
    mod_catalog,
    open_unique_ephemeral,
    strings_by_locale,
    surface,
    wiring,
)

logger = logging.getLogger("kingdom.validation")

VALIDATION_VIEW_KEY = "panel:mod:kingdom:candidates"

_NS = "kingdom:valid"


async def _guild_locale(guild_id: str) -> str:
    """The guild's effective locale (stored choice first, fr fallback)."""
    from .panel import _guild_locale as _panel_locale

    return await _panel_locale(guild_id)

def _realms_service(stack: Any) -> Any:
    """The REALM service of the same stack (None when absent)."""
    return getattr(stack, "realms", None) if stack is not None else None


async def _realms_with_join_request(stack: Any) -> list[Any]:
    """The realms whose Roi asked for the season entry (t2a)."""
    service = _realms_service(stack)
    if service is None:
        return []
    try:
        realms = await service.realms()
    except Exception:
        logger.warning("kingdom: realm join requests read failed", exc_info=True)
        return []
    return [
        realm
        for realm in realms
        if getattr(realm, "join_request", None) and not getattr(realm, "archived_at", 0)
    ]


async def build_validation_panel(guild_id: str) -> discord.ui.LayoutView:
    """Build the pinned validation dashboard's layout (guild-locale strings)."""
    from botforge.mods.kingdom.models import KingdomValidation

    strings = mod_catalog().section("kingdom.validation", await _guild_locale(guild_id))
    stack = wiring()
    pending: list[Any] = []
    accepted: list[Any] = []
    refused: list[Any] = []
    if stack is not None:
        try:
            kingdoms = await stack.kingdoms.kingdoms()
        except Exception:
            logger.warning("kingdom: validation dashboard read failed", exc_info=True)
            kingdoms = []
        for kingdom in kingdoms:
            if kingdom.is_gaia:
                continue
            if kingdom.validation is KingdomValidation.PENDING:
                pending.append(kingdom)
            elif kingdom.validation is KingdomValidation.APPROVED:
                accepted.append(kingdom)
            else:
                refused.append(kingdom)
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['title']}"),
        discord.ui.TextDisplay(str(strings["help"])),
        discord.ui.Separator(),
    ]
    if pending:
        blocks.append(discord.ui.TextDisplay(f"## {strings['pending_header']}"))
        for kingdom in pending:
            king_name = await _king_display_name(stack, kingdom)
            blocks.append(
                discord.ui.TextDisplay(
                    str(strings["row"]).format(name=kingdom.name, king=king_name)
                )
            )
            row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
            row.add_item(
                ValidationDecisionButton(
                    kingdom.id,
                    "ok",
                    str(strings["accept_button"])[:80],
                    discord.ButtonStyle.success,
                )
            )
            row.add_item(
                ValidationDecisionButton(
                    kingdom.id,
                    "no",
                    str(strings["refuse_button"])[:80],
                    discord.ButtonStyle.danger,
                )
            )
            blocks.append(row)
    else:
        blocks.append(discord.ui.TextDisplay(str(strings["empty"])))
    # t2a — the SEASON ENTRY requests of the PERSISTENT realms: the
    # Roi's « S'inscrire » lands here, the admin decides (cards, the
    # presentation in sight — the accepted mockup's ⏳ section).
    entry_requests = await _realms_with_join_request(stack)
    if entry_requests:
        blocks.append(discord.ui.Separator())
        blocks.append(
            discord.ui.TextDisplay(f"## {strings['realm_requests_header']} ({len(entry_requests)})")
        )
        for realm in entry_requests:
            requested = int((getattr(realm, "join_request", {}) or {}).get("requested_at", 0) or 0)
            blocks.append(
                discord.ui.TextDisplay(
                    str(strings["realm_request_row"]).format(
                        name=getattr(realm, "name", "?"),
                        king=getattr(realm, "king_name", "?"),
                        when=fmt_paris(requested),
                    )
                )
            )
            excerpt = str(getattr(realm, "presentation", "") or "").strip()
            if excerpt:
                blocks.append(
                    discord.ui.TextDisplay(
                        str(strings["realm_request_presentation"]).format(
                            excerpt=excerpt[:280] + ("…" if len(excerpt) > 280 else "")
                        )
                    )
                )
            entry_row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
            entry_row.add_item(
                ValidationRealmEntryButton(
                    str(realm.slug),
                    "ok",
                    str(strings["realm_accept_button"])[:80],
                    discord.ButtonStyle.success,
                )
            )
            entry_row.add_item(
                ValidationRealmEntryButton(
                    str(realm.slug),
                    "no",
                    str(strings["realm_refuse_button"])[:80],
                    discord.ButtonStyle.danger,
                )
            )
            blocks.append(entry_row)
    blocks.append(discord.ui.Separator())
    if accepted:
        blocks.append(
            discord.ui.TextDisplay(f"## {strings['accepted_header']} ({len(accepted)})")
        )
        for kingdom in accepted:
            king_name = await _king_display_name(stack, kingdom)
            blocks.append(
                discord.ui.TextDisplay(
                    str(strings["row"]).format(name=kingdom.name, king=king_name)
                )
            )
            row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
            row.add_item(
                ValidationDeleteButton(
                    kingdom.id,
                    str(strings["delete_button"])[:80],
                    discord.ButtonStyle.danger,
                )
            )
            row.add_item(
                ValidationCrownButton(
                    kingdom.id,
                    str(strings["crown_button"])[:80],
                    discord.ButtonStyle.secondary,
                )
            )
            blocks.append(row)
    else:
        blocks.append(
            discord.ui.TextDisplay(f"## {strings['accepted_header']} (0)")
        )
        blocks.append(discord.ui.TextDisplay(str(strings["accepted_empty"])))
    blocks.append(
        discord.ui.TextDisplay(
            _table(strings["refused_header"], strings["table_kingdom"], refused)
        )
    )
    container = discord.ui.Container(*blocks, accent_colour=discord.Colour(0xA72D2D))
    return surface(VALIDATION_VIEW_KEY, container)


def _table(header: str, kingdom_column: str, kingdoms: list[Any]) -> str:
    """One markdown table — the dashboard shape, clamped to the budget."""
    lines = [f"## {header}", f"| {kingdom_column} |", "|---|"]
    for kingdom in kingdoms[:50]:
        lines.append(f"| {str(kingdom.name)[:80]} |")
    if not kingdoms:
        lines.append("| — |")
    body = "\n".join(lines)
    return body if len(body) <= 4000 else body[:3999] + "…"


async def _king_display_name(stack: Any, kingdom: Any) -> str:
    """The kingdom's King's display name (— when unresolvable).

    validation-cards-v1: the king is the lord holding the KING role; the
    old fallback (any active lord) stays for legacy documents.
    """
    from .common import lord_name

    if stack is None:
        return "—"
    king: Any = None
    fallback: Any = None
    for lord in await _lords_safe(stack):
        if lord.kingdom_id != kingdom.id or lord.left:
            continue
        if _is_king(lord):
            king = lord
            break
        fallback = fallback or lord
    return (str(await lord_name(stack.kingdoms, king.id)) or "—") if king is not None else (
        (str(await lord_name(stack.kingdoms, fallback.id)) or "—") if fallback is not None else "—"
    )


def _is_king(lord: Any) -> bool:
    """True when the lord document holds the KING role (name or value)."""
    role = getattr(lord, "role", None)
    return str(getattr(role, "name", role or "")).upper().find("KING") >= 0


async def _active_members(stack: Any, kingdom_id: str) -> list[Any]:
    """The kingdom's active lords, King first (the crown designation menu)."""
    if stack is None:
        return []
    members: list[Any] = []
    for lord in await _lords_safe(stack):
        if lord.kingdom_id == kingdom_id and not lord.left:
            members.append(lord)
    members.sort(key=lambda lord: 0 if _is_king(lord) else 1)
    return members


async def _refresh_pins(bot: Any, guild_id: str) -> None:
    """Re-render the validation pins in place (best-effort, never raises)."""
    from botforge.discord.static_pins import ensure_static_pin, registered_static_pins

    for spec in registered_static_pins():
        if spec.key in (VALIDATION_VIEW_KEY, "panel:mod:kingdom:validation"):
            await ensure_static_pin(bot, spec, guild_id)


async def _lords_safe(stack: Any) -> list[Any]:
    """The season's lords (empty on any read failure — the pin never dies)."""
    try:
        return list(await stack.kingdoms.lords())
    except Exception:
        logger.warning("kingdom: validation lords read failed", exc_info=True)
        return []


class ValidationDecisionButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:(?P<kingdom_id>[a-zA-Z0-9_-]+):(?P<choice>ok|no)",
):
    """One validation decision: ✅ approve or ❌ refuse a pending kingdom."""

    def __init__(self, kingdom_id: str, choice: str, label: str, style: int) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:{kingdom_id}:{choice}"[:100],
                label=label,
                style=style,  # type: ignore[arg-type]
            )
        )
        self.kingdom_id = kingdom_id
        self.choice = choice

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: Any,
        /,
    ) -> ValidationDecisionButton:
        """Rebuild the button from its custom id at click time."""
        button = item if isinstance(item, discord.ui.Button) else None
        label = (button.label or "?") if button is not None else "?"
        style = button.style if button is not None else discord.ButtonStyle.secondary
        return cls(match["kingdom_id"], match["choice"], label, style)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Apply the decision, then re-render the dashboard in place."""
        from botforge.discord.guards import require_admin

        locale = await _guild_locale(str(interaction.guild_id or ""))
        strings = mod_catalog().section("kingdom.validation", locale)
        shared = strings_by_locale(locale)
        admins = _bot_admins(interaction)
        roles = getattr(interaction.client, "roles_service", None)
        if not await require_admin(
            interaction,
            admins,
            roles,
            denied_message=str(strings["denied"]),
        ):
            return
        # windows-v2 fast-ack (Drasah 21/11 « Inscrire n'a pas marché »):
        # the approve/refuse work spans seconds of Discord API calls —
        # the 3-second clock belongs to the ACK, the work takes its
        # time AFTER it. Same lesson as hub-entry-fast-ack.
        await interaction.response.defer(ephemeral=True)
        stack = wiring()
        if stack is None:
            await interaction.followup.send(str(shared["plan_no_service"]), ephemeral=True)
            return
        try:
            if self.choice == "ok":
                kingdom = await stack.kingdoms.approve_kingdom(self.kingdom_id)
                note = str(strings["approved_note"]).format(name=kingdom.name)
            else:
                kingdom = await stack.kingdoms.refuse_kingdom(self.kingdom_id)
                note = str(strings["refused_note"]).format(name=kingdom.name)
        except Exception as exc:  # noqa: BLE001 — the dashboard reports, never raises
            logger.warning("kingdom: validation decision failed (%s)", self.kingdom_id, exc_info=True)
            note = str(shared["console_error"]).format(str(exc)[:150])
        try:
            await interaction.followup.edit_message(
                interaction.message.id,
                view=await build_validation_panel(str(interaction.guild_id or "")),
            )
        except Exception:
            logger.warning("kingdom: validation dashboard refresh failed", exc_info=True)
        await open_unique_ephemeral_safe(interaction, note)


async def _guard(interaction: discord.Interaction, strings: dict[str, str]) -> bool:
    """The click-time admin guard (the pin's visibility is only convenience)."""
    from botforge.discord.guards import require_admin

    return await require_admin(
        interaction,
        _bot_admins(interaction),
        getattr(interaction.client, "roles_service", None),
        denied_message=str(strings["denied"]),
    )


async def _find_kingdom(stack: Any, kingdom_id: str) -> Any | None:
    """One kingdom by id through the service seam (None when gone)."""
    try:
        for kingdom in await stack.kingdoms.kingdoms():
            if str(kingdom.id) == str(kingdom_id):
                return kingdom
    except Exception:
        logger.warning("kingdom: validation kingdom read failed", exc_info=True)
    return None


class ValidationDeleteButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:del:(?P<kingdom_id>[a-zA-Z0-9_-]+)",
):
    """🗑️ Supprimer — open the drop-out confirm card of one validated kingdom."""

    def __init__(self, kingdom_id: str, label: str, style: int) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:del:{kingdom_id}"[:100],
                label=label,
                style=style,  # type: ignore[arg-type]
            )
        )
        self.kingdom_id = kingdom_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: Any,
        /,
    ) -> "ValidationDeleteButton":
        button = item if isinstance(item, discord.ui.Button) else None
        label = (button.label or "?") if button is not None else "?"
        style = button.style if button is not None else discord.ButtonStyle.danger
        return cls(match["kingdom_id"], label, style)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard, resolve, then open the one-click-drop confirm card."""
        # drawer-build-v1 (Check 137) : fast-ack — la lecture derrière
        # ne court jamais contre le chrono de 3 s de Discord (gards
        # et cartes parlent déjà followup — zéro 40060).
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        locale = await _guild_locale(str(interaction.guild_id or ""))
        strings = mod_catalog().section("kingdom.validation", locale)
        if not await _guard(interaction, strings):
            return
        stack = wiring()
        kingdom = await _find_kingdom(stack, self.kingdom_id) if stack is not None else None
        if kingdom is None:
            from .common import open_unique_ephemeral

            await open_unique_ephemeral(interaction, str(strings["gone_note"]))
            return
        from .common import open_unique_ephemeral

        await open_unique_ephemeral(
            interaction, view=_delete_confirm_card(strings, locale, kingdom)
        )


def _delete_confirm_card(
    strings: dict[str, str], locale: str, kingdom: Any
) -> discord.ui.LayoutView:
    """The red confirm card of a kingdom deletion (anti-clic-raté, settings' pattern)."""
    name = str(kingdom.name)[:80]
    yes: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["delete_confirm_button"])[:80],
        custom_id=f"kingdom:valid:del-yes:{kingdom.id}"[:100],
        style=discord.ButtonStyle.danger,
    )
    no: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["delete_cancel_button"])[:80],
        custom_id=f"kingdom:valid:del-no:{kingdom.id}"[:100],
        style=discord.ButtonStyle.secondary,
    )

    async def on_yes(target: discord.Interaction) -> None:
        if not target.response.is_done():
            await target.response.defer(ephemeral=True)
        shared = strings_by_locale(locale)
        note: str
        stack = wiring()
        if stack is None:
            await target.followup.send(str(shared["plan_no_service"]), ephemeral=True)
            return
        # ejection-archive-v1 (Drasah 22/11) — la règle d'or : un royaume
        # ENGAGÉ ne se supprime JAMAIS, il s'ÉJECTE. L'ordre compte :
        # (1) les territoires acquis partent dans le pot commun AVANT le
        # delete (équité stricte : tours complets aux royaumes joueurs,
        # le reste du tour incomplet à Gaïa), (2) le royaume moteur meurt
        # (le delete ne trouve plus rien à détruire), (3) la COQUILLE est
        # libérée et rendue DORMANTE (la maison Discord se MASQUE, elle
        # ne se démolit pas — l'archive et la suppression définitive font
        # ça, pas l'éjection). L'habitat ne bloque JAMAIS la sortie.
        counts: dict[str, int] = {}
        try:
            counts = (
                await stack.kingdoms.redistribute_territories(str(kingdom.id)) or {}
            )
        except Exception:  # noqa: BLE001 — l'éjection ne rate jamais pour la carte
            logger.warning(
                "kingdom: territory redistribution failed (%s)", kingdom.id, exc_info=True
            )
        try:
            deleted = await stack.kingdoms.delete_kingdom(str(kingdom.id))
            note = str(strings["deleted_note"]).format(name=deleted.name)
        except Exception as exc:  # noqa: BLE001 — the card reports, never raises
            logger.warning("kingdom: eject failed (%s)", kingdom.id, exc_info=True)
            note = str(shared["console_error"]).format(str(exc)[:150])
            deleted = None
        if deleted is not None:
            if counts.get("territories"):
                note += (
                    "\n"
                    + str(strings["ejected_realms_note"]).format(
                        territories=counts.get("territories", 0),
                        kingdoms=counts.get("kingdoms", 0),
                        per_kingdom=counts.get("per_kingdom", 0),
                        to_gaia=counts.get("to_gaia", 0),
                    )
                )
            # la coquille : engagement relâché, habitat DORMANT re-ensuré,
            # le SAS se purge tout seul
            try:
                from .realms import ensure_realm_structure
                from .realms import _realm_service as _service_of

                service = _service_of(stack)
                shell = None
                if service is not None:
                    for candidate in await service.realms():
                        engagement = getattr(candidate, "engagement", None) or {}
                        if str(engagement.get("kingdom_id", "")) == str(kingdom.id):
                            shell = await service.release_engagement(str(candidate.id))
                            break
                guild = getattr(target, "guild", None)
                if shell is not None and guild is not None:
                    ids = await ensure_realm_structure(guild, shell, dormant=True)
                    if ids:
                        await service.save_habitat(str(shell.id), ids)
            except Exception:  # noqa: BLE001 — l'habitat ne bloque jamais
                logger.warning(
                    "kingdom: eject habitat sleep failed (%s)", kingdom.id, exc_info=True
                )
        try:
            await _refresh_pins(target.client, str(target.guild_id or ""))
        except Exception:
            logger.warning("kingdom: validation pin refresh failed", exc_info=True)
        # purge-card-close-v1 (Check 139) : la note REMPLACE la carte —
        # l'unique fenêtre ferme la confirmation vivante.
        try:
            await open_unique_ephemeral(target, content=note)
        except Exception:  # noqa: S110 — a vanished window is fine
            pass

    async def on_no(target: discord.Interaction) -> None:
        if not target.response.is_done():
            await target.response.defer(ephemeral=True)

    yes.callback = on_yes
    no.callback = on_no
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.TextDisplay(
            f"**{str(strings['delete_confirm_title']).format(name=name)}**\n"
            f"{strings['delete_confirm_hint']}"
        ),
        accent_colour=discord.Colour(0xED4245),
    )
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row.add_item(yes)
    row.add_item(no)
    container.add_item(row)
    return surface("panel:mod:kingdom:validation:confirm", container)


class ValidationCrownButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:crown:(?P<kingdom_id>[a-zA-Z0-9_-]+)",
):
    """👑 Changer le roi — open the sovereign designation menu (D81)."""

    def __init__(self, kingdom_id: str, label: str, style: int) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:crown:{kingdom_id}"[:100],
                label=label,
                style=style,  # type: ignore[arg-type]
            )
        )
        self.kingdom_id = kingdom_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: Any,
        /,
    ) -> "ValidationCrownButton":
        button = item if isinstance(item, discord.ui.Button) else None
        label = (button.label or "?") if button is not None else "?"
        style = button.style if button is not None else discord.ButtonStyle.secondary
        return cls(match["kingdom_id"], label, style)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard, resolve, then open the designation window."""
        from .common import open_unique_ephemeral

        locale = await _guild_locale(str(interaction.guild_id or ""))
        strings = mod_catalog().section("kingdom.validation", locale)
        if not await _guard(interaction, strings):
            return
        stack = wiring()
        kingdom = await _find_kingdom(stack, self.kingdom_id) if stack is not None else None
        if kingdom is None:
            await open_unique_ephemeral(interaction, str(strings["gone_note"]))
            return
        members = await _active_members(stack, str(kingdom.id))
        if not members:
            await open_unique_ephemeral(interaction, str(strings["crown_no_lords"]))
            return
        view = await _crown_window(strings, locale, kingdom, members)
        await open_unique_ephemeral(interaction, view=view)


async def _crown_window(
    strings: dict[str, str], locale: str, kingdom: Any, members: list[Any]
) -> discord.ui.LayoutView:
    """The designation window: pick a member, the throne changes at once."""
    from .common import lord_name

    stack = wiring()
    options: list[discord.SelectOption] = []
    for lord in members[:25]:
        display = str(await lord_name(stack.kingdoms if stack else None, lord.id))[:100]
        description = str(strings["crown_king_option"]) if _is_king(lord) else None
        options.append(
            discord.SelectOption(
                label=display or str(lord.id)[:100],
                value=str(lord.id),
                default=_is_king(lord),
                description=description,
            )
        )
    select: discord.ui.Select[discord.ui.LayoutView] = discord.ui.Select(
        placeholder=str(strings["crown_select_placeholder"])[:100],
        options=options,
        custom_id=f"kingdom:valid:crown-pick:{kingdom.id}"[:100],
    )
    cancel: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["delete_cancel_button"])[:80],
        custom_id=f"kingdom:valid:crown-cancel:{kingdom.id}"[:100],
        style=discord.ButtonStyle.secondary,
    )

    async def on_pick(target: discord.Interaction) -> None:
        if not target.response.is_done():
            await target.response.defer(ephemeral=True)
        shared = strings_by_locale(locale)
        note: str
        stack = wiring()
        if stack is None:
            await target.followup.send(str(shared["plan_no_service"]), ephemeral=True)
            return
        lord_id = (select.values or [""])[0]
        try:
            realm, _former, new_king = await stack.kingdoms.reassign_king(
                str(kingdom.id), str(lord_id)
            )
            king_display = str(await lord_name(stack.kingdoms, new_king.id))
            note = str(strings["crown_note"]).format(king=king_display, name=realm.name)
        except Exception as exc:  # noqa: BLE001 — the window reports, never raises
            logger.warning("kingdom: crown change failed (%s)", kingdom.id, exc_info=True)
            note = str(shared["console_error"]).format(str(exc)[:150])
        try:
            await _refresh_pins(target.client, str(target.guild_id or ""))
        except Exception:
            logger.warning("kingdom: validation pin refresh failed", exc_info=True)
        # purge-card-close-v1 (Check 139) : la note REMPLACE la carte —
        # l'unique fenêtre ferme la confirmation vivante.
        try:
            await open_unique_ephemeral(target, content=note)
        except Exception:  # noqa: S110 — a vanished window is fine
            pass

    async def on_cancel(target: discord.Interaction) -> None:
        if not target.response.is_done():
            await target.response.defer(ephemeral=True)

    select.callback = on_pick
    cancel.callback = on_cancel
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.TextDisplay(
            f"**{str(strings['crown_title']).format(name=str(kingdom.name)[:80])}**\n"
            f"{strings['crown_hint']}"
        ),
        accent_colour=discord.Colour(0xF0B232),
    )
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row.add_item(select)
    container.add_item(row)
    buttons: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    buttons.add_item(cancel)
    container.add_item(buttons)
    return surface("panel:mod:kingdom:validation:crown", container)


class ValidationRealmEntryButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:realmjoin:(?P<slug>[a-z0-9-]+):(?P<choice>ok|no)",
):
    """The t2a season-entry decision of a PERSISTENT realm."""

    def __init__(self, slug: str, choice: str, label: str, style: int) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:realmjoin:{slug}:{choice}"[:100],
                label=label,
                style=style,  # type: ignore[arg-type]
            )
        )
        self.slug = slug
        self.choice = choice

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: Any,
        /,
    ) -> "ValidationRealmEntryButton":
        button = item if isinstance(item, discord.ui.Button) else None
        label = (button.label or "?") if button is not None else "?"
        style = button.style if button is not None else discord.ButtonStyle.secondary
        return cls(match["slug"], match["choice"], label, style)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Apply the admin's decision, then re-render the dashboard."""
        locale = await _guild_locale(str(interaction.guild_id or ""))
        strings = mod_catalog().section("kingdom.validation", locale)
        if not await _guard(interaction, strings):
            return
        # windows-v2 fast-ack — same lesson as the decision button:
        # accepting a realm enrolls members and deploys a hub (seconds
        # of API calls); the ACK goes first, the work after it.
        await interaction.response.defer(ephemeral=True)
        stack = wiring()
        service = _realms_service(stack)
        realm = await service.realm_of_slug(self.slug) if service is not None else None
        if realm is None or stack is None:
            await open_unique_ephemeral_safe(interaction, str(strings["gone_note"]))
            return
        if self.choice == "no":
            note = await _refuse_season_entry(service, realm, strings)
        else:
            note = await _accept_season_entry(interaction, stack, service, realm, strings, locale)
        try:
            await interaction.followup.edit_message(
                interaction.message.id,
                view=await build_validation_panel(str(interaction.guild_id or "")),
            )
        except Exception:
            logger.warning("kingdom: validation dashboard refresh failed", exc_info=True)
        await open_unique_ephemeral_safe(interaction, note)


async def open_unique_ephemeral_safe(interaction: discord.Interaction, content: str) -> None:
    """_safe_send twin: report without ever raising."""
    from .common import open_unique_ephemeral

    try:
        await open_unique_ephemeral(interaction, content)
    except Exception:  # noqa: BLE001
        logger.warning("kingdom: ephemeral note failed", exc_info=True)


async def _refuse_season_entry(service: Any, realm: Any, strings: dict[str, str]) -> str:
    """The admin refuses: the request drops, the realm stays dormant."""
    try:
        realm = await service.clear_join_request(str(realm.id))
        return str(strings["realm_refused_note"]).format(name=realm.name)
    except Exception as exc:  # noqa: BLE001 — the dashboard reports, never raises
        logger.warning("kingdom: season entry refused-flow failed (%s)", realm.id, exc_info=True)
        return str(strings["realm_entry_error"]).format(error=str(exc)[:150])


async def _accept_season_entry(
    interaction: discord.Interaction,
    stack: Any,
    service: Any,
    realm: Any,
    strings: dict[str, str],
    locale: str,
) -> str:
    """The admin accepts — the realm ENTERS the season (one gesture):

    1. the engine kingdom is created APPROVED via ``add_kingdom`` and
       its STARTER DRAFT is granted at once (the act of entry);
    2. the realm's Roi claims the throne (queue + claim seams);
    3. every other member is enrolled as a Lord of the kingdom;
    4. the shell is bound to the engine kingdom (``engage``), the
       join request is consumed and the habitat WAKES (the three
       masked salons reopen, the hub flips to its vivid state).
    """
    try:
        season = await stack.kingdoms.current_season()
    except Exception:
        season = None
    if season is None:
        return str(strings["realm_entry_no_season"])
    try:
        from botforge.mods.kingdom.models import LordRole

        kingdom = await stack.kingdoms.add_kingdom(str(realm.name))
        king_id = str(getattr(realm, "king_id", ""))
        try:
            await stack.kingdoms.enroll_king_awaiting_kingdom(
                king_id, str(getattr(realm, "king_name", "") or king_id)
            )
            await stack.kingdoms.claim_kingdom(king_id, str(kingdom.id))
        except Exception as exc:  # noqa: BLE001 — the Roi may already ride the season
            logger.warning("kingdom: realm Roi throne claim degraded (%s)", exc)
            raise
        for member_id in getattr(realm, "member_ids", []) or []:
            try:
                await stack.kingdoms.enroll(
                    str(member_id),
                    str(member_id),
                    LordRole.LORD,
                    kingdom_name=str(realm.name),
                )
            except Exception as exc:  # noqa: BLE001 — one member never blocks the entry
                logger.warning("kingdom: realm member enroll degraded (%s)", exc)
        # sas-acceptance-v1 (Drasah 21/11) : engage() renvoie la coquille
        # FRAÎCHE (engagement posé, join_request consommée) — la garder :
        # réveiller l'habitat avec l'objet périmé rendait un hub dormant.
        realm = await service.engage(
            str(realm.id), str(getattr(season, "id", "")), str(kingdom.id)
        )
        note = str(strings["realm_accepted_note"]).format(name=realm.name, kingdom=kingdom.name)
    except Exception as exc:  # noqa: BLE001 — the dashboard reports, never raises
        logger.warning("kingdom: season entry failed (%s)", getattr(realm, "id", "?"), exc_info=True)
        return str(strings["realm_entry_error"]).format(error=str(exc)[:150])
    # the habitat wakes — masked salons reopen, hub flips vivid (best-effort)
    guild = getattr(interaction, "guild", None)
    if guild is not None:
        try:
            from .realms import deploy_realm_hub, ensure_realm_structure

            ids = await ensure_realm_structure(guild, realm, dormant=False)
            # liaison-roless-saison-v1 (Drasah 24/11) : le royaume ENTRE en
            # saison — le Roi reçoit « Kingdom King », les membres « Kingdom
            # Lord » : les champs de bataille et Kingdom-Gaïa s'ouvrent dès
            # le ✅ (les salons attendent ces rôles, personne ne les posait).
            try:
                from .season_roles import sync_season_roles

                await sync_season_roles(interaction.client, guild)
            except Exception:
                logger.warning(
                    "kingdom: the season entry role sync failed (%s) — best-effort",
                    getattr(realm, "id", "?"),
                    exc_info=True,
                )
            hub_message = await deploy_realm_hub(guild, realm, locale=locale)
            if hub_message:
                ids["hub_message"] = hub_message
            # realm-content-v1 (Drasah 21/11) : MP au Roi + bienvenue RP
            # dans Discussions + états d'attente Territoire/Alliances —
            # la passation de la saison remplacera par les fiches réelles.
            try:
                from .realm_content import announce_acceptance

                ids.update(await announce_acceptance(guild, realm, kingdom, locale))
            except Exception:  # noqa: BLE001 — le contenu ne réveille jamais le geste
                logger.warning("kingdom: realm acceptance content failed", exc_info=True)
            if ids:
                realm = await service.save_habitat(str(realm.id), ids)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom: realm habitat wake failed", exc_info=True)
    return note


# ---------------------------------------------------------------------------
# eject-sas-v1 (Drasah 21/11) : « ce royaume n'entre pas »
#
# Le sas est un sas : une ACCEPTATION se corrige dans SA fenêtre (la
# préparation), pas après le départ. L'éjection DEFAIT le geste d'entrée
# (le royaume moteur part avec ses seigneurs et son draft, la coquille
# retourne dormant, l'habitat se rendort) et le Roi reçoit le MOTIF par
# MP — il redemandera l'inscription quand les prérequis sont réunis.
# ---------------------------------------------------------------------------


async def _season_in_setup(stack: Any) -> bool:
    """Whether the season still waits in ITS sas (phase setup)."""
    if stack is None:
        return False
    try:
        season = await stack.kingdoms.current_season()
    except Exception:  # noqa: BLE001 — an unreadable season is a closed sas
        logger.warning("kingdom: eject phase read failed", exc_info=True)
        return False
    return season is not None and str(getattr(season, "phase", "")) == "setup"


async def _eject_season_entry(
    target: discord.Interaction, realm: Any, reason: str, strings: dict[str, str], locale: str
) -> str:
    """Undo one season entry (the sas window only) — the note back.

    L'ordre compte : le royaume moteur part d'abord (ses seigneurs et
    son draft partent avec lui — le seam moteur ``delete_kingdom``),
    puis la coquille est libérée, l'habitat se rendort, et le motif
    part au Roi par MP (best-effort, jamais bloquant).
    """
    shared = strings_by_locale(locale)
    stack = wiring()
    service = _realms_service(stack)
    if stack is None or service is None:
        return str(shared["plan_no_service"])
    if not await _season_in_setup(stack):
        # la fenêtre éphémère peut survivre à un départ de saison — le
        # moteur garde la main (le sas, c'est un sas)
        return str(strings["eject_closed_note"])
    try:
        kingdom_id = str((getattr(realm, "engagement", {}) or {}).get("kingdom_id", ""))
        if kingdom_id:
            deleted = await stack.kingdoms.delete_kingdom(kingdom_id)
            logger.info("kingdom: realm eject deleted kingdom %s", getattr(deleted, "name", "?"))
        realm = await service.release_engagement(str(realm.id))
        guild = getattr(target, "guild", None)
        if guild is not None:
            try:
                from .realms import deploy_realm_hub, ensure_realm_structure

                ids = await ensure_realm_structure(guild, realm, dormant=True)
                hub_message = await deploy_realm_hub(guild, realm, locale=locale)
                if hub_message:
                    ids["hub_message"] = hub_message
                if ids:
                    await service.save_habitat(str(realm.id), ids)
                # realm-content-v1 : hygiène d'éjection — les messages
                # d'entrée partent avec le royaume (best-effort).
                try:
                    from .realm_content import wipe_realm_content

                    await wipe_realm_content(guild, realm)
                except Exception:  # noqa: BLE001
                    logger.warning("kingdom: realm eject wipe failed", exc_info=True)
            except Exception:  # noqa: BLE001 — l'habitat ne bloque jamais
                logger.warning("kingdom: realm habitat sleep failed (%s)", realm.id, exc_info=True)
        note = str(strings["eject_done"]).format(name=getattr(realm, "name", "?"))
    except Exception as exc:  # noqa: BLE001 — the report never breaks the flow
        logger.warning("kingdom: realm eject failed (%s)", realm.id, exc_info=True)
        return str(strings["realm_entry_error"]).format(error=str(exc)[:150])
    # the king learns WHY — DM best-effort (a closed DM degrades to the log)
    try:
        from .common import dm_user_safe

        await dm_user_safe(
            target.client,
            str(getattr(realm, "king_id", "")),
            str(strings["eject_dm"]).format(
                name=str(getattr(realm, "name", "?")), reason=reason or "—"
            ),
        )
    except Exception:  # noqa: BLE001 — dm_user_safe already swallows
        logger.warning("kingdom: eject DM failed", exc_info=True)
    try:
        await _refresh_pins(target.client, str(target.guild_id or ""))
    except Exception:  # noqa: BLE001 — the pin heals on its own refresh
        logger.warning("kingdom: validation pin refresh failed", exc_info=True)
    return note


class _EjectReasonModal(discord.ui.Modal):
    """« ✏️ Autre » — le motif libre, envoyé au Roi tel quel."""

    def __init__(self, realm: Any, strings: dict[str, str], locale: str) -> None:
        super().__init__(title=str(strings["eject_other_modal_title"])[:45])
        self._realm_id = str(getattr(realm, "id", ""))
        self._strings = strings
        self._locale = locale
        self.reason = discord.ui.TextInput(
            required=True,
            max_length=400,
            placeholder=str(strings["eject_other_reason_placeholder"]),
            custom_id="kingdom:valid:eject:reason",
        )
        self.add_item(
            discord.ui.Label(
                text=str(strings["eject_other_reason_label"])[:45],
                component=self.reason,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from .common import open_unique_ephemeral

        await interaction.response.defer(ephemeral=True)
        strings = self._strings
        stack = wiring()
        service = _realms_service(stack)
        realm = None
        try:
            if service is not None:
                for candidate in await service.realms():
                    if str(getattr(candidate, "id", "")) == self._realm_id:
                        realm = candidate
                        break
        except Exception:  # noqa: BLE001 — a read, never a crash
            logger.warning("kingdom: eject modal realm read failed", exc_info=True)
        if realm is None or stack is None:
            await interaction.followup.send(
                str(strings_by_locale(self._locale)["plan_no_service"]), ephemeral=True
            )
            return
        note = await _eject_season_entry(
            interaction, realm, str(self.reason.value or "").strip()[:400], strings, self._locale
        )
        await open_unique_ephemeral(interaction, note)


def _eject_window(
    strings: dict[str, str], locale: str, realm: Any
) -> discord.ui.LayoutView:
    """Le motif — the eject confirm: the reason the King will receive.

    Three presets + a free field (« ✏️ Autre » opens the modal): one
    window, the ids live in ``kingdom:valid:eject-*`` (their OWN
    namespace, the cards' lesson). The surface is DECLARED
    (panel:mod:kingdom:validation:eject) like every ephemeral window.
    """
    name = str(getattr(realm, "name", "?"))[:80]
    slug = str(getattr(realm, "slug", ""))[:50]
    realm_id = str(getattr(realm, "id", ""))[:50]
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.TextDisplay(
            f"**{str(strings['eject_window_title']).format(name=name)}**\n"
            f"{strings['eject_window_hint']}"
        ),
        accent_colour=discord.Colour(0xED4245),
    )
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    choices: list[tuple[str, str]] = [
        ("players", str(strings["eject_reason_players"])[:80]),
        ("rules", str(strings["eject_reason_rules"])[:80]),
    ]

    async def _go(target: discord.Interaction, choice: str) -> None:
        if not target.response.is_done():
            await target.response.defer(ephemeral=True)
        try:
            stack = wiring()
            service = _realms_service(stack)
            realm_now = await service.realm_of_slug(slug) if service is not None else None
        except Exception:  # noqa: BLE001
            realm_now = None
        if realm_now is None:
            await open_unique_ephemeral_safe(target, str(strings["gone_note"]))
            return
        note = await _eject_season_entry(
            target, realm_now, str(strings[f"eject_reason_{choice}"]), strings, locale
        )
        await open_unique_ephemeral_safe(target, note)

    for choice, label in choices:
        button: discord.ui.Button[Any] = discord.ui.Button(
            label=label,
            custom_id=f"{_NS}:eject-go:{slug}:{choice}"[:100],
            style=discord.ButtonStyle.danger,
        )

        async def _on(target: discord.Interaction, _choice: str = choice) -> None:
            await _go(target, _choice)

        button.callback = _on
        row.add_item(button)
    # ✏️ Autre — le motif personnalisé
    other: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["eject_reason_other"])[:80],
        custom_id=f"{_NS}:eject-other:{slug}"[:100],
        style=discord.ButtonStyle.secondary,
    )

    async def _on_other(target: discord.Interaction) -> None:
        # re-resolve the realm at click time (the window is ephemeral,
        # the slug survives, the shell may have changed state)
        stack = wiring()
        service = _realms_service(stack)
        realm_now = await service.realm_of_slug(slug) if service is not None else None
        if realm_now is None:
            await open_unique_ephemeral(
                target, str(strings["gone_note"])
            )
            return
        await target.response.send_modal(_EjectReasonModal(realm_now, strings, locale))

    other.callback = _on_other
    row.add_item(other)
    container.add_item(row)
    return surface("panel:mod:kingdom:validation:eject", container)


class ValidationEjectButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:eject:(?P<slug>[a-z0-9-]+)",
):
    """🗑️ Éjecter du sas — undo one admission in the sas's own window."""

    def __init__(self, slug: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:eject:{slug}"[:100],
                label=label,
                style=discord.ButtonStyle.danger,
            )
        )
        self.slug = slug

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: Any,
        /,
    ) -> "ValidationEjectButton":
        button = item if isinstance(item, discord.ui.Button) else None
        label = (button.label or "?") if button is not None else "?"
        return cls(match["slug"], label)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard, check the sas window, then open the motif window."""
        locale = await _guild_locale(str(interaction.guild_id or ""))
        strings = mod_catalog().section("kingdom.validation", locale)
        if not await _guard(interaction, strings):
            return
        stack = wiring()
        service = _realms_service(stack)
        realm = await service.realm_of_slug(self.slug) if service is not None else None
        if (
            stack is None
            or service is None
            or realm is None
            or not getattr(realm, "engagement", None)
        ):
            await open_unique_ephemeral(interaction, str(strings["gone_note"]))
            return
        if not await _season_in_setup(stack):
            await open_unique_ephemeral(interaction, str(strings["eject_closed_note"]))
            return
        await open_unique_ephemeral(interaction, view=_eject_window(strings, locale, realm))


class ValidationArchiveButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    # drain-coquilles-v1 (Check 135) : un id de coquille porte un ":"
    # ("realm:aegis-123") — le moule l'accepte, ancré $ pour
    # capturer l'id ENTIER (avant : "realm" tronqué, clic mort).
    template=rf"{_NS}:arch:(?P<realm_id>[a-zA-Z0-9_:-]+)$",
):
    """📦 Archiver — take a DORMANT realm out of play (data kept)."""

    def __init__(self, realm_id: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                custom_id=f"{_NS}:arch:{realm_id}"[:100],
                label=label,
                style=discord.ButtonStyle.secondary,
            )
        )
        self.realm_id = realm_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: Any,
        /,
    ) -> "ValidationArchiveButton":
        button = item if isinstance(item, discord.ui.Button) else None
        label = (button.label or "?") if button is not None else "?"
        return cls(match["realm_id"], label)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard, resolve the DORMANT realm, open the confirm card."""
        # drawer-build-v1 (Check 137) : fast-ack — la lecture derrière
        # ne court jamais contre le chrono de 3 s de Discord (gards
        # et cartes parlent déjà followup — zéro 40060).
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        from .common import open_unique_ephemeral

        locale = await _guild_locale(str(interaction.guild_id or ""))
        strings = mod_catalog().section("kingdom.validation", locale)
        if not await _guard(interaction, strings):
            return
        stack = wiring()
        service = _realms_service(stack)
        realm = None
        if service is not None:
            try:
                realm = await service.realm_by_id(str(self.realm_id))
            except Exception:  # noqa: BLE001 — surface reports, never raises
                logger.warning(
                    "kingdom: realm resolve failed (%s)", self.realm_id, exc_info=True
                )
        if (
            realm is None
            or getattr(realm, "engagement", None)
            or getattr(realm, "join_request", None)
        ):
            await open_unique_ephemeral(interaction, str(strings["gone_note"]))
            return
        if getattr(realm, "archived_at", 0):
            await open_unique_ephemeral(
                interaction, str(strings["archive_already_note"])
            )
            return
        await open_unique_ephemeral(
            interaction, view=_archive_confirm_card(strings, locale, realm)
        )


def _archive_confirm_card(
    strings: dict[str, str], locale: str, realm: Any
) -> discord.ui.LayoutView:
    """The confirm card of one dormant realm's archive (the delete pattern)."""
    name = str(getattr(realm, "name", "?"))[:80]
    yes: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["archive_confirm_button"])[:80],
        custom_id=f"{_NS}:arch-yes:{realm.id}"[:100],
        style=discord.ButtonStyle.danger,
    )
    no: discord.ui.Button[Any] = discord.ui.Button(
        label=str(strings["delete_cancel_button"])[:80],
        custom_id=f"{_NS}:arch-no:{realm.id}"[:100],
        style=discord.ButtonStyle.secondary,
    )

    async def on_yes(target: discord.Interaction) -> None:
        if not target.response.is_done():
            await target.response.defer(ephemeral=True)
        shared = strings_by_locale(locale)
        stack = wiring()
        service = _realms_service(stack)
        if stack is None or service is None:
            await target.followup.send(str(shared["plan_no_service"]), ephemeral=True)
            return
        note: str
        deleted = 0
        try:
            archived = await service.archive_realm(
                str(realm.id), reason="settings: admissions drawer"
            )
            # la jambe Discord : la maison part, les données restent
            from .realms import archive_realm_habitat

            deleted = await archive_realm_habitat(target.client, archived)
            note = str(strings["archived_note"]).format(
                name=str(getattr(archived, "name", name)), deleted=deleted
            )
        except Exception as exc:  # noqa: BLE001 — the card reports, never raises
            logger.warning(
                "kingdom: realm archive failed (%s)", realm.id, exc_info=True
            )
            note = str(shared["console_error"]).format(str(exc)[:150])
        # purge-card-close-v1 (Check 139) : idem carte Supprimer — la
        # note d'archivage remplace la carte de confirmation.
        await open_unique_ephemeral(target, content=note)

    async def on_no(target: discord.Interaction) -> None:
        if not target.response.is_done():
            await target.response.defer(ephemeral=True)

    yes.callback = on_yes
    no.callback = on_no
    container = discord.ui.Container()
    container.add_item(
        # confirm-nom-v1 (Drasah 24/11) : le titre porte « {name} » —
        # jamais formaté, la carte disait « Archiver « {name} » ? » en
        # plein écran (l'admin ne savait PAS quel royaume partait) ;
        # la carte de réveil, elle, formatait déjà (l'asymétrie prouvait
        # le raté de params, pas le moule).
        discord.ui.TextDisplay(
            f"## {str(strings['archive_confirm_title']).format(name=name)}"
        )
    )
    container.add_item(
        discord.ui.TextDisplay(
            str(strings["archive_confirm_hint"]).format(
                name=name, deleted=len(getattr(realm, "member_ids", []) or []) + 1
            )
        )
    )
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row.add_item(yes)
    row.add_item(no)
    container.add_item(row)
    return surface("panel:mod:kingdom:validation:confirm", container)


__all__ = [
    "VALIDATION_VIEW_KEY",
    "ValidationArchiveButton",
    "ValidationCrownButton",
    "ValidationDecisionButton",
    "ValidationDeleteButton",
    "ValidationEjectButton",
    "ValidationRealmEntryButton",
    "build_validation_panel",
]
