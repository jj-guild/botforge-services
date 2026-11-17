"""The kingdom-validation dashboard (#339, the detailed candidates view).

The generic admin lists the count; the mod's validation flow needs the
FULL view — this is it, pinned in the declared ``realms`` salon
(``mod.yaml``'s « 👑 royaumes — Kingdom validation panel », admin
only): one row per PENDING kingdom with its King and the ✅ Valider /
❌ Refuser buttons, then the accepted and refused tables (the
dashboard shape — #380's candidates-table form rendered as the pin's
own blocks, the decision rides D70 rule 35).

The template rule (#396): the whole surface is the declared
``view:mod:kingdom:candidates`` id + its data — a pinned layout, not a
hand-rolled render; the decisions are restart-proof DynamicItems with
stable custom ids, guarded at click time (the runtime check is the
security boundary, the salon's visibility is only convenience).
"""

from __future__ import annotations

import logging
from typing import Any

import discord

from .common import _bot_admins, mod_catalog, strings_by_locale, surface, wiring

logger = logging.getLogger("kingdom.validation")

VALIDATION_VIEW_KEY = "view:mod:kingdom:candidates"

_NS = "kingdom:valid"


async def _guild_locale(guild_id: str) -> str:
    """The guild's effective locale (stored choice first, fr fallback)."""
    from .panel import _guild_locale as _panel_locale

    return await _panel_locale(guild_id)

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
    blocks.append(discord.ui.Separator())
    blocks.append(
        discord.ui.TextDisplay(
            _table(strings["accepted_header"], strings["table_kingdom"], accepted)
        )
    )
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
    """The pending kingdom's King's display name (— when unresolvable)."""
    from .common import lord_name

    if stack is None:
        return "—"
    for lord in await _lords_safe(stack):
        if lord.kingdom_id == kingdom.id and not lord.left:
            return str(await lord_name(stack.kingdoms, lord.id)) or "—"
    return "—"


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
            await interaction.response.edit_message(
                view=await build_validation_panel(str(interaction.guild_id or ""))
            )
        except Exception:
            logger.warning("kingdom: validation dashboard refresh failed", exc_info=True)
            await interaction.response.defer()
        try:
            await interaction.followup.send(note, ephemeral=True)
        except Exception:  # noqa: S110 — a vanished window is fine
            pass


__all__ = [
    "VALIDATION_VIEW_KEY",
    "ValidationDecisionButton",
    "build_validation_panel",
]
