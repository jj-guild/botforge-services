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

distributeur-v2 (Drasah 20/11): the reference's FULL cockpit — the
kingdom window is the category menu of the old injector, à
l'identique: Alliances (+ / -), Trésor, Paroisse, Territoires,
Seigneurs, Tech, Statut. The panel rides the service seams (the
admin levers live in the services, the surface only reads and calls).

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

PAGE_SIZE = 25  # Discord caps one select at 25 options


async def _guild_locale(guild_id: str) -> str:
    from .panel import _guild_locale as _panel_locale

    return await _panel_locale(guild_id)


def distributor_strings(locale: str) -> dict[str, str]:
    """The distributor surfaces' strings (``kingdom.distributor`` section)."""
    return dict(mod_catalog().section("kingdom.distributor", str(locale)[:2]))


def _strings(interaction: discord.Interaction) -> dict[str, str]:
    locale = str(getattr(interaction, "locale", "") or "fr")
    return distributor_strings(locale)


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


# ---------------------------------------------------------------------------
# The window plumbing — ONE declared window surface, re-rendered per view
# ---------------------------------------------------------------------------


async def _kingdom_of(stack: Any, kid: str) -> Any | None:
    """Return the kingdom document of an id (None when unwired/unknown)."""
    if stack is None:
        return None
    try:
        return next((k for k in await stack.kingdoms.kingdoms() if str(k.id) == str(kid)), None)
    except Exception:
        logger.warning("kingdom: distributor kingdom read failed", exc_info=True)
        return None


async def _economy_wallet(stack: Any, kid: str) -> int:
    if stack is None:
        return 0
    try:
        return int(await stack.economy.wallet(kid))
    except Exception:
        logger.warning("kingdom: distributor wallet read failed", exc_info=True)
        return 0


def _window(container_items: list[discord.ui.Item[discord.ui.LayoutView]]) -> discord.ui.LayoutView:
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        *container_items, accent_colour=discord.Colour(0x5865F2)
    )
    return surface(WINDOW_VIEW_KEY, container)


def _note_block(strings: dict[str, str], note: str | None) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    """The result note of an action, on top of the re-rendered window."""
    if not note:
        return []
    return [discord.ui.TextDisplay(str(note)[:3000])]


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
    await open_unique_ephemeral(interaction, view=_window(blocks))


# ---------------------------------------------------------------------------
# The category menu (distributeur-v2) — the reference's cockpit, ported
# ---------------------------------------------------------------------------


async def _menu_window(
    interaction: discord.Interaction, kid: str, note: str | None = None
) -> discord.ui.LayoutView:
    """The kingdom's own menu: quick injects + the seven categories."""
    strings = _strings(interaction)
    stack = wiring()
    kingdom = await _kingdom_of(stack, kid)
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['window_title']}"),
        *_note_block(strings, note),
        discord.ui.TextDisplay(
            str(strings["kingdom_header"]).format(str(getattr(kingdom, "name", kid)))
        ),
    ]
    hand = [str(civ) for civ in getattr(kingdom, "civilizations", ()) or ()]
    if hand:
        blocks.append(discord.ui.TextDisplay(str(strings["hand_line"]).format(", ".join(hand))))
    blocks.append(discord.ui.Separator())
    blocks.append(discord.ui.TextDisplay(str(strings["menu_title"]).format(str(getattr(kingdom, "name", kid)))))
    # the quick-inject row (the 19/11 recette's three doors)
    quick: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    quick.add_item(DistributorGiveButton(strings["points_button"], kid, "points").item)
    quick.add_item(DistributorGiveButton(strings["territory_button"], kid, "territory").item)
    quick.add_item(DistributorGiveButton(strings["civ_button"], kid, "civ").item)
    blocks.append(quick)
    # the seven categories, two rows (D68: never an overlong ActionRow)
    categories = (
        "alliance_add",
        "alliance_remove",
        "treasury",
        "parish",
        "territories",
        "lord",
        "tech",
        "status",
    )
    cat_row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    for index, cat in enumerate(categories):
        if index == 5:
            blocks.append(cat_row)
            cat_row = discord.ui.ActionRow()
        cat_row.add_item(DistributorCatButton(strings[f"cat_{cat}"], kid, cat).item)
    blocks.append(cat_row)
    if stack is None or kingdom is None:
        blocks.append(discord.ui.TextDisplay(str(strings["no_kingdoms"])))
    return _window(blocks)


async def _civ_window(
    interaction: discord.Interaction,
    kid: str,
    mode: str,
    page: int,
    note: str | None = None,
) -> discord.ui.LayoutView:
    """The paged civilization select (add or remove mode)."""
    strings = _strings(interaction)
    stack = wiring()
    kingdom = await _kingdom_of(stack, kid)
    rows = await _civ_rows(stack, kid) if stack is not None else []
    if mode == "remove":
        rows = [row for row in rows if row["status"] == "hand"]
    pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(int(page), pages - 1))
    key = "civ_add_title" if mode == "add" else "civ_remove_title"
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['window_title']}"),
        *_note_block(strings, note),
        discord.ui.TextDisplay(
            str(strings[key]).format(str(getattr(kingdom, "name", kid)), page + 1, pages)
        ),
        discord.ui.Separator(),
    ]
    picker = DistributorCivSelect(strings["civ_placeholder"], kid, mode, page)
    options = _civ_options(strings, rows, page, mode, kingdom)
    picker.item.options = options or [discord.SelectOption(label="—", value="")]
    picker_row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    picker_row.add_item(picker.item)
    blocks.append(picker_row)
    nav: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    prev = DistributorCivPageButton(strings["prev_page"], kid, mode, page, "prev")
    next_ = DistributorCivPageButton(strings["next_page"], kid, mode, page, "next")
    prev.item.disabled = page <= 0
    next_.item.disabled = page >= pages - 1
    nav.add_item(prev.item)
    nav.add_item(next_.item)
    nav.add_item(DistributorMenuButton(strings["back_button"], kid).item)
    blocks.append(nav)
    return _window(blocks)


async def _treasury_window(
    interaction: discord.Interaction, kid: str, note: str | None = None
) -> discord.ui.LayoutView:
    """The tech treasury: +/-, set exact."""
    strings = _strings(interaction)
    stack = wiring()
    kingdom = await _kingdom_of(stack, kid)
    wallet = await _economy_wallet(stack, kid)
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['window_title']}"),
        *_note_block(strings, note),
        discord.ui.TextDisplay(
            str(strings["treasury_title"]).format(str(getattr(kingdom, "name", kid)), wallet)
        ),
        discord.ui.Separator(),
    ]
    ops: list[tuple[str, str, int]] = [
        ("p5", "tr_plus5_button", discord.ButtonStyle.success),
        ("p1", "tr_plus1_button", discord.ButtonStyle.success),
        ("m1", "tr_minus1_button", discord.ButtonStyle.secondary),
        ("m5", "tr_minus5_button", discord.ButtonStyle.secondary),
        ("set", "treasury_set", discord.ButtonStyle.primary),
    ]
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    for op, key, style in ops:
        row.add_item(DistributorTreasuryButton(strings[key], kid, op, style).item)
    blocks.append(row)
    back: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    back.add_item(DistributorMenuButton(strings["back_button"], kid).item)
    blocks.append(back)
    return _window(blocks)


async def _parish_window(
    interaction: discord.Interaction, kid: str, note: str | None = None
) -> discord.ui.LayoutView:
    """The Paroisse paliers: force the tier (the admin lever)."""
    strings = _strings(interaction)
    stack = wiring()
    kingdom = await _kingdom_of(stack, kid)
    tier = int(getattr(kingdom, "parish_tier", 1) or 1)
    tier_name = ""
    if stack is not None:
        try:
            tiers = list(getattr(stack.config.parish, "tiers", ()) or [])
            if 0 < tier <= len(tiers):
                tier_name = str(tiers[tier - 1].display_name)
        except Exception:
            tier_name = ""
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['window_title']}"),
        *_note_block(strings, note),
        discord.ui.TextDisplay(
            str(strings["parish_title"]).format(str(getattr(kingdom, "name", kid)), tier or 1, tier_name)
        ),
        discord.ui.Separator(),
    ]
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    for index in (1, 2, 3):
        names = ("", "")
        if stack is not None:
            try:
                tiers = list(getattr(stack.config.parish, "tiers", ()) or [])
                if index <= len(tiers):
                    names = (str(tiers[index - 1].display_name), "")
            except Exception:
                names = ("", "")
        label = f"{index} · {names[0]}" if names[0] else str(index)
        row.add_item(DistributorParishButton(label, kid, index).item)
    blocks.append(row)
    back: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    back.add_item(DistributorMenuButton(strings["back_button"], kid).item)
    blocks.append(back)
    return _window(blocks)


async def _territories_window(
    interaction: discord.Interaction, kid: str, note: str | None = None
) -> discord.ui.LayoutView:
    """The kingdom's territories + the six admin actions."""
    from botforge.mods.kingdom.game_clock import game_now

    strings = _strings(interaction)
    stack = wiring()
    kingdom = await _kingdom_of(stack, kid)
    territories: list[Any] = []
    if stack is not None:
        try:
            territories = [t for t in await stack.territories.territories() if str(t.owner_kingdom_id) == str(kid)]
        except Exception:
            logger.warning("kingdom: distributor territories read failed", exc_info=True)
    names = _map_names(stack)
    lines: list[str] = []
    now = game_now()
    for territory in territories:
        shield = ""
        until = getattr(territory, "protected_until", None)
        if until is not None and until > now:
            shield = strings["terr_shielded"]
        name = names.get(str(territory.map_key), str(territory.map_key))
        lines.append(str(strings["terr_line"]).format(name, shield))
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['window_title']}"),
        *_note_block(strings, note),
        discord.ui.TextDisplay(
            str(strings["terr_title"]).format(str(getattr(kingdom, "name", kid)), len(territories))
        ),
        discord.ui.Separator(),
    ]
    blocks.append(discord.ui.TextDisplay("\n".join(lines) if lines else str(strings["terr_none"])))
    acts: list[tuple[str, str]] = [
        ("give", "terr_give_button"),
        ("transfer", "terr_transfer_button"),
        ("retire", "terr_retire_button"),
        ("replace", "terr_replace_button"),
        ("shield", "terr_shield_button"),
        ("unshield", "terr_unshield_button"),
    ]
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    for index, (act, key) in enumerate(acts):
        if index == 5:
            blocks.append(row)
            row = discord.ui.ActionRow()
        row.add_item(DistributorTerritoryButton(strings[key], kid, act).item)
    blocks.append(row)
    back: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    back.add_item(DistributorMenuButton(strings["back_button"], kid).item)
    blocks.append(back)
    return _window(blocks)


async def _map_pick_window(
    interaction: discord.Interaction, kid: str, note: str | None = None
) -> discord.ui.LayoutView:
    """Pick a still-free map (the Give flow)."""
    strings = _strings(interaction)
    stack = wiring()
    free = await _free_maps(stack)
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['window_title']}"),
        *_note_block(strings, note),
        discord.ui.TextDisplay(str(strings["terr_give_pick_line"])),
        discord.ui.Separator(),
    ]
    if not free:
        blocks.append(discord.ui.TextDisplay(str(strings["terr_maps_none"])))
        back: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        back.add_item(DistributorTerritoryButton(strings["back_button"], kid, "none").item)
        blocks.append(back)
        return _window(blocks)
    picker = DistributorMapSelect(strings["select_placeholder"], kid)
    names = _map_names(stack)
    picker.item.options = [
        discord.SelectOption(label=names.get(key, key)[:100], value=key) for key in free
    ][:25]
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row.add_item(picker.item)
    blocks.append(row)
    back = discord.ui.ActionRow()
    back.add_item(DistributorMenuButton(strings["back_button"], kid).item)
    blocks.append(back)
    return _window(blocks)


async def _territory_pick_window(
    interaction: discord.Interaction, kid: str, act: str, note: str | None = None
) -> discord.ui.LayoutView:
    """Pick one of the kingdom's territories (the five non-give flows)."""
    strings = _strings(interaction)
    stack = wiring()
    kingdom = await _kingdom_of(stack, kid)
    territories: list[Any] = []
    if stack is not None:
        try:
            territories = [t for t in await stack.territories.territories() if str(t.owner_kingdom_id) == str(kid)]
        except Exception:
            territories = []
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['window_title']}"),
        *_note_block(strings, note),
        discord.ui.TextDisplay(str(strings["terr_pick_line"]).format(str(getattr(kingdom, "name", kid)))),
        discord.ui.Separator(),
    ]
    if not territories:
        blocks.append(discord.ui.TextDisplay(str(strings["terr_none"])))
    else:
        picker = DistributorTerritorySelect(strings["select_placeholder"], kid, act)
        names = _map_names(stack)
        picker.item.options = [
            discord.SelectOption(
                label=names.get(str(t.map_key), str(t.map_key))[:100], value=str(t.map_key)
            )
            for t in territories
        ][:25]
        row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        row.add_item(picker.item)
        blocks.append(row)
    back: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    back.add_item(DistributorMenuButton(strings["back_button"], kid).item)
    blocks.append(back)
    return _window(blocks)


async def _kingdom_pick_window(
    interaction: discord.Interaction, kid: str, map_key: str, note: str | None = None
) -> discord.ui.LayoutView:
    """Pick the receiving kingdom of a territory transfer."""
    strings = _strings(interaction)
    stack = wiring()
    names = _map_names(stack)
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['window_title']}"),
        *_note_block(strings, note),
        discord.ui.TextDisplay(
            str(strings["terr_pick_kingdom_line"]).format(names.get(str(map_key), str(map_key)))
        ),
        discord.ui.Separator(),
    ]
    others: list[Any] = []
    if stack is not None:
        try:
            others = [k for k in await stack.kingdoms.kingdoms() if str(k.id) != str(kid) and not k.is_gaia]
        except Exception:
            others = []
    if not others:
        blocks.append(discord.ui.TextDisplay(str(strings["no_kingdoms"])))
    else:
        picker = DistributorKingdomTargetSelect(strings["select_placeholder"], kid, map_key)
        picker.item.options = [
            discord.SelectOption(label=str(k.name)[:100], value=str(k.id)) for k in others
        ][:25]
        row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        row.add_item(picker.item)
        blocks.append(row)
    back: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    back.add_item(DistributorMenuButton(strings["back_button"], kid).item)
    blocks.append(back)
    return _window(blocks)


async def _lord_window(
    interaction: discord.Interaction, kid: str, note: str | None = None
) -> discord.ui.LayoutView:
    """Pick one of the kingdom's active lords."""
    strings = _strings(interaction)
    stack = wiring()
    kingdom = await _kingdom_of(stack, kid)
    lords: list[Any] = []
    if stack is not None:
        try:
            lords = [
                lord
                for lord in await stack.kingdoms.lords()
                if str(lord.kingdom_id or "") == str(kid) and not bool(lord.left)
            ]
        except Exception:
            lords = []
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['window_title']}"),
        *_note_block(strings, note),
        discord.ui.TextDisplay(str(strings["lord_title"]).format(str(getattr(kingdom, "name", kid)))),
        discord.ui.Separator(),
    ]
    if not lords:
        blocks.append(discord.ui.TextDisplay(str(strings["lord_none"])))
    else:
        picker = DistributorLordSelect(strings["select_placeholder"], kid)
        picker.item.options = [
            discord.SelectOption(
                label=str(lord.display_name)[:100],
                value=str(lord.id),
                description=str(strings["lord_line"]).format(
                    strings["lord_role_king" if str(lord.role) in ("king", "LordRole.KING") else "lord_role_lord"],
                    int(lord.attack_used),
                    int(lord.defense_used),
                )[:100],
            )
            for lord in lords
        ][:25]
        row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        row.add_item(picker.item)
        blocks.append(row)
    back: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    back.add_item(DistributorMenuButton(strings["back_button"], kid).item)
    blocks.append(back)
    return _window(blocks)


async def _lord_action_window(
    interaction: discord.Interaction, kid: str, lord_id: str, note: str | None = None
) -> discord.ui.LayoutView:
    """One lord's three levers: budgets, marriage lock, marriage unlock."""
    strings = _strings(interaction)
    stack = wiring()
    lord = None
    if stack is not None:
        try:
            lord = next(
                (item for item in await stack.kingdoms.lords() if str(item.id) == str(lord_id)),
                None,
            )
        except Exception:
            lord = None
    name = str(getattr(lord, "display_name", lord_id))
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['window_title']}"),
        *_note_block(strings, note),
        discord.ui.TextDisplay(str(strings["lord_action_title"]).format(name)),
        discord.ui.Separator(),
    ]
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    row.add_item(DistributorLordActionButton(strings["lord_budgets_button"], kid, lord_id, "budgets").item)
    row.add_item(DistributorLordActionButton(strings["lord_unlock_button"], kid, lord_id, "unlock").item)
    row.add_item(DistributorLordActionButton(strings["lord_lock_button"], kid, lord_id, "lock").item)
    blocks.append(row)
    back: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    back.add_item(DistributorLordSelect(strings["back_button"], kid).item)
    blocks.append(back)
    return _window(blocks)


async def _tech_window(
    interaction: discord.Interaction, kid: str, note: str | None = None
) -> discord.ui.LayoutView:
    """The five combat technologies, plus one purchase / minus one."""
    strings = _strings(interaction)
    stack = wiring()
    kingdom = await _kingdom_of(stack, kid)
    purchases: dict[str, int] = {}
    if stack is not None:
        try:
            state = await stack.attacks.technology_state(kid)
            purchases = dict(state.purchases or {})
        except Exception:
            purchases = {}
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['window_title']}"),
        *_note_block(strings, note),
        discord.ui.TextDisplay(str(strings["tech_title"]).format(str(getattr(kingdom, "name", kid)))),
        discord.ui.Separator(),
    ]
    techs = _combat_technologies(stack)
    if not techs:
        blocks.append(discord.ui.TextDisplay(str(strings["no_service"])))
    else:
        row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        picker_plus = DistributorTechSelect(strings["tech_plus_button"], kid, "plus")
        picker_plus.item.options = [
            discord.SelectOption(
                label=str(display)[:100],
                value=str(key),
                description=str(strings["tech_line"]).format(purchases.get(str(key), 0))[:100],
            )
            for key, display in techs
        ]
        row.add_item(picker_plus.item)
        blocks.append(row)
        row2: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        picker_minus = DistributorTechSelect(strings["tech_minus_button"], kid, "minus")
        picker_minus.item.options = list(picker_plus.item.options)
        row2.add_item(picker_minus.item)
        blocks.append(row2)
    back: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    back.add_item(DistributorMenuButton(strings["back_button"], kid).item)
    blocks.append(back)
    return _window(blocks)


async def _status_window(interaction: discord.Interaction, kid: str) -> discord.ui.LayoutView:
    """The kingdom's full readout (the reference's 🧾 Statut)."""
    from botforge.mods.kingdom.game_clock import game_now

    strings = _strings(interaction)
    stack = wiring()
    kingdom = await _kingdom_of(stack, kid)
    names = _map_names(stack)
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['window_title']}"),
        discord.ui.TextDisplay(
            str(strings["kingdom_header"]).format(str(getattr(kingdom, "name", kid)))
        ),
    ]
    if kingdom is None or stack is None:
        blocks.append(discord.ui.TextDisplay(str(strings["no_kingdoms"])))
        blocks.append(discord.ui.Separator())
        back: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
        back.add_item(DistributorOpenButton(strings["open_button"], discord.ButtonStyle.primary).item)
        blocks.append(back)
        return _window(blocks)
    wallet = await _economy_wallet(stack, kid)
    tier = int(getattr(kingdom, "parish_tier", 1) or 1)
    tier_name = str(tier)
    try:
        tiers = list(getattr(stack.config.parish, "tiers", ()) or ())
        if 0 < tier <= len(tiers):
            tier_name = str(tiers[tier - 1].display_name)
    except Exception:
        tier_name = str(tier)
    validation = str(getattr(kingdom, "validation", "approved"))
    blocks.append(
        discord.ui.TextDisplay(
            str(strings["status_title"]).format(str(kingdom.name), validation)
        )
    )
    blocks.append(
        discord.ui.TextDisplay(str(strings["status_parish"]).format(tier_name, wallet))
    )
    hand = [str(civ) for civ in (kingdom.civilizations or [])]
    if hand:
        blocks.append(
            discord.ui.TextDisplay(str(strings["status_hand"]).format(len(hand), ", ".join(hand)))
        )
    secured = [str(civ) for civ in (kingdom.secured_civilizations or [])]
    if secured:
        blocks.append(discord.ui.TextDisplay(str(strings["status_secured"]).format(", ".join(secured))))
    territories = []
    lords: list[Any] = []
    try:
        territories = [t for t in await stack.territories.territories() if str(t.owner_kingdom_id) == str(kid)]
        lords = [
            lord
            for lord in await stack.kingdoms.lords()
            if str(lord.kingdom_id or "") == str(kid) and not lord.left
        ]
    except Exception:
        logger.warning("kingdom: distributor status read failed", exc_info=True)
    maps_line = ", ".join(names.get(str(t.map_key), str(t.map_key)) for t in territories)
    blocks.append(
        discord.ui.TextDisplay(str(strings["status_territories"]).format(len(territories), maps_line))
    )
    now = game_now()
    for lord in lords:
        role = strings["lord_role_king"] if str(lord.role) in ("king", "LordRole.KING") else strings["lord_role_lord"]
        marriage = str(lord.married_civilization) if lord.married_civilization else strings["status_married_none"]
        lock = ""
        until = getattr(lord, "marriage_locked_until", None)
        if until is not None and int(until) > int(now.timestamp()):
            lock = str(strings["status_lock_line"]).format(_fmt_ts(int(until)))
        blocks.append(
            discord.ui.TextDisplay(
                str(strings["status_lord"]).format(
                    role,
                    str(lord.display_name),
                    marriage,
                    int(lord.attack_used),
                    int(lord.defense_used),
                    lock,
                )
            )
        )
    try:
        state = await stack.attacks.technology_state(kid)
        purchases = dict(state.purchases or {})
    except Exception:
        purchases = {}
    if purchases:
        line = ", ".join(f"{key}×{count}" for key, count in sorted(purchases.items()))
        blocks.append(discord.ui.TextDisplay(str(strings["status_purchases"]).format(line)))
    else:
        blocks.append(discord.ui.TextDisplay(str(strings["status_purchases_none"])))
    blocks.append(discord.ui.Separator())
    back: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    back.add_item(DistributorMenuButton(strings["back_button"], kid).item)
    blocks.append(back)
    return _window(blocks)


# ---------------------------------------------------------------------------
# The catalog helpers (reads only, holes never raises)
# ---------------------------------------------------------------------------


def _map_names(stack: Any) -> dict[str, str]:
    """The map key → display name table of the season's catalog."""
    try:
        return {str(entry.key): str(entry.display_name) for entry in stack.config.maps}
    except Exception:
        return {}


def _combat_technologies(stack: Any) -> list[tuple[str, str]]:
    """The (key, display) combat technologies of the catalog."""
    try:
        return [(str(entry.key), str(entry.display_name)) for entry in stack.config.technologies.list]
    except Exception:
        try:
            from botforge.mods.kingdom.attacks import COMBAT_TECHNOLOGIES

            return [(str(tech), str(tech)) for tech in COMBAT_TECHNOLOGIES]
        except Exception:
            return []


def _fmt_ts(until: int) -> str:
    """Format a unix timestamp in Paris time (« 29/08 19:15 »)."""
    from .common import fmt_paris

    return fmt_paris(until)


async def _free_maps(stack: Any) -> list[str]:
    """The catalog maps still undrawn this season."""
    if stack is None:
        return []
    try:
        drawn = set(await stack.territories.drawn_map_keys())
        catalog = [str(entry.key) for entry in stack.config.maps]
        return [key for key in catalog if key not in drawn]
    except Exception:
        return []


async def _civ_rows(stack: Any, kid: str) -> list[dict[str, str]]:
    """Every catalog civilization with its status for the kingdom."""
    rows: list[dict[str, str]] = []
    if stack is None:
        return rows
    try:
        kingdom = await _kingdom_of(stack, kid)
        hand = {str(civ) for civ in (getattr(kingdom, "civilizations", ()) or ())}
        lords = await stack.kingdoms.lords()
        married: dict[str, str] = {}
        for lord in lords:
            civ = getattr(lord, "married_civilization", None)
            if civ:
                married[str(civ)] = str(lord.display_name)
        for entry in stack.config.civilizations:
            key = str(entry.civilization if hasattr(entry, "civilization") else entry.key)
            display = str(entry.display_name)
            if key in hand:
                rows.append({"key": key, "display_name": display, "status": "hand", "detail": ""})
            elif key in married:
                rows.append(
                    {"key": key, "display_name": display, "status": "married", "detail": married[key]}
                )
            else:
                rows.append({"key": key, "display_name": display, "status": "free", "detail": ""})
    except Exception:
        logger.warning("kingdom: distributor civ rows read failed", exc_info=True)
    return rows


def _civ_options(
    strings: dict[str, str],
    rows: list[dict[str, str]],
    page: int,
    mode: str,
    kingdom: Any,
    /,
) -> list[discord.SelectOption]:
    """Render one page of the civ select with its old status descriptions."""
    secured = {str(civ) for civ in (getattr(kingdom, "secured_civilizations", ()) or ())}
    start = page * PAGE_SIZE
    options: list[discord.SelectOption] = []
    for row in rows[start : start + PAGE_SIZE]:
        if mode == "remove":
            description = (
                strings["civ_secured"] if row["key"] in secured else strings["civ_status_hand"]
            )
        elif row["status"] == "hand":
            description = strings["civ_status_hand"]
        elif row["status"] == "married":
            description = str(strings["civ_status_married"]).format(row["detail"])
        else:
            description = strings["civ_status_free"]
        options.append(
            discord.SelectOption(
                label=row["display_name"][:100], description=description[:100], value=row["key"]
            )
        )
    return options


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
        strings = _strings(interaction)
        yes: discord.ui.Button[Any] = discord.ui.Button(
            label=str(strings["destruct_confirm_button"])[:80],
            custom_id=f"{_NS}:destruct:yes",
            style=discord.ButtonStyle.danger,
        )
        no: discord.ui.Button[Any] = discord.ui.Button(
            label=str(strings["destruct_cancel_button"])[:80],
            custom_id=f"{_NS}:destruct:no",
            style=discord.ButtonStyle.secondary,
        )
        row = discord.ui.ActionRow()
        row.add_item(yes)
        row.add_item(no)

        async def on_yes(target: discord.Interaction) -> None:
            """The confirmed wipe — delete_kingdom via the service seam."""
            from .common import service_failure_note
            from .settings_panel import _safe_followup

            target_strings = _strings(target)
            await target.response.defer(ephemeral=True)
            stack = wiring()
            if stack is None:
                await target.followup.send(target_strings["no_service"], ephemeral=True)
                return
            try:
                from botforge.mods.kingdom.service import TEST_KINGDOM_ID

                kingdom = await stack.kingdoms.delete_kingdom(str(TEST_KINGDOM_ID))
                note = str(target_strings["destruct_done"]).format(str(getattr(kingdom, "name", "")))
            except Exception as exc:  # noqa: BLE001 — the panel reports, never raises
                logger.warning("kingdom: test-kingdom destruct failed", exc_info=True)
                note = service_failure_note(target_strings, "error", exc)
            await _safe_followup(target, note)

        async def on_no(target: discord.Interaction) -> None:
            """The cancelled wipe — a quiet close."""
            await target.response.defer(ephemeral=True)

        yes.callback = on_yes  # type: ignore[method-assign]
        no.callback = on_no  # type: ignore[method-assign]
        blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
            discord.ui.TextDisplay(f"# {strings['destruct_confirm_title']}"),
            discord.ui.TextDisplay(str(strings["destruct_confirm_hint"])),
            discord.ui.Separator(),
            row,
        ]
        await open_unique_ephemeral(interaction, view=_window(blocks))


class DistributorKingdomSelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]], template=rf"{_NS}:pick$"
):
    """The kingdom picker — the choice opens the kingdom's own menu."""

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
        view = await _menu_window(interaction, kingdom_id)
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
                kingdom = await _kingdom_of(stack, kid)
                if kingdom is None:
                    raise ValueError(str(strings["no_kingdoms"]))
                hand = {str(civ) for civ in getattr(kingdom, "civilizations", ()) or ()}
                pool = [
                    str(getattr(entry, "civilization", None) or entry.key)
                    for entry in stack.config.civilizations
                    if str(getattr(entry, "civilization", None) or entry.key) not in hand
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


# ---------------------------------------------------------------------------
# The cockpit's restart-proof items (distributeur-v2)
# ---------------------------------------------------------------------------


class DistributorMenuButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:menu:(?P<kid>[a-z0-9-]+)$",
):
    """« 🔙 Royaume » — back to the kingdom's own category menu."""

    def __init__(self, label: str, kingdom_id: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:menu:{kingdom_id}"[:100],
                style=discord.ButtonStyle.secondary,
            )
        )
        self.kid = kingdom_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        return cls(_strings(interaction)["back_button"], match["kid"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the action (ephemeral, never a raise)."""

        if not await _guard(interaction):
            return
        kid = str(getattr(self, "kid", ""))
        await open_unique_ephemeral(interaction, view=await _menu_window(interaction, kid))


class DistributorCatButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=(
        rf"{_NS}:cat:(?P<kid>[a-z0-9-]+):"
        rf"(?P<cat>alliance-add|alliance-remove|treasury|parish|territories|lord|tech|status)$"
    ),
):
    """One cockpit category door — the kingdom and the category ride the id."""

    def __init__(self, label: str, kingdom_id: str, category: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:cat:{kingdom_id}:{category}"[:100],
                style=discord.ButtonStyle.primary,
            )
        )
        self.kid = kingdom_id
        self.category = category

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        return cls(_strings(interaction)[f"cat_{match['cat'].replace('-', '_')}"], match["kid"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then open the category's own window."""

        if not await _guard(interaction):
            return
        kid = str(getattr(self, "kid", ""))
        category = str(getattr(self, "category", ""))
        if category == "alliance-add":
            view = await _civ_window(interaction, kid, "add", 0)
        elif category == "alliance-remove":
            view = await _civ_window(interaction, kid, "remove", 0)
        elif category == "treasury":
            view = await _treasury_window(interaction, kid)
        elif category == "parish":
            view = await _parish_window(interaction, kid)
        elif category == "territories":
            view = await _territories_window(interaction, kid)
        elif category == "lord":
            view = await _lord_window(interaction, kid)
        elif category == "tech":
            view = await _tech_window(interaction, kid)
        else:
            view = await _status_window(interaction, kid)
        await open_unique_ephemeral(interaction, view=view)


class DistributorCivPageButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:civpage:(?P<kid>[a-z0-9-]+):(?P<mode>add|remove):(?P<page>\d+):(?P<dir>prev|next)$",
):
    """The civ select's ◀ ▶ page turn."""

    def __init__(self, label: str, kingdom_id: str, mode: str, page: int, direction: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:civpage:{kingdom_id}:{mode}:{max(0, int(page))}:{direction}"[:100],
                style=discord.ButtonStyle.secondary,
            )
        )
        self.kid = kingdom_id
        self.mode = mode
        self.page = int(page)
        self.direction = direction

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        key = "prev_page" if match["dir"] == "prev" else "next_page"
        label = _strings(interaction)[key]
        return cls(label, match["kid"], match["mode"], int(match["page"]), match["dir"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then turn to the neighbour page."""

        if not await _guard(interaction):
            return
        page = int(getattr(self, "page", 0))
        step = 1 if str(getattr(self, "direction", "")) == "next" else -1
        view = await _civ_window(
            interaction, str(getattr(self, "kid", "")), str(getattr(self, "mode", "add")), page + step
        )
        await open_unique_ephemeral(interaction, view=view)


class DistributorCivSelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]],
    template=rf"{_NS}:civsel:(?P<kid>[a-z0-9-]+):(?P<mode>add|remove):(?P<page>\d+)$",
):
    """The paged civ select — the choice adds or removes the alliance."""

    def __init__(self, placeholder: str, kingdom_id: str, mode: str, page: int) -> None:
        super().__init__(
            discord.ui.Select(
                placeholder=placeholder[:100],
                custom_id=f"{_NS}:civsel:{kingdom_id}:{mode}:{max(0, int(page))}"[:100],
                min_values=1,
                max_values=1,
            )
        )
        self.kid = kingdom_id
        self.mode = mode
        self.page = int(page)

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the select from the wire (locale placeholder, stable id)."""

        return cls(_strings(interaction)["civ_placeholder"], match["kid"], match["mode"], int(match["page"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then add or remove the chosen civilization."""

        if not await _guard(interaction):
            return
        from botforge.mods.kingdom.game_clock import game_now

        from .common import service_failure_note
        from .settings_panel import _safe_followup

        strings = _strings(interaction)
        values = [str(v) for v in (self.item.values or [])]
        civ = values[0] if values else ""
        kid = str(getattr(self, "kid", ""))
        mode = str(getattr(self, "mode", "add"))
        page = int(getattr(self, "page", 0))
        stack = wiring()
        attempted = False
        try:
            if stack is None or not civ:
                await interaction.response.defer(ephemeral=True)
                return
            kingdom = await _kingdom_of(stack, kid)
            if kingdom is None:
                raise ValueError(str(strings["no_kingdoms"]))
            hand = [str(item) for item in (kingdom.civilizations or [])]
            lords = await stack.kingdoms.lords()
            married = {
                str(getattr(lord, "married_civilization", None) or "")
                for lord in lords
            }
            if mode == "add":
                if civ in hand:
                    raise ValueError(str(strings["civ_status_hand"]))
                if civ in married:
                    raise ValueError(str(strings["civ_status_married"]).format(""))
                kingdom.civilizations = [*hand, civ]
                kingdom.record_acquisition(civ, "distributor", int(game_now().timestamp()))
                await stack.kingdoms.save_kingdom(kingdom)
                note = str(strings["civ_add_done"]).format(str(kingdom.name), civ)
            else:
                if civ not in hand:
                    raise ValueError(str(strings["civ_secured"]))
                kingdom.civilizations = [item for item in hand if item != civ]
                await stack.kingdoms.save_kingdom(kingdom)
                note = str(strings["civ_remove_done"]).format(civ, str(kingdom.name))
            attempted = True
            await open_unique_ephemeral(
                interaction, view=await _civ_window(interaction, kid, mode, page, note)
            )
        except Exception as exc:  # noqa: BLE001 — the panel reports, never raises
            logger.warning("kingdom: distributor civ %s failed", mode, exc_info=True)
            if not attempted and not interaction.response.is_done():
                await _safe_followup(interaction, service_failure_note(strings, "error", exc))


class DistributorTreasuryButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:tr:(?P<kid>[a-z0-9-]+):(?P<op>p5|p1|m1|m5|set)$",
):
    """One treasury lever — +/+/-/- or the exact-value modal."""

    def __init__(self, label: str, kingdom_id: str, op: str, style: discord.ButtonStyle) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:tr:{kingdom_id}:{op}"[:100],
                style=style or discord.ButtonStyle.success,
            )
        )
        self.kid = kingdom_id
        self.op = op

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        strings = _strings(interaction)
        op = match["op"]
        key = {
            "p5": "tr_plus5_button",
            "p1": "tr_plus1_button",
            "m1": "tr_minus1_button",
            "m5": "tr_minus5_button",
            "set": "treasury_set",
        }[op]
        style = (
            discord.ButtonStyle.secondary
            if op in ("m1", "m5")
            else discord.ButtonStyle.primary
            if op == "set"
            else discord.ButtonStyle.success
        )
        return cls(strings[key], match["kid"], op, style)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then run the treasury lever."""

        if not await _guard(interaction):
            return
        strings = _strings(interaction)
        kid = str(getattr(self, "kid", ""))
        op = str(getattr(self, "op", ""))
        stack = wiring()
        if op == "set":
            await interaction.response.send_modal(_TreasurySetModal(kid, str(strings["value_modal_label"])[:45]))
            return
        if stack is None:
            await interaction.response.defer(ephemeral=True)
            return
        deltas = {"p5": 5, "p1": 1, "m1": -1, "m5": -5}
        try:
            delta = deltas[op]
            if delta > 0:
                await stack.economy.grant_tech_points(kid, delta)
            else:
                current = int(await stack.economy.wallet(kid))
                spend = max(0, min(current, -delta))
                if spend > 0:
                    await stack.economy.spend_points(kid, spend)
            note = str(strings["treasury_set_done"]).format(
                strings["treasury_field"], int(await stack.economy.wallet(kid))
            )
            await open_unique_ephemeral(
                interaction, view=await _treasury_window(interaction, kid, note)
            )
        except Exception:  # noqa: BLE001 — the panel reports, never raises
            logger.warning("kingdom: distributor treasury %s failed", op, exc_info=True)
            await interaction.response.defer(ephemeral=True)


class _TreasurySetModal(discord.ui.Modal):
    """The set-exact treasury modal (≤45-char labels, plain ephemeral)."""

    def __init__(self, kingdom_id: str, label: str) -> None:
        strings = distributor_strings("fr")
        super().__init__(title=str(strings["value_modal_title"])[:45], timeout=600)
        self.kid = kingdom_id
        self.value: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label=str(label)[:45],
            custom_id=f"{_NS}:tset:{kingdom_id}",
            required=True,
            max_length=10,
        )
        self.add_item(self.value)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Apply the delta towards the target value, then re-render."""
        from .common import service_failure_note
        from .settings_panel import _safe_followup

        strings = distributor_strings(str(getattr(interaction, "locale", "") or "fr"))
        raw = str(self.value.value or "").strip()
        try:
            target = int(raw)
            if target < 0:
                raise ValueError(raw)
        except ValueError:
            await interaction.response.defer(ephemeral=True)
            await _safe_followup(interaction, str(strings["value_modal_bad"]))
            return
        stack = wiring()
        if stack is None:
            await interaction.response.defer(ephemeral=True)
            await _safe_followup(interaction, str(strings["no_service"]))
            return
        try:
            current = int(await stack.economy.wallet(self.kid))
            if target > current:
                await stack.economy.grant_tech_points(self.kid, target - current)
            elif target < current:
                await stack.economy.spend_points(self.kid, current - target)
            note = str(strings["treasury_set_done"]).format(strings["treasury_field"], target)
            await open_unique_ephemeral(
                interaction, view=await _treasury_window(interaction, self.kid, note)
            )
        except Exception as exc:  # noqa: BLE001 — the panel reports, never raises
            logger.warning("kingdom: distributor treasury set failed", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            await _safe_followup(interaction, service_failure_note(strings, "error", exc))


class DistributorParishButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:par:(?P<kid>[a-z0-9-]+):(?P<tier>[123])$",
):
    """One Paroisse palier door — force the tier (admin lever)."""

    def __init__(self, label: str, kingdom_id: str, tier: int) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:par:{kingdom_id}:{int(tier)}"[:100],
                style=discord.ButtonStyle.primary,
            )
        )
        self.kid = kingdom_id
        self.tier = int(tier)

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        strings = _strings(interaction)
        return cls(f"{match['tier']}", match["kid"], int(match["tier"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Guard the click, then force the palier."""

        if not await _guard(interaction):
            return
        strings = _strings(interaction)
        kid = str(getattr(self, "kid", ""))
        tier = int(getattr(self, "tier", 1))
        stack = wiring()
        attempted = False
        try:
            if stack is None:
                await interaction.response.defer(ephemeral=True)
                return
            kingdom = await stack.kingdoms.force_parish_tier(kid, tier)
            note = str(strings["parish_tier_set"]).format(str(getattr(kingdom, "parish_tier", tier)))
            attempted = True
            await open_unique_ephemeral(
                interaction, view=await _parish_window(interaction, kid, note)
            )
        except Exception:  # noqa: BLE001 — the panel reports, never raises
            logger.warning("kingdom: distributor parish %s failed", tier, exc_info=True)
            if not attempted and not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)


class DistributorTerritoryButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:terr:(?P<kid>[a-z0-9-]+):(?P<act>give|transfer|retire|replace|shield|unshield)$",
):
    """One territory lever door — opens the matching pick window."""

    def __init__(self, label: str, kingdom_id: str, act: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:terr:{kingdom_id}:{act}"[:100],
                style=discord.ButtonStyle.primary,
            )
        )
        self.kid = kingdom_id
        self.act = act

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        """Rebuild the button from the wire (locale label, stable id)."""

        strings = _strings(interaction)
