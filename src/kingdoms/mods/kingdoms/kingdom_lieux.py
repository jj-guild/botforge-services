"""Kingdoms mod — lieux-et-conseil-v1 (Drasah 01/11): the realm hub.

The Le-Royaume refonte: the pinned sheet becomes a CASTLE hub — the
stats move into the ⚔️ Salle du conseil, every place opens as an
ephemeral view with its illustration, and nothing else changes for the
players until the gate opens.

canary-gate-v1: the whole refonte renders ONLY for the kingdom ids
listed below (THE DECLARATION WINS — never a live-state derivation,
leçon divider-gating-v2). During the beta: Nilrem alone. Removing the
id from the list (empty tuple) generalises to every kingdom.

fenetre-unique-v2: every lieu view rides the shared single-window
registry — one live ephemeral per player, whatever opens it.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import discord

logger = logging.getLogger("kingdoms.kingdom_lieux")

# canary-gate-v1 (Drasah 01/11): the ids allowed to render the new hub.
# Empty the tuple (or delete the ids) to generalise — no other change.
CANARY_REALM_KINGDOM_IDS: tuple[str, ...] = ("k-nilrem",)

_LIEUX_ASSETS = Path(__file__).resolve().parent / "assets" / "lieux"

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "hub_flavor": (
            "The castle gates open — every place of the realm lives "
            "behind its door. The state of the kingdom sits in the "
            "Council room."
        ),
        "entree_button": "🏰 Entrance",
        "entree_title": "Where would you like to go?",
        "conseil_button": "⚔️ Council room",
        "remparts_button": "🧭 Ramparts",
        "comptes_button": "🏛️ Chamber of accounts",
        "paroisse_button": "⛪ Parish",
        "voliere_button": "🏗️ Aviary",
        "not_lord": "Only the lords of this kingdom may enter its places.",
        "no_service": "The Kingdoms service is not wired.",
        "conseil_title": "⚔️ Council room — {0}",
        "conseil_actions": "Action cards",
        "sortir_button": "🚪 Leave",
    },
    "fr": {
        "hub_flavor": (
            "Les portes du château s'ouvrent — chaque lieu du royaume "
            "vit derrière sa porte. L'état du royaume siège en Salle "
            "du conseil."
        ),
        "entree_button": "🏰 Entrée",
        "entree_title": "Où souhaitez-vous vous rendre ?",
        "conseil_button": "⚔️ Salle du conseil",
        "remparts_button": "🧭 Remparts",
        "comptes_button": "🏛️ Chambre des comptes",
        "paroisse_button": "⛪ Paroisse",
        "voliere_button": "🏗️ Volière",
        "not_lord": "Seuls les seigneurs du royaume peuvent entrer dans ses lieux.",
        "no_service": "Le service Kingdoms n'est pas câblé.",
        "conseil_title": "⚔️ Salle du conseil — {0}",
        "conseil_actions": "Cartes d'action",
        "sortir_button": "🚪 Sortir",
    },
}


def _strings(locale: str) -> dict[str, str]:
    return STRINGS["fr"] if str(locale).lower().startswith("fr") else STRINGS["en"]


def _locale(interaction: discord.Interaction) -> str:
    return str(interaction.locale) if interaction.locale else "fr"


def is_canary_realm(kingdom: Any | None) -> bool:
    """True when the kingdom renders the new hub (the gate decides)."""
    return kingdom is not None and str(getattr(kingdom, "id", "")) in CANARY_REALM_KINGDOM_IDS


def _lieu_file(filename_on_disk: str, filename: str) -> discord.File | None:
    """Best-effort illustration of one lieu (deployment-local asset)."""
    try:
        path = _LIEUX_ASSETS / filename_on_disk
        if not path.is_file():
            logger.warning("KINGDOM LIEUX: illustration %s missing", filename_on_disk)
            return None
        return discord.File(path, filename=filename, spoiler=False)
    except Exception:
        logger.warning("KINGDOM LIEUX: illustration %s read failed", filename_on_disk, exc_info=True)
        return None


def _lieu_files(filename_on_disk: str, filename: str) -> list[discord.File]:
    file = _lieu_file(filename_on_disk, filename)
    return [file] if file is not None else []


def hub_file() -> discord.File | None:
    """The castle illustration of the hub (Royaume.png)."""
    return _lieu_file("Royaume.png", "royaume.png")


async def _require_lord_kingdom(
    interaction: discord.Interaction,
    wiring: Any,
    strings: dict[str, str],
) -> tuple[Any, Any] | tuple[None, None]:
    """Resolve the clicker's active lord + kingdom (admin-as-king wins)."""
    from kingdoms.mods.kingdoms.kingdom_persistent import _lord_of

    if wiring.kingdoms_service is None:
        await interaction.response.send_message(strings["no_service"], ephemeral=True)
        return (None, None)
    lord = await _lord_of(
        wiring.kingdoms_service, str(interaction.user.id), wiring.bot_admins
    )
    if lord is None or getattr(lord, "left", False):
        await interaction.response.send_message(strings["not_lord"], ephemeral=True)
        return (None, None)
    kingdoms = await wiring.kingdoms_service.kingdoms()
    kingdom = next(
        (k for k in kingdoms if str(k.id) == str(getattr(lord, "kingdom_id", None))),
        None,
    )
    if kingdom is None:
        await interaction.response.send_message(strings["not_lord"], ephemeral=True)
        return (None, None)
    return (lord, kingdom)


def _lieu_view_class(kind: str):
    """Build the DynamicItem class of one hub door."""

    class _KingdomLieuButton(
        discord.ui.DynamicItem[discord.ui.Button[Any]],
        template=rf"kingdoms:lieux:{kind}",
    ):
        """The restart-proof hub door of one lieu (canary render only)."""

        def __init__(self, label: str) -> None:
            super().__init__(
                discord.ui.Button(
                    label=label[:80],
                    custom_id=f"kingdoms:lieux:{kind}",
                    style=discord.ButtonStyle.secondary,
                )
            )

        @classmethod
        async def from_custom_id(
            cls,
            interaction: discord.Interaction,
            item: discord.ui.Item[Any],
            match: re.Match[str],
            /,
        ) -> _KingdomLieuButton:
            """Rebuild from the wire — THIS module's strings only."""
            return cls(_strings(_locale(interaction))[f"{kind}_button"])

        async def callback(self, interaction: discord.Interaction) -> None:
            await _open_lieu(interaction, kind)

    _KingdomLieuButton.__name__ = f"KingdomLieu{kind.capitalize()}Button"
    _KingdomLieuButton.__qualname__ = _KingdomLieuButton.__name__
    return _KingdomLieuButton


KingdomLieuConseilButton = _lieu_view_class("conseil")
KingdomLieuRempartsButton = _lieu_view_class("remparts")
KingdomLieuComptesButton = _lieu_view_class("comptes")
KingdomLieuParoisseButton = _lieu_view_class("paroisse")
KingdomLieuVoliereButton = _lieu_view_class("voliere")


def hub_buttons(locale: str) -> list[Any]:
    """The five doors (they live in the Entrée chooser view)."""
    strings = _strings(locale)
    return [
        KingdomLieuConseilButton(strings["conseil_button"]),
        KingdomLieuRempartsButton(strings["remparts_button"]),
        KingdomLieuComptesButton(strings["comptes_button"]),
        KingdomLieuParoisseButton(strings["paroisse_button"]),
        KingdomLieuVoliereButton(strings["voliere_button"]),
    ]


def entree_view(locale: str) -> Any:
    """The ephemeral chooser behind 🏰 Entrée — « Où souhaitez-vous

    vous rendre ? » — the five doors in one ActionRow (fenetre-unique-v2
    keeps it the clicker's single live window).
    """
    import discord

    strings = _strings(locale)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.TextDisplay(f"## {strings['entree_title']}"))
    view.add_item(discord.ui.ActionRow(*hub_buttons(locale)))
    return view


def _green(button: Any) -> Any:
    """lieux-rows-v1: a default place action renders GREEN."""
    button.item.style = discord.ButtonStyle.success
    return button


def _gray(button: Any) -> Any:
    """lieux-rows-v1: an out-of-stock card renders GRAY and disabled."""
    button.item.style = discord.ButtonStyle.secondary
    button.item.disabled = True
    return button


def _stock_style(button: Any, has_stock: bool) -> Any:
    """Green while held, gray+disabled otherwise (never hidden)."""
    return _green(button) if has_stock else _gray(button)


class KingdomLieuSortirButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:lieux:sortir",
):
    """The red 🚪 Sortir of every lieu view (lieux-rows-v1, Drasah 01/11).

    Line 1 rule: the place's default actions render green and Sortir
    closes the LAST slot in red — one click walks the player back to
    the Entrée orientation (the single ephemeral window is REPLACED,
    fenetre-unique-v2).
    """

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdoms:lieux:sortir",
                style=discord.ButtonStyle.danger,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "KingdomLieuSortirButton":
        """Rebuild from the wire — THIS module's strings only."""
        return cls(_strings(_locale(interaction))["sortir_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await _open_entree(interaction)


def _sortir(locale: str) -> KingdomLieuSortirButton:
    """The red exit of a lieu view."""
    return KingdomLieuSortirButton(_strings(locale)["sortir_button"])


async def _open_entree(interaction: discord.Interaction) -> None:
    """Open the Entrée chooser as the clicker's single ephemeral window."""
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        _open_unique_ephemeral,
        _strings as _merged_strings,
        _wiring,
    )

    locale = _locale(interaction)
    strings = _merged_strings(locale)
    wiring = _wiring()
    if wiring.kingdoms_service is None:
        await interaction.response.send_message(
            _strings(locale)["no_service"], ephemeral=True
        )
        return
    lord, kingdom = await _require_lord_kingdom(
        interaction, wiring, _strings(locale)
    )
    if lord is None or kingdom is None:
        return
    await _open_unique_ephemeral(interaction, view=entree_view(locale))


class KingdomLieuEntreeButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:lieux:entree",
):
    """The hub's ONE door — 🏰 Entrée opens the ephemeral chooser."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdoms:lieux:entree",
                style=discord.ButtonStyle.primary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "KingdomLieuEntreeButton":
        """Rebuild from the wire — THIS module's strings only."""
        return cls(_strings(_locale(interaction))["entree_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await _open_entree(interaction)


def hub_entree_button(locale: str) -> KingdomLieuEntreeButton:
    """The single 🏰 Entrée button the canary hub renders."""
    return KingdomLieuEntreeButton(_strings(locale)["entree_button"])


def canary_salon_display(key: str, name: str, kingdom: Any) -> str:
    """lieux-et-conseil-v1: the council salon becomes « Discussions ».

    Only the canary kingdoms adopt the new display — the player
    kingdoms keep the current name while the gate is active.
    """
    if key == "salle-du-conseil" and is_canary_realm(kingdom):
        return "💬 discussions"
    return name


async def _open_lieu(interaction: discord.Interaction, kind: str) -> None:
    """Open one lieu as the clicker's single ephemeral window."""
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        _open_unique_ephemeral,
        _strings as _merged_strings,
        _wiring,
    )

    locale = _locale(interaction)
    strings = _merged_strings(locale)
    wiring = _wiring()
    if wiring.kingdoms_service is None:
        await interaction.response.send_message(
            _strings(locale)["no_service"], ephemeral=True
        )
        return
    lord, kingdom = await _require_lord_kingdom(interaction, wiring, _strings(locale))
    if lord is None or kingdom is None:
        return
    if kind == "comptes":
        # The ledger is a defer+followup window (heavy mosaic paint).
        await _open_comptes(interaction, wiring, kingdom, strings, locale)
        return
    from kingdoms.mods.kingdoms.kingdom_realm_content import (
        _build_church,
        _build_patrol,
        _gather_state,
    )

    state = await _gather_state(kingdom, wiring)
    if kind == "conseil":
        view, files = build_conseil_view(strings, kingdom, state, wiring, locale)
    elif kind == "remparts":
        view, files = (
            _build_patrol(
                strings,
                kingdom,
                state,
                media="attachment://rempart.png",
                rows=_remparts_rows(strings, state, wiring, locale),
            ),
            _lieu_files("Rempart.png", "rempart.png"),
        )
    elif kind == "paroisse":
        view, files = (
            _build_church(
                strings,
                kingdom,
                state,
                media="attachment://paroisse.png",
                rows=_paroisse_rows(strings, kingdom, state, locale),
            ),
            _paroisse_files(state),
        )
    else:  # voliere
        view, files = await _build_voliere(wiring, kingdom, strings, locale)
    await _open_unique_ephemeral(interaction, view=view, files=files or None)


def _paroisse_files(state: dict[str, Any]) -> list[discord.File]:
    """The parish illustration follows the live tier (Chapelle→Cathédrale)."""
    tier = 1
    try:
        tier = min(3, max(1, int((state.get("parish") or {}).get("tier", 1) or 1)))
    except Exception:
        tier = 1
    return _lieu_files(f"paroisse{tier}.png", "paroisse.png")


async def _build_voliere(
    wiring: Any, kingdom: Any, strings: dict[str, Any], locale: str
) -> tuple[Any, list[discord.File]]:
    """The Volière lieu view — the voliere panel content + illustration."""
    from kingdoms.mods.kingdoms.kingdom_voliere_panel import (
        _voliere_content,
        _voliere_state,
        _voliere_view,
    )

    voliere_state = await _voliere_state(wiring, str(kingdom.id))
    content = await _voliere_content(wiring, kingdom, strings, voliere_state)
    view = _voliere_view(strings, voliere_state)
    # The lieu view wraps the voliere content in the lieu panel so the
    # illustration can ride with it (fenetre-unique keeps one window).
    from kingdoms.mods.kingdoms.kingdom_realm_content import _panel_view_with_buttons

    return (
        _panel_view_with_buttons(
            str(strings.get("voliere_title", "Volière")),
            str(content),
            "kingdoms:realm:view:lieu-voliere",
            discord.Colour.green(),
            [_sortir(locale)],
            media="attachment://voliere.png",
        ),
        _lieu_files("voliere.png", "voliere.png"),
    )


def build_conseil_view(
    strings: dict[str, Any],
    kingdom: Any,
    state: dict[str, Any],
    wiring: Any,
    locale: str,
) -> tuple[Any, list[discord.File]]:
    """The ⚔️ Salle du conseil — the state of the realm + action cards."""
    import discord

    from kingdoms.mods.kingdoms.kingdom_realm_content import (
        _overview_body,
        _panel_view_with_buttons,
    )
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        KingdomMarketTechButton,
        KingdomSeigneurieOpenButton,
        KingdomTraquenardButton,
    )

    lieu = _strings(locale)
    body = "\n".join(
        [
            _overview_body(strings, kingdom, state),
            "",
            f"## {lieu['conseil_actions']}",
        ]
    )
    purchases = dict(state.get("purchases") or {})
    # lieux-rows-v1 (Drasah 01/11) — the council button RULES:
    # line 1 = the default action (green) + Sortir (red, last),
    # line 2 = the technology cards, ALWAYS visible — green while
    # held, gray+disabled while out of stock (never hidden).
    from kingdoms.mods.kingdoms.kingdom_expedition_panel import (
        KingdomExpeditionOpenButton,
        _strings as _expedition_strings,
    )

    row_one = [
        _green(KingdomSeigneurieOpenButton(strings["seigneurie_open_button"])),
        _sortir(locale),
    ]
    row_two = [
        _stock_style(
            KingdomExpeditionOpenButton(_expedition_strings(locale)["open_button"]),
            int(purchases.get("explorateur_stock", 0) or 0) > 0,
        ),
        _stock_style(
            KingdomTraquenardButton(strings),
            int(purchases.get("traquenard", 0) or 0) > 0,
        ),
    ]
    view = _panel_view_with_buttons(
        lieu["conseil_title"].format(getattr(kingdom, "name", "")),
        body,
        "kingdoms:realm:view:lieu-conseil",
        discord.Colour.gold(),
        row_one,
        media="attachment://salle_du_conseil.png",
        rows=[row_one, row_two],
    )
    return view, _lieu_files("salle du conseil.png", "salle_du_conseil.png")


def _remparts_rows(
    strings: dict[str, Any],
    state: dict[str, Any],
    wiring: Any,
    locale: str,
) -> list[list[Any]]:
    """lieux-rows-v1 — the Remparts button rules (Drasah 01/11).

    Line 1: the default war actions (green) + Sortir (red, last).
    Line 2: the placement + card buttons — Garde / Patrouille 1 / 2
    green while their stock/unlock is held (gray+disabled otherwise)
    and the Jeu d'armes card, green while affordable, gray otherwise.
    """
    from kingdoms.mods.kingdoms.kingdom_attack_panel import (
        KingdomAttackManagerButton,
        KingdomDefenseManagerButton,
    )
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        KingdomMarketTechButton,
        KingdomRempartsGuardButton,
        KingdomRempartsPatrouilleButton,
    )

    purchases = dict(state.get("purchases") or {})
    row_one = [
        _green(
            KingdomDefenseManagerButton(
                strings.get("defense_manager_button", "🛡️ Gestion de la défense")
            )
        ),
        _green(
            KingdomAttackManagerButton(
                strings.get("attack_manager_button", "⚔️ Gestion d'attaque")
            )
        ),
        _sortir(locale),
    ]
    guard = _stock_style(
        KingdomRempartsGuardButton(strings),
        int(purchases.get("garde_royale_stock", 0) or 0) > 0,
    )
    patrols = []
    for slot_no in (1, 2):
        patrols.append(
            _stock_style(
                KingdomRempartsPatrouilleButton(slot_no, strings),
                f"patrouille_unlock_{slot_no}" in purchases
                or f"patrouille_slot_{slot_no}" in purchases,
            )
        )
    # Jeu d'armes lives HERE now (Drasah 01/11): the card activates on
    # the Ramparts — green while the treasury affords it, gray+disabled
    # otherwise (never hidden).
    tech_cost = _jeu_d_armes_cost(wiring)
    label = str(strings.get("market_tech", {}).get("jeu_d_armes", "Jeu d'armes"))
    jeu = KingdomMarketTechButton(
        "jeu_d_armes", f"{label} — {tech_cost} ⚙️", discord.ButtonStyle.success
    )
    if int(state.get("wallet", 0) or 0) < tech_cost:
        _gray(jeu)
    return [row_one, [guard, *patrols, jeu]]


def _paroisse_rows(
    strings: dict[str, Any],
    kingdom: Any,
    state: dict[str, Any],
    locale: str,
) -> list[list[Any]]:
    """lieux-rows-v1 — the Paroisse button rules (Drasah 01/11).

    Line 1: the parish's default actions (green) + Sortir (red, last).
    Line 2: the 💒 Mariage arrangé card, ALWAYS visible — green from the
    Église palier while a token is held, gray+disabled otherwise.
    """
    from kingdoms.mods.kingdoms.kingdom_realm_content import _church_buttons

    base = _church_buttons(strings, kingdom, state)
    arrange: Any = None
    others: list[Any] = []
    for button in base:
        if str(getattr(button.item, "custom_id", "")) == "kingdoms:church:arrange":
            arrange = button
        else:
            others.append(button)
    row_one: list[Any] = []
    for button in others:
        # The max-palier Améliorer stays disabled (its own convention).
        if not button.item.disabled:
            _green(button)
        row_one.append(button)
    row_one.append(_sortir(locale))
    parish = state.get("parish") or {}
    tier = int(parish.get("tier", 1) or 1)
    stock = int(getattr(kingdom, "arranged_marriage_stock", 0) or 0)
    if arrange is None:
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            KingdomChurchArrangeButton,
        )

        arrange = KingdomChurchArrangeButton(strings, 0)
    _stock_style(arrange, tier >= 2 and stock > 0)
    return [row_one, [arrange]]


def _jeu_d_armes_cost(wiring: Any) -> int:
    """The configured Jeu d'armes cost (default ladder if unwired)."""
    try:
        technologies = getattr(getattr(wiring, "kingdoms_service", None), "config", None)
        technologies = getattr(technologies, "technologies", None)
        if technologies is not None:
            return int(getattr(technologies, "jeu_d_armes"))
    except Exception:
        pass
    from kingdoms.mods.kingdoms.config import TechnologyCosts

    return int(getattr(TechnologyCosts(), "jeu_d_armes"))


async def _open_comptes(
    interaction: discord.Interaction,
    wiring: Any,
    kingdom: Any,
    strings: dict[str, Any],
    locale: str,
) -> None:
    """The 🏛️ Chambre des comptes — the ledger sheet + illustration.

    Mirrors the ledger button (defer, heavy paint, followup window)
    with the lieu illustration riding along the card attachments.
    """
    from time import monotonic

    from kingdoms.mods.kingdoms.kingdom_persistent import (
        _EPHEMERAL_WINDOWS,
        _close_previous_ephemeral,
        _market_ledger_content,
    )

    await interaction.response.defer(ephemeral=True)
    try:
        content, card_files, card_info_view = await _market_ledger_content(
            wiring, kingdom, strings
        )
    except Exception:
        logger.warning("KINGDOM LIEUX: ledger sheet build failed", exc_info=True)
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _market_error_note,
        )

        await interaction.followup.send(
            _market_error_note(Exception("ledger"), strings), ephemeral=True
        )
        return
    files = list(card_files or []) + _lieu_files(
        "chambre des comptes.png", "chambre_des_comptes.png"
    )
    # lieux-rows-v1: the ledger window carries the red Sortir too.
    if card_info_view is None:
        card_info_view = discord.ui.View(timeout=None)
    try:
        card_info_view.add_item(_sortir(locale))
    except Exception:
        logger.warning("KINGDOM LIEUX: ledger Sortir add failed", exc_info=True)
    user_id = str(getattr(interaction.user, "id", ""))
    await _close_previous_ephemeral(user_id)
    window = await interaction.followup.send(
        content, files=files, view=card_info_view, ephemeral=True
    )
    _EPHEMERAL_WINDOWS[user_id] = (interaction, monotonic(), window)


def register_kingdom_lieux_items(bot: discord.Client) -> None:
    """Re-register the lieu hub doors on the bot (restart-proof)."""
    bot.add_dynamic_items(
        KingdomLieuSortirButton,
        KingdomLieuEntreeButton,
        KingdomLieuConseilButton,
        KingdomLieuRempartsButton,
        KingdomLieuComptesButton,
        KingdomLieuParoisseButton,
        KingdomLieuVoliereButton,
    )
