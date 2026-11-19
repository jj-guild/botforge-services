"""The 🎁 distributeur — the admin test-injector pinned panel (19/11).

The reference's APP injector, ported onto the declared salon: ONE
pinned panel with three doors —

- 🔧 **Ouvrir le distributeur** — the ephemeral injection window: pick
  a kingdom, then hand it 🏰 tech points, a territory (a free map from
  the cadastre) or a civilization (a free one, alliance rule: never a
  duplicate, never a married one). Zero cost, zero limits — the inject
  rides the service seams (``economy.grant_tech_points``,
  ``territories.draw_map_for``, the kingdom's acquisition ledger);
- 🌱 **Créer le royaume test** — ``ensure_test_kingdom`` (Nilrem),
  idempotent;
- 🧨 **Autodestruction du royaume test** — the confirm card, then
  ``delete_kingdom`` (the casquette-removal-v1 replacement: the test
  kingdom is created and removed HERE, never on the console).

Announce-ready (#396): pinned panel + windows are declared templates;
every button is a restart-proof DynamicItem under the
``kingdom:distributor:`` namespace, the kingdom rides the custom id
(itself restart-proof), the click guard is the platform admin check.
"""

from __future__ import annotations

import logging
from typing import Any

import discord

from .common import mod_catalog, open_unique_ephemeral, surface, wiring

logger = logging.getLogger("kingdom.distributor")

DISTRIBUTOR_VIEW_KEY = "panel:mod:kingdom:distributor"
WINDOW_VIEW_KEY = "panel:mod:kingdom:distributor:window"
_NS = "kingdom:distributor"


async def _guild_locale(guild_id: str) -> str:
    from .panel import _guild_locale as _panel_locale

    return await _panel_locale(guild_id)


def distributor_strings(locale: str) -> dict[str, str]:
    """The distributor surfaces' strings (``kingdom.distributor`` section)."""
    return dict(mod_catalog().section("kingdom.distributor", str(locale)[:2]))


def _strings(interaction: discord.Interaction) -> dict[str, str]:
    from .common import locale_of

    return distributor_strings(locale_of(interaction))


async def build_distributor_panel(guild_id: str) -> discord.ui.LayoutView:
    """Build the pinned distributor layout (guild-locale strings)."""
    strings = distributor_strings(await _guild_locale(guild_id))
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['title']}"),
        discord.ui.TextDisplay(str(strings["help"])),
        discord.ui.Separator(),
    ]
    stack = wiring()
    existing = False
    if stack is not None:
        try:
            existing = (await stack.kingdoms.test_kingdom()) is not None
        except Exception:
            logger.warning("kingdom: distributor test-kingdom read failed", exc_info=True)
    if existing:
        blocks.append(discord.ui.TextDisplay(str(strings["test_exists_line"])))
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row.add_item(
        DistributorOpenButton(str(strings["open_button"]), discord.ButtonStyle.primary).item
    )
    row.add_item(
        DistributorTestKingdomButton(
            str(strings["test_kingdom_button"]), discord.ButtonStyle.success
        ).item
    )
    row.add_item(
        DistributorDestructButton(str(strings["destruct_button"]), discord.ButtonStyle.danger).item
    )
    blocks.append(row)
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        *blocks, accent_colour=discord.Colour(0x5865F2)
    )
    return surface(DISTRIBUTOR_VIEW_KEY, container)


async def _guard(interaction: discord.Interaction) -> bool:
    from .settings_panel import _panel_guard

    return await _panel_guard(interaction)


async def _inject_window(interaction: discord.Interaction) -> None:
    """Open the ephemeral kingdom picker of the injection window."""
    strings = _strings(interaction)
    stack = wiring()
    kingdoms: list[Any] = []
    if stack is not None:
        try:
            kingdoms = [k for k in await stack.kingdoms.kingdoms() if not k.is_gaia]
        except Exception:
            logger.warning("kingdom: distributor kingdoms read failed", exc_info=True)
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['window_title']}"),
        discord.ui.TextDisplay(str(strings["window_help"])),
        discord.ui.Separator(),
    ]
    if not kingdoms:
        blocks.append(discord.ui.TextDisplay(str(strings["no_kingdoms"])))
    else:
        picker = DistributorKingdomSelect(str(strings["select_placeholder"]))
        picker.item.options = DistributorKingdomSelect.options_of(kingdoms, strings)
        picker_row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        picker_row.add_item(picker.item)
        blocks.append(picker_row)
        blocks.append(discord.ui.TextDisplay(str(strings["select_hint"])))
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        *blocks, accent_colour=discord.Colour(0x5865F2)
    )
    await open_unique_ephemeral(interaction, view=surface(WINDOW_VIEW_KEY, container))


async def _give_view(interaction: discord.Interaction, kingdom_id: str) -> discord.ui.LayoutView:
    """Build the injection window of ONE kingdom (its id rides the ids)."""
    from botforge.mods.kingdom.service import TEST_KINGDOM_ID

    strings = _strings(interaction)
    stack = wiring()
    kingdom = None
    name = str(kingdom_id)
    hand: list[str] = []
    if stack is not None:
        try:
            kingdom = next(
                (k for k in await stack.kingdoms.kingdoms() if str(k.id) == str(kingdom_id)),
                None,
            )
        except Exception:
            logger.warning("kingdom: distributor kingdom read failed", exc_info=True)
    if kingdom is not None:
        name = str(kingdom.name)
        hand = [str(civ) for civ in getattr(kingdom, "civilizations", ()) or ()]
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['window_title']}"),
        discord.ui.TextDisplay(str(strings["kingdom_header"]).format(name)),
    ]
    if hand:
        blocks.append(discord.ui.TextDisplay(str(strings["hand_line"]).format(", ".join(hand))))
    blocks.append(discord.ui.Separator())
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row.add_item(
        DistributorGiveButton(strings["points_button"], kingdom_id, "points").item
    )
    blocks.append(row)
    row2: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row2.add_item(
        DistributorGiveButton(strings["territory_button"], kingdom_id, "territory").item
    )
    row2.add_item(DistributorGiveButton(strings["civ_button"], kingdom_id, "civ").item)
    blocks.append(row2)
    if stack is None or kingdom is None:
        blocks.append(discord.ui.TextDisplay(str(strings["no_kingdoms"])))
    if str(kingdom_id) == str(TEST_KINGDOM_ID):
        blocks.append(discord.ui.TextDisplay(str(strings["test_hint"])))
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        *blocks, accent_colour=discord.Colour(0x5865F2)
    )
    return surface(WINDOW_VIEW_KEY, container)


# ---------------------------------------------------------------------------
# The pinned panel's three doors
# ---------------------------------------------------------------------------


class DistributorOpenButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:open$"
):
    """« 🔧 Ouvrir le distributeur » — the ephemeral injection window."""

    def __init__(self, label: str, style: discord.ButtonStyle) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id=f"{_NS}:open", style=style or discord.ButtonStyle.primary
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        return cls(_strings(interaction)["open_button"], discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        await _inject_window(interaction)


class DistributorTestKingdomButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:test-kingdom$"
):
    """« 🌱 Créer le royaume test » — ensure_test_kingdom (idempotent)."""

    def __init__(self, label: str, style: discord.ButtonStyle) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:test-kingdom",
                style=style or discord.ButtonStyle.success,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        return cls(_strings(interaction)["test_kingdom_button"], discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        from .common import service_failure_note
        from .settings_panel import _safe_followup

        strings = _strings(interaction)
        await interaction.response.defer(ephemeral=True)
        stack = wiring()
        if stack is None:
            await interaction.followup.send(strings["no_service"], ephemeral=True)
            return
        try:
            kingdom = await stack.kingdoms.ensure_test_kingdom()
            note = str(strings["test_kingdom_done"]).format(str(getattr(kingdom, "name", "")))
        except Exception as exc:  # noqa: BLE001 — the panel reports, never raises
            logger.warning("kingdom: test-kingdom ensure failed", exc_info=True)
            note = service_failure_note(strings, "error", exc)
        await _safe_followup(interaction, note)


class DistributorDestructButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:destruct$"
):
    """« 🧨 Autodestruction » — the confirm card before the wipe."""

    def __init__(self, label: str, style: discord.ButtonStyle) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:destruct",
                style=style or discord.ButtonStyle.danger,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        return cls(_strings(interaction)["destruct_button"], discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        from botforge.mods.kingdom.service import TEST_KINGDOM_ID

        strings = _strings(interaction)
        yes = discord.ui.Button(
            label=str(strings["destruct_confirm_button"])[:80],
            custom_id=f"{_NS}:destruct:yes",
            style=discord.ButtonStyle.danger,
        )
        no = discord.ui.Button(
            label=str(strings["destruct_cancel_button"])[:80],
            custom_id=f"{_NS}:destruct:no",
            style=discord.ButtonStyle.secondary,
        )

        async def on_yes(target: discord.Interaction) -> None:
            from .common import service_failure_note
            from .settings_panel import _safe_followup

            target_strings = _strings(target)
            await target.response.defer(ephemeral=True)
            stack = wiring()
            if stack is None:
                await target.followup.send(target_strings["no_service"], ephemeral=True)
                return
            try:
                kingdom = await stack.kingdoms.delete_kingdom(str(TEST_KINGDOM_ID))
                note = str(target_strings["destruct_done"]).format(
                    str(getattr(kingdom, "name", ""))
                )
            except Exception as exc:  # noqa: BLE001 — the panel reports, never raises
                logger.warning("kingdom: test-kingdom destruct failed", exc_info=True)
                note = service_failure_note(target_strings, "error", exc)
            await _safe_followup(target, note)

        async def on_no(target: discord.Interaction) -> None:
            from .settings_panel import _safe_send

            await _safe_send(target, _strings(target)["cancelled"])

        yes.callback = on_yes
        no.callback = on_no
        row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        row.add_item(yes)
        row.add_item(no)
        container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
            discord.ui.TextDisplay(
                f"**{strings['destruct_confirm_title']}**\n{strings['destruct_confirm_hint']}"
            ),
            row,
            accent_colour=discord.Colour(0xED4245),
        )
        await open_unique_ephemeral(interaction, view=surface(WINDOW_VIEW_KEY, container))


# ---------------------------------------------------------------------------
# The injection window (pick a kingdom, then hand it elements)
# ---------------------------------------------------------------------------


class DistributorKingdomSelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]], template=rf"{_NS}:pick$"
):
    """The kingdom picker — the choice opens the kingdom's own window."""

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
        """Rebuild the button from the wire (locale label, stable id)."""

        return cls(_strings(interaction)["select_placeholder"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        values = [str(v) for v in (self.item.values or [])]
        kingdom_id = values[0] if values else ""
        if not kingdom_id:
            await interaction.response.defer(ephemeral=True)
            return
        view = await _give_view(interaction, kingdom_id)
        await open_unique_ephemeral(interaction, view=view)

    @staticmethod
    def options_of(kingdoms: list[Any], strings: dict[str, str]) -> list[discord.SelectOption]:
        """Render the picker's options (the test kingdom last, marked)."""
        from botforge.mods.kingdom.service import TEST_KINGDOM_ID

        options: list[discord.SelectOption] = []
        test = None
        for kingdom in kingdoms:
            label = str(getattr(kingdom, "name", ""))[:100]
            option = discord.SelectOption(label=label, value=str(kingdom.id))
            if str(kingdom.id) == str(TEST_KINGDOM_ID):
                option.description = strings["test_option"][:100]
                test = option
            else:
                options.append(option)
        if test is not None:
            options.append(test)
        return options[:25]


class DistributorGiveButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:give:(?P<kid>[a-z0-9-]+):(?P<what>points|territory|civ)$",
):
    """One injection button — the kingdom id and the what ride the custom id."""

    def __init__(self, label: str, kingdom_id: str, what: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:give:{kingdom_id}:{what}"[:100],
                style=discord.ButtonStyle.success,
            )
        )
        self.kid = kingdom_id
        self.what = what

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        strings = _strings(interaction)
        key = {"points": "points_button", "territory": "territory_button", "civ": "civ_button"}[
            match["what"]
        ]
        return cls(strings[key], match["kid"], match["what"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        import random

        from botforge.mods.kingdom.game_clock import game_now

        from .common import service_failure_note
        from .settings_panel import _safe_followup

        strings = _strings(interaction)
        kid = str(getattr(self, "kid", "")) or "k"
        what = str(getattr(self, "what", ""))
        await interaction.response.defer(ephemeral=True)
        stack = wiring()
        if stack is None:
            await interaction.followup.send(strings["no_service"], ephemeral=True)
            return
        try:
            if what == "points":
                kingdom = await stack.economy.grant_tech_points(kid, 10)
                note = str(strings["points_done"]).format(str(kingdom.name), 10)
            elif what == "territory":
                drawn = set(await stack.territories.drawn_map_keys())
                catalog = [entry.key for entry in stack.config.maps]
                free = [key for key in catalog if key not in drawn]
                if not free:
                    raise ValueError(str(strings["no_free_map"]))
                key = random.choice(free)
                territory = await stack.territories.draw_map_for(kid, key)
                note = str(strings["territory_done"]).format(str(territory.map_key))
            elif what == "civ":
                kingdom = next(
                    (k for k in await stack.kingdoms.kingdoms() if str(k.id) == kid), None
                )
                if kingdom is None:
                    raise ValueError(str(strings["no_kingdoms"]))
                hand = {str(civ) for civ in getattr(kingdom, "civilizations", ()) or ()}
                pool = [
                    str(entry.civilization)
                    for entry in stack.config.civilizations
                    if str(entry.civilization) not in hand
                ]
                if not pool:
                    raise ValueError(str(strings["no_free_civ"]))
                civ = random.choice(pool)
                kingdom.record_acquisition(civ, "distributor", int(game_now().timestamp()))
                await stack.kingdoms.save_kingdom(kingdom)
                note = str(strings["civ_done"]).format(civ)
            else:
                note = str(strings["error"]).format(what)
        except Exception as exc:  # noqa: BLE001 — the panel reports, never raises
            logger.warning("kingdom: distributor give %s failed", what, exc_info=True)
            note = service_failure_note(strings, "error", exc)
        await _safe_followup(interaction, note)


def distributor_dynamic_items() -> tuple:
    """Every restart-proof DynamicItem of the distributor surfaces."""
    return (
        DistributorOpenButton,
        DistributorTestKingdomButton,
        DistributorDestructButton,
        DistributorKingdomSelect,
        DistributorGiveButton,
    )


__all__ = [
    "DISTRIBUTOR_VIEW_KEY",
    "WINDOW_VIEW_KEY",
    "build_distributor_panel",
    "distributor_dynamic_items",
    "distributor_strings",
]
